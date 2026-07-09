// Created by Metrum AI for Solidigm

import { Server, Activity, MemoryStick } from 'lucide-react';
import type { CPUMetrics } from '@/types/metrics';
import { MetricCard } from './MetricCard';
import { ProgressBar } from '../charts/ProgressBar';
import styles from '@/styles/components/metrics/CPUMetricsCard.module.css';

interface CPUMetricsCardProps {
  cpu: CPUMetrics;
}

export function CPUMetricsCard({ cpu }: CPUMetricsCardProps) {
  const hasData = cpu.usage > 0 || cpu.memoryUsed > 0;

  return (
    <MetricCard title="System Resources" icon={<Server />}>
      <div className={styles.liveStatus}>
        <span className={`${styles.liveDot} ${hasData ? styles.liveDotActive : ''}`} />
        <span className={styles.liveLabel}>{hasData ? 'Live' : 'Connecting'}</span>
      </div>
      <div className={styles.grid}>
        {/* CPU Usage */}
        <div className={styles.metricItem}>
          <div className={styles.metricHeader}>
            <Activity className={styles.metricIcon} />
            <span className={styles.metricLabel}>CPU Usage</span>
            <span className={styles.metricValue}>{cpu.usage.toFixed(0)}%</span>
          </div>
          <ProgressBar
            value={cpu.usage}
            max={100}
            size="sm"
            showValue={false}
          />
        </div>

        {/* CPU Power */}
        <div className={styles.metricItem}>
          <div className={styles.metricHeader}>
            <Activity className={styles.metricIcon} />
            <span className={styles.metricLabel}>CPU Power</span>
            <span className={styles.metricValue}>{cpu.power.toFixed(0)}W</span>
          </div>
        </div>

        {/* Memory */}
        <div className={`${styles.metricItem} ${styles.metricItemFull}`}>
          <div className={styles.metricHeader}>
            <MemoryStick className={styles.metricIcon} />
            <span className={styles.metricLabel}>System Memory</span>
            <span className={styles.metricValue}>
              {cpu.memoryUsed.toFixed(0)} / {cpu.memoryTotal}GB
            </span>
          </div>
          <ProgressBar
            value={cpu.memoryUsed}
            max={cpu.memoryTotal}
            size="sm"
            showValue={false}
          />
        </div>
      </div>
    </MetricCard>
  );
}
