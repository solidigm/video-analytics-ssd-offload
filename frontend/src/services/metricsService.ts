// Created by Metrum AI for Solidigm

import type { GPUMetrics, SSDMetrics, CPUMetrics, SystemMetrics, LLMMetrics, GPUHistory } from '@/types/metrics';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

// History tracking for SSD metrics (rolling window for chart)
const SSD_HISTORY_SIZE = 20;
let ssdHistory: { read: number[]; write: number[]; readLat: number[]; writeLat: number[] } = {
  read: [],
  write: [],
  readLat: [],
  writeLat: [],
};
let previousSSD: SSDMetrics | null = null;

// History tracking for GPU metrics (rolling window for charts)
const GPU_HISTORY_SIZE = 20;
let gpuHistory: GPUHistory = {
  power: [[], [], [], []],
  utilization: [[], [], [], []],
};
let previousGPUs: GPUMetrics[] | null = null;

// Fetch GPU metrics with history tracking
export async function fetchGPUMetrics(): Promise<{ gpus: GPUMetrics[]; history: GPUHistory }> {
  let currentGPUs: GPUMetrics[];

  try {
    const response = await fetch(`${API_BASE}/api/v1/metrics/gpu`);
    if (response.ok) {
      const data = await response.json();
      // Normalize API response to frontend interface
      currentGPUs = (data.gpus || []).map((gpu: any) => ({
        id: gpu.index,
        name: gpu.name,
        power: gpu.power || 0,
        temperature: gpu.temp || 0,
        memoryUsed: gpu.mem_used_gb || 0,
        memoryTotal: gpu.mem_total_gb || 98,
        utilization: gpu.util || 0,
      }));
      if (currentGPUs.length === 0) {
        currentGPUs = generateMockGPUs();
        currentGPUs.forEach(g => { g.error = true; g.errorMessage = 'No GPUs reported by API'; });
      }
    } else {
      currentGPUs = generateMockGPUs();
      currentGPUs.forEach(g => { g.error = true; g.errorMessage = 'GPU metrics unavailable'; });
    }
  } catch (error) {
    console.warn('GPU metrics fetch failed:', error);
    currentGPUs = generateMockGPUs();
    currentGPUs.forEach(g => { g.error = true; g.errorMessage = 'GPU metrics unavailable'; });
  }

  // Update history arrays for each GPU
  currentGPUs.forEach((gpu, i) => {
    gpuHistory.power[i].push(gpu.power);
    gpuHistory.utilization[i].push(gpu.utilization);

    // Keep only last N values
    if (gpuHistory.power[i].length > GPU_HISTORY_SIZE) {
      gpuHistory.power[i].shift();
      gpuHistory.utilization[i].shift();
    }
  });

  // Compute averages and deltas for each GPU
  const enrichedGPUs = currentGPUs.map((gpu, i) => {
    const powerHistory = gpuHistory.power[i];
    const utilHistory = gpuHistory.utilization[i];

    const avgPower = powerHistory.reduce((a, b) => a + b, 0) / powerHistory.length;
    const avgUtilization = utilHistory.reduce((a, b) => a + b, 0) / utilHistory.length;

    const deltaPower = previousGPUs ? gpu.power - previousGPUs[i].power : 0;
    const deltaUtilization = previousGPUs ? gpu.utilization - previousGPUs[i].utilization : 0;

    return {
      ...gpu,
      avgPower,
      avgUtilization,
      deltaPower,
      deltaUtilization,
    };
  });

  // Store current as previous for next iteration
  previousGPUs = currentGPUs.map(gpu => ({ ...gpu }));

  return {
    gpus: enrichedGPUs,
    history: {
      power: gpuHistory.power.map(arr => [...arr]),
      utilization: gpuHistory.utilization.map(arr => [...arr]),
    },
  };
}

