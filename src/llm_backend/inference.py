# Created by Metrum AI for Solidigm

"""
Inference Engine - vLLM deployment with and without KV cache offload.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VLLMConfig:
    """Base vLLM server configuration shared by all deployment modes."""

    model: str = "mistralai/Mistral-7B-Instruct-v0.3"
    max_model_len: int = 200000
    gpu_memory_utilization: float = 0.45
    tensor_parallel_size: int = 1
    dtype: str = "auto"
    trust_remote_code: bool = True
    enforce_eager: bool = False


@dataclass
class LMCacheVLLMConfig(VLLMConfig):
    """vLLM config with LMCache KV offload enabled."""

    kv_connector: str = "LMCacheConnector"
    kv_role: str = "kv_both"
    kv_rank: int = 0
    kv_parallel_size: int = 1
    lmcache_config_file: str = "/app/configs/lmcache_config.yaml"


class InferenceEngine:
    """
    Manages vLLM inference with optional KV cache offload.

    Two deployment modes:
    1. With LMCache: KV cache offloaded to CPU RAM (5GB) + SSD (200GB)
    2. Without LMCache: Standard vLLM with GPU-only KV cache
    """

    def __init__(self, use_kv_offload: bool = True):
        self.use_kv_offload = use_kv_offload
        self.config = self._get_config()

    def _get_config(self) -> VLLMConfig:
        """Get appropriate config based on offload setting."""
        if self.use_kv_offload:
            return LMCacheVLLMConfig()
        return VLLMConfig()

    def get_vllm_args(self) -> list[str]:
        """Generate vLLM server command line arguments."""
        args = [
            "--model",
            self.config.model,
            "--max-model-len",
            str(self.config.max_model_len),
            "--gpu-memory-utilization",
            str(self.config.gpu_memory_utilization),
            "--tensor-parallel-size",
            str(self.config.tensor_parallel_size),
            "--dtype",
            self.config.dtype,
            "--enable-chunked-prefill",
        ]

        if self.config.trust_remote_code:
            args.append("--trust-remote-code")

        if self.config.enforce_eager:
            args.append("--enforce-eager")

        if isinstance(self.config, LMCacheVLLMConfig):
            args.append("--enable-prefix-caching")
            args.extend(
                [
                    "--kv-connector",
                    self.config.kv_connector,
                    "--kv-role",
                    self.config.kv_role,
                    "--kv-rank",
                    str(self.config.kv_rank),
                    "--kv-parallel-size",
                    str(self.config.kv_parallel_size),
                    "--kv-connector-config",
                    self.config.lmcache_config_file,
                ]
            )

        return args

    def get_env_vars(self) -> dict:
        """Get environment variables for vLLM deployment."""
        env = {
            "CUDA_VISIBLE_DEVICES": "0" if self.use_kv_offload else "1",
            "VLLM_ATTENTION_BACKEND": "FLASH_ATTN",
        }

        if self.use_kv_offload:
            env["LMCACHE_CONFIG_FILE"] = "/app/configs/lmcache_config.yaml"

        return env

    def get_deployment_info(self) -> dict:
        """Get deployment configuration summary."""
        return {
            "model": self.config.model,
            "max_context_length": self.config.max_model_len,
            "gpu_memory_utilization": self.config.gpu_memory_utilization,
            "kv_offload_enabled": self.use_kv_offload,
            "gpu_device": "GPU:0" if self.use_kv_offload else "GPU:1",
        }
