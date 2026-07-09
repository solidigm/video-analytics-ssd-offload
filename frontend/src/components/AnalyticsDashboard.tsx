// Created by Metrum AI for Solidigm

import { useState, useEffect } from 'react';
import {
  Zap,
  Activity,
  Clock,
  Database,
  HardDrive,
  TrendingUp,
  BarChart3,
  Cpu,
  Server,
  X,
  RefreshCw,
} from 'lucide-react';
import styles from '@/styles/components/AnalyticsDashboard.module.css';

interface AnalyticsDashboardProps {
  onClose: () => void;
  metrics: {
    baselineTTFT: number | null;
    lmcacheTTFT: number | null;
    speedup: number | null;
    baselineGenTput: number;
    lmcacheGenTput: number;
    diskRead: number;
    diskWrite: number;
    cacheHitRate: number;
  };
  queryHistory: { baseline: number[]; lmcache: number[] };
}

interface GPUMetrics {
  index: number;
  name: string;
  power: number;
  temp: number;
  memUsed: number;
  memTotal: number;
  util: number;
}

interface VLLMMetrics {
  prefix_cache_queries: number;
  prefix_cache_hits: number;
  external_cache_queries: number;
  external_cache_hits: number;
  kv_cache_usage: number;
  prompt_tokens: number;
  generation_tokens: number;
  requests_completed: number;
  cache_hit_rate: number;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

export function AnalyticsDashboard({ onClose, metrics, queryHistory }: AnalyticsDashboardProps) {
  const [gpuMetrics, setGpuMetrics] = useState<GPUMetrics[]>([
    { index: 0, name: 'GPU 0 - LMCache', power: 0, temp: 0, memUsed: 0, memTotal: 98, util: 0 },
    { index: 1, name: 'GPU 1 - Baseline', power: 0, temp: 0, memUsed: 0, memTotal: 98, util: 0 },
    { index: 2, name: 'GPU 2 - VLM', power: 0, temp: 0, memUsed: 0, memTotal: 98, util: 0 },
  ]);

  const [vllmMetrics, setVllmMetrics] = useState<{ lmcache: VLLMMetrics | null; baseline: VLLMMetrics | null }>({
    lmcache: null,
    baseline: null,
  });

  const [ttftHistory, setTtftHistory] = useState({
    baseline: queryHistory.baseline.length > 0 ? queryHistory.baseline : [],
    lmcache: queryHistory.lmcache.length > 0 ? queryHistory.lmcache : [],
  });

  const [isRefreshing, setIsRefreshing] = useState(false);
  const [metricsSource, setMetricsSource] = useState<string>('loading');

  const fetchAllMetrics = async () => {
    try {
      const gpuResp = await fetch(`${API_BASE}/api/v1/metrics/gpu`);
      if (gpuResp.ok) {
        const data = await gpuResp.json();
        if (data.gpus?.length > 0) {
          // Sanitize GPU data to ensure all properties exist
          const sanitizedGpus = data.gpus.slice(0, 3).map((gpu: Partial<GPUMetrics>, idx: number) => ({
            index: gpu.index ?? idx,
            name: gpu.name ?? `GPU ${idx}`,
            power: gpu.power ?? 0,
            temp: gpu.temp ?? 0,
            memUsed: gpu.memUsed ?? 0,
            memTotal: gpu.memTotal ?? 98,
            util: gpu.util ?? 0,
          }));
          setGpuMetrics(sanitizedGpus);
          setMetricsSource(data.source);
        }
      }

      const vllmResp = await fetch(`${API_BASE}/api/v1/metrics/vllm`);
      if (vllmResp.ok) {
        const data = await vllmResp.json();
        setVllmMetrics({
          lmcache: data.lmcache || null,
          baseline: data.baseline || null,
        });
      }
    } catch (error) {
      console.error('Failed to fetch metrics:', error);
      setMetricsSource('error');
    }
  };

  useEffect(() => {
    fetchAllMetrics();
    const interval = setInterval(fetchAllMetrics, 3000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (queryHistory.baseline.length > 0 || queryHistory.lmcache.length > 0) {
      setTtftHistory(queryHistory);
    }
  }, [queryHistory]);

  const refreshMetrics = async () => {
    setIsRefreshing(true);
    await fetchAllMetrics();
    setIsRefreshing(false);
  };

  const baselinePower = gpuMetrics[1]?.power || 0;
  const lmcachePower = gpuMetrics[0]?.power || 0;
  const powerSavings = baselinePower > 0 ? ((baselinePower - lmcachePower) / baselinePower * 100) : 0;

  const avgBaselineTTFT = ttftHistory.baseline.length > 0
    ? ttftHistory.baseline.reduce((a, b) => a + b, 0) / ttftHistory.baseline.length : 0;
  const avgLmcacheTTFT = ttftHistory.lmcache.length > 0
    ? ttftHistory.lmcache.reduce((a, b) => a + b, 0) / ttftHistory.lmcache.length : 0;
  const ttftSpeedup = avgLmcacheTTFT > 0 ? avgBaselineTTFT / avgLmcacheTTFT : 0;

  const allTTFTs = [...ttftHistory.baseline, ...ttftHistory.lmcache];
  const maxTTFT = allTTFTs.length > 0 ? Math.max(...allTTFTs) : 1;
  const hasRealQueryData = ttftHistory.baseline.length > 0 || ttftHistory.lmcache.length > 0;

  const cacheHitRate = vllmMetrics.lmcache?.cache_hit_rate || metrics.cacheHitRate || 0;

  return (
    <div className={styles.overlay}>
      {/* Header */}
      <div className={`solidigm-bg ${styles.header}`}>
        <div className={styles.headerContent}>
          <div className={styles.headerLeft}>
            <div className={styles.headerGroup}>
              <div className={styles.headerIcon}>
                <BarChart3 className={styles.headerIconInner} />
              </div>
              <div className={styles.headerInfo}>
                <h1 className={styles.headerTitle}>Analytics Dashboard</h1>
                <div className={styles.headerSubtitle}>
                  <span className={styles.headerSubtitleText}>KV Cache Offload Metrics</span>
                  <span className={`${styles.statusBadge} ${metricsSource === 'dcgm-exporter' ? styles.statusBadgeLive : styles.statusBadgeConnecting}`}>
                    {metricsSource === 'dcgm-exporter' ? 'LIVE' : 'CONNECTING...'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className={styles.headerActions}>
            <button onClick={refreshMetrics} disabled={isRefreshing} className={styles.refreshButton}>
              <RefreshCw className={`${styles.refreshIcon} ${isRefreshing ? 'animate-spin' : ''}`} />
              Refresh
            </button>
            <button onClick={onClose} className={styles.closeButton}>
              <X className={styles.closeIcon} />
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className={styles.main}>
        {/* Top Stats */}
        <div className={styles.statsRow}>
          <StatCard icon={<Clock />} label="Avg TTFT" value={avgLmcacheTTFT > 0 ? `${avgLmcacheTTFT.toFixed(2)}s` : '--'} color="green" />
          <StatCard icon={<TrendingUp />} label="Speedup" value={ttftSpeedup > 0 ? `${ttftSpeedup.toFixed(1)}x` : '--'} color="gold" />
          <StatCard icon={<Database />} label="Cache Hit" value={`${cacheHitRate.toFixed(0)}%`} color="blue" />
          <StatCard icon={<Zap />} label="Power Saved" value={powerSavings > 0 ? `${powerSavings.toFixed(0)}%` : '--'} color="green" />
          <StatCard icon={<Activity />} label="Requests" value={`${vllmMetrics.lmcache?.requests_completed || 0}`} color="red" />
          <StatCard icon={<HardDrive />} label="KV Usage" value={`${((vllmMetrics.lmcache?.kv_cache_usage || 0) * 100).toFixed(0)}%`} color="blue" />
        </div>

        {/* TTFT Chart */}
        <div className={`card ${styles.chartSection}`}>
          <div className={styles.sectionHeader}>
            <h3 className={styles.sectionTitle}>
              <Clock className={styles.sectionIcon} style={{ color: 'var(--color-baseline)' }} />
              TTFT Comparison
            </h3>
            <div className={styles.legend}>
              <div className={styles.legendItem}>
                <div className={`${styles.legendDot} ${styles.legendDotBaseline}`}></div>
                <span className={styles.legendLabel}>Baseline</span>
              </div>
              <div className={styles.legendItem}>
                <div className={`${styles.legendDot} ${styles.legendDotLmcache}`}></div>
                <span className={styles.legendLabel}>LMCache</span>
              </div>
            </div>
          </div>

          <div className={styles.chartArea}>
            {hasRealQueryData ? (
              ttftHistory.baseline.map((baseVal, idx) => (
                <div key={idx} className={styles.barGroup}>
                  <div
                    className={`${styles.chartBar} ttft-bar-baseline`}
                    style={{ height: `${(baseVal / maxTTFT) * 100}%` }}
                    title={`Baseline: ${baseVal.toFixed(2)}s`}
                  />
                  <div
                    className={`${styles.chartBar} ttft-bar-lmcache`}
                    style={{ height: `${((ttftHistory.lmcache[idx] || 0) / maxTTFT) * 100}%` }}
                    title={`LMCache: ${(ttftHistory.lmcache[idx] || 0).toFixed(2)}s`}
                  />
                </div>
              ))
            ) : (
              <div className={styles.chartEmpty}>
                <div className={styles.chartEmptyContent}>
                  <Clock className={styles.chartEmptyIcon} />
                  <p>Send queries to see comparison</p>
                </div>
              </div>
            )}
          </div>

          <div className={styles.avgStats}>
            <div className={styles.avgStatCard}>
              <div className={styles.avgStatLabel}>Avg Baseline</div>
              <div className={styles.avgStatValue} style={{ color: 'var(--color-baseline)' }}>
                {avgBaselineTTFT > 0 ? `${avgBaselineTTFT.toFixed(2)}s` : '--'}
              </div>
            </div>
            <div className={styles.avgStatCard}>
              <div className={styles.avgStatLabel}>Avg LMCache</div>
              <div className={styles.avgStatValue} style={{ color: 'var(--color-lmcache)' }}>
                {avgLmcacheTTFT > 0 ? `${avgLmcacheTTFT.toFixed(2)}s` : '--'}
              </div>
            </div>
          </div>
        </div>

        {/* GPU Power */}
        <div className={`card ${styles.gpuSection}`}>
          <div className={styles.sectionHeader}>
            <h3 className={styles.sectionTitle}>
              <Zap className={styles.sectionIcon} style={{ color: 'var(--naples-yellow)' }} />
              GPU Power (DCGM)
            </h3>
            <span className={`${styles.statusBadge} ${metricsSource === 'dcgm-exporter' ? styles.statusBadgeLive : styles.statusBadgeConnecting}`}>
              {metricsSource === 'dcgm-exporter' ? 'LIVE' : 'Connecting...'}
            </span>
          </div>

          <div className={styles.gpuList}>
            {gpuMetrics.map((gpu, idx) => (
              <div key={idx} className={styles.gpuItem}>
                <div className={styles.gpuHeader}>
                  <span className={styles.gpuName}>{gpu.name}</span>
                  <span
                    className={styles.gpuValue}
                    style={{ color: idx === 0 ? 'var(--color-lmcache)' : idx === 1 ? 'var(--color-baseline)' : 'var(--solidigm-blue-secondary)' }}
                  >
                    {gpu.power.toFixed(0)}W
                  </span>
                </div>
                <div className={styles.gpuBar}>
                  <div
                    className={`${styles.gpuBarFill} ${idx === 0 ? styles.gpuBarLmcache : idx === 1 ? styles.gpuBarBaseline : styles.gpuBarVlm}`}
                    style={{ width: `${Math.min(100, (gpu.power / 400) * 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>

          <div className={styles.gpuEfficiency}>
            <span className={styles.gpuEfficiencyLabel}>Power Efficiency: </span>
            <span className={styles.gpuEfficiencyValue}>
              {powerSavings > 0 ? `${powerSavings.toFixed(0)}%` : '--'}
            </span>
          </div>
        </div>

        {/* GPU Memory */}
        <div className={`card ${styles.memorySection}`}>
          <h3 className={styles.sectionTitle}>
            <Cpu className={styles.sectionIcon} style={{ color: 'var(--solidigm-blue-secondary)' }} />
            GPU Memory
          </h3>

          <div className={styles.memoryList}>
            {gpuMetrics.map((gpu, idx) => (
              <div key={idx} className={styles.memoryItem}>
                <div className={styles.memoryHeader}>
                  <span className={styles.memoryLabel}>GPU {idx}</span>
                  <span className={styles.memoryValue}>{(gpu.memUsed ?? 0).toFixed(0)}GB / {gpu.memTotal ?? 98}GB</span>
                </div>
                <div className={styles.memoryBar}>
                  <div
                    className={styles.memoryBarFill}
                    style={{ width: `${((gpu.memUsed ?? 0) / (gpu.memTotal || 98)) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Cache Metrics */}
        <div className={styles.cacheSection}>
          <h3 className={styles.cacheTitle}>
            <Database className={styles.cacheTitleIcon} />
            LMCache Metrics
          </h3>

          <div className={styles.cacheGrid}>
            <div className={styles.cacheItem}>
              <div className={styles.cacheItemLabel}>Cache Queries</div>
              <div className={`${styles.cacheItemValue} ${styles.cacheItemValueGreen}`}>
                {(vllmMetrics.lmcache?.external_cache_queries || 0).toFixed(0)}
              </div>
            </div>
            <div className={styles.cacheItem}>
              <div className={styles.cacheItemLabel}>Cache Hits</div>
              <div className={`${styles.cacheItemValue} ${styles.cacheItemValueGreen}`}>
                {(vllmMetrics.lmcache?.external_cache_hits || 0).toFixed(0)}
              </div>
            </div>
            <div className={styles.cacheItem}>
              <div className={styles.cacheItemLabel}>Hit Rate</div>
              <div className={`${styles.cacheItemValue} ${styles.cacheItemValueGold}`}>
                {cacheHitRate.toFixed(0)}%
              </div>
            </div>
            <div className={styles.cacheItem}>
              <div className={styles.cacheItemLabel}>KV Cache</div>
              <div className={`${styles.cacheItemValue} ${styles.cacheItemValueBlue}`}>
                {((vllmMetrics.lmcache?.kv_cache_usage || 0) * 100).toFixed(0)}%
              </div>
            </div>
          </div>
        </div>

        {/* Token Throughput */}
        <div className={`card ${styles.tokenSection}`}>
          <h3 className={styles.sectionTitle}>
            <Activity className={styles.sectionIcon} style={{ color: 'var(--color-baseline)' }} />
            Token Stats
          </h3>

          <div className={styles.tokenGrid}>
            <div className={`${styles.tokenCard} ${styles.tokenCardBaseline}`}>
              <div className={styles.tokenCardLabel}>Baseline TPut</div>
              <div className={styles.tokenCardValue} style={{ color: 'var(--color-baseline)' }}>{(metrics.baselineGenTput ?? 0).toFixed(0)}</div>
              <div className={styles.tokenCardUnit}>tok/s</div>
            </div>
            <div className={`${styles.tokenCard} ${styles.tokenCardLmcache}`}>
              <div className={styles.tokenCardLabel}>LMCache TPut</div>
              <div className={styles.tokenCardValue} style={{ color: 'var(--color-lmcache)' }}>{(metrics.lmcacheGenTput ?? 0).toFixed(0)}</div>
              <div className={styles.tokenCardUnit}>tok/s</div>
            </div>
          </div>

          <div className={styles.tokenStats}>
            <div className={styles.tokenStatRow}>
              <span className={styles.tokenStatLabel}>Prompt Tokens</span>
              <span className={styles.tokenStatValue}>{vllmMetrics.lmcache?.prompt_tokens || 0}</span>
            </div>
            <div className={styles.tokenStatRow}>
              <span className={styles.tokenStatLabel}>Gen Tokens</span>
              <span className={styles.tokenStatValue}>{vllmMetrics.lmcache?.generation_tokens || 0}</span>
            </div>
          </div>
        </div>

        {/* Summary Banner */}
        <div className={`solidigm-bg ${styles.summaryBanner}`}>
          <div className={styles.summaryContent}>
            <div className={styles.summaryLeft}>
              <div className={styles.summaryIcon}>
                <Server className={styles.summaryIconInner} />
              </div>
              <div className={styles.summaryInfo}>
                <div className={styles.summaryBrands}>
                  <span className={styles.summaryBrandSolidigm}>Solidigm</span>
                </div>
                <p className={styles.summarySubtext}>KV Cache Offload to NVMe SSD</p>
              </div>
            </div>

            <div className={styles.summaryStats}>
              <div className={styles.summaryStatCard}>
                <div className={`${styles.summaryStatValue} ${styles.summaryStatValueGreen}`}>
                  {ttftSpeedup > 0 ? `${ttftSpeedup.toFixed(1)}x` : '--'}
                </div>
                <div className={styles.summaryStatLabel}>Speedup</div>
              </div>
              <div className={styles.summaryStatCard}>
                <div className={`${styles.summaryStatValue} ${styles.summaryStatValueGold}`}>
                  {powerSavings > 0 ? `${powerSavings.toFixed(0)}%` : '--'}
                </div>
                <div className={styles.summaryStatLabel}>Power Saved</div>
              </div>
              <div className={styles.summaryStatCard}>
                <div className={`${styles.summaryStatValue} ${styles.summaryStatValueWhite}`}>200k+</div>
                <div className={styles.summaryStatLabel}>Context</div>
              </div>
              <div className={styles.summaryStatCard}>
                <div className={`${styles.summaryStatValue} ${styles.summaryStatValueSpring}`}>1000+</div>
                <div className={styles.summaryStatLabel}>Users</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: string; color: 'green' | 'blue' | 'red' | 'gold' }) {
  const cardClass = {
    green: styles.statCardGreen,
    blue: styles.statCardBlue,
    red: styles.statCardRed,
    gold: styles.statCardGold,
  }[color];

  const valueClass = {
    green: styles.statValueGreen,
    blue: styles.statValueBlue,
    red: styles.statValueRed,
    gold: styles.statValueGold,
  }[color];

  return (
    <div className={`card ${styles.statCard} ${cardClass}`}>
      <div className={styles.statHeader}>
        <div className={styles.statIcon} style={{ color: color === 'green' ? 'var(--color-lmcache)' : color === 'blue' ? 'var(--solidigm-blue-secondary)' : color === 'red' ? 'var(--color-baseline)' : '#b8860b' }}>
          {icon}
        </div>
        <span className={styles.statLabel}>{label}</span>
      </div>
      <div className={`${styles.statValue} ${valueClass}`}>{value}</div>
    </div>
  );
}
