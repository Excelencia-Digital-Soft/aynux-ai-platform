# Sistema Multi-Agente con LangGraph para E-commerce

## 1. Arquitectura del Sistema

### Diagrama de Flujo Principal

```mermaid
graph TB
    %% Entrada del usuario
    U[Usuario] -->|Mensaje| WA[WhatsApp/API Gateway]
    WA --> SG[StateGraph Principal]
    
    %% Estado compartido
    SG --> SS[Shared State]
    
    %% Supervisor
    SS --> SUP[Supervisor Agent]
    SUP -->|Analiza intención| IR[Intent Router]
    
    %% Routing a agentes especializados
    IR -->|categoría| CA[Category Agent]
    IR -->|producto| PA[Product Agent]
    IR -->|promoción| PRA[Promotions Agent]
    IR -->|rastreo| TA[Tracking Agent]
    IR -->|soporte| SA[Support Agent]
    IR -->|factura| IA[Invoice Agent]
    
    %% Herramientas de cada agente
    CA --> CT[Category Tools]
    PA --> PT[Product Tools]
    PRA --> PRT[Promo Tools]
    TA --> TT[Tracking Tools]
    SA --> ST[Support Tools]
    IA --> IT[Invoice Tools]
    
    %% Bases de datos
    CT --> CDB[(ChromaDB)]
    PT --> PG[(PostgreSQL)]
    PT --> CDB
    PRT --> PG
    TT --> API1[Shipping APIs]
    SA --> CDB
    IA --> API2[Invoice APIs]
    
    %% Respuesta
    CA --> RG[Response Generator]
    PA --> RG
    PRA --> RG
    TA --> RG
    SA --> RG
    IA --> RG
    
    RG --> WA
    WA --> U
    
    %% Monitoreo
    SG -.-> LS[LangSmith]
    SG -.-> CP[Checkpointing]
    CP --> PG
```

### Arquitectura de Componentes

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Gateway Layer                         │
├─────────────────────────────────────────────────────────────────┤
│                    LangGraph StateGraph Core                     │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐    │
│  │  Supervisor  │  │Intent Router │  │Response Generator │    │
│  │    Agent     │  │              │  │                   │    │
│  └──────────────┘  └──────────────┘  └───────────────────┘    │
├─────────────────────────────────────────────────────────────────┤
│                    Specialized Agents Layer                      │
│  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌─────────┐ ┌─────────┐ │
│  │Category │ │Product  │ │Promotions│ │Tracking │ │Support  │ │
│  │ Agent   │ │ Agent   │ │  Agent   │ │  Agent  │ │  Agent  │ │
│  └─────────┘ └─────────┘ └──────────┘ └─────────┘ └─────────┘ │
│                        ┌─────────┐                              │
│                        │Invoice  │                              │
│                        │ Agent   │                              │
│                        └─────────┘                              │
├─────────────────────────────────────────────────────────────────┤
│                     Integration Layer                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │  Ollama  │  │ ChromaDB │  │PostgreSQL│  │External APIs │   │
│  │(LLM)     │  │(Vectors) │  │(Data)    │  │(Ship/Invoice)│   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## 2. Esquema de Estado Compartido

```python
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field
from langgraph.graph import MessagesState

class CustomerContext(BaseModel):
    """Contexto del cliente"""
    customer_id: str
    name: str
    email: Optional[str] = None
    phone: str
    tier: Literal["basic", "premium", "vip"] = "basic"
    purchase_history: List[Dict[str, Any]] = Field(default_factory=list)
    preferences: Dict[str, Any] = Field(default_factory=dict)

class ConversationContext(BaseModel):
    """Contexto de la conversación"""
    conversation_id: str
    session_id: str
    channel: Literal["whatsapp", "web", "api"] = "whatsapp"
    language: str = "es"
    timezone: str = "America/Buenos_Aires"

class IntentInfo(BaseModel):
    """Información de intención detectada"""
    primary_intent: str
    confidence: float
    entities: Dict[str, Any] = Field(default_factory=dict)
    requires_handoff: bool = False
    target_agent: Optional[str] = None

class AgentResponse(BaseModel):
    """Respuesta de un agente"""
    agent_name: str
    response_text: str
    data_retrieved: Dict[str, Any] = Field(default_factory=dict)
    tools_used: List[str] = Field(default_factory=list)
    success: bool = True
    error: Optional[str] = None

class SharedState(MessagesState):
    """Estado compartido entre todos los agentes"""
    # Contextos
    customer: CustomerContext
    conversation: ConversationContext
    
    # Intención y routing
    current_intent: Optional[IntentInfo] = None
    intent_history: List[IntentInfo] = Field(default_factory=list)
    
    # Estado del flujo
    current_agent: Optional[str] = None
    agent_history: List[str] = Field(default_factory=list)
    
    # Respuestas y datos
    agent_responses: List[AgentResponse] = Field(default_factory=list)
    retrieved_data: Dict[str, Any] = Field(default_factory=dict)
    
    # Control de flujo
    requires_human: bool = False
    is_complete: bool = False
    error_count: int = 0
    
    # Metadatos
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    checkpoint_id: Optional[str] = None
    
    # Cache y optimización
    cache_keys: List[str] = Field(default_factory=list)
    
    def add_agent_response(self, response: AgentResponse):
        """Añade una respuesta de agente al estado"""
        self.agent_responses.append(response)
        self.updated_at = datetime.now()
    
    def update_intent(self, intent: IntentInfo):
        """Actualiza la intención actual"""
        if self.current_intent:
            self.intent_history.append(self.current_intent)
        self.current_intent = intent
        self.updated_at = datetime.now()
    
    def get_context_summary(self) -> Dict[str, Any]:
        """Obtiene un resumen del contexto actual"""
        return {
            "customer_id": self.customer.customer_id,
            "conversation_id": self.conversation.conversation_id,
            "current_intent": self.current_intent.primary_intent if self.current_intent else None,
            "current_agent": self.current_agent,
            "message_count": len(self.messages),
            "error_count": self.error_count,
            "is_complete": self.is_complete
        }
```

