# utils/kubectl_client.py
# Backward compatibility alias for KubectlClient
# The actual implementation is in k8s_client.py

from utils.k8s_client import K8sClient, K8sClientError


class KubectlClient(K8sClient):
    """
    Alias for K8sClient for backward compatibility.
    Use K8sClient directly in new code.
    """
    pass


__all__ = ["KubectlClient", "K8sClientError"]
