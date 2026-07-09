// Created by Metrum AI for Solidigm

import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import * as echarts from 'echarts';
import {
  Users, Timer, TrendingUp, Zap, Activity, Gauge,
  Clock, Square, RotateCcw, Maximize2, X, BarChart3, TrendingDown,
} from 'lucide-react';
import type { MultiUserSettings } from './MultiUserConfig';
import { getBenchmarkFlushStatus } from '@/services/metricsService';
import styles from '@/styles/components/MultiUserResults.module.css';

// ─── Types ──────────────────────────────────────────────────────────────────

interface MultiUserResultsProps {
  settings: MultiUserSettings;
  runId: string;
  gpuPower: { baseline: number; lmcache: number };
  onReset: () => void;
  onStop: () => void;
  onBenchmarkCompleted?: () => void;
}

interface BenchmarkMetrics {
  type: 'progress' | 'complete';
  elapsed: number;
  completed: { baseline: number; lmcache: number };
  total: number;
  status: string;
  ttft: {
    baseline: { p50: number; p90: number; p95: number };
    lmcache: { p50: number; p90: number; p95: number };
  };
  req_per_sec: { baseline: number; lmcache: number };
  tokens_per_sec: { baseline: number; lmcache: number };
  tpot: { baseline: number; lmcache: number };
  series: {
    baseline_ttfts: number[];
    lmcache_ttfts: number[];
    baseline_tps: number[];
    lmcache_tps: number[];
    baseline_tpot: number[];
    lmcache_tpot: number[];
  };
  prometheus?: {
    instant?: {
      requests_per_sec?: { baseline: number; lmcache: number; vlm: number };
      generation_tokens_per_sec?: { baseline: number; lmcache: number; vlm: number };
      tpot_ms?: { baseline: number; lmcache: number; vlm: number };
      ttft_seconds?: { baseline: number; lmcache: number; vlm: number };
    };
    series?: {
      window?: { start: number | null; end: number | null; step_seconds: number | null };
      timestamps?: number[];
      requests_per_sec?: { baseline: number[]; lmcache: number[]; vlm: number[] };
      generation_tokens_per_sec?: { baseline: number[]; lmcache: number[]; vlm: number[] };
      tpot_ms?: { baseline: number[]; lmcache: number[]; vlm: number[] };
      ttft_seconds?: { baseline: number[]; lmcache: number[]; vlm: number[] };
    };
  };
  total_tokens?: { baseline: number; lmcache: number };
  errors: { baseline: number; lmcache: number };
  per_target_duration?: { baseline: number; lmcache: number };
  per_target_elapsed?: { baseline: number; lmcache: number };
  gpu_power_avg?: { baseline: number; lmcache: number };
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';
const BASELINE_COLOR = '#0ea5e9';
const OFFLOAD_COLOR = '#8b5cf6';

// ─── Utilities ──────────────────────────────────────────────────────────────

// ─── Reusable Chart Hook ────────────────────────────────────────────────────

function useChart(
  ref: React.RefObject<HTMLDivElement | null>,
  buildOption: () => echarts.EChartsOption,
  deps: any[],
) {
  const instance = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    if (!instance.current) {
      instance.current = echarts.init(ref.current, undefined, { renderer: 'canvas' });
    }
    const chart = instance.current;
    const timer = setTimeout(() => chart.resize(), 80);
    chart.setOption(buildOption(), { notMerge: true });

    const onResize = () => chart.resize();
    window.addEventListener('resize', onResize);
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(ref.current);

    return () => { clearTimeout(timer); window.removeEventListener('resize', onResize); ro.disconnect(); };
  }, deps);

  useEffect(() => () => { instance.current?.dispose(); instance.current = null; }, []);
}

// ─── Shared EChart Styles ───────────────────────────────────────────────────

const TOOLTIP: any = {
  backgroundColor: 'rgba(15, 23, 42, 0.95)',
  borderColor: 'rgba(139, 92, 246, 0.2)',
  borderWidth: 1,
  padding: [8, 12],
  textStyle: { fontFamily: 'Geist Mono, monospace', fontSize: 11, color: '#e2e8f0' },
};

const AXIS_LABEL = { color: 'rgba(0, 0, 0, 0.6)', fontSize: 11, fontFamily: 'Geist Mono, monospace', fontWeight: 500 as const };
const AXIS_NAME_STYLE = { color: 'rgba(0, 0, 0, 0.45)', fontSize: 10, fontFamily: 'Geist, sans-serif', fontWeight: 600 as const };
const SPLIT = { lineStyle: { color: 'rgba(0, 0, 0, 0.08)', type: 'solid' as const } };

function lineSeries(
  name: string, data: number[], color: string,
  opts?: { dashed?: boolean; dotted?: boolean; thin?: boolean; step?: 'start' | 'middle' | 'end'; noArea?: boolean },
): echarts.SeriesOption {
  const lineType = opts?.dotted ? 'dotted' : opts?.dashed ? 'dashed' : 'solid';
  const width = opts?.thin ? 1.5 : opts?.dashed ? 2 : 2.5;
  const showArea = !opts?.dashed && !opts?.dotted && !opts?.noArea;
  return {
    name, type: 'line', data, smooth: 0, symbol: 'circle',
    symbolSize: (opts?.dashed || opts?.dotted) ? 3 : 4,
    showSymbol: data.length <= 50,
    emphasis: { itemStyle: { borderWidth: 2, borderColor: '#fff' }, scale: true },
    step: opts?.step,
    lineStyle: { width, color, type: lineType, shadowColor: `${color}30`, shadowBlur: opts?.thin ? 1 : 4 },
    areaStyle: showArea ? {
      color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: `${color}18` },
        { offset: 0.6, color: `${color}06` },
        { offset: 1, color: `${color}00` },
      ]),
    } : undefined,
    animationDuration: 400,
    animationEasing: 'cubicOut',
  };
}

