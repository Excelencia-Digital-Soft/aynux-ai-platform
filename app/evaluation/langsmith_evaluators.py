"""
LangSmith evaluation framework for ConversaShop.
Custom evaluators for conversation quality, agent performance, and business metrics.
"""

import asyncio
import json
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime, timedelta
import logging

from langsmith import Client
from langsmith.schemas import Dataset, Example, Run
from langsmith.evaluation import evaluate, EvaluationResult
from pydantic import BaseModel, Field

from app.config.langsmith_config import get_tracer
from app.agents.langgraph_system.graph import EcommerceAssistantGraph

logger = logging.getLogger(__name__)


class EvaluationMetrics(BaseModel):
    """Container for evaluation metrics."""
    
    accuracy: float = Field(description="Response accuracy (0.0 to 1.0)")
    relevance: float = Field(description="Response relevance (0.0 to 1.0)")
    helpfulness: float = Field(description="Response helpfulness (0.0 to 1.0)")
    coherence: float = Field(description="Response coherence (0.0 to 1.0)")
    agent_routing_accuracy: float = Field(description="Correct agent routing (0.0 to 1.0)")
    response_time_ms: Optional[float] = Field(description="Response time in milliseconds")
    token_count: Optional[int] = Field(description="Total tokens used")
    business_value: float = Field(description="Business value score (0.0 to 1.0)")
    
    def overall_score(self) -> float:
        """Calculate overall weighted score."""
        return (
            self.accuracy * 0.25 +
            self.relevance * 0.20 +
            self.helpfulness * 0.20 +
            self.coherence * 0.15 +
            self.agent_routing_accuracy * 0.10 +
            self.business_value * 0.10
        )


