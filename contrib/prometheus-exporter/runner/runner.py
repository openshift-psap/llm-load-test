"""
Runner that discovers models in a Kubernetes/OpenShift cluster,
runs llm-load-test against each, and writes output JSON files
for the exporter to serve as Prometheus metrics.
"""

import base64
import logging
import os
import subprocess
import sys
import tempfile
import time

import yaml
from kubernetes import client, config

LOG = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# ---------------------------------------------------------------------------
# Kubernetes setup
# ---------------------------------------------------------------------------

try:
    config.load_incluster_config()
except config.ConfigException:
    try:
        config.load_kube_config()
    except config.ConfigException as exc:
        LOG.error("Could not configure Kubernetes client: %s", exc)
        sys.exit(1)

v1 = client.CoreV1Api()

# ---------------------------------------------------------------------------
# Constants / env-driven config
# ---------------------------------------------------------------------------

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/shared_data/output")
DATASET_PATH = os.environ.get("DATASET_PATH", "/app/datasets/dataset.jsonl")
WAIT_TIME = int(os.environ.get("WAIT_TIME", "120"))
CONCURRENCY = int(os.environ.get("CONCURRENCY", "8"))
DURATION = int(os.environ.get("DURATION", "30"))
STREAMING = os.environ.get("STREAMING", "true").lower() == "true"
ENDPOINT = os.environ.get("ENDPOINT", "/v1/chat/completions")
LOG_LEVEL = os.environ.get("LLM_LOAD_TEST_LOG_LEVEL", "info")


def build_config(model_name: str, host_url: str, namespace: str,
                 auth_token: str | None = None) -> dict:
    """Build a llm-load-test config dict for a single model."""
    cfg = {
        "plugin": "openai_plugin",
        "plugin_options": {
            "host": host_url,
            "model_name": model_name,
            "streaming": STREAMING,
            "endpoint": ENDPOINT,
        },
        "load_options": {
            "type": "constant",
            "concurrency": CONCURRENCY,
            "duration": DURATION,
        },
        "dataset": {
            "file": DATASET_PATH,
        },
        "output": {
            "dir": OUTPUT_DIR,
            "file": f"{model_name}_{namespace}.json",
        },
    }

    if auth_token:
        cfg["plugin_options"]["authorization"] = auth_token

    return cfg


def get_auth_token(model_name: str, namespace: str) -> str | None:
    """Retrieve the bearer token from a KServe service-account secret."""
    try:
        secret = v1.read_namespaced_secret(
            f"default-name-{model_name}-sa", namespace
        )
        return base64.b64decode(secret.data["token"]).decode("utf-8")
    except Exception as exc:
        LOG.warning("Could not read auth secret for %s/%s: %s",
                    namespace, model_name, exc)
        return None


def _discover_service_url(model_name: str, namespace: str) -> str | None:
    """Discover the internal service URL for a KServe InferenceService.

    Looks up Services labelled with serving.kserve.io/inferenceservice and
    picks the predictor service, returning a fully-qualified cluster URL
    with the correct protocol and port.
    """
    try:
        services = v1.list_namespaced_service(
            namespace,
            label_selector=f"serving.kserve.io/inferenceservice={model_name}",
        )
    except Exception as exc:
        LOG.warning("Could not list services for %s/%s: %s",
                    namespace, model_name, exc)
        return None

    predictor_svc = None
    for svc in services.items:
        name = svc.metadata.name
        if name.endswith("-predictor"):
            predictor_svc = svc
            break
    if predictor_svc is None:
        for svc in services.items:
            if not svc.metadata.name.endswith("-metrics"):
                predictor_svc = svc
                break
    if predictor_svc is None or not predictor_svc.spec.ports:
        return None

    svc_name = predictor_svc.metadata.name
    port_obj = predictor_svc.spec.ports[0]
    port = port_obj.port
    port_name = (port_obj.name or "").lower()

    if port in (443, 8443) or "https" in port_name or "tls" in port_name:
        protocol = "https"
    else:
        protocol = "http"

    host = f"{svc_name}.{namespace}.svc.cluster.local"
    if (protocol == "https" and port == 443) or (protocol == "http" and port == 80):
        return f"{protocol}://{host}"
    return f"{protocol}://{host}:{port}"


