"""
Example scripts for running LangSmith evaluations on ConversaShop.
These scripts demonstrate how to set up and run evaluations.
"""

import asyncio
import json
import os
from typing import Dict, List, Any
from datetime import datetime

# Make sure the project is importable
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config.langsmith_config import get_tracer
from app.evaluation.langsmith_evaluators import (
    LangSmithEvaluationRunner,
    ConversationQualityEvaluator
)
from app.monitoring.langsmith_dashboard import LangSmithMonitoringDashboard
from app.agents.langgraph_system.graph import EcommerceAssistantGraph


async def create_sample_evaluation_dataset():
    """Create a sample evaluation dataset for ConversaShop."""
    
    # Sample evaluation examples for e-commerce conversations
    examples = [
        {
            "inputs": {
                "message": "¿Cuánto cuesta el iPhone 15?",
                "conversation_id": "eval_001",
                "customer_data": {"user_id": "test_user_1"}
            },
            "outputs": {
                "expected_response": "El iPhone 15 tiene un precio de $899. Está disponible en stock.",
                "expected_agent": "product_agent"
            },
            "metadata": {
                "category": "product_inquiry",
                "intent": "price_check",
                "complexity": "simple"
            }
        },
        {
            "inputs": {
                "message": "Necesito ayuda para elegir entre diferentes laptops",
                "conversation_id": "eval_002",
                "customer_data": {"user_id": "test_user_2"}
            },
            "outputs": {
                "expected_response": "Te puedo ayudar a encontrar la laptop perfecta para ti. ¿Para qué la vas a usar principalmente?",
                "expected_agent": "category_agent"
            },
            "metadata": {
                "category": "product_comparison",
                "intent": "product_advice",
                "complexity": "medium"
            }
        },
        {
            "inputs": {
                "message": "¿Cuáles fueron las ventas del mes pasado?",
                "conversation_id": "eval_003",
                "customer_data": {"user_id": "admin_user"}
            },
            "outputs": {
                "expected_response": "Las ventas del mes pasado fueron de $125,000 con un total de 450 transacciones.",
                "expected_agent": "data_insights_agent"
            },
            "metadata": {
                "category": "analytics",
                "intent": "sales_data",
                "complexity": "complex"
            }
        },
        {
            "inputs": {
                "message": "No funciona mi pedido",
                "conversation_id": "eval_004",
                "customer_data": {"user_id": "test_user_3"}
            },
            "outputs": {
                "expected_response": "Lamento los problemas con tu pedido. ¿Puedes darme tu número de pedido para ayudarte?",
                "expected_agent": "support_agent"
            },
            "metadata": {
                "category": "support",
                "intent": "problem_resolution",
                "complexity": "medium"
            }
        },
        {
            "inputs": {
                "message": "¿Dónde está mi paquete? Número de seguimiento: TRK123456",
                "conversation_id": "eval_005",
                "customer_data": {"user_id": "test_user_4"}
            },
            "outputs": {
                "expected_response": "Tu paquete TRK123456 está en tránsito y llegará mañana antes de las 5 PM.",
                "expected_agent": "tracking_agent"
            },
            "metadata": {
                "category": "logistics",
                "intent": "package_tracking",
                "complexity": "simple"
            }
        },
        {
            "inputs": {
                "message": "¿Tienen descuentos en smartphones?",
                "conversation_id": "eval_006",
                "customer_data": {"user_id": "test_user_5"}
            },
            "outputs": {
                "expected_response": "¡Sí! Tenemos ofertas especiales en smartphones. iPhone 14: 15% desc, Samsung Galaxy S23: 20% desc.",
                "expected_agent": "promotions_agent"
            },
            "metadata": {
                "category": "promotions",
                "intent": "discount_inquiry",
                "complexity": "simple"
            }
        }
    ]
    
    # Initialize evaluation runner (this would need a real graph instance)
    print("Sample evaluation dataset created with {} examples".format(len(examples)))
    print("\nExample structure:")
    print(json.dumps(examples[0], indent=2, ensure_ascii=False))
    
    return examples


