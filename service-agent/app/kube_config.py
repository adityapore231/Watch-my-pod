import logging
from kubernetes import client, config
from kubernetes.client.api_client import ApiClient
from kubernetes.client.configuration import Configuration
from functools import lru_cache

logger = logging.getLogger(__name__)

# Use @lru_cache to act as a singleton
# This ensures we only load the config and create the client once
@lru_cache(maxsize=1)
def get_k8s_api() -> client.CoreV1Api:
    """
    Loads Kubernetes configuration and returns a CoreV1Api client.
    
    Priority:
    1. In-cluster config (if running in a pod)
    2. Kubeconfig from file (for local development)
    """
    try:
        config.load_incluster_config()
        logger.info("Loaded in-cluster Kubernetes config.")
    except config.ConfigException:
        try:
            config.load_kube_config()
            logger.info("Loaded out-of-cluster (kubeconfig) Kubernetes config.")
        except config.ConfigException as e:
            logger.error(f"Could not load any Kubernetes config: {e}")
            raise
    
    # We need to configure the ApiClient to handle retries
    # This makes our client more robust to temporary network issues
    configuration = Configuration.get_default_copy()
    configuration.retries = 3 # Add 3 retries
    
    api_client = ApiClient(configuration=configuration)
    return client.CoreV1Api(api_client)