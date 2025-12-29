#!/usr/bin/env python3
"""Registrar webhook en Chattigo ISV."""

import asyncio

import httpx


async def main():
    base_url = "https://channels.chattigo.com/bsp-cloud-chattigo-isv"
    username = "apimasive@munitintina"
    password = "api@2025"

    async with httpx.AsyncClient(timeout=30) as client:
        # 1. Login
        print("1. Obteniendo token...")
        resp = await client.post(f"{base_url}/login", json={"username": username, "password": password})
        print(f"   Status: {resp.status_code}")
        data = resp.json()
        token = data.get("access_token")
        print(f"   Token: {token[:50]}...")

        # 2. Registrar webhook (sin prefijo Bearer - según código original)
        print("\n2. Registrando webhook...")
        headers = {
            "Authorization": token,  # Sin "Bearer" prefix
            "Content-Type": "application/json",
        }
        payload = {"waId": "5492644710400", "externalWebhook": "https://api.aynux.com.ar/api/v1/webhook"}
        print(f"   Payload: {payload}")

        resp = await client.patch(f"{base_url}/webhooks/inbound", headers=headers, json=payload)
        print(f"   Status: {resp.status_code}")
        print(f"   Response: {resp.text}")

        # 3. Probar envío de mensaje - formato Meta Cloud API
        print("\n3. Probando envío de mensaje (formato Meta)...")

        # Headers con Bearer para mensajes
        msg_headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # Payload estilo Meta Cloud API
        meta_payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": "5492644472542",
            "type": "text",
            "text": {"preview_url": False, "body": "Mensaje de prueba desde Aynux Bot"},
        }

        # Probar diferentes endpoints
        endpoints = [
            f"{base_url}/v15.0/5492644710400/messages",
            f"{base_url}/v14.0/5492644710400/messages",
            "https://channels.chattigo.com/bsp-cloud-chattigo/v15.0/5492644710400/messages",
            "https://api.chattigo.com/v15.0/5492644710400/messages",
        ]

        for endpoint in endpoints:
            print(f"\n   Probando: {endpoint}")
            try:
                resp = await client.post(endpoint, headers=msg_headers, json=meta_payload)
                print(f"   Status: {resp.status_code}")
                print(f"   Response: {resp.text[:200] if resp.text else 'empty'}")
                if resp.status_code == 200:
                    print("   ¡ÉXITO!")
                    break
            except Exception as e:
                print(f"   Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
