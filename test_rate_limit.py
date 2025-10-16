"""
Script de prueba para verificar el rate limiting de DUX API
"""
import asyncio
import logging
from datetime import datetime

from app.clients.dux_api_client import DuxApiClient

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_rate_limiting():
    """Prueba el rate limiting con múltiples requests seguidos"""
    print("\n" + "="*80)
    print("PRUEBA DE RATE LIMITING - DUX API")
    print("="*80)
    print("\nLa API de DUX tiene un límite de 1 petición cada 5 segundos.")
    print("Este test hará 3 peticiones seguidas y verificará que se respeten los tiempos.\n")

    # Resetear el rate limiter antes de empezar para evitar interferencia
    # de requests anteriores
    from app.utils.rate_limiter import dux_rate_limiter
    dux_rate_limiter.rate_limiter.reset()
    print("🔄 Rate limiter reseteado\n")

    async with DuxApiClient() as client:
        times = []

        print("\n📊 Ejecutando 3 peticiones con rate limiting automático...\n")

        for i in range(3):
            start = datetime.now()

            try:
                print(f"⏱️  Request #{i+1} - Inicio: {start.strftime('%H:%M:%S.%f')[:-3]}")
                response = await client.get_items(offset=0, limit=1)
                end = datetime.now()

                elapsed = (end - start).total_seconds()
                times.append(elapsed)

                print(f"✅ Request #{i+1} - Completada en {elapsed:.2f}s")
                print(f"   Total items disponibles: {response.get_total_items()}")

                if i < 2:  # No calcular tiempo entre requests para el último
                    time_to_next = 5.0 - elapsed if elapsed < 5.0 else 0
                    if time_to_next > 0:
                        print(f"   ⏳ Esperando {time_to_next:.2f}s para el siguiente request...")
                    print()

            except Exception as e:
                end = datetime.now()
                elapsed = (end - start).total_seconds()
                print(f"❌ Request #{i+1} - Error después de {elapsed:.2f}s: {e}")
                print()

        print("\n" + "="*80)
        print("RESUMEN DE TIEMPOS")
        print("="*80)

        for i, t in enumerate(times, 1):
            status = "✅ Exitoso" if t >= 0 else "❌ Error"
            print(f"Request #{i}: {t:.2f}s - {status}")

        if len(times) >= 2:
            total_time = sum(times)
            avg_time = total_time / len(times)
            print(f"\nTiempo total: {total_time:.2f}s")
            print(f"Tiempo promedio: {avg_time:.2f}s")
            print(f"Requests por minuto: {60 / avg_time:.2f}")

            print("\n" + "="*80)
            print("VERIFICACIÓN")
            print("="*80)

            # El primer request debería ser instantáneo (o casi)
            # Los siguientes deberían tomar al menos 5 segundos cada uno
            if times[0] < 1.0:
                print("✅ Request #1: Instantáneo como se esperaba")
            else:
                print(f"⚠️  Request #1: Tomó {times[0]:.2f}s (esperado <1s)")

            for i in range(1, len(times)):
                if times[i] >= 4.5:  # Damos un pequeño margen
                    print(f"✅ Request #{i+1}: Respetó el rate limit de 5s")
                else:
                    print(f"⚠️  Request #{i+1}: Tomó {times[i]:.2f}s (esperado ≥5s)")

if __name__ == "__main__":
    asyncio.run(test_rate_limiting())
