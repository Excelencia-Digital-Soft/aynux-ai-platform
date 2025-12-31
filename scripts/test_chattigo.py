#!/usr/bin/env python3
"""
Script de pruebas E2E para la integración con Chattigo API.

Este script verifica:
1. Autenticación con Chattigo API
2. Envío de mensaje de prueba

IMPORTANTE: Las credenciales de Chattigo ahora se almacenan en la base de datos.
Para producción, configure credenciales via Admin API: POST /api/v1/admin/chattigo-credentials

Este script requiere credenciales explícitas via argumentos CLI.

Uso:
    cd python

    # Solo autenticación
    uv run python scripts/test_chattigo.py --username USER --password PASS --auth-only

    # Enviar mensaje de prueba
    uv run python scripts/test_chattigo.py --username USER --password PASS --send-test --phone 5491112345678
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables (only for URLs)
load_dotenv(Path(__file__).parent.parent / ".env")


class ChattigoTester:
    """Clase para probar la integración con Chattigo."""

    def __init__(self, username: str, password: str, did: str, bot_name: str = "Aynux"):
        """
        Initialize tester with explicit credentials.

        Args:
            username: Chattigo API username (required)
            password: Chattigo API password (required)
            did: WhatsApp Business DID (required)
            bot_name: Bot name for messages (default: "Aynux")
        """
        self.login_url = os.getenv(
            "CHATTIGO_LOGIN_URL",
            "https://channels.chattigo.com/bsp-cloud-chattigo-isv/login",
        )
        self.message_url = os.getenv(
            "CHATTIGO_MESSAGE_URL",
            "https://channels.chattigo.com/bsp-cloud-chattigo-isv/webhooks/inbound",
        )
        self.username = username
        self.password = password
        self.did = did
        self.bot_name = bot_name

        self.token: str | None = None
        self.client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    def _print_header(self, title: str):
        """Imprime un encabezado formateado."""
        print("\n" + "=" * 60)
        print(f"  {title}")
        print("=" * 60)

    def _print_result(self, success: bool, message: str):
        """Imprime un resultado formateado."""
        status = "PASS" if success else "FAIL"
        icon = "+" if success else "x"
        print(f"[{icon}] {status}: {message}")

    def _print_info(self, label: str, value: str):
        """Imprime información formateada."""
        print(f"  {label}: {value}")

    async def test_authentication(self) -> bool:
        """Prueba la autenticación con Chattigo API."""
        self._print_header("PRUEBA DE AUTENTICACION")

        if not self.username or not self.password:
            self._print_result(False, "Credenciales no configuradas en .env")
            return False

        self._print_info("Login URL", self.login_url)
        self._print_info("Username", self.username)
        self._print_info("DID", self.did)

        try:
            print("\n  Intentando login...")
            response = await self.client.post(
                self.login_url,
                json={"username": self.username, "password": self.password},
            )

            print(f"  Status Code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                self.token = data.get("access_token") or data.get("token")

                if self.token:
                    self._print_result(True, "Autenticacion exitosa")
                    self._print_info("Token (primeros 50 chars)", self.token[:50] + "...")
                    self._print_info("Usuario", data.get("user", "N/A"))
                    self._print_info("Acceso", str(data.get("access", False)))
                    return True
                else:
                    self._print_result(False, f"Respuesta sin token: {data}")
                    return False
            else:
                self._print_result(False, f"Error HTTP {response.status_code}")
                print(f"  Response: {response.text}")
                return False

        except Exception as e:
            self._print_result(False, f"Excepcion: {e}")
            return False

    async def send_test_message(
        self, phone_number: str, message: str | None = None
    ) -> bool:
        """Envía un mensaje de prueba via Chattigo API."""
        self._print_header("ENVIO DE MENSAJE DE PRUEBA")

        if not self.token:
            print("  No hay token. Ejecutando autenticacion primero...")
            if not await self.test_authentication():
                return False

        if not message:
            message = f"Mensaje de prueba de Aynux Bot - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        self._print_info("Destinatario", phone_number)
        self._print_info("DID (Bot number)", self.did)
        self._print_info("Mensaje", message[:50] + "..." if len(message) > 50 else message)
        self._print_info("Endpoint", self.message_url)

        try:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }

            # Chattigo proprietary format
            payload = {
                "id": str(int(datetime.now().timestamp() * 1000)),
                "did": self.did,
                "msisdn": phone_number,
                "type": "text",
                "channel": "WHATSAPP",
                "content": message,
                "name": self.bot_name,
                "isAttachment": False,
            }

            print(f"\n  Enviando mensaje...")
            print(f"  Payload: {payload}")

            response = await self.client.post(
                self.message_url,
                headers=headers,
                json=payload,
            )

            print(f"  Status Code: {response.status_code}")

            if response.status_code == 200:
                self._print_result(True, "Mensaje enviado exitosamente")
                if response.text:
                    print(f"  Response: {response.text}")
                return True
            else:
                self._print_result(False, f"Error al enviar mensaje")
                print(f"  Response: {response.text}")
                return False

        except Exception as e:
            self._print_result(False, f"Excepcion: {e}")
            return False

    async def run_full_test(self, phone_number: str | None = None):
        """Ejecuta todas las pruebas."""
        self._print_header("PRUEBA COMPLETA E2E - CHATTIGO API")
        print(f"  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Ambiente: {os.getenv('ENVIRONMENT', 'development')}")

        results = {
            "auth": False,
            "send_message": False,
        }

        # 1. Autenticación
        results["auth"] = await self.test_authentication()

        if not results["auth"]:
            print("\n[x] Autenticacion fallida. No se pueden continuar las pruebas.")
            return results

        # 2. Enviar mensaje de prueba (si se proporciona número)
        if phone_number:
            results["send_message"] = await self.send_test_message(phone_number)
        else:
            print("\n[!] No se proporciono numero de telefono. Omitiendo prueba de envio.")
            print("    Use --send-test --phone 5491112345678 para probar envio")

        # Resumen
        self._print_header("RESUMEN DE PRUEBAS")
        self._print_result(results["auth"], "Autenticacion")
        if phone_number:
            self._print_result(results["send_message"], "Envio de mensaje")

        all_passed = all(
            v for k, v in results.items() if k != "send_message" or phone_number
        )
        print("\n" + ("[+] TODAS LAS PRUEBAS PASARON" if all_passed else "[x] ALGUNAS PRUEBAS FALLARON"))

        # Información importante
        self._print_header("INFORMACION IMPORTANTE")
        print("""
  Endpoints API Chattigo:
  - Login: POST https://api.chattigo.com/login
  - Enviar mensaje: POST https://api.chattigo.com/message

  Credenciales ahora se almacenan en base de datos.
  Configure via Admin API: POST /api/v1/admin/chattigo-credentials

  Para tests manuales, pase credenciales via CLI:
  --username, --password, --did, --bot-name
        """)

        return results


async def main():
    parser = argparse.ArgumentParser(
        description="Pruebas de integracion Chattigo API",
        epilog="Credenciales se almacenan en DB. Configure via Admin API: POST /api/v1/admin/chattigo-credentials",
    )
    # Credential arguments (required)
    parser.add_argument("--username", type=str, required=True, help="Chattigo API username")
    parser.add_argument("--password", type=str, required=True, help="Chattigo API password")
    parser.add_argument("--did", type=str, default="5492644710400", help="WhatsApp Business DID")
    parser.add_argument("--bot-name", type=str, default="Aynux", help="Bot name for messages")
    # Action arguments
    parser.add_argument("--auth-only", action="store_true", help="Solo probar autenticacion")
    parser.add_argument("--send-test", action="store_true", help="Enviar mensaje de prueba")
    parser.add_argument("--phone", type=str, help="Numero de telefono para mensaje de prueba")
    parser.add_argument("--message", type=str, help="Mensaje personalizado")

    args = parser.parse_args()

    async with ChattigoTester(
        username=args.username,
        password=args.password,
        did=args.did,
        bot_name=args.bot_name,
    ) as tester:
        if args.auth_only:
            await tester.test_authentication()
        elif args.send_test:
            if not args.phone:
                print("[x] Error: Se requiere --phone para enviar mensaje de prueba")
                sys.exit(1)
            await tester.send_test_message(args.phone, args.message)
        else:
            # Ejecutar prueba completa
            await tester.run_full_test(args.phone)


if __name__ == "__main__":
    asyncio.run(main())
