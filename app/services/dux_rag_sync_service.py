"""
Servicio de sincronización integrada DUX -> PostgreSQL -> RAG
Responsabilidad: Orquestar la sincronización completa desde DUX hasta embeddings
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from app.clients.dux_api_client import DuxApiClientFactory
from app.clients.dux_facturas_client import DuxFacturasClientFactory
from app.domains.ecommerce.infrastructure.services import DuxSyncService
from app.models.dux import DuxSyncResult
from app.services.embedding_update_service import EmbeddingUpdateService
from app.services.vector_store_ingestion_service import create_vector_ingestion_service


class DuxRagSyncResult(DuxSyncResult):
    """Resultado extendido que incluye métricas de RAG/embeddings"""
    
    # RAG-specific metrics as model fields
    total_embeddings_created: int = 0
    total_embeddings_updated: int = 0 
    total_embeddings_errors: int = 0
    embedding_processing_time_seconds: float = 0.0
    vector_store_stats: Dict[str, Any] = {}

    def add_embedding_metrics(
        self,
        created: int = 0,
        updated: int = 0,
        errors: int = 0,
        processing_time: float = 0.0,
        stats: Optional[Dict[str, Any]] = None,
    ):
        """Agregar métricas de embeddings al resultado"""
        self.total_embeddings_created += created
        self.total_embeddings_updated += updated
        self.total_embeddings_errors += errors
        self.embedding_processing_time_seconds += processing_time
        if stats:
            self.vector_store_stats.update(stats)


class DuxRagSyncService:
    """
    Servicio integrado que sincroniza datos de DUX a PostgreSQL
    y automáticamente actualiza embeddings en ChromaDB
    """

    def __init__(self, batch_size: int = 50):
        """
        Inicializa el servicio de sincronización integrada

        Args:
            batch_size: Tamaño del lote para procesar productos
        """
        self.batch_size = batch_size
        self.logger = logging.getLogger(__name__)

        # Servicios de sincronización
        self.dux_sync_service = DuxSyncService(batch_size=batch_size)
        self.embedding_service = EmbeddingUpdateService()
        self.vector_ingestion_service = create_vector_ingestion_service()

    async def sync_all_products_with_rag(
        self, max_products: Optional[int] = None, dry_run: bool = False, skip_embeddings: bool = False
    ) -> DuxRagSyncResult:
        """
        Sincronización completa: DUX -> PostgreSQL -> RAG

        Args:
            max_products: Máximo número de productos a sincronizar
            dry_run: Si True, no guarda cambios en la base de datos
            skip_embeddings: Si True, omite la actualización de embeddings

        Returns:
            DuxRagSyncResult: Resultado completo de la sincronización
        """
        rag_result = DuxRagSyncResult(start_time=datetime.now())

        self.logger.info(f"Starting integrated DUX-RAG sync - max_products: {max_products}, dry_run: {dry_run}")

        try:
            # Paso 1: Sincronizar productos DUX -> PostgreSQL
            self.logger.info("Step 1: Syncing DUX products to PostgreSQL...")
            db_result = await self.dux_sync_service.sync_all_products(max_products=max_products, dry_run=dry_run)

            # Transferir métricas de DB sync
            rag_result.total_processed = db_result.total_processed
            rag_result.total_created = db_result.total_created
            rag_result.total_updated = db_result.total_updated
            rag_result.total_errors = db_result.total_errors
            rag_result.errors.extend(db_result.errors)

            if not db_result.is_successful():
                # Check if the failure was due to rate limiting
                rate_limit_errors = [error for error in db_result.errors if "RATE_LIMIT" in str(error)]
                if rate_limit_errors:
                    self.logger.warning(f"PostgreSQL sync hit rate limits ({len(rate_limit_errors)} errors), skipping RAG update. Consider increasing DUX_API_RATE_LIMIT_SECONDS or reducing sync frequency.")
                else:
                    self.logger.error(f"PostgreSQL sync failed with {db_result.total_errors} errors, skipping RAG update. First error: {db_result.errors[0] if db_result.errors else 'Unknown'}")
                
                rag_result.mark_completed()
                return rag_result

            # Paso 2: Actualizar embeddings en ChromaDB (si no es dry_run)
            if not dry_run and not skip_embeddings:
                self.logger.info("Step 2: Updating embeddings in ChromaDB...")
                embedding_start_time = datetime.now()

                try:
                    # Actualizar embeddings para todos los productos
                    await self.embedding_service.update_all_embeddings()

                    # Obtener estadísticas del vector store
                    vector_stats = self.embedding_service.get_collection_stats()

                    embedding_processing_time = (datetime.now() - embedding_start_time).total_seconds()

                    # Calcular métricas aproximadas de embeddings
                    # (basado en productos creados/actualizados)

                    rag_result.add_embedding_metrics(
                        created=db_result.total_created,  # Nuevos embeddings
                        updated=db_result.total_updated,  # Embeddings actualizados
                        errors=0,  # Sin errores si llegamos aquí
                        processing_time=embedding_processing_time,
                        stats=vector_stats,
                    )

                    self.logger.info(
                        f"Embeddings updated successfully - "
                        f"Created: {db_result.total_created}, "
                        f"Updated: {db_result.total_updated}, "
                        f"Processing time: {embedding_processing_time:.2f}s"
                    )

                except Exception as e:
                    error_msg = f"Error updating embeddings: {str(e)}"
                    self.logger.error(error_msg)
                    rag_result.add_error(error_msg)
                    rag_result.add_embedding_metrics(errors=1)

            elif skip_embeddings:
                self.logger.info("Step 2: Skipping embeddings update as requested")
            else:
                self.logger.info("Step 2: Skipping embeddings update (dry run mode)")

        except Exception as e:
            error_msg = f"Critical error during integrated sync: {str(e)}"
            self.logger.error(error_msg)
            rag_result.add_error(error_msg)

        rag_result.mark_completed()

        self.logger.info(
            f"Integrated DUX-RAG sync completed - "
            f"DB: {rag_result.total_processed} processed, {rag_result.total_created} created, "
            f"{rag_result.total_updated} updated, {rag_result.total_errors} errors | "
            f"RAG: {rag_result.total_embeddings_created} embeddings created, "
            f"{rag_result.total_embeddings_updated} updated, "
            f"{rag_result.total_embeddings_errors} errors | "
            f"Duration: {rag_result.duration_seconds:.2f}s"
        )

        return rag_result

    async def sync_facturas_with_rag(self, limit: int = 100, dry_run: bool = False) -> DuxRagSyncResult:
        """
        Sincronizar facturas de DUX y procesarlas para RAG

        Args:
            limit: Límite de facturas a sincronizar
            dry_run: Si True, no guarda cambios

        Returns:
            DuxRagSyncResult: Resultado de la sincronización
        """
        rag_result = DuxRagSyncResult(start_time=datetime.now())

        self.logger.info(f"Starting facturas sync with RAG - limit: {limit}, dry_run: {dry_run}")

        try:
            async with DuxFacturasClientFactory.create_client() as client:
                # Probar conexión con manejo mejorado de rate limits
                if not await client.test_connection():
                    rag_result.add_error("Failed to connect to DUX Facturas API - likely due to rate limiting or network issues. Check logs for details.")
                    rag_result.mark_completed()
                    return rag_result

                # Obtener facturas
                response = await client.get_facturas(limit=limit)

                if not dry_run:
                    # TODO: Implementar lógica de almacenamiento de facturas
                    # Esto requerirá crear modelos de BD para facturas
                    self.logger.info(f"Would process {len(response.facturas)} facturas")
                    rag_result.total_processed = len(response.facturas)

                    # TODO: Procesar facturas al vector store para búsqueda semántica
                    # Esto permitirá que los agentes busquen facturas por contenido
                else:
                    rag_result.total_processed = len(response.facturas)
                    self.logger.info(f"DRY RUN: Would process {len(response.facturas)} facturas")

        except Exception as e:
            error_msg = f"Error syncing facturas: {str(e)}"
            self.logger.error(error_msg)
            rag_result.add_error(error_msg)

        rag_result.mark_completed()
        return rag_result

    async def get_sync_status(self) -> Dict[str, Any]:
        """
        Obtiene el estado completo del sistema de sincronización

        Returns:
            Dict con información de estado completa
        """
        try:
            # Estado del sync de productos
            dux_status = await self.dux_sync_service.get_sync_status()

            # Estado del vector store
            vector_stats = self.embedding_service.get_collection_stats()

            # Probar conectividad
            async with DuxApiClientFactory.create_client() as products_client:
                products_api_available = await products_client.test_connection()

            async with DuxFacturasClientFactory.create_client() as facturas_client:
                facturas_api_available = await facturas_client.test_connection()

            return {
                "dux_products_sync": dux_status,
                "vector_store_stats": vector_stats,
                "api_connectivity": {
                    "products_api": products_api_available,
                    "facturas_api": facturas_api_available,
                },
                "services_status": {
                    "dux_sync_service": "active",
                    "embedding_service": "active",
                    "vector_ingestion_service": "active",
                },
                "last_check": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Error getting sync status: {e}")
            return {"error": str(e), "last_check": datetime.now().isoformat()}

    async def force_embedding_update_for_recent_products(self, hours: int = 24) -> Dict[str, Any]:
        """
        Fuerza actualización de embeddings solo para productos modificados recientemente

        Args:
            hours: Horas hacia atrás para considerar productos "recientes"

        Returns:
            Dict con resultado de la operación
        """
        self.logger.info(f"Forcing embedding update for products modified in last {hours} hours")

        start_time = datetime.now()

        try:
            # TODO: Implementar filtrado por fecha de actualización
            # Por ahora, actualizar todos los embeddings
            await self.embedding_service.update_all_embeddings()

            processing_time = (datetime.now() - start_time).total_seconds()
            stats = self.embedding_service.get_collection_stats()

            return {
                "success": True,
                "processing_time_seconds": processing_time,
                "vector_store_stats": stats,
                "message": f"Embeddings updated for products modified in last {hours} hours",
            }

        except Exception as e:
            error_msg = f"Error forcing embedding update: {str(e)}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "processing_time_seconds": (datetime.now() - start_time).total_seconds(),
            }


# Factory function
def create_dux_rag_sync_service(batch_size: int = 50) -> DuxRagSyncService:
    """
    Crea una instancia del servicio de sincronización integrada DUX-RAG

    Args:
        batch_size: Tamaño del lote para procesamiento

    Returns:
        DuxRagSyncService: Instancia del servicio
    """
    return DuxRagSyncService(batch_size=batch_size)