## 3. Sistema de Routing e Interpretación de Intenciones

```python
from typing import Dict, Tuple, Optional
from langgraph.prebuilt import ToolExecutor
from langchain_core.messages import HumanMessage, AIMessage
import re

class IntentRouter:
    """Router inteligente para dirigir a los agentes correctos"""
    
    def __init__(self, llm):
        self.llm = llm
        self.intent_patterns = {
            "category_browsing": [
                r"mostrar.*categor",
                r"ver.*productos",
                r"qué.*venden",
                r"explorar.*tienda"
            ],
            "product_inquiry": [
                r"precio.*producto",
                r"característic.*",
                r"especificacion.*",
                r"stock.*",
                r"disponib.*"
            ],
            "promotions": [
                r"oferta.*",
                r"descuento.*",
                r"promocion.*",
                r"rebaja.*"
            ],
            "order_tracking": [
                r"dónde.*pedido",
                r"rastrear.*",
                r"estado.*envío",
                r"tracking.*"
            ],
            "technical_support": [
                r"no.*funciona",
                r"problema.*",
                r"ayuda.*técnica",
                r"soporte.*"
            ],
            "invoice_request": [
                r"factura.*",
                r"comprobante.*",
                r"recibo.*"
            ]
        }
        
        self.agent_mapping = {
            "category_browsing": "category_agent",
            "product_inquiry": "product_agent",
            "promotions": "promotions_agent",
            "order_tracking": "tracking_agent",
            "technical_support": "support_agent",
            "invoice_request": "invoice_agent"
        }
    
    async def analyze_intent(self, state: SharedState) -> IntentInfo:
        """Analiza la intención usando LLM y patrones"""
        last_message = state.messages[-1].content if state.messages else ""
        
        # Primero intentar con patrones regex
        intent = self._pattern_matching(last_message)
        
        if intent:
            confidence = 0.85
        else:
            # Si no hay match, usar LLM
            intent, confidence = await self._llm_intent_detection(
                last_message, 
                state.get_context_summary()
            )
        
        # Extraer entidades
        entities = await self._extract_entities(last_message, intent)
        
        # Determinar si requiere handoff
        requires_handoff = self._check_handoff_requirement(
            intent, 
            confidence, 
            state.error_count
        )
        
        return IntentInfo(
            primary_intent=intent or "general_inquiry",
            confidence=confidence,
            entities=entities,
            requires_handoff=requires_handoff,
            target_agent=self.agent_mapping.get(intent)
        )
    
    def _pattern_matching(self, text: str) -> Optional[str]:
        """Detección rápida basada en patrones"""
        text_lower = text.lower()
        
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return intent
        
        return None
    
    async def _llm_intent_detection(
        self, 
        message: str, 
        context: Dict
    ) -> Tuple[str, float]:
        """Detección de intención usando LLM"""
        prompt = f"""
        Analiza el siguiente mensaje y clasifícalo en una de estas intenciones:
        - category_browsing: explorar categorías o productos en general
        - product_inquiry: consultas sobre productos específicos
        - promotions: búsqueda de ofertas o descuentos
        - order_tracking: rastreo de pedidos
        - technical_support: problemas técnicos o soporte
        - invoice_request: solicitud de facturas
        - general_inquiry: consultas generales
        
        Mensaje: {message}
        Contexto: {context}
        
        Responde en formato JSON:
        {{
            "intent": "nombre_de_intención",
            "confidence": 0.95
        }}
        """
        
        response = await self.llm.ainvoke(prompt)
        # Parsear respuesta
        # ... lógica de parsing ...
        
        return "general_inquiry", 0.5
    
    async def _extract_entities(
        self, 
        message: str, 
        intent: str
    ) -> Dict[str, Any]:
        """Extrae entidades relevantes del mensaje"""
        entities = {}
        
        # Extraer números de pedido
        order_pattern = r"#?\d{6,}"
        order_matches = re.findall(order_pattern, message)
        if order_matches:
            entities["order_numbers"] = order_matches
        
        # Extraer productos mencionados
        # ... más lógica de extracción ...
        
        return entities
    
    def _check_handoff_requirement(
        self, 
        intent: str, 
        confidence: float, 
        error_count: int
    ) -> bool:
        """Determina si se requiere transferencia a humano"""
        if error_count >= 3:
            return True
        
        if confidence < 0.6:
            return True
        
        if intent in ["complex_complaint", "legal_issue"]:
            return True
        
        return False

class SupervisorAgent:
    """Agente supervisor que coordina el flujo"""
    
    def __init__(self, router: IntentRouter):
        self.router = router
    
    async def process(self, state: SharedState) -> SharedState:
        """Procesa el estado y determina el siguiente paso"""
        # Analizar intención
        intent_info = await self.router.analyze_intent(state)
        state.update_intent(intent_info)
        
        # Determinar siguiente agente
        if intent_info.requires_handoff:
            state.requires_human = True
            state.current_agent = "human_agent"
        else:
            state.current_agent = intent_info.target_agent or "general_agent"
        
        # Actualizar historial
        state.agent_history.append(state.current_agent)
        
        return state
```

