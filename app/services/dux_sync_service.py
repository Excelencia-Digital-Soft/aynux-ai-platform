"""
Servicio de sincronización de productos DUX
Responsabilidad: Orquestar la sincronización de productos entre DUX y la base de datos local
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.dux_api_client import DuxApiClient, DuxApiClientFactory
from app.database.async_db import AsyncSessionLocal
from app.models.db.catalog import Brand, Category, Product
from app.models.dux import DuxItem, DuxSyncResult
from app.utils.rate_limiter import dux_rate_limiter


class DuxProductMapper:
    """
    Responsabilidad: Mapear productos de DUX a modelos locales
    """

    @staticmethod
    def map_dux_item_to_product(dux_item: DuxItem) -> Dict[str, Any]:
        """
        Mapea un DuxItem a los campos de Product

        Args:
            dux_item: Item de DUX

        Returns:
            Dict con los campos mapeados para Product
        """
        # Obtener precio principal (LISTA GENERAL)
        price = dux_item.get_precio_lista_general() or Decimal("0.0")

        # Obtener stock disponible
        stock = dux_item.get_stock_local_disponible() or Decimal("0.0")

        # Mapear campos básicos
        product_data = {
            "name": dux_item.item.strip(),
            "description": f"Producto {dux_item.item} - Código: {dux_item.cod_item}",
            "price": float(price),
            "stock": int(stock) if stock >= 0 else 0,
            "sku": dux_item.cod_item,
            "is_active": True,
            # Campos adicionales específicos de DUX
            "cost": float(Decimal(dux_item.costo)) if dux_item.costo else 0.0,
            "tax_percentage": float(Decimal(dux_item.porc_iva)) if dux_item.porc_iva else 0.0,
            "external_code": dux_item.codigo_externo,
            "image_url": dux_item.imagen_url,
        }

        # Agregar código de barras si existe
        if dux_item.has_barcode():
            product_data["barcode"] = dux_item.codigos_barra[0] or ""  # type: ignore

        return product_data

    @staticmethod
    def map_dux_category(dux_item: DuxItem) -> Dict[str, Any]:
        """
        Mapea la categoría de DUX a Category local

        Args:
            dux_item: Item de DUX

        Returns:
            Dict con los campos de Category
        """
        return {
            "name": dux_item.rubro.rubro.strip(),
            "description": f"Categoría importada de DUX - ID: {dux_item.rubro.id_rubro}",
            "external_id": str(dux_item.rubro.id_rubro),
        }

    @staticmethod
    def map_dux_brand(dux_item: DuxItem) -> Optional[Dict[str, Any]]:
        """
        Mapea la marca de DUX a Brand local

        Args:
            dux_item: Item de DUX

        Returns:
            Dict con los campos de Brand o None si no tiene marca
        """
        if not dux_item.marca.marca:
            return None

        return {
            "name": dux_item.marca.marca.strip(),
            "description": "Marca importada de DUX",
            "external_code": dux_item.marca.codigo_marca,
        }


class DuxSyncService:
    """
    Servicio principal de sincronización con DUX
    Responsabilidad: Coordinar la sincronización completa de productos
    """

    def __init__(self, batch_size: int = 50, post_sync_callback: Optional[Callable] = None):
        """
        Inicializa el servicio de sincronización

        Args:
            batch_size: Tamaño del lote para procesar productos
            post_sync_callback: Función opcional a llamar después de cada sincronización de producto
        """
        self.batch_size = batch_size
        self.logger = logging.getLogger(__name__)
        self.mapper = DuxProductMapper()
        self.post_sync_callback = post_sync_callback

    async def sync_all_products(self, max_products: Optional[int] = None, dry_run: bool = False) -> DuxSyncResult:
        """
        Sincroniza todos los productos de DUX

        Args:
            max_products: Máximo número de productos a sincronizar (None = todos)
            dry_run: Si True, no guarda cambios en la base de datos

        Returns:
            DuxSyncResult: Resultado de la sincronización
        """
        result = DuxSyncResult(start_time=datetime.now())

        self.logger.info(f"Starting DUX sync - max_products: {max_products}, dry_run: {dry_run}")

        try:
            async with DuxApiClientFactory.create_client() as client:
                # Probar conexión
                if not await client.test_connection():
                    result.add_error("Failed to connect to DUX API")
                    result.mark_completed()
                    return result

                # Obtener total de productos
                total_available = await client.get_total_items_count()
                products_to_sync = min(total_available, max_products) if max_products else total_available

                self.logger.info(f"Total products available: {total_available}, will sync: {products_to_sync}")

                # Procesar por lotes
                offset = 0
                while offset < products_to_sync:
                    batch_limit = min(self.batch_size, products_to_sync - offset)

                    try:
                        batch_result = await self._sync_batch(client, offset, batch_limit, dry_run)

                        # Actualizar resultado acumulado
                        result.total_processed += batch_result.total_processed
                        result.total_created += batch_result.total_created
                        result.total_updated += batch_result.total_updated
                        result.total_errors += batch_result.total_errors
                        result.errors.extend(batch_result.errors)

                        self.logger.info(
                            f"Batch completed - offset: {offset}, processed: {batch_result.total_processed}, "
                            f"created: {batch_result.total_created}, updated: {batch_result.total_updated}"
                        )

                        offset += batch_limit

                    except Exception as e:
                        error_msg = f"Error processing batch at offset {offset}: {str(e)}"
                        self.logger.error(error_msg)
                        result.add_error(error_msg)

                        # Continuar con el siguiente lote
                        offset += batch_limit

        except Exception as e:
            error_msg = f"Critical error during sync: {str(e)}"
            self.logger.error(error_msg)
            result.add_error(error_msg)

        result.mark_completed()

        self.logger.info(
            f"DUX sync completed - Total: {result.total_processed}, "
            f"Created: {result.total_created}, Updated: {result.total_updated}, "
            f"Errors: {result.total_errors}, Duration: {result.duration_seconds:.2f}s"
        )

        return result

    async def _sync_batch(self, client: DuxApiClient, offset: int, limit: int, dry_run: bool) -> DuxSyncResult:
        """
        Sincroniza un lote de productos

        Args:
            client: Cliente DUX
            offset: Offset para la paginación
            limit: Límite de productos
            dry_run: Si True, no guarda en BD

        Returns:
            DuxSyncResult: Resultado del lote
        """
        batch_result = DuxSyncResult(start_time=datetime.now())

        # Aplicar rate limiting
        rate_info = await dux_rate_limiter.wait_for_next_request()
        if rate_info["wait_time_seconds"] > 0:
            self.logger.debug(f"Rate limit wait: {rate_info['wait_time_seconds']:.2f}s")

        try:
            # Obtener productos de DUX
            response = await client.get_items(offset=offset, limit=limit)

            if not dry_run:
                async with AsyncSessionLocal() as session:
                    for dux_item in response.results:
                        try:
                            item_result = await self._sync_single_product(session, dux_item)

                            if item_result["created"]:
                                batch_result.total_created += 1
                            elif item_result["updated"]:
                                batch_result.total_updated += 1

                            batch_result.total_processed += 1

                        except Exception as e:
                            error_msg = f"Error syncing product {dux_item.cod_item}: {str(e)}"
                            batch_result.add_error(error_msg)
                            self.logger.warning(error_msg)

                    # Commit del lote
                    await session.commit()
            else:
                # En dry run, solo contar
                batch_result.total_processed = len(response.results)
                self.logger.info(f"DRY RUN: Would process {len(response.results)} products")

        except Exception as e:
            error_msg = f"Error in batch sync: {str(e)}"
            batch_result.add_error(error_msg)
            raise

        batch_result.mark_completed()
        return batch_result

    async def _sync_single_product(self, session: AsyncSession, dux_item: DuxItem) -> Dict[str, bool]:
        """
        Sincroniza un producto individual

        Args:
            session: Sesión de BD
            dux_item: Item de DUX

        Returns:
            Dict indicando si fue creado o actualizado
        """
        # Buscar producto existente por SKU
        stmt = select(Product).where(Product.sku == dux_item.cod_item)
        result = await session.execute(stmt)
        existing_product = result.scalar_one_or_none()

        # Obtener o crear categoría
        category = await self._get_or_create_category(session, dux_item)

        # Obtener o crear marca (opcional)
        brand = await self._get_or_create_brand(session, dux_item)

        # Mapear datos del producto
        product_data = self.mapper.map_dux_item_to_product(dux_item)
        product_data["category_id"] = category.id
        if brand:
            product_data["brand_id"] = brand.id

        sync_result = {}
        product_for_callback = None

        if existing_product:
            # Actualizar producto existente
            for key, value in product_data.items():
                if hasattr(existing_product, key):
                    setattr(existing_product, key, value)

            existing_product.updated_at = datetime.now()
            sync_result = {"created": False, "updated": True}
            product_for_callback = existing_product
        else:
            # Crear nuevo producto
            new_product = Product(**product_data)
            session.add(new_product)
            sync_result = {"created": True, "updated": False}
            product_for_callback = new_product

        # Ejecutar callback post-sincronización si está definido
        if self.post_sync_callback and product_for_callback:
            try:
                # Hacer flush para obtener el ID del producto si es nuevo
                await session.flush()
                
                # Llamar al callback con información del producto sincronizado
                callback_data = {
                    "product": product_for_callback,
                    "dux_item": dux_item,
                    "sync_result": sync_result,
                    "category": category,
                    "brand": brand
                }
                
                await self.post_sync_callback(callback_data)
                
            except Exception as e:
                self.logger.warning(f"Post-sync callback failed for product {dux_item.cod_item}: {str(e)}")
                # No interrumpir el sync por errores en el callback

        return sync_result

    async def _get_or_create_category(self, session: AsyncSession, dux_item: DuxItem) -> Category:
        """Obtiene o crea una categoría"""
        # Buscar por external_id
        stmt = select(Category).where(Category.external_id == str(dux_item.rubro.id_rubro))
        result = await session.execute(stmt)
        category = result.scalar_one_or_none()

        if not category:
            category_data = self.mapper.map_dux_category(dux_item)
            category = Category(**category_data)
            session.add(category)
            await session.flush()  # Para obtener el ID

        return category

    async def _get_or_create_brand(self, session: AsyncSession, dux_item: DuxItem) -> Optional[Brand]:
        """Obtiene o crea una marca (si existe)"""
        brand_data = self.mapper.map_dux_brand(dux_item)
        if not brand_data:
            return None

        # Buscar por nombre
        stmt = select(Brand).where(Brand.name == brand_data["name"])
        result = await session.execute(stmt)
        brand = result.scalar_one_or_none()

        if not brand:
            brand = Brand(**brand_data)
            session.add(brand)
            await session.flush()  # Para obtener el ID

        return brand

    async def get_sync_status(self) -> Dict[str, Any]:
        """
        Obtiene el estado actual del rate limiter y la sincronización

        Returns:
            Dict con información de estado
        """
        rate_stats = dux_rate_limiter.get_stats()

        return {
            "rate_limiter": rate_stats,
            "batch_size": self.batch_size,
            "last_sync": None,  # TODO: Implementar tracking de última sincronización
        }