// ─── Chart Components ───────────────────────────────────────────────────────

function TTFTBarChart({ baseline, offload, expanded }: {
  baseline: { p50: number; p90: number; p95: number };
  offload: { p50: number; p90: number; p95: number };
  expanded?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const categories = ['P50', 'P90', 'P95'];
  const bData = [baseline.p50, baseline.p90, baseline.p95];
  const oData = [offload.p50, offload.p90, offload.p95];

  useChart(ref, () => ({
    animation: true,
    grid: { top: expanded ? 36 : 28, right: 20, bottom: expanded ? 40 : 32, left: expanded ? 64 : 56 },
    xAxis: {
      type: 'category', data: categories,
      axisLine: { lineStyle: { color: 'rgba(0, 0, 0, 0.12)' } },
      axisTick: { show: false },
      axisLabel: { ...AXIS_LABEL, fontSize: expanded ? 13 : 12, fontWeight: 600 as const },
    },
    yAxis: {
      type: 'value', min: 0, splitNumber: expanded ? 6 : 4,
      name: 'Seconds', nameLocation: 'end', nameTextStyle: AXIS_NAME_STYLE,
      axisLine: { show: false }, axisTick: { show: false },
      splitLine: SPLIT,
      axisLabel: { ...AXIS_LABEL, formatter: '{value}s' },
    },
    tooltip: {
      trigger: 'axis', ...TOOLTIP,
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        const pct = params[0]?.axisValue;
        const bVal = params.find((p: any) => p.seriesName === 'Baseline')?.value ?? 0;
        const oVal = params.find((p: any) => p.seriesName === 'KV Offload')?.value ?? 0;
        let delta = '';
        if (bVal > 0.01 && oVal > 0.01) {
          const ratio = bVal / oVal;
          delta = ratio >= 1
            ? `<div style="color:#34d399;font-weight:600;margin-top:4px">${ratio.toFixed(1)}x faster</div>`
            : `<div style="color:#f87171;font-weight:600;margin-top:4px">${(1/ratio).toFixed(1)}x slower</div>`;
        }
        return `<div style="line-height:1.7">` +
          `<div style="font-weight:600;margin-bottom:4px;color:#94a3b8">${pct} Latency</div>` +
          `<div style="color:${OFFLOAD_COLOR}">KV Offload: ${oVal.toFixed(2)}s</div>` +
          `<div style="color:${BASELINE_COLOR}">Baseline: ${bVal.toFixed(2)}s</div>` +
          `${delta}</div>`;
      },
    },
    series: [
      {
        name: 'KV Offload', type: 'bar', data: oData,
        barWidth: expanded ? '28%' : '24%',
        barGap: '20%',
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: OFFLOAD_COLOR },
            { offset: 1, color: `${OFFLOAD_COLOR}99` },
          ]),
          borderRadius: [4, 4, 0, 0],
          shadowColor: `${OFFLOAD_COLOR}30`, shadowBlur: 8,
        },
        label: {
          show: true, position: 'top',
          formatter: (p: any) => `${p.value.toFixed(1)}s`,
          fontFamily: 'Geist Mono, monospace', fontSize: expanded ? 12 : 10,
          fontWeight: 600, color: OFFLOAD_COLOR,
        },
        animationDuration: 600, animationEasing: 'cubicOut',
      },
      {
        name: 'Baseline', type: 'bar', data: bData,
        barWidth: expanded ? '28%' : '24%',
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: BASELINE_COLOR },
            { offset: 1, color: `${BASELINE_COLOR}99` },
          ]),
          borderRadius: [4, 4, 0, 0],
        },
        label: {
          show: true, position: 'top',
          formatter: (p: any) => `${p.value.toFixed(1)}s`,
          fontFamily: 'Geist Mono, monospace', fontSize: expanded ? 12 : 10,
          fontWeight: 600, color: BASELINE_COLOR,
        },
        animationDuration: 600, animationEasing: 'cubicOut', animationDelay: 150,
      },
    ],
  }), [baseline.p50, baseline.p90, baseline.p95, offload.p50, offload.p90, offload.p95, expanded]);

  return <div ref={ref} style={{ width: '100%', height: '100%', minHeight: 'clamp(11rem, 28vh, 13.75rem)' }} />;
}