## 4. Especificación de Agentes Especializados

### 4.1 Category Agent

```python
class CategoryAgent:
    """Agente especializado en navegación de categorías"""
    
    def __init__(self, vector_store, llm):
        self.vector_store = vector_store  # ChromaDB
        self.llm = llm
        self.tools = [
            CategorySearchTool(vector_store),
            CategoryHierarchyTool(),
            ProductCountTool()
        ]
    
    async def process(self, state: SharedState) -> SharedState:
        """Procesa consultas de categorías"""
        try:
            # Extraer query del último mensaje
            query = state.messages[-1].content
            
            # Buscar categorías relevantes
            categories = await self.tools[0].search_categories(
                query, 
                limit=5
            )
            
            # Generar respuesta
            response_text = await self._generate_category_response(
                categories, 
                state.customer.preferences
            )
            
            # Crear respuesta del agente
            agent_response = AgentResponse(
                agent_name="category_agent",
                response_text=response_text,
                data_retrieved={"categories": categories},
                tools_used=["CategorySearchTool"],
                success=True
            )
            
            state.add_agent_response(agent_response)
            
        except Exception as e:
            state.error_count += 1
            agent_response = AgentResponse(
                agent_name="category_agent",
                response_text="Lo siento, tuve un problema al buscar categorías.",
                success=False,
                error=str(e)
            )
            state.add_agent_response(agent_response)
        
        return state
    
    async def _generate_category_response(
        self, 
        categories: List[Dict], 
        preferences: Dict
    ) -> str:
        """Genera respuesta personalizada de categorías"""
        # Lógica de generación...
        pass

# Herramientas del Category Agent
class CategorySearchTool:
    """Busca categorías en ChromaDB"""
    def __init__(self, vector_store):
        self.vector_store = vector_store
    
    async def search_categories(self, query: str, limit: int = 5):
        results = await self.vector_store.similarity_search(
            query,
            filter={"type": "category"},
            k=limit
        )
        return results

class CategoryHierarchyTool:
    """Navega la jerarquía de categorías"""
    async def get_subcategories(self, parent_id: str):
        # Lógica para obtener subcategorías
        pass

class ProductCountTool:
    """Cuenta productos por categoría"""
    async def count_products(self, category_id: str):
        # Lógica para contar productos
        pass
```

### 4.2 Product Agent

```python
class ProductAgent:
    """Agente especializado en consultas de productos"""
    
    def __init__(self, vector_store, db_connection, llm):
        self.vector_store = vector_store
        self.db = db_connection  # PostgreSQL
        self.llm = llm
        self.tools = [
            ProductSearchTool(vector_store),
            StockVerificationTool(db_connection),
            PriceCalculatorTool(),
            ProductComparisonTool()
        ]
    
    async def process(self, state: SharedState) -> SharedState:
        """Procesa consultas de productos específicos"""
        try:
            query = state.messages[-1].content
            entities = state.current_intent.entities
            
            # Buscar productos
            products = await self._search_products(query, entities)
            
            # Verificar stock en tiempo real
            for product in products:
                stock_info = await self.tools[1].check_stock(product['id'])
                product['stock'] = stock_info
            
            # Calcular precios personalizados
            prices = await self._calculate_prices(
                products, 
                state.customer.tier
            )
            
            # Generar respuesta
            response_text = await self._generate_product_response(
                products, 
                prices, 
                state.customer
            )
            
            agent_response = AgentResponse(
                agent_name="product_agent",
                response_text=response_text,
                data_retrieved={
                    "products": products,
                    "prices": prices
                },
                tools_used=[
                    "ProductSearchTool", 
                    "StockVerificationTool", 
                    "PriceCalculatorTool"
                ],
                success=True
            )
            
            state.add_agent_response(agent_response)
            
        except Exception as e:
            state.error_count += 1
            # Manejo de error...
        
        return state
    
    async def _search_products(self, query: str, entities: Dict):
        """Busca productos usando múltiples estrategias"""
        # Búsqueda semántica
        semantic_results = await self.tools[0].semantic_search(query)
        
        # Búsqueda por atributos si hay entidades
        if entities.get("product_attributes"):
            attribute_results = await self.tools[0].attribute_search(
                entities["product_attributes"]
            )
            # Combinar resultados
        
        return semantic_results
```