// Fetch SSD metrics with history tracking
export async function fetchSSDMetrics(): Promise<SSDMetrics> {
  let currentMetrics: SSDMetrics;

  try {
    const response = await fetch(`${API_BASE}/api/v1/metrics/ssd`);
    if (response.ok) {
      const data = await response.json();
      // Map API response fields to frontend interface
      // API returns: readMBps, writeMBps, readLatencyMs, writeLatencyMs
      currentMetrics = {
        readThroughput: data.readMBps || data.readThroughput || 0,
        writeThroughput: data.writeMBps || data.writeThroughput || 0,
        readLatency: data.readLatencyMs || data.readLatency || 0,
        writeLatency: data.writeLatencyMs || data.writeLatency || 0,
        ioQueueDepth: data.activeIO || data.ioQueueDepth || 0,
        totalReadGB: data.totalReadGB,
        totalWriteGB: data.totalWriteGB,
        readIOPS: data.readIOPS,
        writeIOPS: data.writeIOPS,
        source: data.source,
      };
    } else {
      currentMetrics = { ...generateMockSSD(), error: true, errorMessage: 'SSD metrics unavailable' };
    }
  } catch (error) {
    console.warn('SSD metrics fetch failed:', error);
    currentMetrics = { ...generateMockSSD(), error: true, errorMessage: 'SSD metrics unavailable' };
  }

  // Update history arrays (rolling window)
  ssdHistory.read.push(currentMetrics.readThroughput);
  ssdHistory.write.push(currentMetrics.writeThroughput);
  ssdHistory.readLat.push(currentMetrics.readLatency);
  ssdHistory.writeLat.push(currentMetrics.writeLatency);

  // Keep only last N values
  if (ssdHistory.read.length > SSD_HISTORY_SIZE) {
    ssdHistory.read.shift();
    ssdHistory.write.shift();
    ssdHistory.readLat.shift();
    ssdHistory.writeLat.shift();
  }

  // Compute rolling averages
  const avgRead = ssdHistory.read.reduce((a, b) => a + b, 0) / ssdHistory.read.length;
  const avgWrite = ssdHistory.write.reduce((a, b) => a + b, 0) / ssdHistory.write.length;

  // Compute deltas (current - previous)
  const deltaRead = previousSSD ? currentMetrics.readThroughput - previousSSD.readThroughput : 0;
  const deltaWrite = previousSSD ? currentMetrics.writeThroughput - previousSSD.writeThroughput : 0;
  const deltaReadLatency = previousSSD ? currentMetrics.readLatency - previousSSD.readLatency : 0;
  const deltaWriteLatency = previousSSD ? currentMetrics.writeLatency - previousSSD.writeLatency : 0;

  // Store current as previous for next iteration
  previousSSD = { ...currentMetrics };

  // Return enriched metrics with history for charts
  return {
    ...currentMetrics,
    avgReadThroughput: avgRead,
    avgWriteThroughput: avgWrite,
    deltaRead,
    deltaWrite,
    deltaReadLatency,
    deltaWriteLatency,
    readHistory: [...ssdHistory.read],
    writeHistory: [...ssdHistory.write],
  };
}

// Fetch CPU metrics
export async function fetchCPUMetrics(): Promise<CPUMetrics> {
  try {
    const response = await fetch(`${API_BASE}/api/v1/metrics/cpu`);
    if (response.ok) {
      const data = await response.json();
      return data;
    }
  } catch (error) {
    console.warn('CPU metrics fetch failed:', error);
  }
  return { ...generateMockCPU(), error: true, errorMessage: 'CPU metrics unavailable' };
}

// Fetch all system metrics combined
export async function fetchAllSystemMetrics(llmMetrics: LLMMetrics): Promise<SystemMetrics & { gpuHistory: GPUHistory }> {
  const [gpuResult, ssd, cpu] = await Promise.all([
    fetchGPUMetrics(),
    fetchSSDMetrics(),
    fetchCPUMetrics(),
  ]);

  return {
    llm: llmMetrics,
    gpus: gpuResult.gpus,
    gpuHistory: gpuResult.history,
    ssd,
    cpu,
    timestamp: Date.now(),
  };
}

// Multi-user benchmark API
export async function startMultiUserBenchmark(numUsers: number, contextMode: 'quick' | 'long_context' = 'long_context'): Promise<{ run_id: string; num_users: number; status: string }> {
  const res = await fetch(`${API_BASE}/api/v1/benchmark/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ num_users: numUsers, context_mode: contextMode }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail || `Benchmark start failed (${res.status})`);
  }
  return res.json();
}

export async function stopMultiUserBenchmark(runId: string): Promise<void> {
  await fetch(`${API_BASE}/api/v1/benchmark/${runId}/stop`, { method: 'POST' });
}

export async function getActiveBenchmark(): Promise<{ active: boolean; run_id?: string; num_users?: number; elapsed?: number; context_mode?: string }> {
  const res = await fetch(`${API_BASE}/api/v1/benchmark/active`);
  if (!res.ok) return { active: false };
  return res.json();
}

export async function stopActiveBenchmark(): Promise<{ run_id: string; status: string } | null> {
  const res = await fetch(`${API_BASE}/api/v1/benchmark/active/stop`, { method: 'POST' });
  if (!res.ok) return null;
  return res.json();
}

export async function getBenchmarkFlushStatus(runId: string): Promise<string> {
  const res = await fetch(`${API_BASE}/api/v1/benchmark/${runId}/flush_status`);
  if (!res.ok) return 'error';
  const data = await res.json();
  return data.flush_status ?? 'pending';
}

// Zero-value generators for fallback (no simulated data)
function generateMockGPUs(): GPUMetrics[] {
  return Array.from({ length: 4 }, (_, i) => ({
    id: i,
    name: `GPU ${i}`,
    power: 0,
    temperature: 0,
    memoryUsed: 0,
    memoryTotal: 0,
    utilization: 0,
  }));
}

function generateMockSSD(): SSDMetrics {
  return {
    readThroughput: 0,
    writeThroughput: 0,
    readLatency: 0,
    writeLatency: 0,
    ioQueueDepth: 0,
  };
}

function generateMockCPU(): CPUMetrics {
  return {
    usage: 0,
    power: 0,
    memoryUsed: 0,
    memoryTotal: 0,
  };
}
