"""
Script to seed the company knowledge base with initial Excelencia ERP information.

This script populates the knowledge base with:
- Mission, vision, and values
- Contact information and social media
- Software catalog descriptions
- FAQs about demos, pricing, implementation
- Client information and success stories

Usage:
    python -m app.scripts.seed_knowledge_base

or from project root:
    uv run python app/scripts/seed_knowledge_base.py
"""

import asyncio
import logging
from datetime import datetime

from app.config.settings import get_settings
from app.database.async_db import get_async_db_context
from app.services.knowledge_service import KnowledgeService

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()


# Initial knowledge base data for Excelencia ERP
INITIAL_KNOWLEDGE = [
    # Mission, Vision, Values
    {
        "title": "Misión y Visión de Excelencia ERP",
        "content": """# Misión

Nuestra misión es proporcionar soluciones tecnológicas innovadoras y confiables que permitan a las organizaciones de 
salud y hotelería optimizar sus procesos operativos, mejorar la calidad de atención a sus clientes y pacientes, y 
alcanzar la excelencia en la gestión.

Nos comprometemos a:
- Desarrollar software de alta calidad adaptado a las necesidades específicas de cada sector
- Brindar soporte técnico continuo y capacitación personalizada
- Innovar constantemente para mantenernos a la vanguardia tecnológica
- Construir relaciones de largo plazo basadas en la confianza y el profesionalismo

# Visión

Ser reconocidos como el proveedor líder de sistemas de gestión ERP para el sector salud y hotelería en América Latina, 
    destacándonos por:
- La calidad y robustez de nuestras soluciones tecnológicas
- El compromiso con la innovación y la mejora continua
- La excelencia en el servicio al cliente
- La contribución al desarrollo y modernización de nuestros sectores objetivo

# Valores Corporativos

**Excelencia**: Nos esforzamos por la calidad en cada aspecto de nuestro trabajo, desde el desarrollo de software hasta 
    el servicio al cliente.

**Innovación**: Buscamos constantemente nuevas formas de mejorar nuestros productos y servicios, manteniéndonos 
    a la vanguardia tecnológica.

**Compromiso**: Estamos comprometidos con el éxito de nuestros clientes y trabajamos como socios estratégicos en 
    su crecimiento.

**Integridad**: Actuamos con honestidad, transparencia y ética profesional en todas nuestras relaciones comerciales.

**Colaboración**: Fomentamos el trabajo en equipo y la comunicación efectiva, tanto internamente como con nuestros 
    clientes y partners.""",
        "document_type": "mission_vision",
        "category": "valores_corporativos",
        "tags": ["misión", "visión", "valores", "corporativo", "empresa"],
        "metadata": {"author": "Excelencia Team", "version": "1.0", "created": datetime.now().isoformat()},
        "active": True,
        "sort_order": 0,
    },
    # Contact Information
    {
        "title": "Información de Contacto y Redes Sociales",
        "content": """# Contacto Excelencia ERP

## Datos de Contacto Principal
- **Email**: info@excelenciaerp.com
- **Email Comercial**: ventas@excelenciaerp.com
- **Email Soporte**: soporte@excelenciaerp.com
- **Teléfono**: +54 11 1234-5678
- **WhatsApp**: +54 9 11 1234-5678

## Oficinas
**Oficina Central**:
Av. Corrientes 1234, Piso 5
C1043AAZ - Ciudad Autónoma de Buenos Aires
Argentina

**Horario de Atención**:
Lunes a Viernes: 9:00 - 18:00 hs (GMT-3)

## Redes Sociales
- **LinkedIn**: linkedin.com/company/excelencia-erp
- **Facebook**: facebook.com/excelenciaerp
- **Twitter**: @ExcelenciaERP
- **Instagram**: @excelencia.erp
- **YouTube**: youtube.com/c/ExcelenciaERP

## Sitio Web
- **Web Principal**: www.excelenciaerp.com
- **Portal de Clientes**: clientes.excelenciaerp.com
- **Centro de Ayuda**: ayuda.excelenciaerp.com
- **Blog**: blog.excelenciaerp.com

## Solicitar Demo
Para solicitar una demostración personalizada, puede:
- Completar el formulario en: www.excelenciaerp.com/demo
- Enviar email a: ventas@excelenciaerp.com
- Llamar al: +54 11 1234-5678
- Contactarnos por WhatsApp: +54 9 11 1234-5678""",
        "document_type": "contact_info",
        "category": "contacto",
        "tags": ["contacto", "email", "teléfono", "redes sociales", "oficina", "demo"],
        "metadata": {"author": "Excelencia Team", "version": "1.0"},
        "active": True,
        "sort_order": 1,
    },
    # Software Catalog - Health Sector
    {
        "title": "Historia Clínica Electrónica - Software de Gestión Médica",
        "content": """# Historia Clínica Electrónica

Sistema completo de gestión de historias clínicas digitales con cumplimiento normativo y seguridad certificada.

## Características Principales

**Registro de Pacientes**:
- Ficha completa del paciente con datos personales, obra social, y contacto
- Gestión de autorizaciones y credenciales
- Historial médico unificado
- Alertas de alergias y condiciones especiales

**Consultas Médicas**:
- Registro digital de consultas con plantillas personalizables
- Soporte para múltiples especialidades
- Adjuntar estudios, imágenes y documentos
- Firma digital del profesional

**Prescripciones y Recetas**:
- Emisión de recetas digitales
- Validación de interacciones medicamentosas
- Integración con farmacias
- Trazabilidad de medicamentos psicotrópicos

**Informes y Estadísticas**:
- Generación automática de informes médicos
- Estadísticas de consultas por especialidad
- Métricas de calidad de atención
- Cumplimiento de protocolos

**Cumplimiento Normativo**:
- Cumplimiento de Ley 26.529 (Derechos del Paciente)
- Certificación de firma digital
- Encriptación de datos sensibles
- Auditoría completa de accesos

## Beneficios
- Reducción de errores médicos
- Acceso rápido al historial del paciente
- Mejora en la toma de decisiones clínicas
- Ahorro de espacio físico
- Cumplimiento legal garantizado

## Ideal Para
Hospitales, clínicas, centros médicos, consultorios particulares, sanatorios.""",
        "document_type": "software_catalog",
        "category": "salud",
        "tags": ["historia clínica", "salud", "hospitales", "médico", "software"],
        "metadata": {"sector": "salud", "module": "historia_clinica"},
        "active": True,
        "sort_order": 10,
    },
    # FAQs
    {
        "title": "Preguntas Frecuentes sobre Demos y Presentaciones",
        "content": """# Preguntas Frecuentes - Demos

## ¿Cómo puedo solicitar una demo?

Puede solicitar una demostración de varias formas:
1. Completando el formulario en www.excelenciaerp.com/demo
2. Enviando un email a ventas@excelenciaerp.com
3. Llamando al +54 11 1234-5678
4. Por WhatsApp al +54 9 11 1234-5678

## ¿Cuánto dura una demo?

Las demos personalizadas duran aproximadamente 60-90 minutos, dependiendo de los módulos de interés y las preguntas que
    surjan.

## ¿La demo es gratuita?

Sí, todas nuestras demostraciones son completamente gratuitas y sin compromiso.

## ¿Puedo solicitar una demo de módulos específicos?

Absolutamente. Personalizamos cada demo según los módulos e industria de interés (Salud, Hoteles, Farmacias, etc.).

## ¿La demo es presencial o virtual?

Ofrecemos ambas modalidades:
- **Virtual**: Por videollamada (Google Meet, Zoom, Teams)
- **Presencial**: En nuestras oficinas o en sus instalaciones (AMBA)

## ¿Cuánto tiempo tarda en agendarse una demo?

Generalmente programamos demos dentro de las 48-72 horas hábiles siguientes a la solicitud.

## ¿Qué necesito para la demo virtual?

Solo necesita:
- Conexión a internet estable
- Navegador web actualizado
- (Opcional) Cámara y micrófono para mejor interacción

## ¿Puedo invitar a mi equipo a la demo?

¡Por supuesto! Recomendamos que participen todos los stakeholders relevantes: dirección, IT, usuarios finales, etc.""",
        "document_type": "faq",
        "category": "demos",
        "tags": ["demo", "preguntas frecuentes", "faq", "presentación"],
        "metadata": {"topic": "demos_presentation"},
        "active": True,
        "sort_order": 20,
    },
    {
        "title": "Preguntas Frecuentes sobre Precios e Implementación",
        "content": """# Preguntas Frecuentes - Precios e Implementación

## ¿Cuál es el costo de Excelencia ERP?

El precio varía según:
- Módulos seleccionados
- Cantidad de usuarios
- Volumen de transacciones
- Servicios adicionales (capacitación, personalización)

Contáctenos para obtener una cotización personalizada: ventas@excelenciaerp.com

## ¿Qué modelo de licenciamiento ofrecen?

Ofrecemos dos modalidades:
1. **Licencia perpetua**: Pago único + mantenimiento anual
2. **SaaS (Cloud)**: Suscripción mensual/anual todo incluido

## ¿Cuánto tiempo lleva la implementación?

Los tiempos típicos son:
- **Consultorio pequeño**: 1-2 semanas
- **Clínica mediana**: 1-2 meses
- **Hospital grande**: 3-6 meses

## ¿Qué incluye la implementación?

- Instalación y configuración del sistema
- Migración de datos desde sistema anterior
- Capacitación de usuarios
- Acompañamiento en puesta en marcha
- Soporte post-implementación

## ¿Ofrecen capacitación?

Sí, incluimos:
- Capacitación inicial personalizada
- Material didáctico y manuales
- Videos tutoriales
- Sesiones de refuerzo
- Soporte permanente

## ¿Qué soporte técnico brindan?

Nuestro soporte incluye:
- Mesa de ayuda telefónica y por email
- Asistencia remota
- Actualizaciones automáticas
- Mantenimiento preventivo
- SLA según plan contratado

## ¿El sistema funciona sin internet?

Depende de la modalidad:
- **Cloud (SaaS)**: Requiere internet
- **On-premise**: Funciona en red local sin internet

## ¿Puedo probar el sistema antes de comprar?

Sí, ofrecemos:
- Demos gratuitas personalizadas
- Período de prueba (según disponibilidad)
- Ambiente de testing para validaciones""",
        "document_type": "faq",
        "category": "comercial",
        "tags": ["precios", "costo", "implementación", "faq", "licencia", "soporte"],
        "metadata": {"topic": "pricing_implementation"},
        "active": True,
        "sort_order": 21,
    },
    # Success Stories
    {
        "title": "Caso de Éxito: Hospital Central - Implementación HCE",
        "content": """# Caso de Éxito: Hospital Central

## Cliente
Hospital Central - 200 camas - Buenos Aires, Argentina

## Desafío
El Hospital Central operaba con historias clínicas en papel, generando:
- Dificultad para acceder a información de pacientes
- Pérdida de documentación
- Errores en prescripciones
- Demoras en atención
- Problemas de cumplimiento normativo

## Solución Implementada
- Historia Clínica Electrónica completa
- Sistema de Turnos Médicos integrado
- Gestión de Internación
- Farmacia digital

## Resultados Obtenidos

**Mejora en Eficiencia**:
- 40% reducción en tiempo de búsqueda de historias clínicas
- 30% aumento en cantidad de consultas diarias
- Eliminación de pérdida de documentación

**Calidad de Atención**:
- 60% reducción de errores de prescripción
- Acceso inmediato al historial completo del paciente
- Mejora en toma de decisiones clínicas

**Cumplimiento Normativo**:
- 100% cumplimiento de Ley 26.529
- Auditoría completa de accesos
- Seguridad certificada de datos

**ROI**:
- Retorno de inversión en 18 meses
- Ahorro anual de $500,000 en papel y archivo
- Reducción de 2 FTE en tareas administrativas

## Testimonio
"La implementación de Excelencia ERP transformó completamente nuestra operación. Ahora podemos brindar una atención más
    rápida y segura a nuestros pacientes." - Dr. Carlos Méndez, Director Médico""",
        "document_type": "success_stories",
        "category": "salud",
        "tags": ["caso de éxito", "hospital", "HCE", "implementación", "resultados"],
        "metadata": {"client": "Hospital Central", "sector": "salud", "year": "2024"},
        "active": True,
        "sort_order": 30,
    },
]


