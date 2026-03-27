# Prometheus Exporter

Prometheus metrics exporter for [llm-load-test](../../README.md). Automatically discovers KServe InferenceService models in a Kubernetes/OpenShift cluster, runs load tests against them, and exports the results as Prometheus metrics.

## Architecture

The application runs as a Kubernetes Deployment with two containers sharing an `emptyDir` volume:

| Container | Purpose |
|-----------|---------|
| **runner** | Discovers models via the Kubernetes API, runs `llm-load-test` against each, writes JSON results to the shared volume |
| **exporter** | Reads the JSON results and serves Prometheus metrics on `/metrics` (port 8080) |

## Metrics Exposed

All metrics carry `model` and `namespace` labels.

### Timing Metrics

Each timing metric is exported with mean and P80/P90/P95/P99 percentiles:

| Metric prefix | Description |
|---------------|-------------|
| `llm_load_test_tpot_*_ms` | Time Per Output Token — time to generate each successive token |
| `llm_load_test_ttft_*_ms` | Time to First Token — latency before the first token is emitted |
| `llm_load_test_itl_*_ms` | Inter-Token Latency — time between consecutive output tokens |
| `llm_load_test_response_time_*_ms` | Response Time — end-to-end request latency |
| `llm_load_test_tt_ack_*_ms` | Time to Acknowledge — time to server's first HTTP acknowledgement |

Each prefix expands to 5 metrics with suffixes: `_mean_ms`, `_p80_ms`, `_p90_ms`, `_p95_ms`, `_p99_ms` (25 metrics total).

### Throughput, Request, and Token Metrics

| Metric | Description |
|--------|-------------|
| `llm_load_test_throughput_tokens_per_sec` | Output tokens generated per second |
| `llm_load_test_total_requests` | Total requests sent in the load test run |
| `llm_load_test_total_failures` | Number of failed requests |
| `llm_load_test_failure_rate_percent` | Percentage of failed requests |
| `llm_load_test_input_tokens_mean` | Mean input (prompt) tokens per request |
| `llm_load_test_output_tokens_mean` | Mean output (generated) tokens per request |

## Prerequisites

- A Kubernetes/OpenShift cluster with KServe InferenceService models deployed
- A ServiceAccount with permissions to list pods and read secrets across namespaces

## Deploying

1. Set the target namespace in `base/kustomization.yaml`
2. Adjust environment variables in `base/files/llm-load-test-config.env` as needed:
   - `DATASET_PATH` — path to the dataset file (default: `/app/datasets/dataset.jsonl`)
   - `WAIT_TIME` — seconds between load test runs (default: `120`)
   - `CONCURRENCY` — number of concurrent users (default: `8`)
   - `DURATION` — duration of each load test in seconds (default: `30`)
   - `STREAMING` — use streaming API (default: `true`)
   - `ENDPOINT` — OpenAI-compatible endpoint path (default: `/v1/chat/completions`)
3. Deploy:

```bash
oc apply -k contrib/prometheus-exporter/base/
```

4. After the exporter is deployed, opt in models to load testing by setting the label `gather_llm_metrics: "true"` on their pods. You can apply this label to existing models or to any model you deploy later. Only labeled pods are discovered and benchmarked.

**Note:** Configuration is managed via Kustomize's `configMapGenerator`. Editing `llm-load-test-config.env` and redeploying will automatically trigger a rollout with the new configuration.

## Building Container Images

Both images should be built from the **repository root** so the runner can install `llm-load-test` from the local source.

```bash
# Exporter (self-contained, build context is the exporter/ directory)
podman build -f contrib/prometheus-exporter/exporter/Containerfile \
  -t <your-registry>/llm-load-test-exporter \
  contrib/prometheus-exporter/exporter/

# Runner (needs repo root as build context to install llm-load-test)
podman build -f contrib/prometheus-exporter/runner/Containerfile \
  -t <your-registry>/llm-load-test-runner \
  .
```

## Grafana Dashboards

The `grafana/` directory contains pre-built Grafana dashboards for visualizing the exported metrics. Import them into your Grafana instance and point them at the Prometheus data source that scrapes the exporter.

## Notes

**Exporter logs:** You may see `[ERROR] Control server error: [Errno 13] Permission denied` from Gunicorn at startup. This has no effect on the application — metrics are served and scraped as usual. The error occurs when the container cannot create Gunicorn's control socket (e.g. under a read-only root filesystem). It is safe to ignore.

## Example /metrics Output

