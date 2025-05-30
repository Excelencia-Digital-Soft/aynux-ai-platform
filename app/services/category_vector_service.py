import logging
from typing import Optional, List, Dict, Any
from langchain_community.embeddings import OllamaEmbeddings
from app.models.chatbot import Message
from app.services.ai_service import AIService

logger = logging.getLogger(__name__)

class CategoryVectorService:
    def __init__(self):
        self.ai_service = AIService()
        self.embeddings = OllamaEmbeddings(
            model="nomic-embed-text",
            base_url="http://localhost:11434"
        )
        
        # Define category mappings
        self.category_keywords = {
            "laptops": ["laptop", "notebook", "portátil", "macbook", "thinkpad", "pavilion", "ideapad"],
            "desktops": ["desktop", "pc", "computadora", "escritorio", "torre", "cpu"],
            "components": ["componente", "procesador", "cpu", "gpu", "tarjeta gráfica", "ram", "memoria", "disco", "ssd", "hdd", "fuente", "motherboard", "placa madre"],
            "peripherals": ["periférico", "mouse", "ratón", "teclado", "keyboard", "monitor", "pantalla", "audífonos", "headset", "webcam", "cámara"]
        }
        
        # Subcategory mappings
        self.subcategory_keywords = {
            "gaming": ["gaming", "gamer", "juegos", "fps", "rgb", "alta performance", "alto rendimiento"],
            "work": ["trabajo", "oficina", "profesional", "business", "empresarial"],
            "budget": ["económico", "barato", "básico", "entrada", "estudiante", "budget"]
        }
    
    async def determine_search_category(self, user_message: str, conversation_history: List[Message]) -> Dict[str, Any]:
        """Determine which category to search based on user message and context"""
        
        # Build context from conversation history
        context = "\n".join([f"{msg.role}: {msg.content}" for msg in conversation_history[-5:]])
        
        prompt = f"""Analiza el siguiente mensaje del usuario y el contexto de la conversación para determinar qué categoría de productos está buscando.

Contexto de conversación:
{context}

Mensaje actual del usuario: {user_message}

Categorías disponibles:
- laptops: Computadoras portátiles, notebooks
- desktops: Computadoras de escritorio, PCs de torre
- components: Componentes de computadora (CPU, GPU, RAM, discos, etc.)
- peripherals: Periféricos (mouse, teclado, monitor, audífonos, etc.)
- all_products: Buscar en todos los productos

Subcategorías (opcional):
- gaming: Productos para gaming/juegos
- work: Productos para trabajo/oficina
- budget: Productos económicos

Responde ÚNICAMENTE con un JSON en el siguiente formato:
{{
    "category": "nombre_categoria",
    "subcategory": "nombre_subcategoria o null",
    "confidence": 0.95,
    "reasoning": "breve explicación"
}}

Si no puedes determinar una categoría específica con confianza, usa "all_products".
"""
        
        try:
            response = await self.ai_service.generate_response(prompt, temperature=0.1)
            
            # Parse JSON response
            import json
            result = json.loads(response.strip())
            
            # Validate response
            if "category" not in result:
                result = {
                    "category": "all_products",
                    "subcategory": None,
                    "confidence": 0.5,
                    "reasoning": "No se pudo determinar categoría específica"
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Error determining search category: {str(e)}")
            
            # Fallback to keyword matching
            return self._fallback_category_detection(user_message)
    
    def _fallback_category_detection(self, message: str) -> Dict[str, Any]:
        """Fallback method using keyword matching"""
        message_lower = message.lower()
        
        # Check main categories
        for category, keywords in self.category_keywords.items():
            for keyword in keywords:
                if keyword in message_lower:
                    # Check subcategories
                    subcategory = None
                    for subcat, subkeywords in self.subcategory_keywords.items():
                        for subkeyword in subkeywords:
                            if subkeyword in message_lower:
                                subcategory = subcat
                                break
                    
                    return {
                        "category": category,
                        "subcategory": subcategory,
                        "confidence": 0.8,
                        "reasoning": f"Detectado por palabra clave: {keyword}"
                    }
        
        # Default to all products
        return {
            "category": "all_products",
            "subcategory": None,
            "confidence": 0.5,
            "reasoning": "No se detectó categoría específica"
        }
    
    async def enhance_search_query(self, user_message: str, category: str) -> str:
        """Enhance the search query based on category context"""
        
        prompt = f"""Mejora la siguiente consulta de búsqueda para la categoría '{category}'.
Expande la consulta con sinónimos y términos relacionados relevantes para mejorar la búsqueda semántica.

Consulta original: {user_message}
Categoría: {category}

Responde SOLO con la consulta mejorada, sin explicaciones adicionales.
La consulta debe ser natural y enfocada en encontrar productos relevantes.
"""
        
        try:
            enhanced_query = await self.ai_service.generate_response(prompt, temperature=0.3)
            return enhanced_query.strip()
        except Exception as e:
            logger.error(f"Error enhancing search query: {str(e)}")
            return user_message