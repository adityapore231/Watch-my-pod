"""
Collector module for fetching logs and events from Kubernetes.
"""

import logging
from typing import Optional, List, Dict, Any
from kubernetes import client, config

logger = logging.getLogger(__name__)


class KubernetesCollector:
    """
    Collector for fetching pod logs and events from Kubernetes.
    """

    def __init__(self):
        """Initialize the Kubernetes collector."""
        logger.info("Initializing Kubernetes Collector...")
        try:
            # Try to load in-cluster config first
            config.load_incluster_config()
            logger.info("Loaded in-cluster Kubernetes config")
        except config.ConfigException:
            # Fall back to kubeconfig
            try:
                config.load_kube_config()
                logger.info("Loaded kubeconfig")
            except config.ConfigException as e:
                logger.error(f"Failed to load Kubernetes config: {e}")
                raise

        self.core_v1 = client.CoreV1Api()

    def get_pod_logs(
        self,
        namespace: str,
        pod_name: str,
        container: Optional[str] = None,
        tail_lines: int = 100
    ) -> str:
        """
        Fetch logs for a specific pod.

        Args:
            namespace: Kubernetes namespace
            pod_name: Name of the pod
            container: Optional container name
            tail_lines: Number of log lines to fetch

        Returns:
            Pod logs as string
        """
        try:
            logger.info(f"Fetching logs for pod {namespace}/{pod_name}")
            logs = self.core_v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                container=container,
                tail_lines=tail_lines
            )
            return logs
        except client.ApiException as e:
            logger.error(f"Error fetching pod logs: {e}")
            return ""

    def get_pod_events(
        self,
        namespace: str,
        pod_name: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch events related to a specific pod.

        Args:
            namespace: Kubernetes namespace
            pod_name: Name of the pod

        Returns:
            List of event dictionaries
        """
        try:
            logger.info(f"Fetching events for pod {namespace}/{pod_name}")
            field_selector = f"involvedObject.name={pod_name}"
            events = self.core_v1.list_namespaced_event(
                namespace=namespace,
                field_selector=field_selector
            )

            event_list = []
            for event in events.items:
                event_list.append({
                    "reason": event.reason,
                    "message": event.message,
                    "type": event.type,
                    "count": event.count,
                    "first_timestamp": event.first_timestamp,
                    "last_timestamp": event.last_timestamp,
                })

            return event_list
        except client.ApiException as e:
            logger.error(f"Error fetching pod events: {e}")
            return []

    def get_pod_status(
        self,
        namespace: str,
        pod_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get the current status of a pod.

        Args:
            namespace: Kubernetes namespace
            pod_name: Name of the pod

        Returns:
            Pod status dictionary or None
        """
        try:
            logger.info(f"Fetching status for pod {namespace}/{pod_name}")
            pod = self.core_v1.read_namespaced_pod(
                name=pod_name,
                namespace=namespace
            )

            return {
                "phase": pod.status.phase,
                "conditions": [
                    {
                        "type": condition.type,
                        "status": condition.status,
                        "reason": condition.reason,
                        "message": condition.message,
                    }
                    for condition in (pod.status.conditions or [])
                ],
                "container_statuses": [
                    {
                        "name": cs.name,
                        "ready": cs.ready,
                        "restart_count": cs.restart_count,
                        "state": str(cs.state),
                    }
                    for cs in (pod.status.container_statuses or [])
                ],
            }
        except client.ApiException as e:
            logger.error(f"Error fetching pod status: {e}")
            return None