class ConversationQualityEvaluator:
    """
    Evaluates the quality of conversations in the ConversaShop system.
    """
    
    def __init__(self):
        """Initialize the evaluator."""
        self.tracer = get_tracer()
    
    def evaluate_response_quality(
        self, 
        input_message: str, 
        actual_response: str, 
        expected_response: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> EvaluationMetrics:
        """
        Evaluate the quality of a single response.
        
        Args:
            input_message: User's input message
            actual_response: System's actual response
            expected_response: Expected response (if available)
            context: Additional context for evaluation
            
        Returns:
            EvaluationMetrics with quality scores
        """
        metrics = EvaluationMetrics(
            accuracy=self._evaluate_accuracy(input_message, actual_response, expected_response),
            relevance=self._evaluate_relevance(input_message, actual_response),
            helpfulness=self._evaluate_helpfulness(input_message, actual_response),
            coherence=self._evaluate_coherence(actual_response),
            agent_routing_accuracy=self._evaluate_agent_routing(input_message, context),
            business_value=self._evaluate_business_value(input_message, actual_response, context)
        )
        
        return metrics
    
    def _evaluate_accuracy(
        self, 
        input_message: str, 
        actual_response: str, 
        expected_response: Optional[str] = None
    ) -> float:
        """Evaluate response accuracy."""
        if not expected_response:
            # Use heuristics for accuracy evaluation
            score = 0.7  # Base score
            
            # Check if response addresses the question
            if self._contains_relevant_keywords(input_message, actual_response):
                score += 0.2
            
            # Check for error messages or fallback responses
            error_indicators = [
                "error", "problema", "disculpa", "no pude", "lo siento"
            ]
            if any(indicator in actual_response.lower() for indicator in error_indicators):
                score -= 0.3
            
            return max(0.0, min(1.0, score))
        else:
            # Compare with expected response (simplified similarity)
            similarity = self._calculate_similarity(actual_response, expected_response)
            return similarity
    
    def _evaluate_relevance(self, input_message: str, actual_response: str) -> float:
        """Evaluate response relevance to the input."""
        # Extract keywords from input
        input_keywords = self._extract_keywords(input_message.lower())
        response_keywords = self._extract_keywords(actual_response.lower())
        
        # Calculate keyword overlap
        if not input_keywords:
            return 0.5  # Neutral score if no keywords
            
        overlap = len(set(input_keywords) & set(response_keywords))
        relevance = overlap / len(input_keywords)
        
        return min(1.0, relevance)
    
    def _evaluate_helpfulness(self, input_message: str, actual_response: str) -> float:
        """Evaluate how helpful the response is."""
        helpful_indicators = [
            "puedes", "te ayudo", "encontré", "disponible", "precio", "$",
            "stock", "categoría", "producto", "información"
        ]
        
        unhelpful_indicators = [
            "no entiendo", "no puedo", "error", "problema", "disculpa"
        ]
        
        score = 0.6  # Base score
        
        # Check for helpful indicators
        helpful_count = sum(1 for indicator in helpful_indicators 
                           if indicator in actual_response.lower())
        score += helpful_count * 0.1
        
        # Check for unhelpful indicators
        unhelpful_count = sum(1 for indicator in unhelpful_indicators 
                             if indicator in actual_response.lower())
        score -= unhelpful_count * 0.2
        
        return max(0.0, min(1.0, score))
    
    def _evaluate_coherence(self, actual_response: str) -> float:
        """Evaluate response coherence and structure."""
        score = 0.7  # Base score
        
        # Check for completeness (not cut off)
        if actual_response.endswith('.') or actual_response.endswith('?'):
            score += 0.1
        
        # Check length (too short might be incoherent)
        if len(actual_response.split()) < 5:
            score -= 0.2
        elif len(actual_response.split()) > 100:
            score -= 0.1  # Too long might be verbose
        
        # Check for repeated words (sign of generation issues)
        words = actual_response.lower().split()
        if len(words) != len(set(words)):
            repetition_ratio = (len(words) - len(set(words))) / len(words)
            score -= repetition_ratio * 0.3
        
        return max(0.0, min(1.0, score))
    
    def _evaluate_agent_routing(
        self, 
        input_message: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> float:
        """Evaluate if the correct agent was selected."""
        if not context or "agent_used" not in context:
            return 0.5  # Neutral score if no agent info
        
        agent_used = context["agent_used"]
        expected_agent = self._determine_expected_agent(input_message)
        
        if agent_used == expected_agent:
            return 1.0
        elif self._are_similar_agents(agent_used, expected_agent):
            return 0.7  # Partial credit for related agents
        else:
            return 0.3
    
    def _evaluate_business_value(
        self, 
        input_message: str, 
        actual_response: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> float:
        """Evaluate business value of the response."""
        score = 0.5  # Base score
        
        # High value indicators
        high_value_indicators = [
            "comprar", "precio", "stock", "disponible", "pedido", "orden"
        ]
        
        # Check if response drives business value
        if any(indicator in actual_response.lower() for indicator in high_value_indicators):
            score += 0.3
        
        # Check if it provides product information
        if "producto" in actual_response.lower() or "$" in actual_response:
            score += 0.2
        
        return min(1.0, score)
    
    def _contains_relevant_keywords(self, input_message: str, response: str) -> bool:
        """Check if response contains keywords relevant to input."""
        input_keywords = self._extract_keywords(input_message.lower())
        response_lower = response.lower()
        
        return any(keyword in response_lower for keyword in input_keywords)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from text."""
        # Simple keyword extraction (can be enhanced with NLP)
        stopwords = {
            "el", "la", "de", "que", "y", "a", "en", "un", "es", "se", "no",
            "te", "lo", "le", "da", "su", "por", "son", "con", "una", "su",
            "al", "del", "las", "los", "me", "mi", "tu", "si", "como"
        }
        
        words = text.split()
        keywords = [word for word in words if word not in stopwords and len(word) > 2]
        return keywords[:10]  # Limit to top 10 keywords
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts."""
        # Simple Jaccard similarity
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def _determine_expected_agent(self, input_message: str) -> str:
        """Determine which agent should handle the message."""
        message_lower = input_message.lower()
        
        # Product queries
        if any(keyword in message_lower for keyword in [
            "producto", "precio", "stock", "disponible", "cuánto cuesta"
        ]):
            return "product_agent"
        
        # Category queries
        if any(keyword in message_lower for keyword in [
            "categoría", "tipo", "clase", "grupo"
        ]):
            return "category_agent"
        
        # Support queries
        if any(keyword in message_lower for keyword in [
            "ayuda", "problema", "soporte", "cómo"
        ]):
            return "support_agent"
        
        # Default fallback
        return "fallback_agent"
    
    def _are_similar_agents(self, agent1: str, agent2: str) -> bool:
        """Check if two agents are functionally similar."""
        similar_groups = [
            {"product_agent", "category_agent"},
            {"support_agent", "fallback_agent"},
            {"tracking_agent", "invoice_agent"}
        ]
        
        for group in similar_groups:
            if agent1 in group and agent2 in group:
                return True
        
        return False


class LangSmithEvaluationRunner:
    """
    Runs evaluations using LangSmith's evaluation framework.
    """
    
    def __init__(self, graph: EcommerceAssistantGraph):
        """
        Initialize evaluation runner.
        
        Args:
            graph: The ConversaShop graph instance to evaluate
        """
        self.graph = graph
        self.tracer = get_tracer()
        self.client = self.tracer.client
        self.evaluator = ConversationQualityEvaluator()
    
    async def create_evaluation_dataset(
        self,
        dataset_name: str,
        examples: List[Dict[str, Any]],
        description: str = ""
    ) -> Optional[Dataset]:
        """
        Create an evaluation dataset in LangSmith.
        
        Args:
            dataset_name: Name for the dataset
            examples: List of example inputs and expected outputs
            description: Description of the dataset
            
        Returns:
            Created dataset or None if failed
        """
        if not self.client:
            logger.warning("LangSmith client not available")
            return None
        
        try:
            # Create the dataset
            dataset = self.client.create_dataset(
                dataset_name=dataset_name,
                description=description
            )
            
            # Add examples to the dataset
            for example in examples:
                self.client.create_example(
                    inputs=example.get("inputs", {}),
                    outputs=example.get("outputs"),
                    metadata=example.get("metadata"),
                    dataset_id=dataset.id
                )
            
            logger.info(f"Created dataset {dataset_name} with {len(examples)} examples")
            return dataset
            
        except Exception as e:
            logger.error(f"Failed to create evaluation dataset: {e}")
            return None
    
    async def run_evaluation(
        self,
        dataset_name: str,
        evaluators: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Run evaluation on a dataset.
        
        Args:
            dataset_name: Name of the dataset to evaluate
            evaluators: List of evaluators to use
            
        Returns:
            Evaluation results
        """
        if not self.client:
            logger.warning("LangSmith client not available")
            return {}
        
        try:
            # Define the prediction function
            async def predict(inputs: Dict[str, Any]) -> Dict[str, Any]:
                """Prediction function for evaluation."""
                message = inputs.get("message", "")
                conversation_id = inputs.get("conversation_id", f"eval_{datetime.now().isoformat()}")
                
                result = await self.graph.process_message(
                    message=message,
                    conversation_id=conversation_id,
                    customer_data=inputs.get("customer_data")
                )
                
                return {
                    "response": result["response"],
                    "agent_used": result["agent_used"],
                    "metadata": {
                        "requires_human": result.get("requires_human", False),
                        "is_complete": result.get("is_complete", False),
                    }
                }
            
            # Define evaluators
            def quality_evaluator(run: Run, example: Example) -> EvaluationResult:
                """Custom quality evaluator."""
                inputs = example.inputs
                outputs = example.outputs
                prediction = run.outputs
                
                if not prediction:
                    return EvaluationResult(
                        key="quality",
                        score=0.0,
                        comment="No prediction available"
                    )
                
                metrics = self.evaluator.evaluate_response_quality(
                    input_message=inputs.get("message", ""),
                    actual_response=prediction.get("response", ""),
                    expected_response=outputs.get("expected_response") if outputs else None,
                    context=prediction.get("metadata", {})
                )
                
                return EvaluationResult(
                    key="quality",
                    score=metrics.overall_score(),
                    comment=f"Accuracy: {metrics.accuracy:.2f}, Relevance: {metrics.relevance:.2f}, "
                           f"Helpfulness: {metrics.helpfulness:.2f}",
                    metadata={
                        "accuracy": metrics.accuracy,
                        "relevance": metrics.relevance,
                        "helpfulness": metrics.helpfulness,
                        "coherence": metrics.coherence,
                        "agent_routing_accuracy": metrics.agent_routing_accuracy,
                        "business_value": metrics.business_value,
                    }
                )
            
            # Run evaluation
            results = evaluate(
                predict,
                data=dataset_name,
                evaluators=[quality_evaluator],
                experiment_prefix="conversashop_eval",
                max_concurrency=3,  # Limit concurrency to avoid overwhelming the system
            )
            
            return {
                "dataset_name": dataset_name,
                "results": results,
                "summary": self._summarize_results(results)
            }
            
        except Exception as e:
            logger.error(f"Failed to run evaluation: {e}")
            return {"error": str(e)}
    
    def _summarize_results(self, results) -> Dict[str, Any]:
        """Summarize evaluation results."""
        # This would process the LangSmith evaluation results
        # and create a summary with key metrics
        return {
            "total_examples": len(results) if hasattr(results, '__len__') else 0,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "completed"
        }
    
    async def continuous_evaluation(
        self,
        hours_lookback: int = 24,
        min_conversations: int = 10
    ) -> Dict[str, Any]:
        """
        Run continuous evaluation on recent conversations.
        
        Args:
            hours_lookback: Hours to look back for conversations
            min_conversations: Minimum number of conversations needed
            
        Returns:
            Evaluation results
        """
        if not self.client:
            logger.warning("LangSmith client not available")
            return {}
        
        try:
            # Get recent runs from LangSmith
            since = datetime.utcnow() - timedelta(hours=hours_lookback)
            
            runs = list(self.client.list_runs(
                project_name=self.tracer.config.project_name,
                start_time=since,
                limit=min_conversations * 2  # Get more than minimum to filter
            ))
            
            if len(runs) < min_conversations:
                return {
                    "status": "insufficient_data",
                    "message": f"Only {len(runs)} conversations found, need at least {min_conversations}",
                    "runs_found": len(runs)
                }
            
            # Analyze the runs
            metrics = []
            for run in runs[:min_conversations]:  # Use only the required number
                if run.inputs and run.outputs:
                    try:
                        quality = self.evaluator.evaluate_response_quality(
                            input_message=run.inputs.get("message", ""),
                            actual_response=run.outputs.get("response", ""),
                            context={
                                "agent_used": run.outputs.get("agent_used"),
                                "response_time_ms": run.latency,
                            }
                        )
                        metrics.append(quality)
                    except Exception as e:
                        logger.warning(f"Failed to evaluate run {run.id}: {e}")
            
            if not metrics:
                return {
                    "status": "no_evaluable_runs",
                    "message": "No runs could be evaluated"
                }
            
            # Calculate aggregate metrics
            avg_metrics = {
                "accuracy": sum(m.accuracy for m in metrics) / len(metrics),
                "relevance": sum(m.relevance for m in metrics) / len(metrics),
                "helpfulness": sum(m.helpfulness for m in metrics) / len(metrics),
                "coherence": sum(m.coherence for m in metrics) / len(metrics),
                "agent_routing_accuracy": sum(m.agent_routing_accuracy for m in metrics) / len(metrics),
                "business_value": sum(m.business_value for m in metrics) / len(metrics),
                "overall_score": sum(m.overall_score() for m in metrics) / len(metrics),
            }
            
            return {
                "status": "completed",
                "period": f"Last {hours_lookback} hours",
                "conversations_analyzed": len(metrics),
                "metrics": avg_metrics,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to run continuous evaluation: {e}")
            return {"status": "error", "error": str(e)}


# Export main classes
__all__ = [
    "EvaluationMetrics",
    "ConversationQualityEvaluator", 
    "LangSmithEvaluationRunner"
]