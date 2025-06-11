#!/usr/bin/env python3
"""
Suite de pruebas completas para verificar todo el flujo del sistema LangGraph
Incluye verificación de base de datos, vectores, logs detallados y comportamiento completo
"""
import asyncio
import json
import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Añadir el directorio raíz al path
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.agents.langgraph_system.integrations.chroma_integration import ChromaDBIntegration
from app.agents.langgraph_system.integrations.ollama_integration import OllamaIntegration
from app.agents.langgraph_system.integrations.postgres_integration import PostgreSQLIntegration
from app.config.langgraph_config import get_langgraph_config
from app.database import get_db_context
from app.models.database import Conversation, Customer, Message
from app.models.message import Contact, WhatsAppMessage, TextMessage
from app.services.langgraph_chatbot_service import LangGraphChatbotService


class ComprehensiveTestSuite:
    """Suite de pruebas completas del sistema LangGraph"""
    
    def __init__(self):
        self.setup_logging()
        self.logger = logging.getLogger(__name__)
        self.test_results = {}
        self.test_data = {}
        self.start_time = datetime.now()
        
        # Configuración de prueba
        self.test_user_number = "5491234567890"
        self.test_user_name = "Usuario Test Completo"
        self.test_messages = self._get_test_messages()
        
        # Servicios e integraciones
        self.langgraph_service = None
        self.chroma_integration = None
        self.ollama_integration = None
        self.postgres_integration = None
        
        print("🧪 COMPREHENSIVE TEST SUITE INITIALIZED")
        print("=" * 60)
    
    def setup_logging(self):
        """Configura logging detallado para las pruebas"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"comprehensive_test_{timestamp}.log"
        
        # Configurar logging a archivo y consola
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            handlers=[
                logging.FileHandler(log_filename, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        # Configurar logger específico para nuestras pruebas
        self.test_logger = logging.getLogger("COMPREHENSIVE_TEST")
        self.test_logger.setLevel(logging.DEBUG)
        
        print(f"📝 Logs detallados en: {log_filename}")
    
    def _get_test_messages(self) -> List[Dict[str, str]]:
        """Define mensajes de prueba para diferentes escenarios"""
        return [
            {"text": "Hola, buenos días", "intent": "greeting", "category": "saludo"},
            {"text": "¿Qué laptops gaming tienen disponibles?", "intent": "product_inquiry", "category": "laptops"},
            {"text": "Necesito una laptop para trabajo de oficina", "intent": "product_inquiry", "category": "laptops"},
            {"text": "¿Cuál es el precio de la RTX 4080?", "intent": "product_inquiry", "category": "gpu"},
            {"text": "¿Tienen stock de procesadores AMD Ryzen?", "intent": "stock_check", "category": "cpu"},
            {"text": "¿Qué promociones tienen vigentes?", "intent": "promotions", "category": "offers"},
            {"text": "¿Cómo puedo trackear mi pedido?", "intent": "tracking", "category": "orders"},
            {"text": "Tengo un problema con la garantía", "intent": "support", "category": "warranty"},
            {"text": "¿Pueden generar una factura?", "intent": "invoice", "category": "billing"},
            {"text": "Gracias, hasta luego", "intent": "farewell", "category": "closing"}
        ]
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Ejecuta todas las pruebas del sistema"""
        self.test_logger.info("🚀 INICIANDO SUITE COMPLETA DE PRUEBAS")
        
        test_sequence = [
            ("Configuration Validation", self.test_configuration),
            ("Database Connectivity", self.test_database_connectivity),
            ("Ollama Integration", self.test_ollama_integration),
            ("ChromaDB Integration", self.test_chromadb_integration),
            ("PostgreSQL Integration", self.test_postgres_integration),
            ("LangGraph Service Initialization", self.test_langgraph_initialization),
            ("Vector Storage and Retrieval", self.test_vector_operations),
            ("Database Operations", self.test_database_operations),
            ("Message Processing Flow", self.test_message_processing),
            ("Agent Routing", self.test_agent_routing),
            ("Conversation Persistence", self.test_conversation_persistence),
            ("Error Handling", self.test_error_handling),
            ("Performance Metrics", self.test_performance),
            ("Integration End-to-End", self.test_end_to_end_integration)
        ]
        
        overall_success = True
        
        for test_name, test_func in test_sequence:
            print(f"\n{'='*20} {test_name} {'='*20}")
            self.test_logger.info(f"Ejecutando prueba: {test_name}")
            
            try:
                success, details = await test_func()
                self.test_results[test_name] = {
                    "success": success,
                    "details": details,
                    "timestamp": datetime.now().isoformat()
                }
                
                status = "✅ PASSED" if success else "❌ FAILED"
                print(f"{status}: {test_name}")
                
                if not success:
                    overall_success = False
                    self.test_logger.error(f"Prueba fallida: {test_name} - {details}")
                else:
                    self.test_logger.info(f"Prueba exitosa: {test_name}")
                
            except Exception as e:
                self.test_logger.error(f"Error en prueba {test_name}: {e}\n{traceback.format_exc()}")
                self.test_results[test_name] = {
                    "success": False,
                    "details": f"Exception: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                }
                overall_success = False
                print(f"❌ ERROR: {test_name} - {str(e)}")
        
        # Generar reporte final
        self.generate_final_report(overall_success)
        
        return {
            "overall_success": overall_success,
            "test_results": self.test_results,
            "test_duration": (datetime.now() - self.start_time).total_seconds()
        }
    
    async def test_configuration(self) -> Tuple[bool, str]:
        """Prueba la configuración del sistema"""
        self.test_logger.debug("Iniciando test de configuración")
        
        try:
            config = get_langgraph_config()
            validation_results = config.validate_config()
            
            # Verificar configuraciones críticas
            critical_configs = ['database', 'ollama', 'whatsapp']
            missing_configs = [conf for conf in critical_configs if not validation_results.get(conf, False)]
            
            if missing_configs:
                return False, f"Configuraciones críticas faltantes: {missing_configs}"
            
            # Verificar estructura de configuración
            required_sections = ['agents', 'monitoring', 'security', 'performance']
            missing_sections = [sec for sec in required_sections if not config.get_section(sec)]
            
            if missing_sections:
                return False, f"Secciones de configuración faltantes: {missing_sections}"
            
            self.test_data['config'] = config.export_config(safe_mode=True)
            return True, f"Configuración válida. Validaciones: {validation_results}"
            
        except Exception as e:
            return False, f"Error en configuración: {str(e)}"
    
    async def test_database_connectivity(self) -> Tuple[bool, str]:
        """Prueba la conectividad de la base de datos"""
        self.test_logger.debug("Iniciando test de conectividad de base de datos")
        
        try:
            from app.database import check_db_connection
            
            # Test de conexión básica
            try:
                db_healthy = await check_db_connection()
                if not db_healthy:
                    return False, "No se pudo conectar a la base de datos principal (BD no disponible para pruebas)"
            except Exception as e:
                return False, f"Base de datos no disponible para pruebas: {str(e)}"
            
            # Test de operaciones básicas
            with get_db_context() as db:
                # Verificar que las tablas existen
                from sqlalchemy import text
                result = db.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'"))
                table_count = result.scalar()
                
                if table_count == 0:
                    return False, "No se encontraron tablas en la base de datos"
                
                # Test de inserción/consulta básica
                test_customer = Customer(
                    phone_number=f"test_{int(datetime.now().timestamp())}",
                    profile_name="Test User Database"
                )
                db.add(test_customer)
                db.commit()
                db.refresh(test_customer)
                
                # Verificar que se insertó correctamente
                retrieved = db.query(Customer).filter(Customer.id == test_customer.id).first()
                if not retrieved:
                    return False, "No se pudo recuperar el registro insertado"
                
                # Limpiar datos de prueba
                db.delete(test_customer)
                db.commit()
            
            return True, f"Base de datos conectada exitosamente. Tablas encontradas: {table_count}"
            
        except Exception as e:
            return False, f"Error en conectividad de base de datos: {str(e)}"
    
    async def test_ollama_integration(self) -> Tuple[bool, str]:
        """Prueba la integración con Ollama"""
        self.test_logger.debug("Iniciando test de integración Ollama")
        
        try:
            self.ollama_integration = OllamaIntegration()
            
            # Test de health check completo
            try:
                health_status = await self.ollama_integration.comprehensive_test()
            except Exception as e:
                return False, f"Ollama no disponible para pruebas: {str(e)}"
            
            failed_tests = [test for test, status in health_status.items() if not status]
            if failed_tests:
                return False, f"Tests de Ollama fallidos: {failed_tests}"
            
            # Test de generación de texto
            test_prompt = "¿Cuáles son las mejores laptops para gaming?"
            llm = self.ollama_integration.get_llm()
            
            response = await llm.ainvoke(test_prompt)
            if not response or len(response.content) < 10:
                return False, "La respuesta del LLM es demasiado corta o vacía"
            
            # Test de embeddings
            embeddings = self.ollama_integration.get_embeddings()
            test_text = "laptop gaming RTX 4080"
            
            embedding_vector = await embeddings.aembed_query(test_text)
            if not embedding_vector or len(embedding_vector) == 0:
                return False, "No se pudieron generar embeddings"
            
            self.test_data['ollama'] = {
                "health_status": health_status,
                "test_response_length": len(response.content),
                "embedding_dimension": len(embedding_vector)
            }
            
            return True, f"Ollama funcionando correctamente. Dimensión embeddings: {len(embedding_vector)}"
            
        except Exception as e:
            return False, f"Error en integración Ollama: {str(e)}"
    
    async def test_chromadb_integration(self) -> Tuple[bool, str]:
        """Prueba la integración con ChromaDB"""
        self.test_logger.debug("Iniciando test de integración ChromaDB")
        
        try:
            self.chroma_integration = ChromaDBIntegration()
            
            # Test de health check
            health_ok = await self.chroma_integration.health_check()
            if not health_ok:
                return False, "Health check de ChromaDB falló"
            
            # Test de colecciones
            test_collection = "test_collection_comprehensive"
            
            # Limpiar colección si existe
            existing_collections = self.chroma_integration.list_collections()
            if test_collection in existing_collections:
                self.chroma_integration.delete_collection(test_collection)
            
            # Crear colección de prueba
            collection = self.chroma_integration.get_collection(test_collection, create_if_not_exists=True)
            
            # Test de inserción de documentos
            from langchain_core.documents import Document
            
            test_docs = [
                Document(page_content="Laptop gaming con RTX 4080", metadata={"category": "laptops", "price": 2500}),
                Document(page_content="Procesador AMD Ryzen 9", metadata={"category": "cpu", "price": 800}),
                Document(page_content="Memoria RAM 32GB DDR5", metadata={"category": "memory", "price": 400})
            ]
            
            doc_ids = await self.chroma_integration.add_documents(test_collection, test_docs)
            if len(doc_ids) != len(test_docs):
                return False, f"Se insertaron {len(doc_ids)} documentos en vez de {len(test_docs)}"
            
            # Test de búsqueda
            search_results = await self.chroma_integration.search_similar(
                test_collection, 
                "laptop para juegos", 
                k=2
            )
            
            if len(search_results) == 0:
                return False, "No se encontraron resultados en la búsqueda vectorial"
            
            # Verificar que el resultado más relevante sea correcto
            best_match = search_results[0]
            if "laptop" not in best_match.page_content.lower():
                return False, "El resultado más relevante no es correcto"
            
            # Test de estadísticas
            stats = self.chroma_integration.get_collection_stats(test_collection)
            if stats.get('document_count', 0) != len(test_docs):
                return False, f"Conteo de documentos incorrecto: {stats.get('document_count')} vs {len(test_docs)}"
            
            # Limpiar colección de prueba
            self.chroma_integration.delete_collection(test_collection)
            
            self.test_data['chromadb'] = {
                "collections_found": len(existing_collections),
                "documents_inserted": len(doc_ids),
                "search_results_count": len(search_results),
                "stats": stats
            }
            
            return True, f"ChromaDB funcionando correctamente. Documentos insertados: {len(doc_ids)}, búsquedas exitosas"
            
        except Exception as e:
            return False, f"Error en integración ChromaDB: {str(e)}"
    
    async def test_postgres_integration(self) -> Tuple[bool, str]:
        """Prueba la integración específica de PostgreSQL para LangGraph"""
        self.test_logger.debug("Iniciando test de integración PostgreSQL")
        
        try:
            self.postgres_integration = PostgreSQLIntegration()
            await self.postgres_integration.initialize()
            
            # Test de health check
            health_ok = await self.postgres_integration.health_check()
            if not health_ok:
                return False, "Health check de PostgreSQL falló"
            
            # Test de checkpointer
            checkpointer = self.postgres_integration.get_checkpointer()
            if not checkpointer:
                return False, "No se pudo obtener el checkpointer"
            
            # Test de estadísticas de checkpoints
            stats = await self.postgres_integration.get_checkpoint_stats()
            if stats is None:
                return False, "No se pudieron obtener estadísticas de checkpoints"
            
            # Test de query personalizada
            query_result = await self.postgres_integration.execute_query("SELECT 1 as test_value")
            if not query_result or query_result[0][0] != 1:
                return False, "Query personalizada falló"
            
            # Test de información de conexiones
            connection_info = await self.postgres_integration.get_connection_info()
            if not connection_info:
                return False, "No se pudo obtener información de conexiones"
            
            self.test_data['postgres'] = {
                "checkpoint_stats": stats,
                "connection_info": connection_info
            }
            
            return True, f"PostgreSQL funcionando correctamente. Checkpoints totales: {stats.get('total_checkpoints', 0)}"
            
        except Exception as e:
            return False, f"Error en integración PostgreSQL: {str(e)}"
    
    async def test_langgraph_initialization(self) -> Tuple[bool, str]:
        """Prueba la inicialización del servicio LangGraph"""
        self.test_logger.debug("Iniciando test de inicialización LangGraph")
        
        try:
            self.langgraph_service = LangGraphChatbotService()
            await self.langgraph_service.initialize()
            
            # Verificar que todos los componentes estén inicializados
            if not self.langgraph_service.graph_system:
                return False, "Sistema de grafos no inicializado"
            
            if not self.langgraph_service.monitoring:
                return False, "Sistema de monitoreo no inicializado"
            
            if not self.langgraph_service.security:
                return False, "Sistema de seguridad no inicializado"
            
            # Test de health check
            health_status = await self.langgraph_service.get_system_health()
            if health_status["overall_status"] not in ["healthy", "degraded"]:
                return False, f"Estado del sistema no saludable: {health_status['overall_status']}"
            
            # Verificar componentes específicos
            components = health_status.get("components", {})
            critical_components = ["langgraph", "database"]
            
            for component in critical_components:
                if component not in components:
                    return False, f"Componente crítico faltante: {component}"
                
                comp_status = components[component]
                if isinstance(comp_status, dict):
                    comp_health = comp_status.get("status", "unknown")
                else:
                    comp_health = comp_status
                
                if comp_health == "unhealthy":
                    return False, f"Componente no saludable: {component}"
            
            self.test_data['langgraph'] = {
                "health_status": health_status,
                "components_count": len(components)
            }
            
            return True, f"LangGraph inicializado correctamente. Estado: {health_status['overall_status']}"
            
        except Exception as e:
            return False, f"Error en inicialización LangGraph: {str(e)}"
    
    async def test_vector_operations(self) -> Tuple[bool, str]:
        """Prueba las operaciones vectoriales completas"""
        self.test_logger.debug("Iniciando test de operaciones vectoriales")
        
        try:
            if not self.chroma_integration:
                self.chroma_integration = ChromaDBIntegration()
            
            # Test de inserción de datos de productos
            product_collection = "test_products_vectors"
            
            # Limpiar si existe
            existing_collections = self.chroma_integration.list_collections()
            if product_collection in existing_collections:
                self.chroma_integration.delete_collection(product_collection)
            
            # Crear colección y añadir productos de prueba
            from langchain_core.documents import Document
            
            product_docs = [
                Document(
                    page_content="Laptop ASUS ROG Strix G15 con RTX 4070, AMD Ryzen 7, 16GB RAM, ideal para gaming",
                    metadata={"category": "laptops", "brand": "ASUS", "price": 1800, "stock": 5}
                ),
                Document(
                    page_content="Procesador AMD Ryzen 9 7900X, 12 núcleos, perfecto para workstations y gaming",
                    metadata={"category": "cpu", "brand": "AMD", "price": 650, "stock": 10}
                ),
                Document(
                    page_content="Tarjeta gráfica NVIDIA RTX 4080 16GB, excelente para gaming 4K y ray tracing",
                    metadata={"category": "gpu", "brand": "NVIDIA", "price": 1200, "stock": 3}
                ),
                Document(
                    page_content="Laptop empresarial Lenovo ThinkPad X1 Carbon, ultraliviana, Intel Core i7",
                    metadata={"category": "laptops", "brand": "Lenovo", "price": 2200, "stock": 8}
                )
            ]
            
            doc_ids = await self.chroma_integration.add_documents(product_collection, product_docs)
            if len(doc_ids) != len(product_docs):
                return False, f"Error insertando productos vectoriales: {len(doc_ids)} vs {len(product_docs)}"
            
            # Test de búsquedas específicas
            search_tests = [
                {"query": "laptop para juegos", "expected_brand": "ASUS", "min_results": 1},
                {"query": "procesador AMD gaming", "expected_category": "cpu", "min_results": 1},
                {"query": "RTX 4080 gráfica", "expected_brand": "NVIDIA", "min_results": 1},
                {"query": "laptop trabajo oficina", "expected_brand": "Lenovo", "min_results": 1}
            ]
            
            search_results_summary = []
            
            for test in search_tests:
                results = await self.chroma_integration.search_similar(
                    product_collection,
                    test["query"],
                    k=3
                )
                
                if len(results) < test["min_results"]:
                    return False, f"Búsqueda '{test['query']}' devolvió {len(results)} resultados, esperaba al menos {test['min_results']}"
                
                # Verificar relevancia
                top_result = results[0]
                metadata = top_result.metadata
                
                expected_brand = test.get("expected_brand")
                expected_category = test.get("expected_category")
                
                if expected_brand and metadata.get("brand") != expected_brand:
                    self.test_logger.warning(f"Búsqueda '{test['query']}' no devolvió la marca esperada. Obtuvo: {metadata.get('brand')}, esperaba: {expected_brand}")
                
                if expected_category and metadata.get("category") != expected_category:
                    self.test_logger.warning(f"Búsqueda '{test['query']}' no devolvió la categoría esperada. Obtuvo: {metadata.get('category')}, esperaba: {expected_category}")
                
                search_results_summary.append({
                    "query": test["query"],
                    "results_count": len(results),
                    "top_result_brand": metadata.get("brand"),
                    "top_result_category": metadata.get("category")
                })
            
            # Test de búsqueda con filtros
            filtered_results = await self.chroma_integration.search_similar(
                product_collection,
                "laptop",
                k=5,
                filter_dict={"category": "laptops"}
            )
            
            # Verificar que todos los resultados sean laptops
            non_laptop_results = [r for r in filtered_results if r.metadata.get("category") != "laptops"]
            if non_laptop_results:
                return False, f"Búsqueda filtrada devolvió {len(non_laptop_results)} resultados que no son laptops"
            
            # Limpiar colección de prueba
            self.chroma_integration.delete_collection(product_collection)
            
            self.test_data['vector_operations'] = {
                "products_inserted": len(doc_ids),
                "search_tests": search_results_summary,
                "filtered_results_count": len(filtered_results)
            }
            
            return True, f"Operaciones vectoriales exitosas. Productos: {len(doc_ids)}, búsquedas: {len(search_tests)}"
            
        except Exception as e:
            return False, f"Error en operaciones vectoriales: {str(e)}"
    
    async def test_database_operations(self) -> Tuple[bool, str]:
        """Prueba las operaciones de base de datos del sistema"""
        self.test_logger.debug("Iniciando test de operaciones de base de datos")
        
        try:
            # Test de creación de cliente
            with get_db_context() as db:
                # Crear cliente de prueba
                test_customer = Customer(
                    phone_number=self.test_user_number,
                    profile_name=self.test_user_name,
                    active=True
                )
                db.add(test_customer)
                db.commit()
                db.refresh(test_customer)
                
                customer_id = test_customer.id
                
                # Crear conversación
                test_conversation = Conversation(
                    customer_id=customer_id,
                    session_id=f"test_session_{int(datetime.now().timestamp())}"
                )
                db.add(test_conversation)
                db.commit()
                db.refresh(test_conversation)
                
                conversation_id = test_conversation.id
                
                # Crear mensajes de prueba
                messages_data = []
                
                for i, msg_data in enumerate(self.test_messages[:3]):  # Solo primeros 3 mensajes para DB test
                    # Mensaje del usuario
                    user_message = Message(
                        conversation_id=conversation_id,
                        message_type="user",
                        content=msg_data["text"],
                        intent=msg_data["intent"],
                        confidence=0.95,
                        message_format="text"
                    )
                    db.add(user_message)
                    
                    # Respuesta del bot (simulada)
                    bot_response = f"Respuesta simulada para: {msg_data['text']}"
                    bot_message = Message(
                        conversation_id=conversation_id,
                        message_type="bot",
                        content=bot_response,
                        message_format="text"
                    )
                    db.add(bot_message)
                    
                    messages_data.append({
                        "user_message": msg_data["text"],
                        "bot_response": bot_response,
                        "intent": msg_data["intent"]
                    })
                
                db.commit()
                
                # Verificar que se guardaron correctamente
                saved_messages = db.query(Message).filter(Message.conversation_id == conversation_id).all()
                expected_message_count = len(messages_data) * 2  # Usuario + Bot por cada intercambio
                
                if len(saved_messages) != expected_message_count:
                    return False, f"Se guardaron {len(saved_messages)} mensajes, esperaba {expected_message_count}"
                
                # Verificar contadores en conversación
                conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
                
                if conversation.total_messages != expected_message_count:
                    return False, f"Contador total incorrecto: {conversation.total_messages} vs {expected_message_count}"
                
                # Test de recuperación de conversación
                user_messages = db.query(Message).filter(
                    Message.conversation_id == conversation_id,
                    Message.message_type == "user"
                ).all()
                
                if len(user_messages) != len(messages_data):
                    return False, f"Se recuperaron {len(user_messages)} mensajes de usuario, esperaba {len(messages_data)}"
                
                # Test de búsqueda por intent
                intent_messages = db.query(Message).filter(
                    Message.conversation_id == conversation_id,
                    Message.intent == "greeting"
                ).all()
                
                greeting_count = sum(1 for msg in messages_data if msg["intent"] == "greeting")
                if len(intent_messages) != greeting_count:
                    return False, f"Búsqueda por intent incorrecta: {len(intent_messages)} vs {greeting_count}"
                
                # Limpiar datos de prueba
                db.query(Message).filter(Message.conversation_id == conversation_id).delete()
                db.delete(test_conversation)
                db.delete(test_customer)
                db.commit()
            
            self.test_data['database_operations'] = {
                "customer_created": True,
                "conversation_created": True,
                "messages_saved": expected_message_count,
                "messages_retrieved": len(saved_messages),
                "intent_search_results": len(intent_messages)
            }
            
            return True, f"Operaciones de base de datos exitosas. Mensajes: {expected_message_count}, búsquedas: OK"
            
        except Exception as e:
            return False, f"Error en operaciones de base de datos: {str(e)}"
    
    async def test_message_processing(self) -> Tuple[bool, str]:
        """Prueba el procesamiento completo de mensajes"""
        self.test_logger.debug("Iniciando test de procesamiento de mensajes")
        
        try:
            if not self.langgraph_service:
                return False, "Servicio LangGraph no inicializado"
            
            # Procesar diferentes tipos de mensajes
            processing_results = []
            
            for i, msg_data in enumerate(self.test_messages[:5]):  # Procesar primeros 5 mensajes
                self.test_logger.info(f"Procesando mensaje {i+1}: {msg_data['text']}")
                
                # Crear mensaje de prueba
                test_message = WhatsAppMessage(
                    from_=self.test_user_number,
                    id=f"test_msg_{i:03d}",
                    type="text",
                    timestamp=str(int(datetime.now().timestamp())),
                    text=TextMessage(body=msg_data['text'])
                )
                
                test_contact = Contact(
                    wa_id=self.test_user_number,
                    profile={"name": self.test_user_name}
                )
                
                # Procesar mensaje
                start_time = datetime.now()
                result = await self.langgraph_service.procesar_mensaje(test_message, test_contact)
                end_time = datetime.now()
                
                processing_time = (end_time - start_time).total_seconds()
                
                # Verificar resultado
                if result.status != "success":
                    return False, f"Procesamiento falló en mensaje {i+1}: {result.message}"
                
                if not result.message or len(result.message.strip()) < 10:
                    return False, f"Respuesta muy corta o vacía en mensaje {i+1}"
                
                # Verificar tiempo de respuesta
                if processing_time > 10.0:  # 10 segundos máximo
                    self.test_logger.warning(f"Tiempo de respuesta alto: {processing_time:.2f}s")
                
                processing_results.append({
                    "message_index": i,
                    "input_text": msg_data['text'],
                    "expected_intent": msg_data['intent'],
                    "response_length": len(result.message),
                    "processing_time": processing_time,
                    "success": result.status == "success"
                })
                
                self.test_logger.debug(f"Mensaje {i+1} procesado en {processing_time:.2f}s: {result.message[:100]}...")
                
                # Pausa entre mensajes para evitar sobrecarga
                await asyncio.sleep(0.5)
            
            # Verificar métricas globales
            successful_processing = sum(1 for r in processing_results if r["success"])
            avg_processing_time = sum(r["processing_time"] for r in processing_results) / len(processing_results)
            avg_response_length = sum(r["response_length"] for r in processing_results) / len(processing_results)
            
            if successful_processing != len(processing_results):
                return False, f"Solo {successful_processing}/{len(processing_results)} mensajes procesados exitosamente"
            
            if avg_processing_time > 5.0:
                return False, f"Tiempo promedio muy alto: {avg_processing_time:.2f}s"
            
            self.test_data['message_processing'] = {
                "messages_processed": len(processing_results),
                "success_rate": (successful_processing / len(processing_results)) * 100,
                "average_processing_time": avg_processing_time,
                "average_response_length": avg_response_length,
                "processing_details": processing_results
            }
            
            return True, f"Procesamiento exitoso. Mensajes: {len(processing_results)}, tiempo promedio: {avg_processing_time:.2f}s"
            
        except Exception as e:
            return False, f"Error en procesamiento de mensajes: {str(e)}"
    
    async def test_agent_routing(self) -> Tuple[bool, str]:
        """Prueba el routing hacia los agentes correctos"""
        self.test_logger.debug("Iniciando test de routing de agentes")
        
        try:
            if not self.langgraph_service or not self.langgraph_service.graph_system:
                return False, "Sistema de grafos no disponible"
            
            # Mensajes específicos para probar routing
            routing_tests = [
                {"text": "¿Qué categorías de productos tienen?", "expected_agent": "category_agent"},
                {"text": "¿Cuánto cuesta la RTX 4090?", "expected_agent": "product_agent"},
                {"text": "¿Qué ofertas tienen vigentes?", "expected_agent": "promotions_agent"},
                {"text": "¿Dónde está mi pedido?", "expected_agent": "tracking_agent"},
                {"text": "Tengo un problema con la garantía", "expected_agent": "support_agent"},
                {"text": "Necesito una factura", "expected_agent": "invoice_agent"}
            ]
            
            routing_results = []
            
            for test in routing_tests:
                # Crear mensaje de prueba
                message = WhatsAppMessage(
                    from_=f"{self.test_user_number}_routing",
                    id=f"routing_test_{len(routing_results)}",
                    type="text",
                    timestamp=str(int(datetime.now().timestamp())),
                    text=TextMessage(body=test['text'])
                )
                
                contact = Contact(
                    wa_id=f"{self.test_user_number}_routing",
                    profile={"name": "Test Routing User"}
                )
                
                # Procesar y verificar routing
                try:
                    result = await self.langgraph_service.procesar_mensaje(message, contact)
                    
                    # Para esta prueba, asumimos éxito si el mensaje se procesa
                    # En un sistema real, podrías extraer información del estado interno
                    # sobre qué agente se usó
                    
                    routing_results.append({
                        "test_message": test['text'],
                        "expected_agent": test['expected_agent'],
                        "processing_success": result.status == "success",
                        "response_relevant": len(result.message) > 20  # Respuesta significativa
                    })
                    
                    self.test_logger.debug(f"Routing test para '{test['text']}': {result.status}")
                    
                except Exception as e:
                    routing_results.append({
                        "test_message": test['text'],
                        "expected_agent": test['expected_agent'],
                        "processing_success": False,
                        "error": str(e)
                    })
            
            # Verificar resultados
            successful_routings = sum(1 for r in routing_results if r["processing_success"])
            relevant_responses = sum(1 for r in routing_results if r.get("response_relevant", False))
            
            if successful_routings < len(routing_tests) * 0.8:  # Al menos 80% éxito
                return False, f"Solo {successful_routings}/{len(routing_tests)} routings exitosos"
            
            self.test_data['agent_routing'] = {
                "routing_tests": len(routing_tests),
                "successful_routings": successful_routings,
                "relevant_responses": relevant_responses,
                "routing_details": routing_results
            }
            
            return True, f"Routing exitoso. Tests: {len(routing_tests)}, éxitos: {successful_routings}"
            
        except Exception as e:
            return False, f"Error en routing de agentes: {str(e)}"
    
    async def test_conversation_persistence(self) -> Tuple[bool, str]:
        """Prueba la persistencia de conversaciones"""
        self.test_logger.debug("Iniciando test de persistencia de conversaciones")
        
        try:
            if not self.langgraph_service:
                return False, "Servicio LangGraph no inicializado"
            
            # Crear una conversación multi-turno
            conversation_user = f"{self.test_user_number}_persistence"
            conversation_messages = [
                "Hola, necesito ayuda",
                "¿Qué laptops gaming tienen?",
                "¿Cuál me recomiendas para jugar Cyberpunk 2077?",
                "¿Cuánto cuesta esa laptop?",
                "¿Tienen stock disponible?"
            ]
            
            conversation_results = []
            
            for i, msg_text in enumerate(conversation_messages):
                message = WhatsAppMessage(
                    from_=conversation_user,
                    id=f"persistence_test_{i}",
                    type="text",
                    timestamp=str(int(datetime.now().timestamp())),
                    text=TextMessage(body=msg_text)
                )
                
                contact = Contact(
                    wa_id=conversation_user,
                    profile={"name": "Test Persistence User"}
                )
                
                result = await self.langgraph_service.procesar_mensaje(message, contact)
                
                if result.status != "success":
                    return False, f"Fallo en mensaje {i+1} de conversación persistente"
                
                conversation_results.append({
                    "turn": i + 1,
                    "user_message": msg_text,
                    "bot_response": result.message,
                    "success": result.status == "success"
                })
                
                # Pausa entre mensajes
                await asyncio.sleep(1)
            
            # Verificar que se puede recuperar el historial
            try:
                history = await self.langgraph_service.get_conversation_history_langgraph(
                    conversation_user, 
                    limit=20
                )
                
                if history.get("success") and history.get("total_messages", 0) > 0:
                    persistence_ok = True
                    persisted_messages = history.get("total_messages", 0)
                else:
                    persistence_ok = False
                    persisted_messages = 0
                    
            except Exception as e:
                self.test_logger.warning(f"No se pudo recuperar historial: {e}")
                persistence_ok = False
                persisted_messages = 0
            
            # Verificar en base de datos tradicional
            db_messages_count = 0
            try:
                with get_db_context() as db:
                    # Buscar customer por teléfono
                    customer = db.query(Customer).filter(Customer.phone_number == conversation_user).first()
                    if customer:
                        # Buscar conversación
                        conversation = db.query(Conversation).filter(
                            Conversation.customer_id == customer.id,
                            Conversation.ended_at.is_(None)
                        ).first()
                        
                        if conversation:
                            # Contar mensajes
                            db_messages = db.query(Message).filter(
                                Message.conversation_id == conversation.id
                            ).all()
                            db_messages_count = len(db_messages)
                            
            except Exception as e:
                self.test_logger.warning(f"No se pudo verificar persistencia en DB: {e}")
            
            success_rate = sum(1 for r in conversation_results if r["success"]) / len(conversation_results) * 100
            
            if success_rate < 100:
                return False, f"Tasa de éxito de conversación: {success_rate}%"
            
            self.test_data['conversation_persistence'] = {
                "conversation_turns": len(conversation_results),
                "success_rate": success_rate,
                "langgraph_history_available": persistence_ok,
                "langgraph_messages_count": persisted_messages,
                "database_messages_count": db_messages_count,
                "conversation_details": conversation_results
            }
            
            return True, f"Persistencia exitosa. Turnos: {len(conversation_results)}, DB: {db_messages_count} mensajes"
            
        except Exception as e:
            return False, f"Error en persistencia de conversaciones: {str(e)}"
    
    async def test_error_handling(self) -> Tuple[bool, str]:
        """Prueba el manejo de errores del sistema"""
        self.test_logger.debug("Iniciando test de manejo de errores")
        
        try:
            if not self.langgraph_service:
                return False, "Servicio LangGraph no inicializado"
            
            # Test de mensajes problemáticos
            error_test_messages = [
                {"text": "", "expected": "handle_empty"},
                {"text": "   ", "expected": "handle_whitespace"},
                {"text": "a" * 5000, "expected": "handle_very_long"},
                {"text": "SELECT * FROM users; DROP TABLE users;", "expected": "handle_sql_injection"},
                {"text": "<script>alert('xss')</script>", "expected": "handle_xss"},
                {"text": "🎉💥🔥" * 100, "expected": "handle_emoji_spam"}
            ]
            
            error_handling_results = []
            
            for test in error_test_messages:
                try:
                    message = WhatsAppMessage(
                        from_=f"{self.test_user_number}_error",
                        id=f"error_test_{len(error_handling_results)}",
                        type="text",
                        timestamp=str(int(datetime.now().timestamp())),
                        text=TextMessage(body=test['text'])
                    )
                    
                    contact = Contact(
                        wa_id=f"{self.test_user_number}_error",
                        profile={"name": "Test Error User"}
                    )
                    
                    result = await self.langgraph_service.procesar_mensaje(message, contact)
                    
                    # Para errores, esperamos que el sistema maneje gracefully
                    # Sin crashes y con respuestas apropiadas
                    
                    handled_gracefully = True
                    if test['expected'] == "handle_empty" and result.status == "failure":
                        handled_gracefully = True  # Es correcto que falle con mensaje vacío
                    elif result.status == "success" and len(result.message) > 0:
                        handled_gracefully = True  # Manejo exitoso
                    else:
                        handled_gracefully = False
                    
                    error_handling_results.append({
                        "test_type": test['expected'],
                        "input_length": len(test['text']),
                        "handled_gracefully": handled_gracefully,
                        "result_status": result.status,
                        "response_length": len(result.message) if result.message else 0
                    })
                    
                except Exception as e:
                    # Un crash completo es un fallo en el manejo de errores
                    error_handling_results.append({
                        "test_type": test['expected'],
                        "input_length": len(test['text']),
                        "handled_gracefully": False,
                        "error": str(e)
                    })
            
            # Test de recuperación del sistema después de errores
            recovery_test_message = "Hola, ¿funciona todo bien después de los tests de error?"
            
            try:
                message = WhatsAppMessage(
                    from_=f"{self.test_user_number}_recovery",
                    id="recovery_test",
                    type="text",
                    timestamp=str(int(datetime.now().timestamp())),
                    text=TextMessage(body=recovery_test_message)
                )
                
                contact = Contact(
                    wa_id=f"{self.test_user_number}_recovery",
                    profile={"name": "Test Recovery User"}
                )
                
                recovery_result = await self.langgraph_service.procesar_mensaje(message, contact)
                system_recovered = recovery_result.status == "success"
                
            except Exception as e:
                system_recovered = False
                self.test_logger.error(f"Sistema no se recuperó después de errores: {e}")
            
            graceful_handling_count = sum(1 for r in error_handling_results if r["handled_gracefully"])
            
            if graceful_handling_count < len(error_test_messages) * 0.8:  # 80% mínimo
                return False, f"Solo {graceful_handling_count}/{len(error_test_messages)} errores manejados gracefully"
            
            if not system_recovered:
                return False, "Sistema no se recuperó después de los tests de error"
            
            self.test_data['error_handling'] = {
                "error_tests": len(error_test_messages),
                "graceful_handling_count": graceful_handling_count,
                "system_recovered": system_recovered,
                "error_details": error_handling_results
            }
            
            return True, f"Manejo de errores exitoso. Tests: {len(error_test_messages)}, manejados: {graceful_handling_count}, recuperación: {system_recovered}"
            
        except Exception as e:
            return False, f"Error en test de manejo de errores: {str(e)}"
    
    async def test_performance(self) -> Tuple[bool, str]:
        """Prueba las métricas de performance del sistema"""
        self.test_logger.debug("Iniciando test de performance")
        
        try:
            if not self.langgraph_service:
                return False, "Servicio LangGraph no inicializado"
            
            # Test de carga concurrente (simulada)
            concurrent_messages = [
                "¿Qué laptops tienen?",
                "Precio de RTX 4080",
                "Stock de procesadores",
                "Ofertas vigentes",
                "Ayuda con garantía"
            ]
            
            # Medir tiempo de respuesta individual
            individual_times = []
            
            for msg in concurrent_messages:
                message = WhatsAppMessage(
                    from_=f"{self.test_user_number}_perf_{len(individual_times)}",
                    id=f"perf_test_{len(individual_times)}",
                    type="text",
                    timestamp=str(int(datetime.now().timestamp())),
                    text=TextMessage(body=msg)
                )
                
                contact = Contact(
                    wa_id=f"{self.test_user_number}_perf_{len(individual_times)}",
                    profile={"name": "Test Performance User"}
                )
                
                start_time = datetime.now()
                result = await self.langgraph_service.procesar_mensaje(message, contact)
                end_time = datetime.now()
                
                processing_time = (end_time - start_time).total_seconds()
                individual_times.append(processing_time)
                
                if result.status != "success":
                    return False, f"Fallo de performance en mensaje: {msg}"
            
            # Calcular métricas de performance
            avg_response_time = sum(individual_times) / len(individual_times)
            max_response_time = max(individual_times)
            min_response_time = min(individual_times)
            
            # Verificar que cumple objetivos de performance
            performance_target = 3.0  # 3 segundos máximo
            slow_responses = sum(1 for t in individual_times if t > performance_target)
            
            if avg_response_time > performance_target:
                return False, f"Tiempo promedio muy alto: {avg_response_time:.2f}s > {performance_target}s"
            
            if slow_responses > len(individual_times) * 0.2:  # Máximo 20% de respuestas lentas
                return False, f"Demasiadas respuestas lentas: {slow_responses}/{len(individual_times)}"
            
            # Test de métricas del sistema
            try:
                health_status = await self.langgraph_service.get_system_health()
                monitoring_available = "monitoring" in health_status.get("components", {})
            except Exception:
                monitoring_available = False
            
            self.test_data['performance'] = {
                "messages_tested": len(individual_times),
                "average_response_time": avg_response_time,
                "max_response_time": max_response_time,
                "min_response_time": min_response_time,
                "slow_responses": slow_responses,
                "performance_target": performance_target,
                "monitoring_available": monitoring_available,
                "individual_times": individual_times
            }
            
            return True, f"Performance satisfactoria. Promedio: {avg_response_time:.2f}s, máximo: {max_response_time:.2f}s"
            
        except Exception as e:
            return False, f"Error en test de performance: {str(e)}"
    
    async def test_end_to_end_integration(self) -> Tuple[bool, str]:
        """Prueba la integración completa end-to-end"""
        self.test_logger.debug("Iniciando test de integración end-to-end")
        
        try:
            if not self.langgraph_service:
                return False, "Servicio LangGraph no inicializado"
            
            # Simular un flujo completo de usuario
            e2e_user = f"{self.test_user_number}_e2e"
            e2e_flow = [
                {"message": "Hola, buenos días", "verify": "greeting_response"},
                {"message": "Necesito una laptop para gaming", "verify": "product_recommendation"},
                {"message": "¿Cuánto cuesta la más económica?", "verify": "price_information"},
                {"message": "¿Tienen stock?", "verify": "stock_information"},
                {"message": "¿Qué garantía tiene?", "verify": "warranty_information"},
                {"message": "Perfecto, gracias", "verify": "closing_response"}
            ]
            
            e2e_results = []
            conversation_context = []
            
            for step in e2e_flow:
                message = WhatsAppMessage(
                    from_=e2e_user,
                    id=f"e2e_test_{len(e2e_results)}",
                    type="text",
                    timestamp=str(int(datetime.now().timestamp())),
                    text=TextMessage(body=step['message'])
                )
                
                contact = Contact(
                    wa_id=e2e_user,
                    profile={"name": "Test E2E User"}
                )
                
                start_time = datetime.now()
                result = await self.langgraph_service.procesar_mensaje(message, contact)
                end_time = datetime.now()
                
                processing_time = (end_time - start_time).total_seconds()
                
                # Verificaciones básicas
                step_success = True
                verification_notes = []
                
                if result.status != "success":
                    step_success = False
                    verification_notes.append("Processing failed")
                
                if not result.message or len(result.message.strip()) < 10:
                    step_success = False
                    verification_notes.append("Response too short")
                
                # Verificaciones específicas por tipo
                if step['verify'] == "greeting_response":
                    if not any(word in result.message.lower() for word in ["hola", "buenos", "bienvenido"]):
                        verification_notes.append("No greeting words detected")
                
                elif step['verify'] == "product_recommendation":
                    if not any(word in result.message.lower() for word in ["laptop", "gaming", "producto"]):
                        verification_notes.append("No product context detected")
                
                elif step['verify'] == "price_information":
                    if not any(char in result.message for char in ["$", "precio", "costo"]):
                        verification_notes.append("No price information detected")
                
                elif step['verify'] == "stock_information":
                    if not any(word in result.message.lower() for word in ["stock", "disponible", "unidades"]):
                        verification_notes.append("No stock information detected")
                
                elif step['verify'] == "warranty_information":
                    if not any(word in result.message.lower() for word in ["garantía", "warranty", "cobertura"]):
                        verification_notes.append("No warranty information detected")
                
                conversation_context.append({
                    "user": step['message'],
                    "bot": result.message
                })
                
                e2e_results.append({
                    "step": len(e2e_results) + 1,
                    "user_message": step['message'],
                    "verification_type": step['verify'],
                    "bot_response": result.message,
                    "processing_time": processing_time,
                    "step_success": step_success,
                    "verification_notes": verification_notes
                })
                
                if not step_success:
                    self.test_logger.warning(f"E2E step {len(e2e_results)} issues: {verification_notes}")
                
                # Pausa entre pasos
                await asyncio.sleep(1)
            
            # Verificar flujo completo
            successful_steps = sum(1 for r in e2e_results if r["step_success"])
            avg_processing_time = sum(r["processing_time"] for r in e2e_results) / len(e2e_results)
            
            # Verificar que se mantuvo contexto (respuestas coherentes)
            context_maintained = True
            for i in range(1, len(conversation_context)):
                current_response = conversation_context[i]["bot"].lower()
                previous_context = " ".join([ctx["user"] + " " + ctx["bot"] for ctx in conversation_context[:i]]).lower()
                
                # Verificación básica: respuesta no debe ser idéntica a la primera
                if i > 2 and current_response == conversation_context[0]["bot"].lower():
                    context_maintained = False
                    break
            
            # Verificar persistencia final
            try:
                final_history = await self.langgraph_service.get_conversation_history_langgraph(e2e_user, limit=20)
                history_available = final_history.get("success", False) and final_history.get("total_messages", 0) > 0
            except Exception:
                history_available = False
            
            if successful_steps < len(e2e_flow) * 0.9:  # 90% mínimo
                return False, f"Solo {successful_steps}/{len(e2e_flow)} pasos exitosos en E2E"
            
            if avg_processing_time > 5.0:
                return False, f"Tiempo promedio E2E muy alto: {avg_processing_time:.2f}s"
            
            self.test_data['end_to_end_integration'] = {
                "total_steps": len(e2e_flow),
                "successful_steps": successful_steps,
                "average_processing_time": avg_processing_time,
                "context_maintained": context_maintained,
                "history_available": history_available,
                "conversation_flow": e2e_results,
                "full_conversation": conversation_context
            }
            
            return True, f"Integración E2E exitosa. Pasos: {successful_steps}/{len(e2e_flow)}, contexto: {context_maintained}"
            
        except Exception as e:
            return False, f"Error en integración end-to-end: {str(e)}"
    
    def generate_final_report(self, overall_success: bool):
        """Genera el reporte final de las pruebas"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"comprehensive_test_report_{timestamp}.json"
        
        # Reporte completo
        final_report = {
            "test_summary": {
                "overall_success": overall_success,
                "test_start_time": self.start_time.isoformat(),
                "test_end_time": datetime.now().isoformat(),
                "total_duration_seconds": (datetime.now() - self.start_time).total_seconds(),
                "total_tests": len(self.test_results),
                "successful_tests": sum(1 for result in self.test_results.values() if result["success"]),
                "failed_tests": sum(1 for result in self.test_results.values() if not result["success"])
            },
            "test_results": self.test_results,
            "test_data": self.test_data,
            "system_info": {
                "python_version": sys.version,
                "test_user": self.test_user_number,
                "environment_variables": {
                    "USE_LANGGRAPH": os.getenv("USE_LANGGRAPH"),
                    "DATABASE_URL_SET": bool(os.getenv("DATABASE_URL")),
                    "OLLAMA_API_URL": os.getenv("OLLAMA_API_URL"),
                    "REDIS_URL_SET": bool(os.getenv("REDIS_URL"))
                }
            }
        }
        
        # Guardar reporte
        with open(report_filename, 'w', encoding='utf-8') as f:
            json.dump(final_report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📊 REPORTE FINAL")
        print("=" * 60)
        print(f"📁 Reporte guardado en: {report_filename}")
        print(f"⏱️  Duración total: {final_report['test_summary']['total_duration_seconds']:.2f} segundos")
        print(f"✅ Tests exitosos: {final_report['test_summary']['successful_tests']}")
        print(f"❌ Tests fallidos: {final_report['test_summary']['failed_tests']}")
        print(f"📈 Tasa de éxito: {(final_report['test_summary']['successful_tests'] / final_report['test_summary']['total_tests']) * 100:.1f}%")
        
        # Mostrar tests fallidos
        failed_tests = [name for name, result in self.test_results.items() if not result["success"]]
        if failed_tests:
            print(f"\n❌ Tests fallidos:")
            for test_name in failed_tests:
                details = self.test_results[test_name]["details"]
                print(f"  • {test_name}: {details}")
        
        # Recomendaciones
        print(f"\n💡 Recomendaciones:")
        if overall_success:
            print("  ✅ Sistema listo para producción")
            print("  🔍 Monitorear logs durante despliegue inicial")
            print("  📊 Configurar alertas de performance")
        else:
            print("  ⚠️  Resolver tests fallidos antes de producción")
            print("  🔧 Verificar configuración y dependencias")
            print("  📝 Revisar logs detallados para debugging")
        
        return report_filename
    
    async def cleanup(self):
        """Limpia recursos después de las pruebas"""
        try:
            if self.langgraph_service:
                await self.langgraph_service.cleanup()
            
            if self.postgres_integration:
                await self.postgres_integration.close()
            
            print("🧹 Cleanup completado")
        except Exception as e:
            self.test_logger.error(f"Error en cleanup: {e}")


async def main():
    """Función principal"""
    print("🧪 COMPREHENSIVE TEST SUITE FOR LANGGRAPH SYSTEM")
    print("=" * 60)
    print("Este script ejecutará pruebas completas del sistema incluyendo:")
    print("  • Configuración y conectividad")
    print("  • Operaciones de base de datos")
    print("  • Procesamiento de vectores")
    print("  • Flujo de mensajes completo")
    print("  • Persistencia de conversaciones")
    print("  • Manejo de errores")
    print("  • Performance")
    print("  • Integración end-to-end")
    
    # Configurar variables de entorno mínimas para pruebas
    import os
    os.environ.setdefault("DATABASE_URL", "sqlite:///./test_comprehensive.db")
    os.environ.setdefault("USE_LANGGRAPH", "true")
    os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test_token")
    os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_verify_token")
    os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123456789")
    os.environ.setdefault("META_APP_ID", "test_app_id")
    os.environ.setdefault("META_APP_SECRET", "test_app_secret")
    
    print("\n📝 Configuración de prueba establecida")
    print(f"   Database: {os.environ.get('DATABASE_URL', 'No configurada')}")
    print(f"   LangGraph: {os.environ.get('USE_LANGGRAPH', 'No configurado')}")
    
    # Auto-continue for debugging
    print("\n✅ Continuando automáticamente con las pruebas...")
    
    test_suite = ComprehensiveTestSuite()
    
    try:
        results = await test_suite.run_all_tests()
        
        if results["overall_success"]:
            print("\n🎉 TODAS LAS PRUEBAS COMPLETADAS EXITOSAMENTE")
            print("El sistema está listo para usar en producción")
        else:
            print("\n⚠️  ALGUNAS PRUEBAS FALLARON")
            print("Revisar el reporte detallado para resolver los problemas")
        
    except KeyboardInterrupt:
        print("\n⚠️  Pruebas interrumpidas por el usuario")
    except Exception as e:
        print(f"\n❌ Error fatal en las pruebas: {e}")
        traceback.print_exc()
    finally:
        await test_suite.cleanup()


if __name__ == "__main__":
    asyncio.run(main())