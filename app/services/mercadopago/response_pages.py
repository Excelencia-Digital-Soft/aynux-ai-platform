"""
HTML response page generator for MercadoPago redirect endpoints.

Generates user-facing HTML pages for payment status redirects:
- Success: Payment approved confirmation
- Failure: Payment rejected/failed notification
- Pending: Payment under review notification

These pages are displayed to users after completing the MP checkout flow.
"""

from __future__ import annotations


class MercadoPagoResponsePages:
    """Generates HTML pages for MP payment redirect responses."""

    @staticmethod
    def success(
        payment_id: str | None,
        status: str | None,
        external_reference: str | None,
    ) -> str:
        """Generate success confirmation HTML page."""
        return f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pago Exitoso</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .card {{
            background: white;
            border-radius: 16px;
            padding: 40px;
            max-width: 420px;
            width: 100%;
            text-align: center;
            box-shadow: 0 10px 40px rgba(0,0,0,0.15);
        }}
        .icon {{ font-size: 64px; margin-bottom: 16px; }}
        h1 {{ color: #28a745; font-size: 28px; margin-bottom: 12px; }}
        .message {{ color: #666; font-size: 16px; margin-bottom: 24px; }}
        .details {{
            background: #f8f9fa;
            padding: 16px;
            border-radius: 8px;
            text-align: left;
            margin-bottom: 24px;
        }}
        .details p {{ margin: 8px 0; color: #444; font-size: 14px; }}
        .details strong {{ color: #333; }}
        .whatsapp-note {{
            background: #dcfce7;
            color: #166534;
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 14px;
            margin-bottom: 16px;
        }}
        .close-note {{ color: #999; font-size: 13px; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">&#10004;</div>
        <h1>Pago Exitoso!</h1>
        <p class="message">Tu pago ha sido procesado correctamente.</p>
        <div class="details">
            <p><strong>ID de Pago:</strong> {payment_id or 'N/A'}</p>
            <p><strong>Estado:</strong> {status or 'approved'}</p>
        </div>
        <div class="whatsapp-note">
            Recibiras el comprobante por WhatsApp en breve.
        </div>
        <p class="close-note">Puedes cerrar esta ventana.</p>
    </div>
</body>
</html>
"""

    @staticmethod
    def failure(
        payment_id: str | None,
        status: str | None,
        external_reference: str | None,
    ) -> str:
        """Generate failure/rejection HTML page."""
        return f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pago No Procesado</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .card {{
            background: white;
            border-radius: 16px;
            padding: 40px;
            max-width: 420px;
            width: 100%;
            text-align: center;
            box-shadow: 0 10px 40px rgba(0,0,0,0.15);
        }}
        .icon {{ font-size: 64px; margin-bottom: 16px; }}
        h1 {{ color: #dc3545; font-size: 28px; margin-bottom: 12px; }}
        .message {{ color: #666; font-size: 16px; margin-bottom: 24px; }}
        .details {{
            background: #f8f9fa;
            padding: 16px;
            border-radius: 8px;
            text-align: left;
            margin-bottom: 24px;
        }}
        .details p {{ margin: 8px 0; color: #444; font-size: 14px; }}
        .details strong {{ color: #333; }}
        .retry-note {{
            background: #fef3cd;
            color: #856404;
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 14px;
            margin-bottom: 16px;
        }}
        .close-note {{ color: #999; font-size: 13px; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">&#10060;</div>
        <h1>Pago No Procesado</h1>
        <p class="message">No pudimos procesar tu pago.</p>
        <div class="details">
            <p><strong>ID de Pago:</strong> {payment_id or 'N/A'}</p>
            <p><strong>Estado:</strong> {status or 'rejected'}</p>
        </div>
        <div class="retry-note">
            Puedes intentar nuevamente o contactar a tu farmacia para mas informacion.
        </div>
        <p class="close-note">Puedes cerrar esta ventana.</p>
    </div>
</body>
</html>
"""

    @staticmethod
    def pending(
        payment_id: str | None,
        status: str | None,
        external_reference: str | None,
    ) -> str:
        """Generate pending payment HTML page."""
        return f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pago Pendiente</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #ffc107 0%, #fd7e14 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .card {{
            background: white;
            border-radius: 16px;
            padding: 40px;
            max-width: 420px;
            width: 100%;
            text-align: center;
            box-shadow: 0 10px 40px rgba(0,0,0,0.15);
        }}
        .icon {{ font-size: 64px; margin-bottom: 16px; }}
        h1 {{ color: #856404; font-size: 28px; margin-bottom: 12px; }}
        .message {{ color: #666; font-size: 16px; margin-bottom: 24px; }}
        .details {{
            background: #f8f9fa;
            padding: 16px;
            border-radius: 8px;
            text-align: left;
            margin-bottom: 24px;
        }}
        .details p {{ margin: 8px 0; color: #444; font-size: 14px; }}
        .details strong {{ color: #333; }}
        .pending-note {{
            background: #fff3cd;
            color: #856404;
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 14px;
            margin-bottom: 16px;
        }}
        .close-note {{ color: #999; font-size: 13px; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">&#8987;</div>
        <h1>Pago Pendiente</h1>
        <p class="message">Tu pago esta siendo procesado.</p>
        <div class="details">
            <p><strong>ID de Pago:</strong> {payment_id or 'N/A'}</p>
            <p><strong>Estado:</strong> {status or 'pending'}</p>
        </div>
        <div class="pending-note">
            Te notificaremos por WhatsApp cuando se confirme el pago.
        </div>
        <p class="close-note">Puedes cerrar esta ventana.</p>
    </div>
</body>
</html>
"""