function TTFTTimelineChart({ baselineTTFTs, offloadTTFTs }: {
  baselineTTFTs: number[]; offloadTTFTs: number[];
}) {
  const ref = useRef<HTMLDivElement>(null);
  const maxLen = Math.max(baselineTTFTs.length, offloadTTFTs.length, 1);
  const xData = Array.from({ length: maxLen }, (_, i) => `${i + 1}`);

  useChart(ref, () => ({
    animation: true,
    grid: { top: 30, right: 20, bottom: 44, left: 64 },
    xAxis: {
      type: 'category', data: xData, boundaryGap: false,
      name: 'Request #', nameLocation: 'center', nameGap: 28,
      nameTextStyle: AXIS_NAME_STYLE,
      axisLine: { lineStyle: { color: 'rgba(0, 0, 0, 0.12)' } },
      axisTick: { show: false },
      axisLabel: { ...AXIS_LABEL, show: true, interval: Math.max(Math.floor(xData.length / 12) - 1, 0), formatter: '#{value}' },
    },
    yAxis: {
      type: 'value', min: 0, splitNumber: 6,
      name: 'Seconds', nameLocation: 'end', nameTextStyle: AXIS_NAME_STYLE,
      axisLine: { show: false }, axisTick: { show: false },
      splitLine: SPLIT,
      axisLabel: { ...AXIS_LABEL, formatter: '{value}s' },
    },
    tooltip: {
      trigger: 'axis', ...TOOLTIP,
      axisPointer: { type: 'cross', crossStyle: { color: 'rgba(139, 92, 246, 0.3)' } },
      formatter: (params: any) => {
        const reqNum = params[0]?.axisValue;
        const bVal = params.find((p: any) => p.seriesName === 'Baseline')?.value;
        const oVal = params.find((p: any) => p.seriesName === 'KV Offload')?.value;
        const rows: string[] = [`<div style="font-weight:600;margin-bottom:4px;color:#94a3b8">Request #${reqNum}</div>`];
        if (oVal != null) rows.push(`<div style="color:${OFFLOAD_COLOR}">KV Offload: ${oVal.toFixed(2)}s</div>`);
        if (bVal != null) rows.push(`<div style="color:${BASELINE_COLOR}">Baseline: ${bVal.toFixed(2)}s</div>`);
        if (bVal != null && oVal != null && oVal > 0.01) {
          const ratio = bVal / oVal;
          const color = ratio >= 1 ? '#34d399' : '#f87171';
          const label = ratio >= 1 ? `${ratio.toFixed(1)}x faster` : `${(1/ratio).toFixed(1)}x slower`;
          rows.push(`<div style="color:${color};margin-top:2px;font-weight:600">${label}</div>`);
        }
        return `<div style="line-height:1.7">${rows.join('')}</div>`;
      },
    },
    series: [
      lineSeries('KV Offload', offloadTTFTs, OFFLOAD_COLOR),
      lineSeries('Baseline', baselineTTFTs, BASELINE_COLOR),
    ],
  }), [baselineTTFTs, offloadTTFTs]);

  return <div ref={ref} style={{ width: '100%', height: '100%', minHeight: 'clamp(11rem, 28vh, 13.75rem)' }} />;
}

function SimpleLineChart({ baselineData, offloadData, unit, yAxisName, lowerIsBetter, step, expanded, xData, xAxisName, completionMarkers }: {
  baselineData: number[]; offloadData: number[]; unit: string;
  yAxisName?: string; lowerIsBetter?: boolean; step?: 'start' | 'middle' | 'end';
  expanded?: boolean; xData?: string[]; xAxisName?: string;
  completionMarkers?: { xValue: string; label: string; color: string }[];
}) {
  const ref = useRef<HTMLDivElement>(null);
  const maxLen = Math.max(baselineData.length, offloadData.length, 1);
  const hasCustomX = !!xData?.length;
  const axisData = hasCustomX
    ? [...xData!, ...Array.from({ length: Math.max(0, maxLen - xData!.length) }, (_, i) => `${xData!.length + i + 1}`)].slice(0, maxLen)
    : Array.from({ length: maxLen }, (_, i) => `${i + 1}`);
  const axisName = xAxisName ?? (hasCustomX ? 'Elapsed Time' : 'Request #');

  useChart(ref, () => ({
    animation: true,
    grid: { top: expanded ? 30 : 24, right: 20, bottom: expanded ? 44 : 36, left: expanded ? 64 : 56 },
    xAxis: {
      type: 'category', data: axisData, boundaryGap: false,
      name: axisName, nameLocation: 'center', nameGap: expanded ? 28 : 22,
      nameTextStyle: AXIS_NAME_STYLE,
      axisLine: { lineStyle: { color: 'rgba(0, 0, 0, 0.12)' } },
      axisTick: { show: false },
      axisLabel: {
        ...AXIS_LABEL,
        show: true,
        interval: Math.max(Math.floor(axisData.length / (expanded ? 12 : 6)) - 1, 0),
        formatter: (value: string) => (hasCustomX ? value : `#${value}`),
      },
    },
    yAxis: {
      type: 'value', min: 0, splitNumber: expanded ? 5 : 3,
      name: yAxisName, nameLocation: 'end', nameTextStyle: AXIS_NAME_STYLE,
      axisLine: { show: false }, axisTick: { show: false },
      splitLine: SPLIT,
      axisLabel: { ...AXIS_LABEL, formatter: (v: number) => `${v % 1 === 0 ? v : v.toFixed(1)}${unit.trim() ? '' : ''}` },
    },
    tooltip: {
      trigger: 'axis', ...TOOLTIP,
      axisPointer: expanded ? { type: 'cross', crossStyle: { color: 'rgba(139, 92, 246, 0.3)' } } : { type: 'line' },
      formatter: (params: any) => {
        const reqNum = params[0]?.axisValue;
        const bVal = params.find((p: any) => p.seriesName === 'Baseline')?.value;
        const oVal = params.find((p: any) => p.seriesName === 'KV Offload')?.value;
        const axisValue = hasCustomX ? `${reqNum}` : `#${reqNum}`;
        const rows: string[] = [`<div style="font-weight:600;margin-bottom:4px;color:#94a3b8">${axisName}: ${axisValue}</div>`];
        if (oVal != null) rows.push(`<div style="color:${OFFLOAD_COLOR}">KV Offload: ${oVal.toFixed(2)}${unit}</div>`);
        if (bVal != null) rows.push(`<div style="color:${BASELINE_COLOR}">Baseline: ${bVal.toFixed(2)}${unit}</div>`);
        if (bVal != null && oVal != null && bVal > 0.001 && oVal > 0.001) {
          if (lowerIsBetter) {
            const pctFaster = ((bVal - oVal) / bVal) * 100;
            const color = pctFaster >= 0 ? '#34d399' : '#f87171';
            const label = pctFaster >= 0 ? 'faster' : 'slower';
            rows.push(`<div style="color:${color};margin-top:2px;font-weight:600">${Math.abs(pctFaster).toFixed(0)}% ${label}</div>`);
          } else {
            const ratio = oVal / bVal;
            const pctUp = (ratio - 1) * 100;
            const color = pctUp >= 0 ? '#34d399' : '#f87171';
            const label = pctUp >= 0 ? `+${pctUp.toFixed(0)}%` : `${pctUp.toFixed(0)}%`;
            rows.push(`<div style="color:${color};margin-top:2px;font-weight:600">${label} throughput</div>`);
          }
        }
        return `<div style="line-height:1.7">${rows.join('')}</div>`;
      },
    },
    series: [
      {
        ...lineSeries('KV Offload', offloadData, OFFLOAD_COLOR, { step }),
        ...(completionMarkers?.length ? {
          markLine: {
            silent: true,
            symbol: 'none',
            animation: false,
            data: completionMarkers.map(m => ({
              xAxis: m.xValue,
              lineStyle: { color: m.color, type: 'dashed' as const, width: 1.5, opacity: 0.35 },
              label: {
                show: true,
                formatter: m.label,
                position: 'insideEndTop' as const,
                fontSize: expanded ? 10 : 9,
                fontFamily: 'Geist Mono, monospace',
                color: m.color,
                opacity: 0.6,
              },
            })),
          },
        } : {}),
      },
      lineSeries('Baseline', baselineData, BASELINE_COLOR, { step }),
    ],
  }), [baselineData, offloadData, unit, expanded, axisData, axisName, hasCustomX, step, lowerIsBetter, yAxisName, completionMarkers]);

  return <div ref={ref} style={{ width: '100%', height: '100%', minHeight: 'clamp(11rem, 28vh, 13.75rem)' }} />;
}

