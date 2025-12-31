#!/usr/bin/env python3
"""
Script de prueba para diferentes formatos de numero de telefono.

WhatsApp Business tiene varias reglas:
1. Ventana de 24 horas: Solo puedes enviar mensajes a usuarios que te escribieron
2. Formato del numero: Puede requerir formato especifico (con/sin +, codigo de pais, etc.)

IMPORTANTE: Las credenciales de Chattigo ahora se almacenan en la base de datos.
Configure credenciales via Admin API: POST /api/v1/admin/chattigo-credentials

Uso:
    cd python
    uv run python scripts/test_chattigo_phone_formats.py --username USER --password PASS --phone 5492644472542
"""

import argparse
import asyncio
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


class PhoneFormatTester:
    def __init__(self, username: str, password: str, did: str, bot_name: str = "Aynux"):
        self.base_url = "https://channels.chattigo.com/bsp-cloud-chattigo-isv"
        self.login_url = f"{self.base_url}/login"
        self.message_url = f"{self.base_url}/webhooks/inbound"

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

    async def authenticate(self) -> bool:
        print("Autenticando...")
        response = await self.client.post(
            self.login_url,
            json={"username": self.username, "password": self.password},
        )
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            print(f"[+] Token obtenido")
            return True
        print(f"[x] Error: {response.status_code}")
        return False

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    async def send_message(self, msisdn: str, content: str) -> tuple[int, str]:
        """Envia mensaje con el payload simple que da 200."""
        payload = {
            "id": str(int(time.time() * 1000)),
            "did": self.did,
            "msisdn": msisdn,
            "type": "text",
            "channel": "WHATSAPP",
            "content": content,
            "name": self.bot_name,
            "isAttachment": False,
            "chatType": "OUTBOUND",  # Incluimos esto porque tambien dio 200
        }

        try:
            response = await self.client.post(
                self.message_url,
                headers=self._get_headers(),
                json=payload,
            )
            return response.status_code, response.text[:200] if response.text else "(empty)"
        except Exception as e:
            return -1, str(e)

    async def run_phone_format_tests(self, base_phone: str):
        """Prueba diferentes formatos del numero de telefono."""
        print("\n" + "=" * 70)
        print("  PRUEBA DE FORMATOS DE NUMERO DE TELEFONO")
        print("=" * 70)

        print(f"\n  DID (numero bot): {self.did}")
        print(f"  Numero base: {base_phone}")

        if not await self.authenticate():
            return

        # Generar variantes del numero
        # Asumiendo base_phone es: 5492644472542
        # Posibles formatos:
        # - 5492644472542 (codigo pais + area + numero, sin +)
        # - +5492644472542 (con +)
        # - 549 2644 472542 (con espacios)
        # - 92644472542 (sin codigo pais completo)
        # - 2644472542 (solo area + numero)
        # - 542644472542 (54 + area sin 9)

        # Limpiar el numero base
        clean = base_phone.replace("+", "").replace(" ", "").replace("-", "")

        variants = []

        # Formato completo sin +
        variants.append(("completo_sin_plus", clean))

        # Formato con +
        variants.append(("con_plus", f"+{clean}"))

        # Si empieza con 549, probar sin el 9 de celular
        if clean.startswith("549"):
            without_9 = "54" + clean[3:]
            variants.append(("sin_9_celular", without_9))

        # Si empieza con 54, probar sin codigo de pais
        if clean.startswith("54"):
            without_country = clean[2:]
            variants.append(("sin_codigo_pais", without_country))

            # Sin 54 pero con 9
            if clean.startswith("549"):
                only_9_and_rest = "9" + clean[3:]
                variants.append(("solo_9_y_numero", only_9_and_rest))

        # Solo el numero local (ultimos 10 digitos)
        if len(clean) > 10:
            local = clean[-10:]
            variants.append(("solo_local_10dig", local))

        print("\n  Variantes a probar:")
        for name, phone in variants:
            print(f"    - {name}: {phone}")

        print("\n" + "-" * 70)
        print("  ENVIANDO MENSAJES:")
        print("-" * 70)

        ts = time.strftime("%H:%M:%S")

        for name, phone in variants:
            content = f"Test {name} ({ts})"
            status, response = await self.send_message(phone, content)

            icon = "+" if status == 200 else "x"
            print(f"  [{icon}] {name} ({phone}): HTTP {status}")

            if status != 200:
                print(f"      Response: {response[:100]}")

            await asyncio.sleep(1)  # Pausa entre mensajes

        print("\n" + "=" * 70)
        print("  IMPORTANTE - REGLAS DE WHATSAPP BUSINESS:")
        print("=" * 70)
        print("""
  1. VENTANA DE 24 HORAS: Solo puedes enviar mensajes a usuarios
     que te escribieron en las ultimas 24 horas.

  2. MENSAJES FUERA DE VENTANA: Requieren usar templates aprobados
     por WhatsApp/Meta.

  3. NUMERO DEL BOT (DID): Verifica que el DID configurado sea
     correcto y este asociado a tu cuenta Chattigo ISV.

  PARA PROBAR:
  - El usuario destino debe PRIMERO enviar un mensaje al numero del bot
  - Esperar unos segundos
  - Luego volver a ejecutar este script
        """)


async def main():
    parser = argparse.ArgumentParser(
        description="Prueba de formatos de telefono Chattigo ISV",
        epilog="Credenciales se almacenan en DB. Configure via Admin API: POST /api/v1/admin/chattigo-credentials",
    )
    # Credential arguments (required)
    parser.add_argument("--username", type=str, required=True, help="Chattigo API username")
    parser.add_argument("--password", type=str, required=True, help="Chattigo API password")
    parser.add_argument("--did", type=str, default="5492644710400", help="WhatsApp Business DID")
    parser.add_argument("--bot-name", type=str, default="Aynux", help="Bot name for messages")
    # Test arguments
    parser.add_argument("--phone", type=str, default="5492644472542", help="Phone number for test")
    args = parser.parse_args()

    async with PhoneFormatTester(
        username=args.username,
        password=args.password,
        did=args.did,
        bot_name=args.bot_name,
    ) as tester:
        await tester.run_phone_format_tests(args.phone)


if __name__ == "__main__":
    asyncio.run(main())
