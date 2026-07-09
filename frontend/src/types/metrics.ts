// Created by Metrum AI for Solidigm

// LLM Performance Metrics
export interface LLMMetrics {
  ttft: {
    baseline: number | null;
    lmcache: number | null;
  };
  speedup: number | null;
  generationThroughput: {
    baseline: number;
    lmcache: number;
    vlm?: number;
  };
  promptThroughput?: {
    baseline: number;
    lmcache: number;
    vlm?: number;
  };
  kvCacheUsage?: {
    baseline: number;
    lmcache: number;
    vlm?: number;
  };
  cacheHitRate: number;
  cacheHitRates?: {
    baseline: number;
    lmcache: number;
    vlm: number;
  };
}

// GPU Metrics (per GPU, 4 total)
export interface GPUMetrics {
  id: number;
  name: string;
  power: number;        // Watts (0-660W)
  temperature: number;  // Celsius (20-90°C)
  memoryUsed: number;   // GB
  memoryTotal: number;  // GB (typically 80-98 GB)
  utilization: number;  // % (0-100%)
  // Computed fields for charts
  avgPower?: number;
  avgUtilization?: number;
  deltaPower?: number;
  deltaUtilization?: number;
  // Error state (set when API is unreachable)
  error?: boolean;
  errorMessage?: string;
}

// GPU History for charts (all 4 GPUs)
export interface GPUHistory {
  power: number[][];       // [gpu0[], gpu1[], gpu2[], gpu3[]]
  utilization: number[][]; // [gpu0[], gpu1[], gpu2[], gpu3[]]
}

// SSD Metrics (Solidigm NVMe)
export interface SSDMetrics {
  readThroughput: number;   // GB (total) or MB/s (rate)
  writeThroughput: number;  // GB (total) or MB/s (rate)
  readLatency: number;      // ms
  writeLatency: number;     // ms
  ioQueueDepth: number;     // count (active IO operations)
  // Total counters
  totalReadGB?: number;     // Total GB read
  totalWriteGB?: number;    // Total GB written
  readIOPS?: number;        // Total read operations
  writeIOPS?: number;       // Total write operations
  source?: string;          // Data source (node-exporter, proc-diskstats, simulated)
  // Computed fields for avg + delta display
  avgReadThroughput?: number;   // Rolling average
  avgWriteThroughput?: number;  // Rolling average
  deltaRead?: number;           // Current - Previous
  deltaWrite?: number;          // Current - Previous
  deltaReadLatency?: number;    // Current - Previous
  deltaWriteLatency?: number;   // Current - Previous
  // History arrays for live chart
  readHistory?: number[];       // Last 20 read throughput values
  writeHistory?: number[];      // Last 20 write throughput values
  // Error state (set when API is unreachable)
  error?: boolean;
  errorMessage?: string;
}

// CPU Metrics
export interface CPUMetrics {
  usage: number;        // % (0-100%)
  power: number;        // Watts
  memoryUsed: number;   // GB
  memoryTotal: number;  // GB
  // Error state (set when API is unreachable)
  error?: boolean;
  errorMessage?: string;
}

// Combined System Metrics
export interface SystemMetrics {
  llm: LLMMetrics;
  gpus: GPUMetrics[];
  ssd: SSDMetrics;
  cpu: CPUMetrics;
  timestamp: number;
}

// Metrics History for Charts
export interface MetricsHistory {
  ttft: {
    baseline: number[];
    lmcache: number[];
  };
  gpuUtilization: number[][];  // [gpu0[], gpu1[], gpu2[], gpu3[]]
  ssdThroughput: {
    read: number[];
    write: number[];
  };
  cpuUsage: number[];
  timestamps: number[];
}

// Default/Initial values
export const DEFAULT_GPU_METRICS: GPUMetrics = {
  id: 0,
  name: 'GPU 0',
  power: 0,
  temperature: 0,
  memoryUsed: 0,
  memoryTotal: 80,
  utilization: 0,
};

export const DEFAULT_SSD_METRICS: SSDMetrics = {
  readThroughput: 0,
  writeThroughput: 0,
  readLatency: 0,
  writeLatency: 0,
  ioQueueDepth: 0,
};

export const DEFAULT_CPU_METRICS: CPUMetrics = {
  usage: 0,
  power: 0,
  memoryUsed: 0,
  memoryTotal: 256,
};