// ─── UI Sub-Components ──────────────────────────────────────────────────────

function HighlightCard({ icon, value, label, sublabel, peak, delay }: {
  icon: React.ReactNode; value: React.ReactNode; label: string;
  sublabel: string; peak: string; delay: number;
}) {
  return (
    <motion.div className={styles.highlightCard}
      initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
      transition={{ delay, type: 'spring', damping: 20 }}>
      <div className={styles.highlightIcon}>{icon}</div>
      <div className={styles.highlightContent}>
        <span className={styles.highlightValue}>{value}</span>
        <span className={styles.highlightLabel}>{label}</span>
        <span className={styles.highlightSublabel}>{sublabel}</span>
      </div>
      <div className={styles.highlightPeak}>{peak}</div>
    </motion.div>
  );
}

function Legend() {
  return (
    <div className={styles.chartLegend}>
      <div className={styles.legendItem}>
        <span className={styles.legendDot} style={{ background: OFFLOAD_COLOR, boxShadow: `0 0 4px ${OFFLOAD_COLOR}60` }} />
        <span className={styles.legendLabel}>KV Offload</span>
      </div>
      <div className={styles.legendItem}>
        <span className={styles.legendDot} style={{ background: BASELINE_COLOR }} />
        <span className={styles.legendLabel}>Baseline</span>
      </div>
    </div>
  );
}

function TTFTLegend() {
  return (
    <div className={styles.chartLegend}>
      <div className={styles.legendItem}>
        <span className={styles.legendDot} style={{ background: OFFLOAD_COLOR, boxShadow: `0 0 4px ${OFFLOAD_COLOR}60` }} />
        <span className={styles.legendLabel}>KV Offload</span>
      </div>
      <div className={styles.legendItem}>
        <span className={styles.legendDot} style={{ background: BASELINE_COLOR }} />
        <span className={styles.legendLabel}>Baseline</span>
      </div>
    </div>
  );
}

function IdlePulse() {
  return (
    <span className={styles.idlePulse}>
      <span className={styles.idleLine} />
      <span className={styles.idleDot} />
    </span>
  );
}

function formatTime(s: number) {
  const m = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
}

function formatElapsedPoint(totalSeconds: number) {
  const sec = Math.max(0, Math.round(totalSeconds));
  const m = Math.floor(sec / 60);
  const rem = sec % 60;
  return m > 0 ? `${m}:${String(rem).padStart(2, '0')}` : `${rem}s`;
}

function parseElapsedLabel(label: string): number {
  if (label.includes(':')) {
    const [m, s] = label.split(':').map(Number);
    return m * 60 + s;
  }
  return parseInt(label) || 0;
}

function findClosestXLabel(elapsedSeconds: number, xData: string[]): string | null {
  if (!xData.length || elapsedSeconds <= 0) return null;
  let bestIdx = 0;
  let bestDiff = Infinity;
  for (let i = 0; i < xData.length; i++) {
    const diff = Math.abs(parseElapsedLabel(xData[i]) - elapsedSeconds);
    if (diff < bestDiff) { bestDiff = diff; bestIdx = i; }
  }
  return xData[bestIdx];
}

