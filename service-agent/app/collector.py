import logging
from datetime import datetime, timezone
from kubernetes import client
from kubernetes.client.rest import ApiException
from .kube_config import get_k8s_api

logger = logging.getLogger(__name__)

def _to_aware(dt: datetime) -> datetime:
    """
    Convert a datetime to an aware datetime in UTC.
    If dt is None → returns datetime.min with UTC tzinfo.
    If dt is naive (no tzinfo) → assume UTC.
    If dt is aware → convert to UTC.
    """
    if dt is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def get_pod_logs(api: client.CoreV1Api, namespace: str, pod_name: str, trigger_reason: str) -> str:
    """
    Fetches the logs from a pod, intelligently deciding whether to
    look at the 'previous' or 'current' container based on the trigger reason.
    """
    # Strategy 1: For 'CrashLoopBackOff', the error is likely in the PREVIOUS container.
    if trigger_reason == "CrashLoopBackOff":
        try:
            logs = api.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                previous=True,
                tail_lines=100
            )
            return logs
        except ApiException as e:
            logger.warning(f"Could not fetch previous logs for {namespace}/{pod_name} (Reason: {e.reason}). Falling back to current.")
            # fallback to current logs
            pass

    # Strategy 2: For other reasons, try CURRENT logs, else fallback to PREVIOUS
    try:
        logs = api.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            previous=False,
            tail_lines=100
        )
        return logs
    except ApiException as e:
        logger.error(f"Could not fetch current logs for {namespace}/{pod_name}: {e.reason}")
        try:
            logs = api.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                previous=True,
                tail_lines=100
            )
            logger.warning(f"Fallback to previous=True succeeded for {namespace}/{pod_name}")
            return logs
        except ApiException as e2:
            logger.error(f"Could not fetch ANY logs for {namespace}/{pod_name}: {e2.reason}")
            return f"Error: Could not fetch any logs. Reason: {e2.reason}"

def get_pod_events(api: client.CoreV1Api, namespace: str, pod_name: str) -> str:
    """
    Fetches Kubernetes events for the given pod, sorts them by first_timestamp (UTC aware),
    and formats them into a readable string.
    """
    try:
        field_selector = f"involvedObject.name={pod_name}"
        events_list = api.list_namespaced_event(
            namespace=namespace,
            field_selector=field_selector,
            limit=20
        )

        if not events_list.items:
            return "No events found for this pod."

        formatted_events = ["--- Kubernetes Events ---"]

        # Sort by first_timestamp (UTC aware)
        sorted_events = sorted(
            events_list.items,
            key=lambda e: _to_aware(e.first_timestamp)
        )

        for event in sorted_events:
            raw_ts = event.last_timestamp or event.first_timestamp
            ts = _to_aware(raw_ts)
            time_str = ts.strftime('%Y-%m-%d %H:%M:%S %Z') if ts else "N/A"

            formatted_events.append(
                f"Time: {time_str}\n"
                f"Type: {event.type}\n"
                f"Reason: {event.reason}\n"
                f"Message: {event.message}\n"
                f"-----------------"
            )

        return "\n".join(formatted_events)

    except ApiException as e:
        logger.error(f"Could not fetch events for {namespace}/{pod_name}: {e.reason}")
        return f"Error: Could not fetch events. Reason: {e.reason}"
    except Exception as e:
        logger.error(f"An unexpected error occurred formatting events for {namespace}/{pod_name}: {e}", exc_info=True)
        return f"Error: An unexpected error occurred while formatting events: {e}"

def collect_pod_data(namespace: str, pod_name: str, trigger_reason: str) -> dict:
    """
    Main function for this module.
    Collects all necessary data for the AI agent.
    """
    logger.info(f"Collector starting for {namespace}/{pod_name} (Reason: {trigger_reason})")
    try:
        api = get_k8s_api()

        logs = get_pod_logs(api, namespace, pod_name, trigger_reason)
        events = get_pod_events(api, namespace, pod_name)

        return {
            "logs": logs,
            "events": events
        }

    except Exception as e:
        logger.error(f"Error during data collection for {namespace}/{pod_name}: {e}", exc_info=True)
        return {
            "logs": "Error: Data collection failed.",
            "events": f"Error: {e}"
        }
