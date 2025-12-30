#!/usr/bin/env python3
"""
Script de prueba especifica para aislar campos criticos de Chattigo ISV.

Uso:
    cd python
    uv run python scripts/test_chattigo_specific.py --phone 5492644472542
"""

import asyncio
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


class ChattigoSpecificTester:
    def __init__(self):
        self.base_url = "https://channels.chattigo.com/bsp-cloud-chattigo-isv"
        self.login_url = f"{self.base_url}/login"
        self.message_url = f"{self.base_url}/webhooks/inbound"

        self.username = os.getenv("CHATTIGO_USERNAME", "")
        self.password = os.getenv("CHATTIGO_PASSWORD", "")
        self.did = os.getenv("CHATTIGO_DID", "5492644710400")
        self.bot_name = os.getenv("CHATTIGO_BOT_NAME", "Aynux")
        self.channel_id = int(os.getenv("CHATTIGO_CHANNEL_ID", "0"))
        self.id_campaign = os.getenv("CHATTIGO_ID_CAMPAIGN", "")

        self.token: str | None = None
        self.client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    async def authenticate(self) -> bool:
        print("Autenticando...")
        response = await self.client.post(
            self.login_url,
            json={"username": self.username, "password": self.password},
        )
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token")
            print(f"[+] Token obtenido")
            return True
        print(f"[x] Error auth: {response.status_code}")
        return False

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    async def test_payload(self, name: str, payload: dict) -> tuple[int, str]:
        """Prueba un payload y retorna (status_code, response)."""
        try:
            response = await self.client.post(
                self.message_url,
                headers=self._get_headers(),
                json=payload,
            )
            return response.status_code, response.text[:200] if response.text else "(empty)"
        except Exception as e:
            return -1, str(e)

    async def run_specific_tests(self, phone: str):
        """Pruebas especificas para aislar campos criticos."""
        print("\n" + "=" * 70)
        print("  PRUEBAS ESPECIFICAS - AISLANDO CAMPOS CRITICOS")
        print("=" * 70)

        print(f"\n  DID: {self.did}")
        print(f"  Channel ID: {self.channel_id}")
        print(f"  Phone: {phone}")

        if not await self.authenticate():
            return

        ts = int(time.time() * 1000)

        # Test 1: Payload minimo (el que funciono con 200)
        tests = [
            ("1_minimo", {
                "id": str(ts),
                "did": self.did,
                "msisdn": phone,
                "type": "text",
                "channel": "WHATSAPP",
                "content": "Test 1: Payload minimo",
                "name": self.bot_name,
                "isAttachment": False,
            }),

            # Test 2: Agregar chatType OUTBOUND
            ("2_con_chatType", {
                "id": str(ts + 1),
                "did": self.did,
                "msisdn": phone,
                "type": "text",
                "channel": "WHATSAPP",
                "content": "Test 2: Con chatType",
                "name": self.bot_name,
                "isAttachment": False,
                "chatType": "OUTBOUND",
            }),

            # Test 3: chatType + channelProvider
            ("3_chatType_provider", {
                "id": str(ts + 2),
                "did": self.did,
                "msisdn": phone,
                "type": "text",
                "channel": "WHATSAPP",
                "content": "Test 3: chatType + provider",
                "name": self.bot_name,
                "isAttachment": False,
                "chatType": "OUTBOUND",
                "channelProvider": "APICLOUDBSP",
            }),

            # Test 4: Type con mayuscula (como BSP)
            ("4_Type_mayuscula", {
                "id": str(ts + 3),
                "did": self.did,
                "msisdn": phone,
                "type": "Text",  # Mayuscula
                "channel": "WHATSAPP",
                "content": "Test 4: Type mayuscula",
                "name": self.bot_name,
                "isAttachment": False,
            }),

            # Test 5: Type mayuscula + chatType + channelProvider
            ("5_Type_chat_provider", {
                "id": str(ts + 4),
                "did": self.did,
                "msisdn": phone,
                "type": "Text",
                "channel": "WHATSAPP",
                "content": "Test 5: Type+chat+provider",
                "name": self.bot_name,
                "isAttachment": False,
                "chatType": "OUTBOUND",
                "channelProvider": "APICLOUDBSP",
            }),

            # Test 6: Con channelId
            ("6_con_channelId", {
                "id": str(ts + 5),
                "did": self.did,
                "msisdn": phone,
                "type": "Text",
                "channel": "WHATSAPP",
                "channelId": self.channel_id,
                "content": "Test 6: Con channelId",
                "name": self.bot_name,
                "isAttachment": False,
                "chatType": "OUTBOUND",
                "channelProvider": "APICLOUDBSP",
            }),

            # Test 7: Payload BSP completo (sin idChat ni idCampaign)
            ("7_bsp_sin_ids", {
                "id": str(ts + 6),
                "did": self.did,
                "msisdn": phone,
                "type": "Text",
                "channel": "WHATSAPP",
                "channelId": self.channel_id,
                "channelProvider": "APICLOUDBSP",
                "content": "Test 7: BSP sin IDs",
                "name": self.bot_name,
                "isAttachment": False,
                "chatType": "OUTBOUND",
                "stateAgent": "BOT",
            }),

            # Test 8: BSP completo con idChat=0
            ("8_bsp_idChat_0", {
                "id": str(ts + 7),
                "idChat": 0,
                "did": self.did,
                "msisdn": phone,
                "type": "Text",
                "channel": "WHATSAPP",
                "channelId": self.channel_id,
                "channelProvider": "APICLOUDBSP",
                "content": "Test 8: BSP idChat=0",
                "name": self.bot_name,
                "isAttachment": False,
                "chatType": "OUTBOUND",
                "stateAgent": "BOT",
            }),

            # Test 9: idChat como null/None (no incluirlo)
            ("9_sin_idChat", {
                "id": str(ts + 8),
                "did": self.did,
                "msisdn": phone,
                "type": "Text",
                "channel": "WHATSAPP",
                "channelId": self.channel_id,
                "channelProvider": "APICLOUDBSP",
                "content": "Test 9: Sin idChat",
                "name": self.bot_name,
                "isAttachment": False,
                "chatType": "OUTBOUND",
                "stateAgent": "BOT",
            }),

            # Test 10: Con idCampaign (si esta configurado)
            ("10_con_campaign", {
                "id": str(ts + 9),
                "did": self.did,
                "msisdn": phone,
                "type": "Text",
                "channel": "WHATSAPP",
                "channelId": self.channel_id,
                "channelProvider": "APICLOUDBSP",
                "content": "Test 10: Con campaign",
                "name": self.bot_name,
                "idCampaign": self.id_campaign or "default",
                "isAttachment": False,
                "chatType": "OUTBOUND",
                "stateAgent": "BOT",
            }),
        ]

        print("\n" + "-" * 70)
        print("  RESULTADOS:")
        print("-" * 70)

        results_200 = []
        results_error = []

        for name, payload in tests:
            status, response = await self.test_payload(name, payload)

            icon = "+" if status == 200 else "x"
            print(f"  [{icon}] {name}: HTTP {status}")

            if status == 200:
                results_200.append(name)
            else:
                results_error.append((name, status, response[:100]))

            await asyncio.sleep(0.5)

        print("\n" + "-" * 70)
        print("  RESUMEN:")
        print("-" * 70)

        print(f"\n  Payloads con HTTP 200: {len(results_200)}")
        for name in results_200:
            print(f"    - {name}")

        if results_error:
            print(f"\n  Payloads con ERROR (no 200):")
            for name, status, resp in results_error:
                print(f"    - {name}: HTTP {status}")
                if status not in [200, 404]:
                    print(f"      {resp}")

        print("\n" + "=" * 70)
        print("  VERIFICA TU WHATSAPP - ¿LLEGO ALGUN MENSAJE?")
        print("  Si llego, identifica cual por el contenido del mensaje.")
        print("=" * 70)


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--phone", type=str, default="5492644472542")
    args = parser.parse_args()

    async with ChattigoSpecificTester() as tester:
        await tester.run_specific_tests(args.phone)


if __name__ == "__main__":
    asyncio.run(main())