### 4.3 Promotions Agent

```python
class PromotionsAgent:
    """Agente especializado en promociones y descuentos"""
    
    def __init__(self, db_connection, cache_service, llm):
        self.db = db_connection
        self.cache = cache_service
        self.llm = llm
        self.tools = [
            ActivePromotionsTool(db_connection),
            PersonalizedOffersTool(),
            PromotionEligibilityTool(),
            CouponGeneratorTool()
        ]
    
    async def process(self, state: SharedState) -> SharedState:
        """Procesa consultas sobre promociones"""
        try:
            # Verificar caché primero
            cache_key = f"promos_{state.customer.customer_id}"
            cached_promos = await self.cache.get(cache_key)
            
            if not cached_promos:
                # Obtener promociones activas
                active_promos = await self.tools[0].get_active_promotions()
                
                # Filtrar por elegibilidad del cliente
                eligible_promos = await self._filter_eligible_promotions(
                    active_promos,
                    state.customer
                )
                
                # Cachear por 1 hora
                await self.cache.set(cache_key, eligible_promos, ttl=3600)
            else:
                eligible_promos = cached_promos
            
            # Generar ofertas personalizadas
            personalized = await self.tools[1].generate_personalized_offers(
                state.customer,
                eligible_promos
            )
            
            # Crear respuesta
            response_text = await self._format_promotions_response(
                personalized,
                state.customer.preferences.get("communication_style", "formal")
            )
            
            agent_response = AgentResponse(
                agent_name="promotions_agent",
                response_text=response_text,
                data_retrieved={
                    "promotions": eligible_promos,
                    "personalized_offers": personalized
                },
                tools_used=["ActivePromotionsTool", "PersonalizedOffersTool"],
                success=True
            )
            
            state.add_agent_response(agent_response)
            
        except Exception as e:
            state.error_count += 1
            # Manejo de error...
        
        return state
```

### 4.4 Tracking Agent

```python
class TrackingAgent:
    """Agente especializado en rastreo de pedidos"""
    
    def __init__(self, db_connection, shipping_apis, llm):
        self.db = db_connection
        self.shipping_apis = shipping_apis  # APIs externas
        self.llm = llm
        self.tools = [
            OrderLookupTool(db_connection),
            ShippingTrackingTool(shipping_apis),
            DeliveryEstimationTool(),
            TrackingNotificationTool()
        ]
    
    async def process(self, state: SharedState) -> SharedState:
        """Procesa consultas de rastreo"""
        try:
            entities = state.current_intent.entities
            
            # Buscar números de orden
            order_numbers = entities.get("order_numbers", [])
            
            if not order_numbers:
                # Buscar órdenes recientes del cliente
                recent_orders = await self.tools[0].get_recent_orders(
                    state.customer.customer_id
                )
            else:
                # Buscar órdenes específicas
                recent_orders = await self.tools[0].get_orders_by_number(
                    order_numbers
                )
            
            # Obtener información de tracking
            tracking_info = []
            for order in recent_orders:
                tracking = await self.tools[1].get_tracking_info(
                    order['tracking_number'],
                    order['carrier']
                )
                tracking_info.append({
                    "order": order,
                    "tracking": tracking
                })
            
            # Estimar entrega
            for info in tracking_info:
                estimation = await self.tools[2].estimate_delivery(
                    info['tracking']
                )
                info['estimated_delivery'] = estimation
            
            # Generar respuesta
            response_text = await self._generate_tracking_response(
                tracking_info
            )
            
            agent_response = AgentResponse(
                agent_name="tracking_agent",
                response_text=response_text,
                data_retrieved={"tracking_info": tracking_info},
                tools_used=[
                    "OrderLookupTool", 
                    "ShippingTrackingTool", 
                    "DeliveryEstimationTool"
                ],
                success=True
            )
            
            state.add_agent_response(agent_response)
            
        except Exception as e:
            state.error_count += 1
            # Manejo de error...
        
        return state
```

### 4.5 Support Agent

```python
class SupportAgent:
    """Agente de soporte técnico"""
    
    def __init__(self, vector_store, knowledge_base, llm):
        self.vector_store = vector_store
        self.kb = knowledge_base  # ChromaDB con documentación
        self.llm = llm
        self.tools = [
            TroubleshootingTool(knowledge_base),
            ProductManualTool(vector_store),
            FAQSearchTool(vector_store),
            TicketCreationTool()
        ]
    
    async def process(self, state: SharedState) -> SharedState:
        """Procesa consultas de soporte técnico"""
        try:
            query = state.messages[-1].content
            
            # Buscar en base de conocimiento
            kb_results = await self.tools[0].search_troubleshooting(query)
            
            # Buscar en FAQs
            faq_results = await self.tools[2].search_faqs(query)
            
            # Si no hay solución clara, preparar para crear ticket
            if not kb_results and not faq_results:
                ticket_data = await self._prepare_support_ticket(
                    state
                )
                
                response_text = await self._generate_escalation_response(
                    ticket_data
                )
            else:
                # Generar respuesta con soluciones
                response_text = await self._generate_solution_response(
                    kb_results,
                    faq_results
                )
            
            agent_response = AgentResponse(
                agent_name="support_agent",
                response_text=response_text,
                data_retrieved={
                    "kb_results": kb_results,
                    "faq_results": faq_results
                },
                tools_used=["TroubleshootingTool", "FAQSearchTool"],
                success=True
            )
            
            state.add_agent_response(agent_response)
            
        except Exception as e:
            state.error_count += 1
            # Manejo de error...
        
        return state
```

