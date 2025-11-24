"""
Metrics Tracker - Tracks and analyzes performance metrics for agent execution
"""

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional


class MetricsTracker:
    """Tracks performance metrics during agent execution"""

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset all metrics"""
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.steps: List[Dict[str, Any]] = []
        self.agent_visits: Dict[str, int] = defaultdict(int)
        self.step_timeline: List[Dict[str, Any]] = []
        self.total_steps = 0
        self.errors: List[Dict[str, Any]] = []

    def start_conversation(self):
        """Mark the start of a conversation"""
        self.reset()
        self.start_time = datetime.now()

    def end_conversation(self):
        """Mark the end of a conversation"""
        self.end_time = datetime.now()

    def record_step(self, node: str, timestamp: str):
        """
        Record a single execution step.

        Args:
            node: Node name that was executed
            timestamp: ISO format timestamp
        """
        self.total_steps += 1

        # Update agent visits
        if node:
            self.agent_visits[node] += 1

        # Record step
        step_data = {"step": self.total_steps, "node": node, "timestamp": timestamp, "recorded_at": datetime.now()}

        self.steps.append(step_data)

        # Calculate duration if we have a previous step
        if len(self.steps) > 1:
            prev_step = self.steps[-2]
            current_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            prev_time = datetime.fromisoformat(prev_step["timestamp"].replace("Z", "+00:00"))
            duration = (current_time - prev_time).total_seconds()

            step_data["duration"] = duration

        self.step_timeline.append(step_data)

    def record_error(self, error: str, node: Optional[str] = None):
        """
        Record an error that occurred during execution.

        Args:
            error: Error message
            node: Node where error occurred (optional)
        """
        self.errors.append({"error": error, "node": node, "timestamp": datetime.now().isoformat()})

    def get_total_time(self) -> float:
        """
        Get total execution time in seconds.

        Returns:
            Total time in seconds, or 0 if not started/ended
        """
        if not self.start_time or not self.end_time:
            return 0.0

        return (self.end_time - self.start_time).total_seconds()

    def get_avg_step_time(self) -> float:
        """
        Get average time per step.

        Returns:
            Average step time in seconds
        """
        if self.total_steps == 0:
            return 0.0

        total_time = self.get_total_time()
        return total_time / self.total_steps

    def get_agent_visit_frequency(self) -> Dict[str, int]:
        """
        Get frequency of visits per agent.

        Returns:
            Dictionary mapping agent names to visit counts
        """
        return dict(self.agent_visits)

    def get_most_visited_agent(self) -> Optional[str]:
        """
        Get the most frequently visited agent.

        Returns:
            Agent name or None if no visits
        """
        if not self.agent_visits:
            return None

        return max(self.agent_visits.items(), key=lambda x: x[1])[0]

    def get_execution_path(self) -> List[str]:
        """
        Get the execution path as a list of node names.

        Returns:
            List of node names in execution order
        """
        return [step["node"] for step in self.steps if step.get("node")]

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get all metrics as a dictionary.

        Returns:
            Dictionary containing all metrics
        """
        return {
            "total_time": self.get_total_time(),
            "total_steps": self.total_steps,
            "avg_step_time": self.get_avg_step_time(),
            "agent_visits": self.get_agent_visit_frequency(),
            "most_visited_agent": self.get_most_visited_agent(),
            "execution_path": self.get_execution_path(),
            "step_timeline": self.step_timeline,
            "errors": self.errors,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }

    def get_step_durations(self) -> List[float]:
        """
        Get list of step durations.

        Returns:
            List of durations in seconds
        """
        return [step.get("duration", 0) for step in self.steps if "duration" in step]

    def get_slowest_step(self) -> Optional[Dict[str, Any]]:
        """
        Get the slowest execution step.

        Returns:
            Step dictionary or None
        """
        steps_with_duration = [step for step in self.steps if "duration" in step]

        if not steps_with_duration:
            return None

        return max(steps_with_duration, key=lambda x: x["duration"])

    def get_fastest_step(self) -> Optional[Dict[str, Any]]:
        """
        Get the fastest execution step.

        Returns:
            Step dictionary or None
        """
        steps_with_duration = [step for step in self.steps if "duration" in step]

        if not steps_with_duration:
            return None

        return min(steps_with_duration, key=lambda x: x["duration"])

    def get_summary(self) -> str:
        """
        Get a human-readable summary of metrics.

        Returns:
            Summary string
        """
        metrics = self.get_metrics()

        summary_lines = [
            "=== Resumen de Métricas ===",
            f"Tiempo Total: {metrics['total_time']:.2f}s",
            f"Pasos Totales: {metrics['total_steps']}",
            f"Tiempo Promedio/Paso: {metrics['avg_step_time']:.2f}s",
            f"Agente Más Visitado: {metrics['most_visited_agent'] or 'N/A'}",
            f"Errores: {len(metrics['errors'])}",
            "",
            "Ruta de Ejecución:",
            " → ".join(metrics["execution_path"]),
        ]

        return "\n".join(summary_lines)

    def export_to_dict(self) -> Dict[str, Any]:
        """
        Export all metrics to a dictionary for serialization.

        Returns:
            Complete metrics dictionary
        """
        return self.get_metrics()
