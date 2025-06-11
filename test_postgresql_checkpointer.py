#!/usr/bin/env python3
"""
Test específico para el checkpointer de PostgreSQL con LangGraph
"""
import asyncio
import sys
from pathlib import Path

# Añadir el directorio raíz al path
sys.path.append(str(Path(__file__).parent))

import asyncpg
from langgraph.checkpoint.postgres import PostgresSaver
from app.config.settings import get_settings

async def test_postgresql_checkpointer():
    """Test directo del checkpointer de PostgreSQL"""
    
    settings = get_settings()
    connection_string = settings.database_url
    
    print("🔧 Testing PostgreSQL Checkpointer")
    print("=" * 60)
    print(f"Connection string: {connection_string}")
    
    # Test 1: Conexión básica con asyncpg
    print("\n1️⃣ Test conexión básica con asyncpg...")
    try:
        # Probar conexión simple
        conn = await asyncpg.connect(connection_string)
        version = await conn.fetchval("SELECT version()")
        print(f"✅ Conexión exitosa: {version[:50]}...")
        await conn.close()
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return False
    
    # Test 2: Crear pool de conexiones
    print("\n2️⃣ Test pool de conexiones...")
    try:
        pool = await asyncpg.create_pool(
            connection_string,
            min_size=2,
            max_size=10,
            command_timeout=60
        )
        print(f"✅ Pool creado exitosamente")
        
        # Verificar pool
        async with pool.acquire() as conn:
            result = await conn.fetchval("SELECT 1")
            print(f"✅ Pool funcional: SELECT 1 = {result}")
            
    except Exception as e:
        print(f"❌ Error creando pool: {e}")
        return False
    
    # Test 3: Diferentes formas de crear PostgresSaver
    print("\n3️⃣ Test PostgresSaver...")
    
    # Opción A: Con pool
    print("\n   A) Intentando con pool de asyncpg...")
    try:
        saver_pool = PostgresSaver(pool)
        print("✅ PostgresSaver creado con pool")
        
        # Intentar setup
        await saver_pool.setup()
        print("✅ Setup completado con pool")
        
    except Exception as e:
        print(f"❌ Error con pool: {e}")
        
        # Opción B: Con sync connection string
        print("\n   B) Intentando con sync connection string...")
        try:
            # Convertir a formato sync para PostgresSaver
            sync_conn_str = connection_string.replace("postgresql://", "postgresql+psycopg2://")
            
            async with PostgresSaver.from_conn_string(sync_conn_str) as saver:
                await saver.setup()
                print("✅ Setup completado con sync connection string")
                
        except Exception as e:
            print(f"❌ Error con sync string: {e}")
            
            # Opción C: Con diccionario de configuración
            print("\n   C) Intentando con configuración dict...")
            try:
                # Parsear connection string
                import urllib.parse
                parsed = urllib.parse.urlparse(connection_string)
                
                config = {
                    "host": parsed.hostname or "localhost",
                    "port": parsed.port or 5432,
                    "user": parsed.username or "postgres",
                    "password": parsed.password or "",
                    "database": parsed.path.lstrip("/") if parsed.path else "postgres"
                }
                
                print(f"   Config: {config}")
                
                # Crear nuevo pool con config
                pool2 = await asyncpg.create_pool(**config)
                saver_dict = PostgresSaver(pool2)
                await saver_dict.setup()
                print("✅ Setup completado con config dict")
                
                # Cleanup
                await pool2.close()
                
            except Exception as e:
                print(f"❌ Error con config dict: {e}")
    
    # Test 4: Verificar tablas de checkpoint
    print("\n4️⃣ Verificando tablas de checkpoint...")
    try:
        async with pool.acquire() as conn:
            # Buscar tablas relacionadas con checkpoint
            tables = await conn.fetch("""
                SELECT tablename 
                FROM pg_tables 
                WHERE schemaname = 'public' 
                AND tablename LIKE '%checkpoint%'
            """)
            
            if tables:
                print(f"✅ Tablas de checkpoint encontradas:")
                for table in tables:
                    print(f"   - {table['tablename']}")
            else:
                print("⚠️  No se encontraron tablas de checkpoint")
                
    except Exception as e:
        print(f"❌ Error verificando tablas: {e}")
    
    # Cleanup
    await pool.close()
    print("\n✅ Test completado")
    return True

async def test_alternative_checkpointer():
    """Test de alternativas al checkpointer"""
    
    print("\n🔄 ALTERNATIVAS AL CHECKPOINTER")
    print("=" * 60)
    
    # Opción 1: MemorySaver (en memoria)
    print("\n1️⃣ MemorySaver (para desarrollo)...")
    try:
        from langgraph.checkpoint.memory import MemorySaver
        
        memory_saver = MemorySaver()
        print("✅ MemorySaver disponible como alternativa")
        
        # Test básico
        thread_id = "test_thread"
        checkpoint = {
            "messages": ["Hola", "¿Cómo estás?"],
            "state": {"intent": "greeting"}
        }
        
        # Guardar checkpoint
        await memory_saver.aput(thread_id, checkpoint, {})
        print("✅ Checkpoint guardado en memoria")
        
        # Recuperar checkpoint
        saved = await memory_saver.aget(thread_id)
        print(f"✅ Checkpoint recuperado: {saved}")
        
    except Exception as e:
        print(f"❌ Error con MemorySaver: {e}")
    
    # Opción 2: SQLite (persistente pero local)
    print("\n2️⃣ SQLite checkpointer...")
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        
        sqlite_saver = SqliteSaver.from_conn_string("sqlite:///checkpoints.db")
        print("✅ SqliteSaver disponible como alternativa")
        
    except Exception as e:
        print(f"❌ Error con SqliteSaver: {e}")
    
    print("\n💡 Recomendaciones:")
    print("   - Para desarrollo: usar MemorySaver")
    print("   - Para testing: usar SqliteSaver") 
    print("   - Para producción: resolver PostgresSaver")

async def main():
    """Función principal"""
    print("🧪 TEST DEL CHECKPOINTER DE POSTGRESQL")
    print("=" * 60)
    
    # Test principal
    await test_postgresql_checkpointer()
    
    # Test alternativas
    await test_alternative_checkpointer()

if __name__ == "__main__":
    asyncio.run(main())