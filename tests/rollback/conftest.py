import os
import pytest
from kubernetes import client, config


@pytest.fixture(scope="session")
def k8s_apps():
    """Kubernetes AppsV1 клиент."""
    if os.environ.get("KUBECONFIG"):
        config.load_kube_config()
    else:
        config.load_incluster_config()
    return client.CustomObjectsApi()


@pytest.fixture(scope="session")
def namespace():
    return os.environ.get("K8S_NAMESPACE", "ml-platform")


@pytest.fixture(scope="session")
def gateway_url():
    return os.environ.get("GATEWAY_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def prometheus_url():
    return os.environ.get("PROMETHEUS_URL", "http://localhost:9090")