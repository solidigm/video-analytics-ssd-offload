# Release v1.0

## Features

* **SSD-Backed KV Cache Offloading**: Real-time side-by-side comparison of GPU-only inference vs NVMe KV cache offloading using the NVIDIA Dynamo runtime with LMCache, demonstrating TTFT speedup and GPU power savings on Solidigm D7-PS1010 NVMe SSDs.
* **Dual LLM Comparison Dashboard**: Two identical MegaBeam-Mistral-7B-300k instances (one Baseline, one LMCache-offloaded) receive the same query simultaneously, with live streaming of TTFT, GPU power draw, SSD throughput, and cache hit rates.
* **Four Demo Scenarios**: Cold Start (Recent Games), Warm Cache (In-Game Analysis), Long Context (Season Archive ~262K tokens), and Multi-User Load Test — each highlighting different caching behaviors and NVMe advantages.
* **Multi-User k6 Benchmark**: Concurrent user load testing via k6 containers with xk6-sse, orchestrated through the Docker API, comparing throughput and latency distributions across both LLM endpoints.
* **Vision-Language Model Video Analysis**: Qwen3-VL-30B-A3B-Thinking analyzes uploaded football game video frames for play analysis, formations, and game state extraction.
* **Full Observability Stack**: Prometheus + DCGM Exporter + Node Exporter + Grafana for real-time GPU utilization, SSD I/O, CPU/memory metrics, and vLLM-specific telemetry.
* **Automated Cache Seeding**: Pre-analyzed game context files auto-seeded into both LLM instances on API startup for instant demo readiness.
* **One-Command Deployment**: Interactive `setup_quick.sh` validates all prerequisites, configures environment variables, pulls assets via Git LFS, and launches all services with `docker compose up -d`.
* **Real-Time Dashboard**: React-based SPA with live-updating TTFT speedup cards, GPU power charts, SSD throughput gauges, and cache hit rate panels using ECharts.
* **American Football LangGraph Agent**: LangGraph-powered agent for structured game analysis queries across multi-season context.

# Components

| Component | Version | License |
| --- | --- | --- |
| fastapi | 0.115.0 | [MIT](https://opensource.org/licenses/MIT) |
| uvicorn | 0.32.0 | [BSD 3-Clause License](https://opensource.org/licenses/BSD-3-Clause) |
| pydantic | 2.10.0 | [MIT](https://opensource.org/licenses/MIT) |
| httpx | 0.28.0 | [BSD 3-Clause License](https://opensource.org/licenses/BSD-3-Clause) |
| opencv-python-headless | 4.10.0.84 | [Apache License 2.0](https://opensource.org/licenses/Apache-2.0) |
| asyncpg | 0.30.0 | [Apache License 2.0](https://opensource.org/licenses/Apache-2.0) |
| sqlalchemy | 2.0.36 | [MIT](https://opensource.org/licenses/MIT) |
| alembic | 1.14.0 | [MIT](https://opensource.org/licenses/MIT) |
| prometheus-client | 0.21.0 | [Apache License 2.0](https://opensource.org/licenses/Apache-2.0) |
| python-multipart | 0.0.18 | [MIT](https://opensource.org/licenses/MIT) |
| python-dotenv | 1.0.1 | [BSD 3-Clause License](https://opensource.org/licenses/BSD-3-Clause) |
| aiofiles | 24.1.0 | [Apache License 2.0](https://opensource.org/licenses/Apache-2.0) |
| langchain | 0.3.14 | [MIT](https://opensource.org/licenses/MIT) |
| langchain-openai | 0.2.14 | [MIT](https://opensource.org/licenses/MIT) |
| langgraph | 0.2.60 | [MIT](https://opensource.org/licenses/MIT) |
| opentelemetry-api | 1.29.0 | [Apache License 2.0](https://opensource.org/licenses/Apache-2.0) |
| opentelemetry-sdk | 1.29.0 | [Apache License 2.0](https://opensource.org/licenses/Apache-2.0) |
| opentelemetry-instrumentation-httpx | 0.50b0 | [Apache License 2.0](https://opensource.org/licenses/Apache-2.0) |
| opentelemetry-exporter-otlp | 1.29.0 | [Apache License 2.0](https://opensource.org/licenses/Apache-2.0) |
| react | 19.2.3 | [MIT](https://opensource.org/licenses/MIT) |
| react-dom | 19.2.3 | [MIT](https://opensource.org/licenses/MIT) |
| react-redux | 9.2.0 | [MIT](https://opensource.org/licenses/MIT) |
| @reduxjs/toolkit | 2.11.2 | [MIT](https://opensource.org/licenses/MIT) |
| echarts | 6.0.0 | [Apache License 2.0](https://opensource.org/licenses/Apache-2.0) |
| lucide-react | 0.562.0 | [ISC License](https://opensource.org/licenses/ISC) |
| motion | 12.27.5 | [MIT](https://opensource.org/licenses/MIT) |
| react-markdown | 10.1.0 | [MIT](https://opensource.org/licenses/MIT) |
| @radix-ui/react-tooltip | 1.2.8 | [MIT](https://opensource.org/licenses/MIT) |
| vite | 7.3.1 | [MIT](https://opensource.org/licenses/MIT) |
| typescript | 5.7.2 | [Apache License 2.0](https://opensource.org/licenses/Apache-2.0) |
| eslint | 9.39.2 | [MIT](https://opensource.org/licenses/MIT) |
| @playwright/test | 1.58.2 | [Apache License 2.0](https://opensource.org/licenses/Apache-2.0) |
| pnpm | 10.28.0 | [MIT](https://opensource.org/licenses/MIT) |
| node (runtime) | 20 LTS | [MIT](https://opensource.org/licenses/MIT) |
| python (runtime) | 3.11 | [PSF License](https://docs.python.org/3/license.html) |
| postgres | 16.4-alpine | [PostgreSQL License](https://www.postgresql.org/about/licence/) |
| nginx | alpine | [BSD 2-Clause License](https://opensource.org/licenses/BSD-2-Clause) |
| prometheus | v2.54.1 | [Apache License 2.0](https://opensource.org/licenses/Apache-2.0) |
| node-exporter | latest | [Apache License 2.0](https://opensource.org/licenses/Apache-2.0) |
| dcgm-exporter | 3.3.5-3.4.1-ubuntu22.04 | [Apache License 2.0](https://opensource.org/licenses/Apache-2.0) |
| grafana | 11.3.0 | [AGPL-3.0](https://opensource.org/licenses/AGPL-3.0) |
| vllm-openai (VLM) | cu130-nightly | [Apache License 2.0](https://opensource.org/licenses/Apache-2.0) |
| vllm-dynamo (NGC) | 1.0.0 | [Apache License 2.0](https://opensource.org/licenses/Apache-2.0) |
| LMCache | 0.3.12 | [Apache License 2.0](https://opensource.org/licenses/Apache-2.0) |
| MegaBeam-Mistral-7B-300k | — | [Apache License 2.0](https://opensource.org/licenses/Apache-2.0) |
| Qwen3-VL-30B-A3B-Thinking | — | [Apache License 2.0](https://opensource.org/licenses/Apache-2.0) |
| k6 | latest | [AGPL-3.0](https://opensource.org/licenses/AGPL-3.0) |
| xk6-sse | latest | [Apache License 2.0](https://opensource.org/licenses/Apache-2.0) |
| serve | 14 | [MIT](https://opensource.org/licenses/MIT) |
| docker (static CLI in API) | 27.5.1 | [Apache License 2.0](https://opensource.org/licenses/Apache-2.0) |