def run_load_test(cfg: dict) -> None:
    """Write a temporary config and invoke the ``load-test`` CLI."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as tmp:
        yaml.dump(cfg, tmp)
        config_path = tmp.name

    try:
        result = subprocess.run(
            ["load-test", "-c", config_path, "-log", LOG_LEVEL],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
        )
        if result.returncode != 0:
            LOG.error(
                "load-test failed (rc=%d) for %s:\nstdout: %s\nstderr: %s",
                result.returncode,
                cfg["plugin_options"]["model_name"],
                result.stdout[-500:] if result.stdout else "",
                result.stderr[-500:] if result.stderr else "",
            )
        else:
            LOG.info("load-test completed successfully for %s",
                     cfg["plugin_options"]["model_name"])
    except subprocess.TimeoutExpired:
        LOG.error("load-test timed out for %s",
                  cfg["plugin_options"]["model_name"])
    except FileNotFoundError:
        LOG.error(
            "load-test CLI not found. Make sure llm-load-test is installed."
        )
        sys.exit(1)
    finally:
        os.unlink(config_path)


def _remove_stale_files(active_files: set[str]) -> None:
    """Remove result files that don't correspond to any active model."""
    if not os.path.isdir(OUTPUT_DIR):
        return
    for filename in os.listdir(OUTPUT_DIR):
        if filename.endswith(".json") and filename not in active_files:
            filepath = os.path.join(OUTPUT_DIR, filename)
            try:
                os.remove(filepath)
                LOG.info("Removed stale result file: %s", filename)
            except OSError as exc:
                LOG.warning("Could not remove stale file %s: %s", filename, exc)


def discover_and_test_models() -> None:
    """Discover KServe InferenceService models and run load tests."""
    try:
        model_pods = v1.list_pod_for_all_namespaces(
            label_selector="serving.kserve.io/inferenceservice"
        )
    except Exception as exc:
        LOG.error("Failed to list model pods: %s", exc)
        return

    active_files: set[str] = set()

    for pod in model_pods.items:
        model_name = pod.metadata.labels.get(
            "serving.kserve.io/inferenceservice", "unknown"
        )
        namespace = pod.metadata.namespace

        # Only test pods that are Running and opted-in
        gather = pod.metadata.labels.get("gather_llm_metrics")
        if pod.status.phase != "Running" or not gather:
            LOG.debug(
                "Skipping %s/%s (phase=%s, gather_llm_metrics=%s)",
                namespace, model_name, pod.status.phase, gather,
            )
            continue

        active_files.add(f"{model_name}_{namespace}.json")

        # Check if token auth is required
        annotations = pod.metadata.annotations or {}
        enable_auth = (
            annotations.get("security.opendatahub.io/enable-auth") == "true"
        )
        auth_token = get_auth_token(model_name, namespace) if enable_auth else None

        host_url = _discover_service_url(model_name, namespace)
        if host_url is None:
            host_url = f"https://{model_name}.{namespace}.svc.cluster.local"
            LOG.warning("No predictor service found for %s/%s, falling back to %s",
                        namespace, model_name, host_url)

        LOG.info("Running load test for model %s in namespace %s (url=%s)",
                 model_name, namespace, host_url)

        cfg = build_config(model_name, host_url, namespace, auth_token)
        run_load_test(cfg)

        LOG.info("Completed load test for model %s in namespace %s",
                 model_name, namespace)

    _remove_stale_files(active_files)


def main() -> None:
    """Main loop: discover models and run load tests periodically."""
    LOG.info(
        "Starting runner (wait=%ds, concurrency=%d, duration=%ds)",
        WAIT_TIME, CONCURRENCY, DURATION,
    )

    while True:
        discover_and_test_models()
        LOG.info("Sleeping %d seconds until next run...", WAIT_TIME)
        time.sleep(WAIT_TIME)


if __name__ == "__main__":
    main()

