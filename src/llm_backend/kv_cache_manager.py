# Created by Metrum AI for Solidigm

"""
KV Cache Manager - Manages tiered KV cache with SSD offload via LMCache.
"""

import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


class CacheTier(Enum):
    """Logical storage tiers used by the KV cache stack."""

    GPU_VRAM = "gpu_vram"
    SYSTEM_DRAM = "system_dram"
    NVME_SSD = "nvme_ssd"


@dataclass
class CacheStats:  # pylint: disable=too-many-instance-attributes
    """Runtime utilization and operation counters for the cache manager."""

    gpu_vram_used_gb: float = 0.0
    gpu_vram_total_gb: float = 0.0
    dram_used_gb: float = 0.0
    dram_total_gb: float = 5.0
    ssd_used_gb: float = 0.0
    ssd_total_gb: float = 200.0
    cache_hit_rate: float = 0.0
    eviction_count: int = 0
    offload_count: int = 0
    onboard_count: int = 0


@dataclass
class KVCacheConfig:
    """Static configuration for KV cache capacity and behavior."""

    ssd_path: str = "/mnt/nvme/kv_cache"
    ssd_capacity_gb: int = 200
    dram_capacity_gb: int = 5
    gpu_memory_utilization: float = 0.45
    eviction_policy: str = "lru"
    enable_gds: bool = True
    prefetch_enabled: bool = True


class KVCacheManager:
    """
    Manages tiered KV cache storage across GPU VRAM, DRAM, and NVMe SSDs.

    Architecture:
    - Hot Tier: GPU VRAM (fastest, limited capacity)
    - Warm Tier: System DRAM (5GB allocated)
    - Cold Tier: NVMe SSD (200GB capacity)
    """

    def __init__(self, config: Optional[KVCacheConfig] = None):
        self.config = config or KVCacheConfig()
        self._init_cache_directories()
        self._stats = CacheStats()
        self._cache_index = {}

    def _init_cache_directories(self) -> None:
        """Initialize SSD cache directory structure."""
        cache_path = Path(self.config.ssd_path)
        cache_path.mkdir(parents=True, exist_ok=True)
        (cache_path / "video_context").mkdir(exist_ok=True)
        (cache_path / "session_state").mkdir(exist_ok=True)
        logger.info("KV cache directory initialized at %s", self.config.ssd_path)

    def get_lmcache_config(self) -> dict:
        """Generate LMCache configuration for vLLM integration."""
        return {
            "chunk_size": 256,
            "local_device": "cuda",
            "remote_url": None,
            "remote_serde": None,
            "storage_backend": {
                "type": "tiered",
                "tiers": [
                    {
                        "name": "cpu",
                        "type": "cpu",
                        "capacity_gb": self.config.dram_capacity_gb,
                    },
                    {
                        "name": "disk",
                        "type": "disk",
                        "path": self.config.ssd_path,
                        "capacity_gb": self.config.ssd_capacity_gb,
                        "use_gds": self.config.enable_gds,
                    },
                ],
                "eviction_policy": self.config.eviction_policy,
            },
            "prefetch": {
                "enabled": self.config.prefetch_enabled,
                "num_blocks": 8,
                "trigger_threshold": 0.7,
            },
        }

    def get_cache_stats(self) -> CacheStats:
        """Get current cache statistics."""
        return self._stats

    def get_offload_metrics(self) -> dict:
        """Get metrics about KV cache offload operations."""
        return {
            "offload_path": self.config.ssd_path,
            "ssd_capacity_gb": self.config.ssd_capacity_gb,
            "dram_capacity_gb": self.config.dram_capacity_gb,
            "ssd_used_gb": self._stats.ssd_used_gb,
            "gds_enabled": self.config.enable_gds,
            "cache_hit_rate": self._stats.cache_hit_rate,
        }
