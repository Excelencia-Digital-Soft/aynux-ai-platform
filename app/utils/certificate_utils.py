import io
from datetime import datetime, timedelta
from typing import Optional

import qrcode
from PIL import Image, ImageDraw, ImageFont


class CertificateGenerator:
    """
    Clase para generar certificados con código QR
    """

    @staticmethod
    async def generate_qr_certificate(
        nombre_completo: str, documento: str, id_ciudadano: str
    ) -> Optional[bytes]:
        """
        Genera un certificado con código QR

        Args:
            nombre_completo: Nombre completo del ciudadano
            documento: Número de documento
            id_ciudadano: ID del ciudadano

        Returns:
            Bytes de la imagen generada o None si hay error
        """
        try:
            # Datos para el código QR
            fecha_actual = datetime.now().strftime("%Y-%m-%d")
            fecha_vencimiento = (datetime.now() + timedelta(days=30)).strftime(
                "%Y-%m-%d"
            )

            qr_data = (
                f"ID:{id_ciudadano}|"
                f"DOCUMENTO:{documento}|"
                f"FECHA:{fecha_actual}|"
                f"VENCIMIENTO:{fecha_vencimiento}"
            )

            # Generar código QR
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_data)
            qr.make(fit=True)

            qr_img = qr.make_image(fill_color="black", back_color="white")

            # Crear imagen base para el certificado
            width, height = 800, 600
            certificate = Image.new(
                "RGB",
                (width, height),
            )
            draw = ImageDraw.Draw(certificate)

            # Intentar cargar fuentes, usar fuente por defecto si no se encuentran
            try:
                title_font = ImageFont.truetype("Arial.ttf", 40)
                subtitle_font = ImageFont.truetype("Arial.ttf", 30)
                normal_font = ImageFont.truetype("Arial.ttf", 24)
            except OSError:
                # Usar fuente por defecto si no se encuentra Arial
                title_font = ImageFont.load_default()
                subtitle_font = ImageFont.load_default()
                normal_font = ImageFont.load_default()

            # Dibujar bordes y título
            draw.rectangle([(0, 0), (width, height)], outline="darkgreen", width=10)
            draw.text(
                (width // 2, 50),
                "MUNICIPALIDAD",
                fill="darkgreen",
                font=title_font,
                anchor="mm",
            )
            draw.text(
                (width // 2, 100),
                "Certificado de Residencia",
                fill="darkgreen",
                font=subtitle_font,
                anchor="mm",
            )

            # Dibujar línea divisoria
            draw.line([(50, 140), (width - 50, 140)], fill="darkgreen", width=2)

            # Agregar datos del ciudadano
            draw.text(
                (width // 2, 200),
                "Por la presente se certifica que:",
                fill="black",
                font=normal_font,
                anchor="mm",
            )

            draw.text(
                (width // 2, 250),
                f"{nombre_completo}",
                fill="black",
                font=subtitle_font,
                anchor="mm",
            )

            draw.text(
                (width // 2, 300),
                f"DNI: {documento}",
                fill="black",
                font=normal_font,
                anchor="mm",
            )

            draw.text(
                (width // 2, 350),
                "es residente de este municipio.",
                fill="black",
                font=normal_font,
                anchor="mm",
            )

            # Fechas
            draw.text(
                (width // 2, 420),
                f"Fecha de emisión: {fecha_actual}",
                fill="black",
                font=normal_font,
                anchor="mm",
            )

            draw.text(
                (width // 2, 460),
                f"Válido hasta: {fecha_vencimiento}",
                fill="black",
                font=normal_font,
                anchor="mm",
            )

            # Agregar código QR
            qr_pos = (width - qr_img.width - 100, height - qr_img.height - 100)  # type: ignore
            certificate.paste(qr_img, qr_pos)

            # Convertir a bytes
            img_byte_arr = io.BytesIO()
            certificate.save(img_byte_arr, format="PNG")
            return img_byte_arr.getvalue()

        except Exception as e:
            print(f"Error al generar certificado: {e}")
            return None
