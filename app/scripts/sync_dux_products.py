#!/usr/bin/env python3
"""
Script para sincronizar productos desde la API DUX
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Añadir el directorio raíz al path
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.services.dux_sync_service import DuxSyncService
from app.utils.rate_limiter import dux_rate_limiter
import logging


def setup_logging(verbose: bool = False):
    """Configura el logging"""
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('dux_sync.log')
        ]
    )


async def test_connection():
    """Prueba la conexión con la API DUX"""
    print("🔗 Probando conexión con API DUX...")
    
    from app.clients.dux_api_client import DuxApiClientFactory
    
    async with DuxApiClientFactory.create_client() as client:
        success = await client.test_connection()
        
        if success:
            total_items = await client.get_total_items_count()
            print(f"✅ Conexión exitosa! Total de productos disponibles: {total_items:,}")
            return True
        else:
            print("❌ Error de conexión con API DUX")
            return False


async def show_sync_status():
    """Muestra el estado del sincronizador"""
    print("📊 Estado del sincronizador DUX:")
    
    sync_service = DuxSyncService()
    status = await sync_service.get_sync_status()
    
    print(f"  • Tamaño de lote: {status['batch_size']}")
    print(f"  • Requests totales: {status['rate_limiter']['total_requests']}")
    print(f"  • Tiempo transcurrido: {status['rate_limiter']['elapsed_time_seconds']:.1f}s")
    print(f"  • Requests por minuto: {status['rate_limiter']['requests_per_minute']:.1f}")
    print(f"  • Tiempo hasta próxima request: {status['rate_limiter']['time_until_next_allowed']:.1f}s")


async def sync_products(
    max_products: int = None,
    batch_size: int = 50,
    dry_run: bool = False
):
    """Sincroniza productos desde DUX"""
    print(f"🚀 Iniciando sincronización de productos DUX...")
    print(f"  • Máximo productos: {max_products or 'Todos'}")
    print(f"  • Tamaño de lote: {batch_size}")
    print(f"  • Modo: {'DRY RUN (no guarda)' if dry_run else 'REAL (guarda en BD)'}")
    print()
    
    # Crear servicio de sincronización
    sync_service = DuxSyncService(batch_size=batch_size)
    
    # Ejecutar sincronización
    result = await sync_service.sync_all_products(
        max_products=max_products,
        dry_run=dry_run
    )
    
    # Mostrar resultados
    print(f"\n📈 Resultados de la sincronización:")
    print(f"  • Productos procesados: {result.total_processed:,}")
    print(f"  • Productos creados: {result.total_created:,}")
    print(f"  • Productos actualizados: {result.total_updated:,}")
    print(f"  • Errores: {result.total_errors:,}")
    print(f"  • Duración: {result.duration_seconds:.2f} segundos")
    
    if result.errors:
        print(f"\n❌ Errores encontrados:")
        for i, error in enumerate(result.errors[:10], 1):  # Mostrar máximo 10 errores
            print(f"  {i}. {error}")
        if len(result.errors) > 10:
            print(f"  ... y {len(result.errors) - 10} errores más")
    
    # Mostrar estadísticas finales del rate limiter
    print(f"\n📊 Estadísticas de rate limiting:")
    stats = dux_rate_limiter.get_stats()
    print(f"  • Total requests: {stats['total_requests']}")
    print(f"  • Tiempo total: {stats['elapsed_time_seconds']:.1f}s")
    print(f"  • Promedio requests/minuto: {stats['requests_per_minute']:.1f}")
    
    return result


async def interactive_mode():
    """Modo interactivo para configurar la sincronización"""
    print("🎮 Modo interactivo de sincronización DUX")
    print("=" * 50)
    
    # Probar conexión primero
    if not await test_connection():
        return
    
    print()
    
    # Configuración interactiva
    try:
        max_products_input = input("Máximo de productos a sincronizar (Enter para todos): ").strip()
        max_products = int(max_products_input) if max_products_input else None
        
        batch_size_input = input("Tamaño de lote [50]: ").strip()
        batch_size = int(batch_size_input) if batch_size_input else 50
        
        dry_run_input = input("¿Modo DRY RUN? (s/N): ").strip().lower()
        dry_run = dry_run_input in ['s', 'y', 'yes', 'si', 'sí']
        
        print()
        confirm = input("¿Continuar con la sincronización? (s/N): ").strip().lower()
        
        if confirm in ['s', 'y', 'yes', 'si', 'sí']:
            await sync_products(max_products, batch_size, dry_run)
        else:
            print("❌ Sincronización cancelada")
            
    except KeyboardInterrupt:
        print("\n👋 Sincronización interrumpida por el usuario")
    except ValueError as e:
        print(f"❌ Error en los datos ingresados: {e}")


async def main():
    """Función principal"""
    parser = argparse.ArgumentParser(description="Sincronizador de productos DUX")
    parser.add_argument("--test", action="store_true", help="Probar conexión con API DUX")
    parser.add_argument("--status", action="store_true", help="Mostrar estado del sincronizador")
    parser.add_argument("--sync", action="store_true", help="Ejecutar sincronización")
    parser.add_argument("--interactive", action="store_true", help="Modo interactivo")
    parser.add_argument("--max-products", type=int, help="Máximo número de productos a sincronizar")
    parser.add_argument("--batch-size", type=int, default=50, help="Tamaño del lote (default: 50)")
    parser.add_argument("--dry-run", action="store_true", help="Modo dry run (no guarda en BD)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Logging detallado")
    
    args = parser.parse_args()
    
    # Configurar logging
    setup_logging(args.verbose)
    
    if args.test:
        await test_connection()
    elif args.status:
        await show_sync_status()
    elif args.sync:
        await sync_products(args.max_products, args.batch_size, args.dry_run)
    elif args.interactive:
        await interactive_mode()
    else:
        print("🤖 Sincronizador de productos DUX")
        print("\nOpciones disponibles:")
        print("  --test          Probar conexión")
        print("  --status        Mostrar estado")
        print("  --sync          Sincronizar productos")
        print("  --interactive   Modo interactivo")
        print("\nEjemplos:")
        print("  python sync_dux_products.py --test")
        print("  python sync_dux_products.py --sync --max-products 100 --dry-run")
        print("  python sync_dux_products.py --interactive")


if __name__ == "__main__":
    asyncio.run(main())