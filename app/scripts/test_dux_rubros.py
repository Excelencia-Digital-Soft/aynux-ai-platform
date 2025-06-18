#!/usr/bin/env python3
"""
Script de prueba para el cliente de rubros DUX
Propósito: Validar la funcionalidad del cliente de rubros
"""

import asyncio
import logging
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.clients.dux_rubros_client import DuxRubrosClient, DuxRubrosClientFactory
from app.models.dux import DuxApiError


async def test_rubros_connection():
    """Prueba la conexión básica con la API de rubros"""
    print("🔍 Probando conexión con API de rubros DUX...")
    
    async with DuxRubrosClientFactory.create_client() as client:
        try:
            success = await client.test_connection()
            if success:
                print("✅ Conexión exitosa con API de rubros DUX")
                return True
            else:
                print("❌ Falló la conexión con API de rubros DUX")
                return False
        except DuxApiError as e:
            print(f"❌ Error de API DUX: {e.error_code} - {e.error_message}")
            return False
        except Exception as e:
            print(f"❌ Error inesperado: {e}")
            return False


async def test_get_all_rubros():
    """Prueba obtener todos los rubros"""
    print("\n📦 Obteniendo todos los rubros...")
    
    async with DuxRubrosClientFactory.create_client() as client:
        try:
            response = await client.get_rubros()
            
            print(f"✅ Se obtuvieron {response.get_total_rubros()} rubros")
            
            # Mostrar algunos rubros de ejemplo
            rubros_sorted = response.get_sorted_rubros()
            print("\n📋 Primeros 10 rubros (ordenados):")
            for i, rubro in enumerate(rubros_sorted[:10], 1):
                print(f"  {i:2d}. ID: {rubro.id_rubro:4d} - {rubro.rubro}")
            
            if len(rubros_sorted) > 10:
                print(f"  ... y {len(rubros_sorted) - 10} más")
            
            return response
            
        except DuxApiError as e:
            print(f"❌ Error de API DUX: {e.error_code} - {e.error_message}")
            return None
        except Exception as e:
            print(f"❌ Error inesperado: {e}")
            return None


async def test_search_rubros(response):
    """Prueba la búsqueda de rubros específicos"""
    if not response:
        print("⚠️  No hay datos de rubros para probar búsquedas")
        return
    
    print("\n🔎 Probando búsquedas de rubros...")
    
    async with DuxRubrosClientFactory.create_client() as client:
        # Buscar el primer rubro por ID
        if response.rubros:
            primer_rubro = response.rubros[0]
            
            # Buscar por ID
            print(f"\n🆔 Buscando rubro por ID: {primer_rubro.id_rubro}")
            rubro_por_id = await client.get_rubro_by_id(primer_rubro.id_rubro)
            if rubro_por_id:
                print(f"✅ Encontrado: {rubro_por_id}")
            else:
                print("❌ No encontrado")
            
            # Buscar por nombre
            print(f"\n📝 Buscando rubro por nombre: '{primer_rubro.rubro}'")
            rubro_por_nombre = await client.get_rubro_by_name(primer_rubro.rubro)
            if rubro_por_nombre:
                print(f"✅ Encontrado: {rubro_por_nombre}")
            else:
                print("❌ No encontrado")
            
            # Buscar algo que no existe
            print(f"\n❓ Buscando rubro inexistente: 'RUBRO_INEXISTENTE'")
            rubro_inexistente = await client.get_rubro_by_name("RUBRO_INEXISTENTE")
            if rubro_inexistente:
                print(f"⚠️  Inesperadamente encontrado: {rubro_inexistente}")
            else:
                print("✅ Correctamente no encontrado")


async def test_rubros_utility_methods(response):
    """Prueba los métodos de utilidad de la respuesta"""
    if not response:
        print("⚠️  No hay datos de rubros para probar métodos de utilidad")
        return
    
    print("\n🛠️  Probando métodos de utilidad...")
    
    # Obtener nombres de rubros
    nombres = response.get_rubro_names()
    print(f"📝 Nombres de rubros ({len(nombres)} total):")
    for i, nombre in enumerate(nombres[:5], 1):
        print(f"  {i}. {nombre}")
    if len(nombres) > 5:
        print(f"  ... y {len(nombres) - 5} más")
    
    # Buscar por método directo
    if response.rubros:
        primer_rubro = response.rubros[0]
        
        encontrado = response.find_rubro_by_id(primer_rubro.id_rubro)
        print(f"\n🔍 Búsqueda directa por ID {primer_rubro.id_rubro}: {'✅ Encontrado' if encontrado else '❌ No encontrado'}")
        
        encontrado_nombre = response.find_rubro_by_name(primer_rubro.rubro)
        print(f"🔍 Búsqueda directa por nombre '{primer_rubro.rubro}': {'✅ Encontrado' if encontrado_nombre else '❌ No encontrado'}")


async def main():
    """Función principal que ejecuta todas las pruebas"""
    print("🚀 Iniciando pruebas del cliente de rubros DUX")
    print("=" * 50)
    
    # Configurar logging
    logging.basicConfig(level=logging.INFO)
    
    try:
        # Prueba 1: Conexión
        connection_ok = await test_rubros_connection()
        if not connection_ok:
            print("\n❌ No se puede continuar con las pruebas sin conexión")
            return
        
        # Prueba 2: Obtener rubros
        response = await test_get_all_rubros()
        
        # Prueba 3: Búsquedas
        await test_search_rubros(response)
        
        # Prueba 4: Métodos de utilidad
        await test_rubros_utility_methods(response)
        
        print("\n" + "=" * 50)
        print("✅ Todas las pruebas completadas exitosamente")
        
    except KeyboardInterrupt:
        print("\n⚠️  Pruebas interrumpidas por el usuario")
    except Exception as e:
        print(f"\n❌ Error inesperado en las pruebas: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())