async def seed_knowledge_base():
    """Seed the knowledge base with initial Excelencia ERP information."""
    logger.info("=" * 80)
    logger.info("Starting knowledge base seeding process")
    logger.info("=" * 80)

    try:
        async with get_async_db_context() as db:
            service = KnowledgeService(db)

            # Get current statistics
            stats_before = await service.get_statistics()
            logger.info("\nCurrent statistics:")
            logger.info(f"  Total active documents: {stats_before['database']['total_active']}")
            logger.info(f"  Embedding coverage: {stats_before['database']['embedding_coverage']:.1f}%")

            # Insert initial knowledge
            success_count = 0
            error_count = 0

            for i, knowledge_data in enumerate(INITIAL_KNOWLEDGE, 1):
                try:
                    logger.info(f"\n[{i}/{len(INITIAL_KNOWLEDGE)}] Creating: {knowledge_data['title']}")

                    # Create document with automatic embedding generation
                    result = await service.create_knowledge(
                        knowledge_data=knowledge_data,
                        auto_embed=True,  # Generate embeddings automatically
                    )

                    logger.info(f"  ✓ Created successfully (ID: {result['id']})")
                    logger.info(f"  Embedding generated: {result['has_embedding']}")
                    success_count += 1

                except Exception as e:
                    logger.error(f"  ✗ Error creating document: {e}")
                    error_count += 1

            # Get final statistics
            stats_after = await service.get_statistics()

            logger.info("\n" + "=" * 80)
            logger.info("Seeding process completed")
            logger.info("=" * 80)
            logger.info("\nResults:")
            logger.info(f"  ✓ Successfully created: {success_count}")
            logger.info(f"  ✗ Errors: {error_count}")
            logger.info("\nFinal statistics:")
            logger.info(f"  Total active documents: {stats_after['database']['total_active']}")
            logger.info(f"  Embedding coverage: {stats_after['database']['embedding_coverage']:.1f}%")
            logger.info(f"  Embedding model: {stats_after['embedding_model']}")

            # Show ChromaDB statistics
            logger.info("\nChromaDB collections:")
            for collection, count in stats_after["chromadb_collections"].items():
                logger.info(f"  {collection}: {count} documents")

            logger.info("\n✅ Knowledge base seeding completed successfully!")

    except Exception as e:
        logger.error(f"\n❌ Error seeding knowledge base: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    # Run the seeding process
    asyncio.run(seed_knowledge_base())