### 4.6 Invoice Agent

```python
class InvoiceAgent:
    """Agente de generación de facturas"""
    
    def __init__(self, db_connection, invoice_api, llm):
        self.db = db_connection
        self.invoice_api = invoice_api
        self.llm = llm
        self.tools = [
            InvoiceGeneratorTool(invoice_api),
            TaxCalculatorTool(),
            InvoiceValidatorTool(),
            InvoiceDeliveryTool()
        ]
    
    async def process(self, state: SharedState) -> SharedState:
        """Procesa solicitudes de facturas"""
        try:
            entities = state.current_intent.entities
            order_numbers = entities.get("order_numbers", [])
            
            # Buscar órdenes para facturar
            if not order_numbers:
                # Buscar órdenes sin factura
                orders = await self._get_unfactured_orders(
                    state.customer.customer_id
                )
            else:
                orders = await self._get_orders_by_number(order_numbers)
            
            # Generar facturas
            invoices = []
            for order in orders:
                # Calcular impuestos
                taxes = await self.tools[1].calculate_taxes(order)
                
                # Generar factura
                invoice = await self.tools[0].generate_invoice(
                    order,
                    taxes,
                    state.customer
                )
                
                # Validar factura
                is_valid = await self.tools[2].validate_invoice(invoice)
                
                if is_valid:
                    invoices.append(invoice)
                    
                    # Enviar factura
                    await self.tools[3].send_invoice(
                        invoice,
                        state.customer.email
                    )
            
            # Generar respuesta
            response_text = await self._generate_invoice_response(
                invoices
            )
            
            agent_response = AgentResponse(
                agent_name="invoice_agent",
                response_text=response_text,
                data_retrieved={"invoices": invoices},
                tools_used=[
                    "InvoiceGeneratorTool",
                    "TaxCalculatorTool",
                    "InvoiceValidatorTool",
                    "InvoiceDeliveryTool"
                ],
                success=True
            )
            
            state.add_agent_response(agent_response)
            
        except Exception as e:
            state.error_count += 1
            # Manejo de error...
        
        return state
```

## 5. Plan de Integración con Sistemas Externos

### 5.1 Integración con Ollama

```python
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

class OllamaIntegration:
    """Gestiona la integración con Ollama"""
    
    def __init__(self, model_name: str = "llama3.1:8b"):
        self.model_name = model_name
        self.base_url = "http://localhost:11434"
        
    def get_llm(self, temperature: float = 0.7):
        """Obtiene instancia del LLM"""
        return ChatOllama(
            model=self.model_name,
            base_url=self.base_url,
            temperature=temperature,
            num_gpu=1,
            num_thread=8,
            repeat_penalty=1.1,
            top_k=40,
            top_p=0.9
        )
    
    async def health_check(self) -> bool:
        """Verifica disponibilidad del servicio"""
        try:
            llm = self.get_llm()
            response = await llm.ainvoke("test")
            return True
        except Exception:
            return False
```

### 5.2 Integración con ChromaDB

```python
from chromadb import AsyncClient
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings

class ChromaDBIntegration:
    """Gestiona la integración con ChromaDB"""
    
    def __init__(self):
        self.client = AsyncClient()
        self.embeddings = OllamaEmbeddings(
            model="mxbai-embed-large",
            base_url="http://localhost:11434"
        )
    
    async def get_collection(self, name: str):
        """Obtiene o crea una colección"""
        try:
            collection = await self.client.get_collection(name)
        except:
            collection = await self.client.create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"}
            )
        return collection
    
    def get_vector_store(self, collection_name: str):
        """Obtiene el vector store para LangChain"""
        return Chroma(
            client=self.client,
            collection_name=collection_name,
            embedding_function=self.embeddings
        )
```

### 5.3 Integración con PostgreSQL y Checkpointing

```python
from langgraph.checkpoint.postgres import PostgresSaver
from sqlalchemy.ext.asyncio import create_async_engine
import asyncpg

class PostgreSQLIntegration:
    """Gestiona la integración con PostgreSQL"""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.engine = create_async_engine(
            connection_string,
            pool_size=20,
            max_overflow=30,
            pool_pre_ping=True
        )
    
    async def get_checkpointer(self):
        """Obtiene el checkpointer para LangGraph"""
        # Crear pool de conexiones para checkpointing
        pool = await asyncpg.create_pool(
            self.connection_string,
            min_size=5,
            max_size=10
        )
        
        return PostgresSaver(pool)
    
    async def init_checkpoint_tables(self):
        """Inicializa las tablas necesarias para checkpointing"""
        async with self.engine.begin() as conn:
            await conn.run_sync(PostgresSaver.create_tables)
```

