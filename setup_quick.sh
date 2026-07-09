#!/usr/bin/env bash
# Created by Metrum AI for Solidigm

# =============================================================================
# Tactical Sports Analytics — Quick Setup
# Checks prerequisites,configuration, and launches services.
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[ OK ]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[FAIL]${NC}  $*"; }
die()   { error "$*"; exit 1; }
hr()    { echo -e "${BOLD}────────────────────────────────────────────────────${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
hr
echo -e "  ${BOLD}Tactical Sports Analytics — Quick Setup${NC}"
hr
echo ""

# =============================================================================
# STEP 1: PREREQUISITES
# =============================================================================
echo -e "${BOLD}[1/4] Checking prerequisites...${NC}"
echo ""
PREREQ_FAIL=0

# Docker
if ! command -v docker &>/dev/null; then
    error "docker not found — install: https://docs.docker.com/get-docker/"
    PREREQ_FAIL=1
elif ! docker info &>/dev/null 2>&1; then
    error "Docker daemon not running — start with: sudo systemctl start docker"
    PREREQ_FAIL=1
else
    ok "Docker $(docker --version | awk '{print $3}' | tr -d ',')"
fi

# Docker Compose v2
if docker compose version &>/dev/null 2>&1; then
    ok "Docker Compose $(docker compose version --short 2>/dev/null || echo 'v2')"
else
    error "Docker Compose v2 not found — install: https://docs.docker.com/compose/install/"
    PREREQ_FAIL=1
fi

# NVIDIA drivers + GPUs
if ! command -v nvidia-smi &>/dev/null; then
    error "nvidia-smi not found — NVIDIA drivers required"
    PREREQ_FAIL=1
else
    GPU_COUNT=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | wc -l || echo 0)
    if [ "$GPU_COUNT" -lt 3 ]; then
        error "${GPU_COUNT} GPU(s) detected — minimum 3 required (LMCache LLM, Baseline LLM, VLM)"
        PREREQ_FAIL=1
    else
        GPU_NAMES=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | tr '\n' ',' | sed 's/,$//')
        ok "${GPU_COUNT} GPU(s): ${GPU_NAMES}"
    fi
fi

# NVIDIA Container Toolkit
if ! docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi -L &>/dev/null 2>&1; then
    warn "NVIDIA Container Toolkit may not be configured — GPU passthrough might fail"
    warn "Install: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html"
else
    ok "NVIDIA Container Toolkit (GPU passthrough verified)"
fi

# Git LFS
if git lfs version &>/dev/null 2>&1; then
    ok "Git LFS $(git lfs version 2>/dev/null | awk '{print $2}')"
else
    warn "Git LFS not installed — video assets will be LFS pointer stubs"
    warn "Fix: sudo apt install git-lfs && git lfs install && git lfs pull"
fi

# Disk space (≥50 GB)
FREE_GB=$(df -BG "$SCRIPT_DIR" | awk 'NR==2{gsub("G","",$4); print $4}')
if [ "${FREE_GB:-0}" -lt 250 ]; then
    warn "Only ${FREE_GB} GB free — recommended ≥250 GB (models + data + videos)"
else
    ok "${FREE_GB} GB free disk space"
fi

# RAM (≥64 GB)
TOTAL_RAM_GB=$(awk '/MemTotal/{printf "%d", $2/1024/1024}' /proc/meminfo 2>/dev/null || echo 0)
if [ "${TOTAL_RAM_GB:-0}" -lt 64 ]; then
    warn "${TOTAL_RAM_GB} GB RAM — recommended ≥64 GB"
else
    ok "${TOTAL_RAM_GB} GB total RAM"
fi

echo ""
if [ "$PREREQ_FAIL" -ne 0 ]; then
    die "Fix the errors above then re-run this script."
fi

# =============================================================================
# STEP 2: GIT LFS PULL
# =============================================================================
echo -e "${BOLD}[2/4] Pulling video assets (Git LFS)...${NC}"
echo ""
if git lfs version &>/dev/null 2>&1; then
    info "Downloading videos ≤111 MB from Git LFS (~700 MB)..."
    git lfs pull && ok "Video assets ready"
else
    warn "Skipping — Git LFS not installed"
fi
echo ""

# =============================================================================
# STEP 3: ENVIRONMENT CONFIGURATION
# =============================================================================
echo -e "${BOLD}[3/4] Environment configuration${NC}"
echo ""
if [ -f .env ]; then
    warn ".env already exists."
    read -rp "  Overwrite it? [y/N]: " _ow || _ow="N"
    if [[ ! "${_ow:-N}" =~ ^[Yy]$ ]]; then
        info "Keeping existing .env — skipping configuration."
        echo ""
    else
        rm .env
    fi
