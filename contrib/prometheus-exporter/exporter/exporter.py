"""
Prometheus metrics exporter for llm-load-test results.

Reads JSON output files produced by the runner container and exposes
them as Prometheus gauge metrics on the /metrics endpoint.
"""

import json
import logging
import os

from flask import Flask
from prometheus_client import CollectorRegistry, Gauge, generate_latest

LOG = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/shared_data/output")

# ---------------------------------------------------------------------------
# Prometheus metrics registry
# ---------------------------------------------------------------------------

registry = CollectorRegistry()

LABEL_NAMES = ["model", "namespace"]

# Timing metrics: each has mean + P80/P90/P95/P99
TIMING_METRICS = {
    "tpot": "Time Per Output Token",
    "ttft": "Time to First Token",
    "itl": "Inter-Token Latency",
    "response_time": "Response Time",
    "tt_ack": "Time to Acknowledge",
}

PERCENTILES = [
    ("mean", "Mean", "mean"),
    ("p80", "P80", "percentile_80"),
    ("p90", "P90", "percentile_90"),
    ("p95", "P95", "percentile_95"),
    ("p99", "P99", "percentile_99"),
]

# timing_gauges[metric_key][suffix] = (Gauge, json_field)
timing_gauges: dict[str, dict[str, tuple]] = {}
for _mk, _ml in TIMING_METRICS.items():
    timing_gauges[_mk] = {}
    for _suffix, _label, _json_field in PERCENTILES:
        _name = f"llm_load_test_{_mk}_{_suffix}_ms"
        _desc = f"{_label} {_ml} (ms)"
        _g = Gauge(_name, _desc, labelnames=LABEL_NAMES, registry=registry)
        timing_gauges[_mk][_suffix] = (_g, _json_field)

# Scalar and token metrics
throughput_metric = Gauge(
    "llm_load_test_throughput_tokens_per_sec",
    "Throughput (tokens/sec)",
    labelnames=LABEL_NAMES,
    registry=registry,
)
total_requests_metric = Gauge(
    "llm_load_test_total_requests",
    "Total requests in the load test run",
    labelnames=LABEL_NAMES,
    registry=registry,
)
total_failures_metric = Gauge(
    "llm_load_test_total_failures",
    "Total failed requests",
    labelnames=LABEL_NAMES,
    registry=registry,
)
failure_rate_metric = Gauge(
    "llm_load_test_failure_rate_percent",
    "Percentage of failed requests",
    labelnames=LABEL_NAMES,
    registry=registry,
)
input_tokens_mean_metric = Gauge(
    "llm_load_test_input_tokens_mean",
    "Mean input tokens per request",
    labelnames=LABEL_NAMES,
    registry=registry,
)
output_tokens_mean_metric = Gauge(
    "llm_load_test_output_tokens_mean",
    "Mean output tokens per request",
    labelnames=LABEL_NAMES,
    registry=registry,
)

SCALAR_GAUGES = [
    throughput_metric,
    total_requests_metric,
    total_failures_metric,
    failure_rate_metric,
    input_tokens_mean_metric,
    output_tokens_mean_metric,
]

ALL_GAUGES: list[Gauge] = [
    g for pct_gauges in timing_gauges.values()
    for g, _ in pct_gauges.values()
] + SCALAR_GAUGES


def _safe_get(data: dict, *keys, default=None):
    """Safely traverse nested dicts."""
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def _set_gauge(gauge: Gauge, labels: dict, value) -> None:
    """Set a gauge only if value is not None."""
    if value is not None:
        gauge.labels(**labels).set(value)


def set_metrics() -> None:
    """Read output JSON files and update Prometheus gauges."""
    for gauge in ALL_GAUGES:
        gauge._metrics.clear()

    if not os.path.isdir(OUTPUT_DIR):
        try:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
        except OSError:
            pass
        return

    files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith(".json")]
    if not files:
        return

    for filename in files:
        filepath = os.path.join(OUTPUT_DIR, filename)

        base = os.path.splitext(filename)[0]
        parts = base.rsplit("_", 1)
        if len(parts) != 2:
            LOG.warning("Skipping file with unexpected name format: %s", filename)
            continue

        model_name, namespace = parts
        labels = {"model": model_name, "namespace": namespace}

        try:
            with open(filepath, "r") as f:
                results = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            LOG.error("Failed to read %s: %s", filepath, exc)
            continue

        summary = results.get("summary", {})
        if not summary:
            LOG.warning("No summary in %s", filepath)
            continue

        # Timing metrics (mean + percentiles)
        for metric_key, pct_gauges in timing_gauges.items():
            for gauge, json_field in pct_gauges.values():
                _set_gauge(gauge, labels,
                           _safe_get(summary, metric_key, json_field))

        # Scalar metrics
        _set_gauge(throughput_metric, labels, summary.get("throughput"))
        _set_gauge(total_requests_metric, labels,
                   summary.get("total_requests"))
        _set_gauge(total_failures_metric, labels,
                   summary.get("total_failures"))
        _set_gauge(failure_rate_metric, labels, summary.get("failure_rate"))
        _set_gauge(input_tokens_mean_metric, labels,
                   _safe_get(summary, "input_tokens", "mean"))
        _set_gauge(output_tokens_mean_metric, labels,
                   _safe_get(summary, "output_tokens", "mean"))

        LOG.info("Updated metrics for model=%s namespace=%s",
                 model_name, namespace)


def create_app(**kwargs) -> Flask:
    """Create the Flask application."""
    app = Flask(__name__)

    @app.route("/metrics", methods=["GET"])
    def export_metrics():
        set_metrics()
        return (
            generate_latest(registry),
            200,
            {"Content-Type": "text/plain; charset=utf-8"},
        )

    @app.route("/healthz", methods=["GET"])
    def healthz():
        return "ok", 200

    @app.route("/readyz", methods=["GET"])
    def readyz():
        return "ok", 200

    return app