```
# HELP llm_load_test_tpot_mean_ms Mean Time Per Output Token (ms)
# TYPE llm_load_test_tpot_mean_ms gauge
llm_load_test_tpot_mean_ms{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 8.028828125373279
# HELP llm_load_test_tpot_p80_ms P80 Time Per Output Token (ms)
# TYPE llm_load_test_tpot_p80_ms gauge
llm_load_test_tpot_p80_ms{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 7.968595240910668
# HELP llm_load_test_tpot_p90_ms P90 Time Per Output Token (ms)
# TYPE llm_load_test_tpot_p90_ms gauge
llm_load_test_tpot_p90_ms{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 10.094975246521487
# HELP llm_load_test_tpot_p95_ms P95 Time Per Output Token (ms)
# TYPE llm_load_test_tpot_p95_ms gauge
llm_load_test_tpot_p95_ms{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 12.339521228152398
# HELP llm_load_test_tpot_p99_ms P99 Time Per Output Token (ms)
# TYPE llm_load_test_tpot_p99_ms gauge
llm_load_test_tpot_p99_ms{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 15.945512777856603
# HELP llm_load_test_ttft_mean_ms Mean Time to First Token (ms)
# TYPE llm_load_test_ttft_mean_ms gauge
llm_load_test_ttft_mean_ms{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 128.11345687279334
# HELP llm_load_test_ttft_p80_ms P80 Time to First Token (ms)
# TYPE llm_load_test_ttft_p80_ms gauge
llm_load_test_ttft_p80_ms{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 144.19751167297363
# HELP llm_load_test_ttft_p90_ms P90 Time to First Token (ms)
# TYPE llm_load_test_ttft_p90_ms gauge
llm_load_test_ttft_p90_ms{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 186.4311218261719
# HELP llm_load_test_ttft_p95_ms P95 Time to First Token (ms)
# TYPE llm_load_test_ttft_p95_ms gauge
llm_load_test_ttft_p95_ms{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 279.4327616691586
# HELP llm_load_test_ttft_p99_ms P99 Time to First Token (ms)
# TYPE llm_load_test_ttft_p99_ms gauge
llm_load_test_ttft_p99_ms{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 823.1433725357049
# HELP llm_load_test_itl_mean_ms Mean Inter-Token Latency (ms)
# TYPE llm_load_test_itl_mean_ms gauge
llm_load_test_itl_mean_ms{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 7.063575863406763
# HELP llm_load_test_itl_p80_ms P80 Inter-Token Latency (ms)
# TYPE llm_load_test_itl_p80_ms gauge
llm_load_test_itl_p80_ms{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 7.0560087916362715
# HELP llm_load_test_itl_p90_ms P90 Inter-Token Latency (ms)
# TYPE llm_load_test_itl_p90_ms gauge
llm_load_test_itl_p90_ms{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 8.609594476039927
# HELP llm_load_test_itl_p95_ms P95 Inter-Token Latency (ms)
# TYPE llm_load_test_itl_p95_ms gauge
llm_load_test_itl_p95_ms{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 10.022274727059886
# HELP llm_load_test_itl_p99_ms P99 Inter-Token Latency (ms)
# TYPE llm_load_test_itl_p99_ms gauge
llm_load_test_itl_p99_ms{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 10.63403127785016
# HELP llm_load_test_response_time_mean_ms Mean Response Time (ms)
# TYPE llm_load_test_response_time_mean_ms gauge
llm_load_test_response_time_mean_ms{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 1031.7217386685884
# HELP llm_load_test_response_time_p80_ms P80 Response Time (ms)
# TYPE llm_load_test_response_time_p80_ms gauge
llm_load_test_response_time_p80_ms{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 1153.2029628753662
# HELP llm_load_test_response_time_p90_ms P90 Response Time (ms)
# TYPE llm_load_test_response_time_p90_ms gauge
llm_load_test_response_time_p90_ms{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 1322.1412181854248
# HELP llm_load_test_response_time_p95_ms P95 Response Time (ms)
# TYPE llm_load_test_response_time_p95_ms gauge
llm_load_test_response_time_p95_ms{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 1456.7198753356931
# HELP llm_load_test_response_time_p99_ms P99 Response Time (ms)
# TYPE llm_load_test_response_time_p99_ms gauge
llm_load_test_response_time_p99_ms{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 2335.965375900268
# HELP llm_load_test_tt_ack_mean_ms Mean Time to Acknowledge (ms)
# TYPE llm_load_test_tt_ack_mean_ms gauge
llm_load_test_tt_ack_mean_ms{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 128.07771976177509
# HELP llm_load_test_tt_ack_p80_ms P80 Time to Acknowledge (ms)
# TYPE llm_load_test_tt_ack_p80_ms gauge
llm_load_test_tt_ack_p80_ms{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 144.17171478271484
# HELP llm_load_test_tt_ack_p90_ms P90 Time to Acknowledge (ms)
# TYPE llm_load_test_tt_ack_p90_ms gauge
llm_load_test_tt_ack_p90_ms{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 186.40327453613284
# HELP llm_load_test_tt_ack_p95_ms P95 Time to Acknowledge (ms)
# TYPE llm_load_test_tt_ack_p95_ms gauge
llm_load_test_tt_ack_p95_ms{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 279.3550610542294
# HELP llm_load_test_tt_ack_p99_ms P99 Time to Acknowledge (ms)
# TYPE llm_load_test_tt_ack_p99_ms gauge
llm_load_test_tt_ack_p99_ms{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 823.0641603469842
# HELP llm_load_test_throughput_tokens_per_sec Throughput (tokens/sec)
# TYPE llm_load_test_throughput_tokens_per_sec gauge
llm_load_test_throughput_tokens_per_sec{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 559.7666666666667
# HELP llm_load_test_total_requests Total requests in the load test run
# TYPE llm_load_test_total_requests gauge
llm_load_test_total_requests{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 130.0
# HELP llm_load_test_total_failures Total failed requests
# TYPE llm_load_test_total_failures gauge
llm_load_test_total_failures{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 0.0
# HELP llm_load_test_failure_rate_percent Percentage of failed requests
# TYPE llm_load_test_failure_rate_percent gauge
llm_load_test_failure_rate_percent{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 0.0
# HELP llm_load_test_input_tokens_mean Mean input tokens per request
# TYPE llm_load_test_input_tokens_mean gauge
llm_load_test_input_tokens_mean{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 189.47692307692307
# HELP llm_load_test_output_tokens_mean Mean output tokens per request
# TYPE llm_load_test_output_tokens_mean gauge
llm_load_test_output_tokens_mean{model="granite-31-2b-v100",namespace="ai-performance-profiling"} 129.1769230769231
```