### 5.4 APIs Externas

```python
class ExternalAPIsIntegration:
    """Gestiona integraciones con APIs externas"""
    
    def __init__(self):
        self.shipping_providers = {
            "fedex": FedExAPI(),
            "ups": UPSAPI(),
            "dhl": DHLAPI()
        }
        self.payment_providers = {
            "stripe": StripeAPI(),
            "mercadopago": MercadoPagoAPI()
        }
        self.invoice_provider = InvoiceAPI()
    
    async def track_shipment(self, tracking_number: str, carrier: str):
        """Rastrea un envío"""
        provider = self.shipping_providers.get(carrier.lower())
        if provider:
            return await provider.track(tracking_number)
        raise ValueError(f"Carrier {carrier} not supported")
    
    async def generate_invoice(self, order_data: dict):
        """Genera una factura"""
        return await self.invoice_provider.create_invoice(order_data)
```

## 6. Consideraciones de Escalabilidad y Monitoreo

### 6.1 Estrategia de Escalabilidad

```python
class ScalabilityManager:
    """Gestiona la escalabilidad del sistema"""
    
    def __init__(self):
        self.load_balancer = LoadBalancer()
        self.auto_scaler = AutoScaler()
        self.cache_manager = CacheManager()
    
    async def distribute_request(self, state: SharedState):
        """Distribuye requests entre instancias"""
        # Seleccionar instancia basada en carga
        instance = await self.load_balancer.select_instance(
            agent_type=state.current_agent,
            load_metrics=await self.get_load_metrics()
        )
        
        return instance
    
    async def scale_agents(self):
        """Escala agentes según demanda"""
        metrics = await self.get_system_metrics()
        
        for agent_type, metric in metrics.items():
            if metric['cpu'] > 80 or metric['response_time'] > 2000:
                await self.auto_scaler.scale_up(agent_type)
            elif metric['cpu'] < 20:
                await self.auto_scaler.scale_down(agent_type)

class CacheStrategy:
    """Estrategia de caché multinivel"""
    
    def __init__(self):
        self.l1_cache = InMemoryCache(max_size=1000)  # Local
        self.l2_cache = RedisCache()  # Distribuido
        self.l3_cache = PostgreSQLCache()  # Persistente
    
    async def get(self, key: str):
        """Busca en caché multinivel"""
        # L1 - Memoria local
        value = await self.l1_cache.get(key)
        if value:
            return value
        
        # L2 - Redis
        value = await self.l2_cache.get(key)
        if value:
            await self.l1_cache.set(key, value)
            return value
        
        # L3 - PostgreSQL
        value = await self.l3_cache.get(key)
        if value:
            await self.l2_cache.set(key, value)
            await self.l1_cache.set(key, value)
            return value
        
        return None
```

### 6.2 Sistema de Monitoreo

```python
from langsmith import Client
from opentelemetry import trace, metrics
import structlog

class MonitoringSystem:
    """Sistema completo de monitoreo"""
    
    def __init__(self):
        self.langsmith = Client()
        self.tracer = trace.get_tracer(__name__)
        self.meter = metrics.get_meter(__name__)
        self.logger = structlog.get_logger()
        
        # Métricas
        self.response_time = self.meter.create_histogram(
            "agent_response_time",
            description="Tiempo de respuesta por agente"
        )
        self.error_counter = self.meter.create_counter(
            "agent_errors",
            description="Errores por agente"
        )
        self.intent_counter = self.meter.create_counter(
            "intent_classifications",
            description="Clasificaciones de intención"
        )
    
    async def trace_agent_execution(self, agent_name: str, state: SharedState):
        """Traza la ejecución de un agente"""
        with self.tracer.start_as_current_span(f"agent_{agent_name}") as span:
            span.set_attribute("agent.name", agent_name)
            span.set_attribute("conversation.id", state.conversation.conversation_id)
            span.set_attribute("customer.id", state.customer.customer_id)
            
            # Log estructurado
            self.logger.info(
                "agent_execution_started",
                agent=agent_name,
                conversation_id=state.conversation.conversation_id,
                intent=state.current_intent.primary_intent if state.current_intent else None
            )
            
            # Enviar a LangSmith
            await self.langsmith.log_run(
                name=f"agent_{agent_name}",
                inputs={"state": state.dict()},
                run_type="agent"
            )
    
    def record_metrics(self, agent_name: str, duration: float, error: bool = False):
        """Registra métricas de ejecución"""
        self.response_time.record(
            duration * 1000,  # en ms
            {"agent": agent_name}
        )
        
        if error:
            self.error_counter.add(1, {"agent": agent_name})

class HealthChecker:
    """Verifica salud del sistema"""
    
    def __init__(self, components: dict):
        self.components = components
    
    async def check_health(self) -> dict:
        """Verifica salud de todos los componentes"""
        health_status = {
            "status": "healthy",
            "components": {},
            "timestamp": datetime.now().isoformat()
        }
        
        for name, component in self.components.items():
            try:
                is_healthy = await component.health_check()
                health_status["components"][name] = {
                    "status": "healthy" if is_healthy else "unhealthy",
                    "checked_at": datetime.now().isoformat()
                }
                
                if not is_healthy:
                    health_status["status"] = "degraded"
                    
            except Exception as e:
                health_status["components"][name] = {
                    "status": "unhealthy",
                    "error": str(e),
                    "checked_at": datetime.now().isoformat()
                }
                health_status["status"] = "unhealthy"
        
        return health_status
```

