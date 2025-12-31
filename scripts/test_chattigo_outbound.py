#!/usr/bin/env python3
"""
Script de prueba exhaustivo para encontrar el endpoint correcto de Chattigo ISV.

Prueba múltiples combinaciones de:
1. Endpoints: /outbound, /webhooks/outbound, /webhooks/inbound, /message, /send
2. Payloads: Simplificado vs BSP completo con chatType OUTBOUND

IMPORTANTE: Las credenciales de Chattigo ahora se almacenan en la base de datos.
Configure credenciales via Admin API: POST /api/v1/admin/chattigo-credentials

Uso:
    cd python
    uv run python scripts/test_chattigo_outbound.py --username USER --password PASS
"""

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Load environment variables (only for URLs)
load_dotenv(Path(__file__).parent.parent / ".env")


class ChattigoOutboundTester:
    """Tester exhaustivo para encontrar el endpoint de outbound de Chattigo ISV."""

    def __init__(self, username: str, password: str, did: str, bot_name: str = "Aynux"):
        self.base_url = "https://channels.chattigo.com/bsp-cloud-chattigo-isv"
        self.login_url = os.getenv("CHATTIGO_LOGIN_URL", f"{self.base_url}/login")
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
        print("\n" + "=" * 70)
        print(f"  {title}")
        print("=" * 70)

    def _print_result(self, success: bool, message: str):
        status = "PASS" if success else "FAIL"
        icon = "+" if success else "x"
        print(f"[{icon}] {status}: {message}")

    async def authenticate(self) -> bool:
        """Autenticarse con Chattigo."""
        self._print_header("AUTENTICACION")

        if not self.username or not self.password:
            self._print_result(False, "Credenciales no configuradas")
            return False

        try:
            response = await self.client.post(
                self.login_url,
                json={"username": self.username, "password": self.password},
            )

            print(f"  Login URL: {self.login_url}")
            print(f"  Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                self.token = data.get("access_token")
                if self.token:
                    self._print_result(True, "Token obtenido")
                    return True

            self._print_result(False, f"Error: {response.text[:200]}")
            return False

        except Exception as e:
            self._print_result(False, f"Excepcion: {e}")
            return False

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _build_simple_payload(self, msisdn: str, message: str) -> dict:
        """Payload simplificado (el que usamos actualmente)."""
        return {
            "id": str(int(time.time() * 1000)),
            "did": self.did,
            "msisdn": msisdn,
            "type": "text",
            "channel": "WHATSAPP",
            "content": message,
            "name": self.bot_name,
            "isAttachment": False,
        }

    def _build_bsp_payload(self, msisdn: str, message: str, id_chat: int = 0) -> dict:
        """Payload estilo BSP completo con chatType OUTBOUND."""
        return {
            "id": str(int(time.time() * 1000)),
            "idChat": id_chat,
            "chatType": "OUTBOUND",
            "did": self.did,
            "msisdn": msisdn,
            "type": "Text",  # Mayuscula como BSP
            "channel": "WHATSAPP",
            "channelId": self.channel_id,
            "channelProvider": "APICLOUDBSP",  # Mismo que BSP
            "content": message,
            "name": self.bot_name,
            "idCampaign": self.id_campaign,
            "isAttachment": False,
            "stateAgent": "BOT",
        }

    def _build_isv_outbound_payload(self, msisdn: str, message: str, id_chat: int = 0) -> dict:
        """Payload para ISV con chatType OUTBOUND pero sin channelProvider BSP."""
        return {
            "id": str(int(time.time() * 1000)),
            "idChat": id_chat,
            "chatType": "OUTBOUND",
            "did": self.did,
            "msisdn": msisdn,
            "type": "text",
            "channel": "WHATSAPP",
            "channelId": self.channel_id,
            "content": message,
            "name": self.bot_name,
            "idCampaign": self.id_campaign,
            "isAttachment": False,
            "stateAgent": "BOT",
        }

    async def test_endpoint(
        self,
        endpoint: str,
        payload: dict,
        payload_name: str
    ) -> dict:
        """Prueba un endpoint con un payload especifico."""
        url = f"{self.base_url}{endpoint}"

        try:
            response = await self.client.post(
                url,
                headers=self._get_headers(),
                json=payload,
            )

            result = {
                "endpoint": endpoint,
                "payload_type": payload_name,
                "status_code": response.status_code,
                "success": response.status_code == 200,
                "response": response.text[:500] if response.text else "(empty)",
            }

            return result

        except Exception as e:
            return {
                "endpoint": endpoint,
                "payload_type": payload_name,
                "status_code": -1,
                "success": False,
                "response": str(e),
            }

    async def run_exhaustive_test(self, phone_number: str):
        """Ejecuta pruebas exhaustivas de todos los endpoints y payloads."""
        self._print_header("PRUEBA EXHAUSTIVA DE ENDPOINTS CHATTIGO ISV")

        print(f"\n  Configuracion:")
        print(f"    DID: {self.did}")
        print(f"    Channel ID: {self.channel_id}")
        print(f"    ID Campaign: {self.id_campaign or '(no configurado)'}")
        print(f"    Telefono destino: {phone_number}")

        if not await self.authenticate():
            return

        # Endpoints a probar
        endpoints = [
            "/outbound",
            "/webhooks/outbound",
            "/webhooks/inbound",
            "/message",
            "/messages",
            "/send",
            "/api/outbound",
            "/api/message",
        ]

        # Payloads a probar
        timestamp = time.strftime("%H:%M:%S")
        payloads = [
            ("simple", self._build_simple_payload(phone_number, f"Test simple {timestamp}")),
            ("bsp_full", self._build_bsp_payload(phone_number, f"Test BSP {timestamp}")),
            ("isv_outbound", self._build_isv_outbound_payload(phone_number, f"Test ISV {timestamp}")),
        ]

        results = []

        self._print_header("PROBANDO ENDPOINTS")

        for endpoint in endpoints:
            print(f"\n--- Endpoint: {endpoint} ---")

            for payload_name, payload in payloads:
                result = await self.test_endpoint(endpoint, payload, payload_name)
                results.append(result)

                status_icon = "+" if result["success"] else "x"
                print(f"  [{status_icon}] {payload_name}: HTTP {result['status_code']}")

                if result["status_code"] == 200:
                    print(f"      Response: {result['response'][:100]}")
                elif result["status_code"] not in [404, -1]:
                    print(f"      Response: {result['response'][:200]}")

                # Pequeña pausa para no sobrecargar
                await asyncio.sleep(0.5)

        # Resumen
        self._print_header("RESUMEN DE RESULTADOS")

        successful = [r for r in results if r["success"]]
        if successful:
            print("\n  ENDPOINTS QUE RETORNARON 200:")
            for r in successful:
                print(f"    - {r['endpoint']} con payload {r['payload_type']}")
                print(f"      Response: {r['response'][:150]}")
        else:
            print("\n  [!] Ningun endpoint retorno 200")

        # Mostrar 4xx/5xx (no 404)
        errors = [r for r in results if r["status_code"] not in [200, 404, -1]]
        if errors:
            print("\n  ENDPOINTS CON ERRORES INTERESANTES (no 404):")
            for r in errors:
                print(f"    - {r['endpoint']} ({r['payload_type']}): HTTP {r['status_code']}")
                print(f"      {r['response'][:150]}")

        return results


async def main():
    parser = argparse.ArgumentParser(
        description="Prueba exhaustiva de Chattigo ISV",
        epilog="Credenciales se almacenan en DB. Configure via Admin API: POST /api/v1/admin/chattigo-credentials",
    )
    # Credential arguments (required)
    parser.add_argument("--username", type=str, required=True, help="Chattigo API username")
    parser.add_argument("--password", type=str, required=True, help="Chattigo API password")
    parser.add_argument("--did", type=str, default="5492644710400", help="WhatsApp Business DID")
    parser.add_argument("--bot-name", type=str, default="Aynux", help="Bot name for messages")
    # Test arguments
    parser.add_argument("--phone", type=str, default="5492644472542",
                        help="Numero de telefono para prueba")

    args = parser.parse_args()

    async with ChattigoOutboundTester(
        username=args.username,
        password=args.password,
        did=args.did,
        bot_name=args.bot_name,
    ) as tester:
        await tester.run_exhaustive_test(args.phone)


if __name__ == "__main__":
    asyncio.run(main())