fi

if [ ! -f .env ]; then
    cp .env.example .env

    echo "  Press Enter to accept the default shown in [brackets]."
    echo ""

    # --- Required ---
    echo -e "  ${BOLD}Secrets (required)${NC}"
    while true; do
        read -rp "  HuggingFace API Token (hf_...): " _hf || _hf=""
        [ -n "$_hf" ] && break
        error "  HF_TOKEN is required to download model weights — cannot be empty."
    done
    sed -i "s|HF_TOKEN=.*|HF_TOKEN=${_hf}|" .env

    read -rsp "  PostgreSQL password [postgres]: " _pg || _pg=""; echo ""
    _pg="${_pg:-postgres}"
    sed -i "s|POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${_pg}|" .env

    read -rsp "  Grafana admin password [admin]: " _gr || _gr=""; echo ""
    _gr="${_gr:-admin}"
    sed -i "s|GRAFANA_PASSWORD=.*|GRAFANA_PASSWORD=${_gr}|" .env

    echo ""

    # --- Model config ---
    echo -e "  ${BOLD}Model configuration${NC}"
    read -rp "  LLM model [aws-prototyping/MegaBeam-Mistral-7B-300k]: " _llm || _llm=""
    _llm="${_llm:-aws-prototyping/MegaBeam-Mistral-7B-300k}"
    sed -i "s|LLM_MODEL=.*|LLM_MODEL=${_llm}|" .env

    read -rp "  VLM model [Qwen/Qwen3-VL-30B-A3B-Thinking]: " _vlm || _vlm=""
    _vlm="${_vlm:-Qwen/Qwen3-VL-30B-A3B-Thinking}"
    sed -i "s|VLM_MODEL=.*|VLM_MODEL=${_vlm}|" .env

    echo ""

    # --- KV cache ---
    echo -e "  ${BOLD}LMCache / KV offload${NC}"
    read -rp "  NVMe SSD KV cache path [/mnt/ssd/kv_cache]: " _kv || _kv=""
    _kv="${_kv:-/mnt/ssd/kv_cache}"
    sed -i "s|KV_CACHE_PATH=.*|KV_CACHE_PATH=${_kv}|" .env

    read -rp "  KV cache size in GB [100]: " _kvgb || _kvgb=""
    _kvgb="${_kvgb:-100}"
    sed -i "s|KV_CACHE_SIZE_GB=.*|KV_CACHE_SIZE_GB=${_kvgb}|" .env

    echo ""

    # --- Auto-seed ---
    echo -e "  ${BOLD}Cache seeding${NC}"
    read -rp "  Auto-seed game contexts on startup? [true]: " _seed || _seed=""
    _seed="${_seed:-true}"
    sed -i "s|AUTO_SEED_ON_STARTUP=.*|AUTO_SEED_ON_STARTUP=${_seed}|" .env

    # --- Auto-computed deployment paths ---
    _compose_project=$(basename "$SCRIPT_DIR")
    sed -i "s|BENCHMARK_HOST_DATA_DIR=.*|BENCHMARK_HOST_DATA_DIR=${SCRIPT_DIR}/data|" .env
    sed -i "s|K6_DOCKER_NETWORK=.*|K6_DOCKER_NETWORK=${_compose_project}_default|" .env

    echo ""
    ok ".env written — see .env.example for all available options"
    echo ""
fi

# =============================================================================
# STEP 4: LAUNCH
# =============================================================================
echo -e "${BOLD}[4/4] Building & starting services...${NC}"
echo ""
info "Building k6-sse image (multi-user benchmark)..."
docker compose build k6-sse && ok "k6-sse image built" || warn "k6-sse build failed — multi-user benchmark will not work until rebuilt"
echo ""
docker compose up -d

echo ""
hr
ok "All services started."
hr
echo ""
echo "  Endpoints:"
echo "    UI        →  http://localhost:8100"
echo "    API       →  http://localhost:8100/health"
echo "    API Docs  →  http://localhost:8100/docs"
echo "    Grafana   →  http://localhost:3000"
echo ""
echo "  First boot: vLLM servers download ~30 GB of model weights."
echo "  This takes 5-15 min. Monitor with:"
echo "    docker compose logs -f vllm-lmcache vllm-baseline"
echo ""