async def run_quality_evaluation_example():
    """Example of running quality evaluation on sample conversations."""
    
    print("\n" + "="*60)
    print("QUALITY EVALUATION EXAMPLE")
    print("="*60)
    
    evaluator = ConversationQualityEvaluator()
    
    # Sample conversations to evaluate
    test_conversations = [
        {
            "input": "¿Cuánto cuesta el iPhone 15?",
            "output": "El iPhone 15 Pro tiene un precio de $999 y está disponible en stock. ¿Te interesa conocer las especificaciones?",
            "context": {"agent_used": "product_agent"}
        },
        {
            "input": "Necesito ayuda",
            "output": "Error: No pude procesar tu solicitud",
            "context": {"agent_used": "fallback_agent"}
        },
        {
            "input": "¿Tienen laptops gaming?",
            "output": "Sí, tenemos excelentes laptops gaming. La ASUS ROG Strix por $1,299 y la MSI Gaming por $1,499. Ambas con tarjetas gráficas RTX 4060.",
            "context": {"agent_used": "product_agent"}
        }
    ]
    
    print("Evaluating {} sample conversations...\n".format(len(test_conversations)))
    
    for i, conversation in enumerate(test_conversations, 1):
        print(f"--- Conversation {i} ---")
        print(f"Input: {conversation['input']}")
        print(f"Output: {conversation['output']}")
        print(f"Agent: {conversation['context']['agent_used']}")
        
        # Evaluate quality
        metrics = evaluator.evaluate_response_quality(
            input_message=conversation["input"],
            actual_response=conversation["output"],
            context=conversation["context"]
        )
        
        print(f"Results:")
        print(f"  Accuracy: {metrics.accuracy:.2f}")
        print(f"  Relevance: {metrics.relevance:.2f}")
        print(f"  Helpfulness: {metrics.helpfulness:.2f}")
        print(f"  Coherence: {metrics.coherence:.2f}")
        print(f"  Agent Routing: {metrics.agent_routing_accuracy:.2f}")
        print(f"  Business Value: {metrics.business_value:.2f}")
        print(f"  Overall Score: {metrics.overall_score():.2f}")
        print()