### 6.3 Seguridad y RBAC

```python
from cryptography.fernet import Fernet
import jwt

class SecurityManager:
    """Gestiona seguridad y control de acceso"""
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self.fernet = Fernet(Fernet.generate_key())
        
        # Definir roles y permisos
        self.rbac_config = {
            "customer": {
                "allowed_agents": [
                    "category_agent",
                    "product_agent",
                    "promotions_agent",
                    "tracking_agent"
                ],
                "denied_tools": ["InternalPricingTool", "CustomerDataModificationTool"]
            },
            "premium_customer": {
                "allowed_agents": "all",
                "denied_tools": ["InternalPricingTool"]
            },
            "support_staff": {
                "allowed_agents": "all",
                "denied_tools": []
            }
        }
    
    def encrypt_sensitive_data(self, data: str) -> str:
        """Encripta datos sensibles"""
        return self.fernet.encrypt(data.encode()).decode()
    
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """Desencripta datos sensibles"""
        return self.fernet.decrypt(encrypted_data.encode()).decode()
    
    async def check_permissions(
        self, 
        user_role: str, 
        agent: str, 
        tool: str = None
    ) -> bool:
        """Verifica permisos RBAC"""
        role_config = self.rbac_config.get(user_role, {})
        
        # Verificar acceso a agente
        allowed_agents = role_config.get("allowed_agents", [])
        if allowed_agents != "all" and agent not in allowed_agents:
            return False
        
        # Verificar acceso a herramienta
        if tool:
            denied_tools = role_config.get("denied_tools", [])
            if tool in denied_tools:
                return False
        
        return True
    
    def generate_session_token(self, user_data: dict) -> str:
        """Genera token JWT para sesión"""
        payload = {
            "user_id": user_data["id"],
            "role": user_data["role"],
            "exp": datetime.utcnow() + timedelta(hours=24)
        }
        return jwt.encode(payload, self.secret_key, algorithm="HS256")
```

## 7. Implementación del StateGraph Principal

