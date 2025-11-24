"""
Domain Pattern Repository - Almacenamiento de patrones de clasificación de dominios.

Sigue el Single Responsibility Principle: solo almacena y provee
acceso a patrones de clasificación de dominios.
"""

from typing import Any


class DomainPatternRepository:
    """
    Repository para patrones de clasificación de dominios.

    Aplica SRP: Solo se encarga de almacenar y proveer patrones.
    No hace clasificación, no maneja estadísticas, no procesa mensajes.

    En el futuro, esto podría cargar patrones desde una base de datos
    o archivo de configuración, permitiendo patrones configurables por cliente.
    """

    def __init__(self):
        """Initialize domain patterns repository."""
        self._patterns: dict[str, dict[str, Any]] = {
            "ecommerce": {
                "description": "Comercio electrónico - compras, productos, ventas",
                "keywords": [
                    "comprar",
                    "producto",
                    "precio",
                    "tienda",
                    "envío",
                    "stock",
                    "descuento",
                    "carrito",
                    "pago",
                    "factura",
                    "garantía",
                    "devolución",
                    "catálogo",
                    "disponible",
                    "oferta",
                    "promoción",
                    "entrega",
                ],
                "phrases": [
                    "quiero comprar",
                    "cuánto cuesta",
                    "está disponible",
                    "hacer pedido",
                    "ver productos",
                    "necesito cotización",
                ],
                "indicators": ["$", "precio", "pesos", "dolares", "envío gratis"],
            },
            "hospital": {
                "description": "Salud - citas médicas, consultas, urgencias",
                "keywords": [
                    "cita",
                    "doctor",
                    "médico",
                    "consulta",
                    "urgencia",
                    "emergencia",
                    "síntoma",
                    "turno",
                    "especialista",
                    "hospital",
                    "clínica",
                    "paciente",
                    "dolor",
                    "fiebre",
                    "medicamento",
                    "receta",
                    "análisis",
                ],
                "phrases": [
                    "necesito cita",
                    "consulta médica",
                    "ver doctor",
                    "agendar turno",
                    "emergencia médica",
                    "resultado de análisis",
                ],
                "indicators": [
                    "urgente",
                    "dolor",
                    "cita médica",
                    "especialista",
                    "hospital",
                ],
            },
            "credit": {
                "description": "Créditos - préstamos, pagos, cobranzas",
                "keywords": [
                    "préstamo",
                    "crédito",
                    "pagar",
                    "deuda",
                    "cuota",
                    "interés",
                    "financiamiento",
                    "refinanciar",
                    "mora",
                    "vencimiento",
                    "balance",
                    "cuenta",
                    "transferencia",
                    "cobranza",
                    "pago",
                    "saldo",
                    "abono",
                ],
                "phrases": [
                    "pagar cuota",
                    "solicitar préstamo",
                    "consultar saldo",
                    "refinanciar deuda",
                    "abonar a mi cuenta",
                    "fecha de vencimiento",
                ],
                "indicators": [
                    "cuota",
                    "interés",
                    "vencimiento",
                    "refinanciar",
                    "saldo pendiente",
                ],
            },
        }

    def get_all_domains(self) -> list[str]:
        """
        Get list of all available domains.

        Returns:
            List of domain names
        """
        return list(self._patterns.keys())

    def get_description(self, domain: str) -> str:
        """
        Get description for a domain.

        Args:
            domain: Domain name

        Returns:
            Domain description
        """
        return self._patterns.get(domain, {}).get("description", "")

    def get_keywords(self, domain: str) -> list[str]:
        """
        Get keywords for a domain.

        Args:
            domain: Domain name

        Returns:
            List of keywords
        """
        return self._patterns.get(domain, {}).get("keywords", [])

    def get_phrases(self, domain: str) -> list[str]:
        """
        Get phrases for a domain.

        Args:
            domain: Domain name

        Returns:
            List of phrases
        """
        return self._patterns.get(domain, {}).get("phrases", [])

    def get_indicators(self, domain: str) -> list[str]:
        """
        Get indicators for a domain.

        Args:
            domain: Domain name

        Returns:
            List of indicators
        """
        return self._patterns.get(domain, {}).get("indicators", [])

    def get_pattern(self, domain: str) -> dict[str, Any]:
        """
        Get complete pattern for a domain.

        Args:
            domain: Domain name

        Returns:
            Complete pattern dictionary
        """
        return self._patterns.get(domain, {})

    def add_domain(
        self,
        domain: str,
        description: str,
        keywords: list[str],
        phrases: list[str],
        indicators: list[str],
    ) -> None:
        """
        Add new domain pattern.

        This allows for runtime configuration of new domains.

        Args:
            domain: Domain name
            description: Domain description
            keywords: List of keywords
            phrases: List of phrases
            indicators: List of indicators
        """
        self._patterns[domain] = {
            "description": description,
            "keywords": keywords,
            "phrases": phrases,
            "indicators": indicators,
        }

    def update_keywords(self, domain: str, keywords: list[str]) -> None:
        """
        Update keywords for a domain.

        Args:
            domain: Domain name
            keywords: New list of keywords
        """
        if domain in self._patterns:
            self._patterns[domain]["keywords"] = keywords

    def domain_exists(self, domain: str) -> bool:
        """
        Check if domain exists.

        Args:
            domain: Domain name

        Returns:
            True if domain exists
        """
        return domain in self._patterns

    def get_stats(self) -> dict[str, Any]:
        """
        Get repository statistics.

        Returns:
            Statistics about patterns
        """
        stats = {
            "total_domains": len(self._patterns),
            "domains": {},
        }

        for domain, pattern in self._patterns.items():
            stats["domains"][domain] = {
                "keywords_count": len(pattern.get("keywords", [])),
                "phrases_count": len(pattern.get("phrases", [])),
                "indicators_count": len(pattern.get("indicators", [])),
            }

        return stats
