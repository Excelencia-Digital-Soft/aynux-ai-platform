#!/usr/bin/env python3
"""
Script de pruebas E2E para la integración con Chattigo ISV.

Este script verifica:
1. Autenticación con Chattigo API
2. Envío de mensaje de prueba via /webhooks/inbound

Uso:
    cd python
    uv run python scripts/test_chattigo.py

    # Solo autenticación
    uv run python scripts/test_chattigo.py --auth-only

    # Enviar mensaje de prueba
    uv run python scripts/test_chattigo.py --send-test --phone 5491112345678
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

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env")


class ChattigoTester:
    """Clase para probar la integración con Chattigo."""

    def __init__(self):
        self.base_url = os.getenv(
            "CHATTIGO_BASE_URL",
            "https://channels.chattigo.com/bsp-cloud-chattigo-isv",
        )
        self.username = os.getenv("CHATTIGO_USERNAME", "")
        self.password = os.getenv("CHATTIGO_PASSWORD", "")
        self.channel_id = int(os.getenv("CHATTIGO_CHANNEL_ID", "12676"))
        self.campaign_id = os.getenv("CHATTIGO_CAMPAIGN_ID", "7883")
        self.bot_name = os.getenv("CHATTIGO_BOT_NAME", "Aynux")

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

        self._print_info("Base URL", self.base_url)
        self._print_info("Username", self.username)
        self._print_info("Channel ID", str(self.channel_id))

        try:
            print("\n  Intentando login...")
            # Endpoint correcto: /login (sin /api-bot/)
            response = await self.client.post(
                f"{self.base_url}/login",
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

    async def send_test_message(self, phone_number: str, message: str | None = None) -> bool:
        """Envía un mensaje de prueba via /webhooks/inbound."""
        self._print_header("ENVIO DE MENSAJE DE PRUEBA")

        if not self.token:
            print("  No hay token. Ejecutando autenticacion primero...")
            if not await self.test_authentication():
                return False

        if not message:
            message = f"Mensaje de prueba de Aynux Bot - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        self._print_info("Destinatario", phone_number)
        self._print_info("Mensaje", message[:50] + "..." if len(message) > 50 else message)
        self._print_info("Endpoint", f"{self.base_url}/webhooks/inbound")

        try:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }

            # Payload para /webhooks/inbound
            payload = {
                "did": str(self.channel_id),
                "msisdn": phone_number,
                "name": self.bot_name,
                "type": "text",
                "channel": "WHATSAPP",
                "content": message,
                "isAttachment": False,
            }

            print(f"\n  Enviando mensaje...")
            print(f"  Payload: {payload}")

            response = await self.client.post(
                f"{self.base_url}/webhooks/inbound",
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
        self._print_header("PRUEBA COMPLETA E2E - CHATTIGO ISV")
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
  Endpoints API Chattigo ISV:
  - Login: POST /login
  - Enviar mensaje: POST /webhooks/inbound

  Webhook de respuestas (donde Chattigo envia mensajes):
  - Se configura en el panel de Chattigo, no via API
  - URL configurada: https://api.aynux.com.ar/api/v1/webhook
  - Contactar a Chattigo si no esta configurado
        """)

        return results


async def main():
    parser = argparse.ArgumentParser(description="Pruebas de integracion Chattigo ISV")
    parser.add_argument("--auth-only", action="store_true", help="Solo probar autenticacion")
    parser.add_argument("--send-test", action="store_true", help="Enviar mensaje de prueba")
    parser.add_argument("--phone", type=str, help="Numero de telefono para mensaje de prueba")
    parser.add_argument("--message", type=str, help="Mensaje personalizado")

    args = parser.parse_args()

    async with ChattigoTester() as tester:
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