```python
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolExecutor

class EcommerceAssistantGraph:
    """Graph principal del asistente e-commerce"""
    
    def __init__(self, config: dict):
        self.config = config
        self.checkpointer = config["checkpointer"]
        self.security_manager = config["security_manager"]
        self.monitoring = config["monitoring"]
        
        # Inicializar componentes
        self._init_components()
        
        # Construir el graph
        self.graph = self._build_graph()
        self.app = self.graph.compile(
            checkpointer=self.checkpointer
        )
    
    def _init_components(self):
        """Inicializa todos los componentes"""
        # LLM
        llm_integration = OllamaIntegration()
        self.llm = llm_integration.get_llm()
        
        # Vector Store
        chroma_integration = ChromaDBIntegration()
        self.vector_store = chroma_integration.get_vector_store("products")
        
        # Router
        self.router = IntentRouter(self.llm)
        
        # Supervisor
        self.supervisor = SupervisorAgent(self.router)
        
        # Agentes especializados
        self.agents = {
            "category_agent": CategoryAgent(self.vector_store, self.llm),
            "product_agent": ProductAgent(
                self.vector_store, 
                self.config["db_connection"], 
                self.llm
            ),
            "promotions_agent": PromotionsAgent(
                self.config["db_connection"],
                self.config["cache_service"],
                self.llm
            ),
            "tracking_agent": TrackingAgent(
                self.config["db_connection"],
                self.config["shipping_apis"],
                self.llm
            ),
            "support_agent": SupportAgent(
                self.vector_store,
                self.config["knowledge_base"],
                self.llm
            ),
            "invoice_agent": InvoiceAgent(
                self.config["db_connection"],
                self.config["invoice_api"],
                self.llm
            )
        }
    
    def _build_graph(self) -> StateGraph:
        """Construye el graph de LangGraph"""
        # Crear el StateGraph
        workflow = StateGraph(SharedState)
        
        # Añadir nodos
        workflow.add_node("supervisor", self.supervisor.process)
        
        # Añadir agentes
        for agent_name, agent in self.agents.items():
            workflow.add_node(agent_name, agent.process)
        
        # Añadir nodo de respuesta
        workflow.add_node("response_generator", self._generate_response)
        
        # Definir flujo
        workflow.set_entry_point("supervisor")
        
        # Routing desde supervisor
        workflow.add_conditional_edges(
            "supervisor",
            self._route_to_agent,
            {
                "category_agent": "category_agent",
                "product_agent": "product_agent",
                "promotions_agent": "promotions_agent",
                "tracking_agent": "tracking_agent",
                "support_agent": "support_agent",
                "invoice_agent": "invoice_agent",
                "human_agent": END,
                "end": END
            }
        )
        
        # Todos los agentes van al generador de respuesta
        for agent_name in self.agents.keys():
            workflow.add_edge(agent_name, "response_generator")
        
        # El generador de respuesta puede volver al supervisor o terminar
        workflow.add_conditional_edges(
            "response_generator",
            self._check_completion,
            {
                "continue": "supervisor",
                "end": END
            }
        )
        
        return workflow
    
    def _route_to_agent(self, state: SharedState) -> str:
        """Determina a qué agente dirigir"""
        if state.requires_human:
            return "human_agent"
        
        if state.is_complete:
            return "end"
        
        return state.current_agent or "end"
    
    def _check_completion(self, state: SharedState) -> str:
        """Verifica si la conversación está completa"""
        if state.is_complete or state.requires_human:
            return "end"
        
        # Si hay múltiples intenciones pendientes
        if len(state.intent_history) < 3:  # Límite de rebotes
            return "continue"
        
        return "end"
    
    async def _generate_response(self, state: SharedState) -> SharedState:
        """Genera la respuesta final consolidada"""
        # Recopilar todas las respuestas de agentes
        agent_responses = state.agent_responses
        
        if not agent_responses:
            state.is_complete = True
            return state
        
        # Tomar la última respuesta
        last_response = agent_responses[-1]
        
        # Añadir como mensaje del asistente
        state.messages.append(
            AIMessage(content=last_response.response_text)
        )
        
        # Verificar si necesita más información
        if "¿" in last_response.response_text or "?" in last_response.response_text:
            # Espera respuesta del usuario
            state.is_complete = False
        else:
            # Considerar si la consulta fue resuelta
            state.is_complete = self._is_query_resolved(state)
        
        return state
    
    def _is_query_resolved(self, state: SharedState) -> bool:
        """Determina si la consulta fue resuelta"""
        # Lógica simple: si hubo respuesta exitosa del agente correcto
        if state.agent_responses:
            last_response = state.agent_responses[-1]
            return last_response.success
        return False
    
    async def process_message(
        self, 
        message: str, 
        conversation_id: str,
        customer_data: dict
    ) -> dict:
        """Procesa un mensaje del usuario"""
        # Crear o recuperar estado
        config = {"configurable": {"thread_id": conversation_id}}
        
        # Obtener estado actual
        current_state = await self.app.aget_state(config)
        
        if current_state.values:
            state = SharedState(**current_state.values)
        else:
            # Nuevo estado
            state = SharedState(
                messages=[HumanMessage(content=message)],
                customer=CustomerContext(**customer_data),
                conversation=ConversationContext(
                    conversation_id=conversation_id,
                    session_id=f"session_{conversation_id}"
                )
            )
        
        # Añadir nuevo mensaje
        state.messages.append(HumanMessage(content=message))
        
        # Procesar con el graph
        result = await self.app.ainvoke(state, config)
        
        # Extraer respuesta
        last_message = result["messages"][-1]
        
        return {
            "response": last_message.content,
            "conversation_id": conversation_id,
            "state_summary": result.get_context_summary()
        }
```

## 8. Ejemplo de Uso

```python
# Configuración inicial
config = {
    "checkpointer": await PostgreSQLIntegration(
        "postgresql://user:pass@localhost/ecommerce"
    ).get_checkpointer(),
    "db_connection": db_connection,
    "cache_service": RedisCache(),
    "shipping_apis": ExternalAPIsIntegration(),
    "invoice_api": InvoiceAPI(),
    "knowledge_base": knowledge_base_store,
    "security_manager": SecurityManager(secret_key),
    "monitoring": MonitoringSystem()
}

# Crear el assistant
assistant = EcommerceAssistantGraph(config)

# Procesar mensaje
response = await assistant.process_message(
    message="Quiero ver laptops gaming con RTX 4070",
    conversation_id="conv_123",
    customer_data={
        "customer_id": "cust_456",
        "name": "Juan Pérez",
        "email": "juan@email.com",
        "phone": "+5491234567890",
        "tier": "premium"
    }
)

print(response["response"])
# Output: "¡Excelente elección! Tengo 5 laptops gaming con RTX 4070 disponibles..."
```

Este sistema multi-agente proporciona:

1. **Alta modularidad**: Cada agente es independiente y especializado
2. **Escalabilidad horizontal**: Los agentes pueden escalar independientemente
3. **Resiliencia**: Checkpointing y recuperación ante errores
4. **Trazabilidad**: Integración completa con LangSmith
5. **Seguridad**: RBAC y encriptación de datos sensibles
6. **Performance**: Caché multinivel y optimizaciones
7. **Flexibilidad**: Fácil agregar nuevos agentes o modificar flujos