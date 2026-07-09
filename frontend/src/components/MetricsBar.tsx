// Created by Metrum AI for Solidigm

import type { Metrics } from '@/pages/Home';
import styles from '@/styles/components/MetricsBar.module.css';

interface MetricsBarProps {
  metrics: Metrics;
}

interface MetricCardProps {
  label: string;
  value: string | number;
  unit: string;
  color?: 'red' | 'green' | 'blue' | 'gold';
  highlight?: boolean;
}

function MetricCard({ label, value, unit, color = 'blue', highlight }: MetricCardProps) {
  const cardColorClass = {
    red: styles.metricCardRed,
    green: styles.metricCardGreen,
    blue: styles.metricCardBlue,
    gold: styles.metricCardGold,
  }[color];

  const valueColorClass = {
    red: styles.metricValueRed,
    green: styles.metricValueGreen,
    blue: styles.metricValueBlue,
    gold: styles.metricValueGold,
  }[color];

  return (
    <div className={`${styles.metricCard} ${cardColorClass} ${highlight ? styles.metricCardHighlight : ''}`}>
      <span className={styles.metricLabel}>{label}</span>
      <span className={`${styles.metricValue} ${valueColorClass}`}>
        {value === null || value === '--' ? '--' : typeof value === 'number' ? value.toFixed(2) : value}
      </span>
      <span className={styles.metricUnit}>{unit}</span>
    </div>
  );
}

export function MetricsBar({ metrics }: MetricsBarProps) {
  return (
    <div className={styles.container}>
      <div className={`${styles.inner} scrollbar-thin`}>
        <MetricCard label="Baseline TTFT" value={metrics.baselineTTFT ?? '--'} unit="seconds" color="red" />
        <MetricCard label="LMCache TTFT" value={metrics.lmcacheTTFT ?? '--'} unit="seconds" color="green" />
        <MetricCard
          label="Speedup"
          value={metrics.speedup ?? '--'}
          unit="times faster"
          color="gold"
          highlight={metrics.speedup !== null && metrics.speedup > 1}
        />
        <MetricCard label="Baseline TPut" value={metrics.baselineGenTput} unit="tok/s" color="red" />
        <MetricCard label="LMCache TPut" value={metrics.lmcacheGenTput} unit="tok/s" color="green" />
        <MetricCard label="Prompt Tokens" value={metrics.diskRead} unit="total" color="blue" />
        <MetricCard label="Gen Tokens" value={metrics.diskWrite} unit="total" color="blue" />
        <MetricCard
          label="Cache Hit"
          value={`${metrics.cacheHitRate.toFixed(0)}%`}
          unit="rate"
          color="green"
          highlight={metrics.cacheHitRate > 50}
        />
      </div>
    </div>
  );
}