// ─── Main Component ─────────────────────────────────────────────────────────

export function MultiUserResults({ settings, runId, gpuPower, onReset, onStop, onBenchmarkCompleted }: MultiUserResultsProps) {
  const numUsers = settings.numUsers;
  const [metrics, setMetrics] = useState<BenchmarkMetrics | null>(null);
  const [isRunning, setIsRunning] = useState(true);
  const [connState, setConnState] = useState<'connected' | 'reconnecting'>('connected');
  const [expandedChart, setExpandedChart] = useState<string | null>(null);
  const [ttftView, setTtftView] = useState<'summary' | 'timeline'>('summary');
  const [flushStatus, setFlushStatus] = useState<string>('pending');

  // SSE connection with auto-reconnect.
  // IMPORTANT: isRunning is ONLY set to false by:
  //   (a) data.type === 'complete' from the server
  //   (b) the user clicking Stop
  // A dropped SSE connection is NOT a completion signal — it reconnects silently.
  useEffect(() => {
    if (!runId) return;

    let es: EventSource | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let attempt = 0;
    let destroyed = false;

    const connect = () => {
      if (destroyed) return;
      es = new EventSource(`${API_BASE}/api/v1/benchmark/${runId}/events`);

      es.onmessage = (event) => {
        try {
          const data: BenchmarkMetrics = JSON.parse(event.data);
          setConnState('connected');
          attempt = 0; // reset backoff on successful message
          setMetrics(data);
          if (data.type === 'complete') {
            destroyed = true;
            setIsRunning(false);
            es?.close();
          }
        } catch (e) {
          console.warn('Failed to parse benchmark SSE event:', e);
        }
      };

      es.onerror = () => {
        if (destroyed) return;
        es?.close();
        es = null;
        setConnState('reconnecting');
        // Exponential backoff: 2s, 4s, 8s, 16s, capped at 30s
        const delay = Math.min(2000 * Math.pow(2, attempt), 30000);
        attempt++;
        reconnectTimer = setTimeout(connect, delay);
      };
    };

    connect();

    return () => {
      destroyed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      es?.close();
    };
  }, [runId]);

  // Flush status polling after benchmark completes
  useEffect(() => {
    if (isRunning || !runId) return;
    let cancelled = false;
    const poll = async () => {
      while (!cancelled) {
        const status = await getBenchmarkFlushStatus(runId);
        if (cancelled) break;
        setFlushStatus(status);
        if (status === 'done' || status === 'error') {
          onBenchmarkCompleted?.();
          break;
        }
        await new Promise(r => setTimeout(r, 2000));
      }
    };
    poll();
    return () => { cancelled = true; };
  }, [isRunning, runId]);

  // Compute chart data from SSE metrics
  const elapsed = metrics?.elapsed ?? 0;

  // Raw TTFT arrays (used for highlight cards + Req/s chart)
  const baselineTTFTs = metrics?.series?.baseline_ttfts ?? [];
  const lmcacheTTFTs = metrics?.series?.lmcache_ttfts ?? [];

  // K6 per-request series (fallback when Prometheus series not yet available)
  const baselineTps = metrics?.series?.baseline_tps ?? [];
  const lmcacheTps = metrics?.series?.lmcache_tps ?? [];
  const baselineTpot = metrics?.series?.baseline_tpot ?? [];
  const lmcacheTpot = metrics?.series?.lmcache_tpot ?? [];

  // Prometheus over-time series (preferred — separate per GPU)
  const promSeries = metrics?.prometheus?.series;
  const promTimestamps = promSeries?.timestamps ?? [];
  const promWindowStart = promSeries?.window?.start ?? (promTimestamps[0] ?? null);
  const promXData = promWindowStart == null
    ? []
    : promTimestamps.map((ts) => formatElapsedPoint(ts - promWindowStart));

  // Tokens/sec — prefer Prometheus (per-GPU), fall back to k6 per-request averages
  const promBaselineTps = promSeries?.generation_tokens_per_sec?.baseline ?? [];
  const promLmcacheTps = promSeries?.generation_tokens_per_sec?.lmcache ?? [];
  const hasPromTpsSeries = promBaselineTps.length > 0 || promLmcacheTps.length > 0;
  const chartBaselineTps = hasPromTpsSeries ? promBaselineTps : baselineTps;
  const chartLmcacheTps = hasPromTpsSeries ? promLmcacheTps : lmcacheTps;

  // TPOT — prefer Prometheus, fall back to k6
  const promBaselineTpot = promSeries?.tpot_ms?.baseline ?? [];
  const promLmcacheTpot = promSeries?.tpot_ms?.lmcache ?? [];
  const hasPromTpotSeries = promBaselineTpot.length > 0 || promLmcacheTpot.length > 0;
  const chartBaselineTpot = hasPromTpotSeries ? promBaselineTpot : baselineTpot;
  const chartLmcacheTpot = hasPromTpotSeries ? promLmcacheTpot : lmcacheTpot;

  // Req/s — Prometheus only (k6 burst approximation was removed as inaccurate)
  const chartBaselineReq = promSeries?.requests_per_sec?.baseline ?? [];
  const chartLmcacheReq = promSeries?.requests_per_sec?.lmcache ?? [];

  // ─── Completion markers for time-series charts ──────────────────────────
  // Dim vertical lines showing when each target finished all its requests.
  // Only shown after benchmark completes to ensure accuracy.
  const completionMarkers: { xValue: string; label: string; color: string }[] = [];
  if (!isRunning && promXData.length > 0 && metrics?.per_target_elapsed) {
    const pte = metrics.per_target_elapsed;
    if (pte.lmcache > 0) {
      const xVal = findClosestXLabel(pte.lmcache, promXData);
      if (xVal) completionMarkers.push({ xValue: xVal, label: 'KV Offload done', color: OFFLOAD_COLOR });
    }
    if (pte.baseline > 0) {
      const xVal = findClosestXLabel(pte.baseline, promXData);
      if (xVal) completionMarkers.push({ xValue: xVal, label: 'Baseline done', color: BASELINE_COLOR });
    }
  }

  // ─── Highlight card values ──────────────────────────────────────────────
  // All metrics use per-target generation time:
  //   t1 = baseline generation window (first→last completion)
  //   t2 = lmcache generation window (first→last completion)
  // Fall back to per_target_elapsed when duration is 0 (single-user run: only 1 request per target)
  const t1 = (metrics?.per_target_duration?.baseline ?? 0) || (metrics?.per_target_elapsed?.baseline ?? 0);
  const t2 = (metrics?.per_target_duration?.lmcache ?? 0) || (metrics?.per_target_elapsed?.lmcache ?? 0);

  // TTFT Improvement — P95 ratio: baseline_p95 / lmcache_p95
  const baselineP95 = metrics?.ttft?.baseline?.p95 ?? 0;
  const lmcacheP95 = metrics?.ttft?.lmcache?.p95 ?? 0;
  const ttftImprovement = (baselineP95 > 0.01 && lmcacheP95 > 0.01) ? baselineP95 / lmcacheP95 : 0;

  // Req/s — completed_requests / generation_time per target
  const reqSecB = t1 > 0 ? (metrics?.completed?.baseline ?? 0) / t1 : 0;
  const reqSecO = t2 > 0 ? (metrics?.completed?.lmcache ?? 0) / t2 : 0;
  const reqsRatio = reqSecB > 0 ? reqSecO / reqSecB : 0;

  // Throughput — total_tokens / generation_time per target
  const tokSecB = t1 > 0 ? (metrics?.total_tokens?.baseline ?? 0) / t1 : 0;
  const tokSecO = t2 > 0 ? (metrics?.total_tokens?.lmcache ?? 0) / t2 : 0;
  const throughputUplift = tokSecB > 0 ? ((tokSecO / tokSecB) - 1) * 100 : 0;

  // Energy Efficiency — tok/J = total_tokens / (avg_gpu_power × generation_time)
  const baselineW = metrics?.gpu_power_avg?.baseline || gpuPower.baseline || 1;
  const lmcacheW = metrics?.gpu_power_avg?.lmcache || gpuPower.lmcache || 1;
  const baselineEnergy = baselineW * t1; // Joules (W × s)
  const lmcacheEnergy = lmcacheW * t2;
  const baselineTokPerJ = baselineEnergy > 0 ? (metrics?.total_tokens?.baseline ?? 0) / baselineEnergy : 0;
  const lmcacheTokPerJ = lmcacheEnergy > 0 ? (metrics?.total_tokens?.lmcache ?? 0) / lmcacheEnergy : 0;
  const powerEff = baselineTokPerJ > 0 ? lmcacheTokPerJ / baselineTokPerJ : 0;

  const handleStop = () => {
    setIsRunning(false);
    onStop();
  };

  return (
    <motion.div className={styles.container}
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.4 }}>

      {/* ═══ METADATA BAR ═══ */}
      <div className={styles.metaBar}>
        <div className={styles.metaLeft}>
          {isRunning ? (
            connState === 'reconnecting' ? (
              <span className={styles.reconnectingBadge}>Reconnecting...</span>
            ) : (
              <div className={styles.runningIndicator}>
                <span className={styles.runningDot} />
                <span className={styles.runningDot} />
                <span className={styles.runningDot} />
              </div>
            )
          ) : flushStatus === 'flushing' ? (
            <span className={styles.flushingBadge}>Flushing cache...</span>
          ) : (
            <span className={styles.completedBadge}>Completed</span>
          )}
          <span className={styles.metaTitle}>Multi-User Simulation</span>
          <div className={styles.metaBadge}>
            <Users size={13} />
            <span>{numUsers} Users</span>
          </div>
          <div className={styles.metaBadge}>
            <Timer size={13} />
            <span>{formatTime(elapsed)}</span>
          </div>
          {metrics && (() => {
            const done = (metrics.completed?.baseline ?? 0) + (metrics.completed?.lmcache ?? 0);
            const total = numUsers * 2;
            const pct = total > 0 ? Math.round((done / total) * 100) : 0;
            return (
              <div className={styles.progressBadge} title={`${done} / ${total} requests completed`}>
                <Activity size={13} />
                <div className={styles.progressBarTrack}>
                  <div className={styles.progressBarFill} style={{ width: `${pct}%` }} />
                </div>
                <span className={styles.progressBarLabel}>{pct}%</span>
              </div>
            );
          })()}
          {metrics?.per_target_elapsed && !isRunning && (
            <>
              <div className={styles.metaBadge} title="Baseline total elapsed">
                <Clock size={13} />
                <span>Baseline {formatTime(metrics.per_target_elapsed.baseline)}</span>
              </div>
              <div className={styles.metaBadge} title="KV Offload total elapsed">
                <Clock size={13} />
                <span>KV Offload {formatTime(metrics.per_target_elapsed.lmcache)}</span>
              </div>
            </>
          )}
          {metrics && ((metrics.errors?.baseline ?? 0) + (metrics.errors?.lmcache ?? 0) > 0) && (
            <div className={styles.metaBadge} style={{ opacity: 0.6 }} title="Request errors">
              <span style={{ fontSize: '11px' }}>⚠ {(metrics.errors.baseline ?? 0) + (metrics.errors.lmcache ?? 0)} errors</span>
            </div>
          )}
        </div>
        <div className={styles.metaRight}>
          {isRunning && (
            <button className={styles.stopButton} onClick={handleStop}>
              <Square size={12} /> Stop
            </button>
          )}
          <button className={styles.resetButton} onClick={onReset}>
            <RotateCcw size={12} /> Reset
          </button>
        </div>
      </div>

      {/* ═══ CONTENT ═══ */}
      <div className={styles.scrollArea}>

        {/* ─── HIGHLIGHTS (always visible, values only after completion) ─── */}
        <div className={styles.highlightRow}>
          <HighlightCard
            icon={<TrendingUp size={16} />}
            value={!isRunning && ttftImprovement > 1 ? `${ttftImprovement.toFixed(1)}x` : <IdlePulse />}
            label="TTFT Improvement"
            sublabel="P95 Ratio · KV Offload vs Baseline"
            peak={!isRunning ? `P95 Offload: ${(metrics?.ttft?.lmcache?.p95 ?? 0).toFixed(1)}s\nP95 Baseline: ${(metrics?.ttft?.baseline?.p95 ?? 0).toFixed(1)}s` : ''}
            delay={0.05}
          />
          <HighlightCard
            icon={<Zap size={16} />}
            value={!isRunning && reqsRatio > 1 ? `${reqsRatio.toFixed(1)}x` : (!isRunning && reqSecO > 0 ? `${reqSecO.toFixed(2)}` : <IdlePulse />)}
            label="Requests / Second"
            sublabel="req/s · KV Offload vs Baseline"
            peak={!isRunning ? `Offload: ${reqSecO.toFixed(2)} req/s\nBaseline: ${reqSecB.toFixed(2)} req/s` : ''}
            delay={0.1}
          />
          <HighlightCard
            icon={<Gauge size={16} />}
            value={!isRunning && powerEff > 0 ? `${powerEff.toFixed(1)}x` : <IdlePulse />}
            label="Energy Efficiency"
            sublabel="tok/J · over generation time"
            peak={!isRunning ? `Offload: ${lmcacheTokPerJ.toFixed(2)} tok/J\nBaseline: ${baselineTokPerJ.toFixed(2)} tok/J` : ''}
            delay={0.15}
          />
          <HighlightCard
            icon={<Activity size={16} />}
            value={!isRunning && throughputUplift > 0 ? `+${throughputUplift.toFixed(0)}%` : <IdlePulse />}
            label="Throughput Uplift"
            sublabel="tok/s · KV Offload vs Baseline"
            peak={!isRunning ? `Offload: ${tokSecO.toFixed(0)} tok/s\nBaseline: ${tokSecB.toFixed(0)} tok/s` : ''}
            delay={0.2}
          />
        </div>

        {/* ─── CHARTS 2x2 GRID ─── */}
        <div className={styles.chartGrid}>

          {/* TTFT */}
          <motion.div className={styles.chartCard} onClick={() => setExpandedChart('ttft')}
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}>
            <div className={styles.chartHeader}>
              <div className={styles.chartTitle}><Clock size={14} /><span>Time to First Token (TTFT)</span></div>
              <TTFTLegend />
              <Maximize2 size={13} className={styles.expandIcon} />
            </div>
            <div className={styles.chartBody}>
              <TTFTBarChart
                baseline={metrics?.ttft?.baseline ?? { p50: 0, p90: 0, p95: 0 }}
                offload={metrics?.ttft?.lmcache ?? { p50: 0, p90: 0, p95: 0 }}
              />
            </div>
          </motion.div>

          {/* Tokens/s */}
          <motion.div className={styles.chartCard} onClick={() => setExpandedChart('tokSec')}
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
            <div className={styles.chartHeader}>
              <div className={styles.chartTitle}><Activity size={14} /><span>Tokens / Second</span></div>
              <Legend />
              <Maximize2 size={13} className={styles.expandIcon} />
            </div>
            <div className={styles.chartBody}>
              <SimpleLineChart
                baselineData={chartBaselineTps}
                offloadData={chartLmcacheTps}
                unit=" tok/s"
                yAxisName="Tokens/sec"
                xData={hasPromTpsSeries ? promXData : undefined}
                xAxisName={hasPromTpsSeries ? 'Elapsed Time' : 'Request #'}
                completionMarkers={hasPromTpsSeries ? completionMarkers : undefined}
              />
            </div>
          </motion.div>

          {/* TPOT */}
          <motion.div className={styles.chartCard} onClick={() => setExpandedChart('tpot')}
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35 }}>
            <div className={styles.chartHeader}>
              <div className={styles.chartTitle}><Timer size={14} /><span>Time Per Output Token (TPOT)</span></div>
              <Legend />
              <Maximize2 size={13} className={styles.expandIcon} />
            </div>
            <div className={styles.chartBody}>
              <SimpleLineChart
                baselineData={chartBaselineTpot}
                offloadData={chartLmcacheTpot}
                unit=" ms"
                yAxisName="Milliseconds"
                lowerIsBetter
                xData={hasPromTpotSeries ? promXData : undefined}
                xAxisName={hasPromTpotSeries ? 'Elapsed Time' : 'Request #'}
                completionMarkers={hasPromTpotSeries ? completionMarkers : undefined}
              />
            </div>
          </motion.div>

          {/* Req/s — computed as cumulative completed / elapsed */}
          <motion.div className={styles.chartCard} onClick={() => setExpandedChart('reqSec')}
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}>
            <div className={styles.chartHeader}>
              <div className={styles.chartTitle}><Zap size={14} /><span>Requests / Second</span></div>
              <Legend />
              <Maximize2 size={13} className={styles.expandIcon} />
            </div>
            <div className={styles.chartBody}>
              <SimpleLineChart
                baselineData={chartBaselineReq}
                offloadData={chartLmcacheReq}
                unit=" req/s"
                yAxisName="Requests/sec"
                xData={promXData}
                xAxisName="Elapsed Time"
                completionMarkers={completionMarkers}
              />
            </div>
          </motion.div>

        </div>

      </div>

      {/* ═══ EXPANDED CHART OVERLAY ═══ */}
      <AnimatePresence>
        {expandedChart && (
          <motion.div className={styles.expandedOverlay}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={() => setExpandedChart(null)}>
            <motion.div className={styles.expandedCard}
              initial={{ opacity: 0, scale: 0.92, y: 24 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.92, y: 24 }}
              transition={{ duration: 0.3, type: 'spring', damping: 25 }}
              onClick={(e) => e.stopPropagation()}>

              <div className={styles.expandedHeader}>
                {expandedChart === 'ttft' && (
                  <>
                    <div className={styles.chartTitle}><Clock size={14} /><span>Time to First Token (TTFT)</span></div>
                    <div className={styles.viewToggle}>
                      <button
                        className={`${styles.toggleBtn} ${ttftView === 'summary' ? styles.toggleBtnActive : ''}`}
                        onClick={(e) => { e.stopPropagation(); setTtftView('summary'); }}
                      >
                        <BarChart3 size={12} /> Summary
                      </button>
                      <button
                        className={`${styles.toggleBtn} ${ttftView === 'timeline' ? styles.toggleBtnActive : ''}`}
                        onClick={(e) => { e.stopPropagation(); setTtftView('timeline'); }}
                      >
                        <TrendingDown size={12} /> Timeline
                      </button>
                    </div>
                    <Legend />
                  </>
                )}
                {expandedChart === 'tokSec' && (
                  <><div className={styles.chartTitle}><Activity size={14} /><span>Tokens / Second</span></div><Legend /></>
                )}
                {expandedChart === 'tpot' && (
                  <><div className={styles.chartTitle}><Timer size={14} /><span>Time Per Output Token (TPOT)</span></div><Legend /></>
                )}
                {expandedChart === 'reqSec' && (
                  <><div className={styles.chartTitle}><Zap size={14} /><span>Requests / Second</span></div><Legend /></>
                )}
                <button className={styles.expandedClose} onClick={() => setExpandedChart(null)}>
                  <X size={16} />
                </button>
              </div>

              <div className={styles.expandedBody}>
                {expandedChart === 'ttft' && ttftView === 'summary' && (
                  <TTFTBarChart
                    baseline={metrics?.ttft?.baseline ?? { p50: 0, p90: 0, p95: 0 }}
                    offload={metrics?.ttft?.lmcache ?? { p50: 0, p90: 0, p95: 0 }}
                    expanded
                  />
                )}
                {expandedChart === 'ttft' && ttftView === 'timeline' && (
                  <TTFTTimelineChart
                    baselineTTFTs={baselineTTFTs}
                    offloadTTFTs={lmcacheTTFTs}
                  />
                )}
                {expandedChart === 'tokSec' && (
                  <SimpleLineChart
                    baselineData={chartBaselineTps}
                    offloadData={chartLmcacheTps}
                    unit=" tok/s"
                    yAxisName="Tokens/sec"
                    xData={hasPromTpsSeries ? promXData : undefined}
                    xAxisName={hasPromTpsSeries ? 'Elapsed Time' : 'Request #'}
                    completionMarkers={hasPromTpsSeries ? completionMarkers : undefined}
                    expanded
                  />
                )}
                {expandedChart === 'tpot' && (
                  <SimpleLineChart
                    baselineData={chartBaselineTpot}
                    offloadData={chartLmcacheTpot}
                    unit=" ms"
                    yAxisName="Milliseconds"
                    lowerIsBetter
                    xData={hasPromTpotSeries ? promXData : undefined}
                    xAxisName={hasPromTpotSeries ? 'Elapsed Time' : 'Request #'}
                    completionMarkers={hasPromTpotSeries ? completionMarkers : undefined}
                    expanded
                  />
                )}
                {expandedChart === 'reqSec' && (
                  <SimpleLineChart
                    baselineData={chartBaselineReq}
                    offloadData={chartLmcacheReq}
                    unit=" req/s"
                    yAxisName="Requests/sec"
                    xData={promXData}
                    xAxisName="Elapsed Time"
                    completionMarkers={completionMarkers}
                    expanded
                  />
                )}
              </div>

            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

    </motion.div>
  );
}
