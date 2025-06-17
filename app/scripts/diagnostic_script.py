#!/usr/bin/env python3
"""
Script de diagnóstico completo para verificar la configuración del sistema
"""

import asyncio
import logging
import sys
from pathlib import Path

from httpx import ConnectError

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config.settings import get_settings
from app.database import check_db_connection
from app.repositories.redis_repository import RedisRepository
from app.services.whatsapp_service import WhatsAppService

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class SystemDiagnostic:
    """Clase para realizar diagnósticos del sistema"""

    def __init__(self):
        self.settings = get_settings()
        self.issues = []
        self.warnings = []

    def print_header(self, title: str):
        """Imprime un header formateado"""
        print(f"\n{'=' * 60}")
        print(f"🔍 {title}")
        print(f"{'=' * 60}")

    def print_check(self, item: str, status: bool, details: str = ""):
        """Imprime el resultado de una verificación"""
        icon = "✅" if status else "❌"
        print(f"{icon} {item}")
        if details:
            print(f"   📝 {details}")

    def add_issue(self, issue: str):
        """Añade un problema crítico"""
        self.issues.append(issue)

    def add_warning(self, warning: str):
        """Añade una advertencia"""
        self.warnings.append(warning)

    async def check_environment_variables(self):
        """Verifica las variables de entorno"""
        self.print_header("VARIABLES DE ENTORNO")

        # Variables críticas
        critical_vars = {
            "WHATSAPP_PHONE_NUMBER_ID": self.settings.WHATSAPP_PHONE_NUMBER_ID,
            "WHATSAPP_VERIFY_TOKEN": self.settings.WHATSAPP_VERIFY_TOKEN,
            "JWT_SECRET_KEY": self.settings.JWT_SECRET_KEY,
            "DB_NAME": self.settings.DB_NAME,
            "DB_USER": self.settings.DB_USER,
        }

        for var_name, var_value in critical_vars.items():
            if var_value:
                self.print_check(f"{var_name}", True, f"Configurado ({len(str(var_value))} caracteres)")
            else:
                self.print_check(f"{var_name}", False, "NO CONFIGURADO")
                self.add_issue(f"Variable de entorno {var_name} no está configurada")

        # Variables opcionales
        optional_vars = {
            "DB_PASSWORD": self.settings.DB_PASSWORD,
            "REDIS_PASSWORD": self.settings.REDIS_PASSWORD,
        }

        for var_name, var_value in optional_vars.items():
            if var_value:
                self.print_check(f"{var_name}", True, "Configurado")
            else:
                self.print_check(f"{var_name}", True, "Sin contraseña (OK)")

    async def check_database_connection(self):
        """Verifica la conexión a PostgreSQL"""
        self.print_header("BASE DE DATOS POSTGRESQL")

        try:
            # Verificar conexión
            db_connected = await check_db_connection()

            if db_connected:
                self.print_check(
                    "Conexión a PostgreSQL", True, f"Conectado a {self.settings.DB_HOST}:{self.settings.DB_PORT}"
                )

                # Verificar si las tablas existen
                from app.database import get_db_context
                from app.models.db import Customer

                try:
                    with get_db_context() as db:
                        count = db.query(Customer).count()
                        self.print_check("Tablas de base de datos", True, f"Tabla customers tiene {count} registros")
                except Exception as table_error:
                    self.print_check("Tablas de base de datos", False, f"Error: {str(table_error)}")
                    self.add_issue("Las tablas de la base de datos no existen o no son accesibles")

            else:
                self.print_check("Conexión a PostgreSQL", False, "No se puede conectar")
                self.add_issue(f"No se puede conectar a PostgreSQL en {self.settings.DB_HOST}:{self.settings.DB_PORT}")

        except Exception as e:
            self.print_check("Conexión a PostgreSQL", False, f"Error: {str(e)}")
            self.add_issue(f"Error al verificar PostgreSQL: {str(e)}")

    async def check_redis_connection(self):
        """Verifica la conexión a Redis"""
        self.print_header("REDIS")

        try:
            from app.repositories.dummy_redis_client import DummyRedisClient

            # Crear un repositorio de prueba
            redis_repo = RedisRepository(dict, prefix="test")

            # Verificar si está usando DummyRedisClient
            if isinstance(redis_repo.redis_client, DummyRedisClient):
                self.print_check("Conexión a Redis", False, "Usando cliente dummy (Redis no disponible)")
                self.add_warning("Redis no está disponible, usando almacenamiento local")
            else:
                # Hacer prueba de escritura/lectura
                test_key = "diagnostic_test"
                test_value = {"test": "data"}

                success = redis_repo.set(test_key, test_value)
                if success:
                    retrieved = redis_repo.get(test_key)
                    if retrieved:
                        redis_repo.delete(test_key)  # Limpiar
                        self.print_check(
                            "Conexión a Redis",
                            True,
                            f"Conectado a {self.settings.REDIS_HOST}:{self.settings.REDIS_PORT}",
                        )
                    else:
                        self.print_check("Conexión a Redis", False, "Escritura OK pero lectura falló")
                        self.add_warning("Redis funciona parcialmente")
                else:
                    self.print_check("Conexión a Redis", False, "No se pudo escribir datos")
                    self.add_warning("Redis no permite escritura")

        except Exception as e:
            self.print_check("Conexión a Redis", False, f"Error: {str(e)}")
            self.add_warning(f"Error al verificar Redis: {str(e)}")

    async def check_whatsapp_config(self):
        """Verifica la configuración de WhatsApp"""
        self.print_header("WHATSAPP API")

        try:
            whatsapp_service = WhatsAppService()
            config_check = await whatsapp_service.verificar_configuracion()

            if config_check["valid"]:
                self.print_check("Configuración de WhatsApp", True, "Configuración válida")

                # Mostrar detalles de configuración
                config = config_check["config"]
                print(f"   📋 Base URL: {config['base_url']}")
                print(f"   📋 Versión: {config['version']}")
                print(f"   📋 Phone ID: {config['phone_id']}")
                print(f"   📋 Token length: {config['token_length']} caracteres")

            else:
                self.print_check("Configuración de WhatsApp", False, "Configuración inválida")
                for issue in config_check["issues"]:
                    print(f"   ❌ {issue}")
                    self.add_issue(f"WhatsApp: {issue}")

        except Exception as e:
            self.print_check("Configuración de WhatsApp", False, f"Error: {str(e)}")
            self.add_issue(f"Error al verificar WhatsApp: {str(e)}")

    async def check_ai_service(self):
        """Verifica el servicio de AI (Ollama)"""
        self.print_header("SERVICIO DE AI (OLLAMA)")

        try:
            import httpx

            # Verificar si Ollama está corriendo
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.settings.OLLAMA_API_URL}/api/tags")

                if response.status_code == 200:
                    models = response.json()
                    self.print_check("Ollama Service", True, f"Corriendo en {self.settings.OLLAMA_API_URL}")

                    # Verificar si el modelo configurado existe
                    model_names = [model["name"] for model in models.get("models", [])]
                    if self.settings.OLLAMA_API_MODEL in model_names:
                        self.print_check(f"Modelo {self.settings.OLLAMA_API_MODEL}", True, "Modelo disponible")
                    else:
                        self.print_check(f"Modelo {self.settings.OLLAMA_API_MODEL}", False, "Modelo no encontrado")
                        self.add_warning(f"Modelo {self.settings.OLLAMA_API_MODEL} no está disponible")
                        print(f"   📋 Modelos disponibles: {', '.join(model_names)}")
                else:
                    self.print_check("Ollama Service", False, f"HTTP {response.status_code}")
                    self.add_warning("Ollama responde pero con error")

        except ConnectError:
            self.print_check("Ollama Service", False, "No se puede conectar")
            self.add_warning(f"No se puede conectar a Ollama en {self.settings.OLLAMA_API_URL}")
        except Exception as e:
            self.print_check("Ollama Service", False, f"Error: {str(e)}")
            self.add_warning(f"Error al verificar Ollama: {str(e)}")

    async def run_full_diagnostic(self):
        """Ejecuta el diagnóstico completo"""
        print("🚀 DIAGNÓSTICO COMPLETO DEL SISTEMA")
        print("=" * 60)

        # Ejecutar todas las verificaciones
        await self.check_environment_variables()
        await self.check_database_connection()
        await self.check_redis_connection()
        await self.check_whatsapp_config()
        await self.check_ai_service()

        # Mostrar resumen
        self.print_header("RESUMEN")

        if not self.issues and not self.warnings:
            print("🎉 ¡Todo está perfecto! El sistema está listo.")
            return True

        if self.issues:
            print("❌ PROBLEMAS CRÍTICOS ENCONTRADOS:")
            for i, issue in enumerate(self.issues, 1):
                print(f"   {i}. {issue}")

        if self.warnings:
            print("\n⚠️  ADVERTENCIAS:")
            for i, warning in enumerate(self.warnings, 1):
                print(f"   {i}. {warning}")

        print("\n📊 ESTADÍSTICAS:")
        print(f"   • Problemas críticos: {len(self.issues)}")
        print(f"   • Advertencias: {len(self.warnings)}")

        if self.issues:
            print("\n🔧 PASOS PARA SOLUCIONAR:")
            print("   1. Revisar y configurar las variables de entorno")
            print("   2. Ejecutar: python -m app.database.init_database")
            print("   3. Verificar configuración de WhatsApp API")
            print("   4. Ejecutar diagnóstico nuevamente")

        return len(self.issues) == 0


async def main():
    """Función principal"""
    diagnostic = SystemDiagnostic()
    success = await diagnostic.run_full_diagnostic()

    if success:
        print("\n🚀 ¡Sistema listo para ejecutar!")
        print("   Ejecuta: uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload")
    else:
        print("\n⚠️  Soluciona los problemas antes de continuar.")

    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