async def run_monitoring_dashboard_example():
    """Example of using the monitoring dashboard."""
    
    print("\n" + "="*60)
    print("MONITORING DASHBOARD EXAMPLE")
    print("="*60)
    
    # Initialize monitoring dashboard
    dashboard = LangSmithMonitoringDashboard()
    
    print("Generating sample dashboard data...")
    
    # Generate dashboard data (this would normally pull from real LangSmith data)
    dashboard_data = await dashboard.generate_dashboard_data(hours_back=24)
    
    if "error" in dashboard_data:
        print(f"Note: {dashboard_data['error']}")
        print("This is expected without a real LangSmith connection.")
        
        # Show what the dashboard structure would look like
        print("\nExpected dashboard structure:")
        sample_structure = {
            "timestamp": datetime.utcnow().isoformat(),
            "period_hours": 24,
            "performance": {
                "avg_response_time": 850.5,
                "p95_response_time": 2100.0,
                "p99_response_time": 3500.0,
                "success_rate": 0.94,
                "error_rate": 0.06,
                "total_requests": 1247,
                "requests_per_minute": 0.87
            },
            "agents": [
                {
                    "agent_name": "product_agent",
                    "usage_count": 456,
                    "success_rate": 0.96,
                    "avg_response_time": 780.2,
                    "routing_accuracy": 0.89,
                    "business_value_score": 0.85
                },
                {
                    "agent_name": "support_agent", 
                    "usage_count": 234,
                    "success_rate": 0.91,
                    "avg_response_time": 950.1,
                    "routing_accuracy": 0.87,
                    "business_value_score": 0.72
                }
            ],
            "quality": {
                "avg_accuracy": 0.82,
                "avg_relevance": 0.85,
                "avg_helpfulness": 0.79,
                "avg_coherence": 0.88,
                "overall_quality_score": 0.84
            },
            "health_status": "healthy",
            "alerts": {
                "new": [],
                "recent": [],
                "total_unresolved": 0
            }
        }
        print(json.dumps(sample_structure, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(dashboard_data, indent=2, ensure_ascii=False))


async def continuous_evaluation_example():
    """Example of running continuous evaluation."""
    
    print("\n" + "="*60)
    print("CONTINUOUS EVALUATION EXAMPLE")
    print("="*60)
    
    # This would require a real graph instance and LangSmith data
    print("Continuous evaluation monitors system performance over time.")
    print("It would:")
    print("1. Pull recent conversations from LangSmith")
    print("2. Evaluate them for quality metrics")
    print("3. Compare against baselines and thresholds")
    print("4. Generate alerts if metrics decline")
    print("5. Provide recommendations for improvement")
    
    print("\nExample output:")
    sample_continuous_eval = {
        "status": "completed",
        "period": "Last 24 hours",
        "conversations_analyzed": 127,
        "metrics": {
            "accuracy": 0.83,
            "relevance": 0.86,
            "helpfulness": 0.81,
            "coherence": 0.89,
            "agent_routing_accuracy": 0.88,
            "business_value": 0.79,
            "overall_score": 0.84
        },
        "trends": {
            "accuracy_change": "+2.3%",
            "response_time_change": "-5.1%",
            "error_rate_change": "+0.8%"
        },
        "recommendations": [
            "Agent routing accuracy slightly down - review intent classification",
            "Response times improved - good optimization work",
            "Consider expanding training data for edge cases"
        ]
    }
    print(json.dumps(sample_continuous_eval, indent=2, ensure_ascii=False))


async def setup_langsmith_integration():
    """Show how to set up LangSmith integration."""
    
    print("\n" + "="*60)
    print("LANGSMITH SETUP GUIDE")
    print("="*60)
    
    print("1. Environment Variables Setup:")
    print("   Add these to your .env file:")
    print("   LANGSMITH_API_KEY=your_api_key_here")
    print("   LANGSMITH_PROJECT=conversashop-production")
    print("   LANGSMITH_TRACING_ENABLED=true")
    print()
    
    print("2. Initialize tracing in your code:")
    print("   ```python")
    print("   from app.config.langsmith_config import get_tracer")
    print("   tracer = get_tracer()")
    print("   ```")
    print()
    
    print("3. Use tracing decorators:")
    print("   ```python")
    print("   from app.agents.langgraph_system.utils.tracing import trace_async_method")
    print("   ")
    print("   @trace_async_method(name='my_agent', run_type='agent')")
    print("   async def my_agent_method(self, message: str):")
    print("       # Your agent logic here")
    print("       pass")
    print("   ```")
    print()
    
    print("4. Set up evaluation:")
    print("   ```python")
    print("   from app.evaluation import LangSmithEvaluationRunner")
    print("   ")
    print("   runner = LangSmithEvaluationRunner(your_graph)")
    print("   results = await runner.run_evaluation('your_dataset')")
    print("   ```")
    print()
    
    print("5. Use monitoring dashboard:")
    print("   ```python")
    print("   from app.monitoring import LangSmithMonitoringDashboard")
    print("   ")
    print("   dashboard = LangSmithMonitoringDashboard()")
    print("   metrics = await dashboard.generate_dashboard_data()")
    print("   ```")


async def main():
    """Run all examples."""
    print("ConversaShop LangSmith Integration Examples")
    print("=" * 50)
    
    try:
        # Check if LangSmith is configured
        tracer = get_tracer()
        if tracer.config.api_key:
            print(f"✅ LangSmith configured for project: {tracer.config.project_name}")
        else:
            print("⚠️  LangSmith API key not found - examples will show structure only")
        
        print()
        
        # Run examples
        await create_sample_evaluation_dataset()
        await run_quality_evaluation_example()
        await run_monitoring_dashboard_example()
        await continuous_evaluation_example()
        await setup_langsmith_integration()
        
        print("\n" + "="*60)
        print("EXAMPLES COMPLETED")
        print("="*60)
        print("Next steps:")
        print("1. Set up your LangSmith API key")
        print("2. Run your ConversaShop application with tracing enabled")
        print("3. Create evaluation datasets with real conversations")
        print("4. Set up monitoring dashboards")
        print("5. Configure alerts and thresholds")
        
    except Exception as e:
        print(f"Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())