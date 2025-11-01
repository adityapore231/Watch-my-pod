"""
FastAPI server for receiving triggers from the Go monitor.
"""

import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional

from .agent import AIAgent
from .collector import KubernetesCollector
from .alerter import SlackAlerter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Watch-my-pod AI Agent",
    description="AI-powered Kubernetes pod monitoring and alerting service",
    version="0.1.0"
)

# Initialize components
ai_agent = AIAgent()
collector = KubernetesCollector()
alerter = SlackAlerter()


class PodEvent(BaseModel):
    """Model for pod event data."""
    pod_name: str
    namespace: str
    event_type: str
    phase: Optional[str] = None
    message: Optional[str] = None


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Watch-my-pod AI Agent",
        "status": "running",
        "version": "0.1.0"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/analyze")
async def analyze_pod_event(event: PodEvent):
    """
    Analyze a pod event and send alerts.

    Args:
        event: Pod event data

    Returns:
        Analysis results
    """
    try:
        logger.info(f"Received event for pod {event.namespace}/{event.pod_name}")

        # Collect additional data from Kubernetes
        pod_status = collector.get_pod_status(event.namespace, event.pod_name)
        pod_events = collector.get_pod_events(event.namespace, event.pod_name)
        pod_logs = collector.get_pod_logs(
            event.namespace,
            event.pod_name,
            tail_lines=100
        )

        # Prepare event data for analysis
        event_data = {
            "pod_name": event.pod_name,
            "namespace": event.namespace,
            "event_type": event.event_type,
            "phase": event.phase,
            "message": event.message,
            "status": pod_status,
            "events": pod_events,
            "logs": pod_logs[:1000] if pod_logs else "",  # Limit log size
        }

        # Analyze with AI agent
        analysis = ai_agent.analyze_pod_event(event_data)

        # Send alert to Slack
        alert_sent = alerter.send_alert(analysis)

        return {
            "success": True,
            "analysis": analysis,
            "alert_sent": alert_sent
        }

    except Exception as e:
        logger.error(f"Error analyzing pod event: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/summarize-logs")
async def summarize_logs(
    namespace: str,
    pod_name: str,
    tail_lines: int = 100
):
    """
    Fetch and summarize pod logs.

    Args:
        namespace: Kubernetes namespace
        pod_name: Name of the pod
        tail_lines: Number of log lines to fetch

    Returns:
        Log summary
    """
    try:
        logger.info(f"Summarizing logs for pod {namespace}/{pod_name}")

        # Fetch logs
        logs = collector.get_pod_logs(namespace, pod_name, tail_lines=tail_lines)

        if not logs:
            return {
                "success": False,
                "message": "No logs found or error fetching logs"
            }

        # Summarize with AI
        summary = ai_agent.summarize_logs(logs)

        return {
            "success": True,
            "pod_name": pod_name,
            "namespace": namespace,
            "summary": summary
        }

    except Exception as e:
        logger.error(f"Error summarizing logs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
