// Created by Metrum AI for Solidigm

import { Cpu, Thermometer, HardDrive, Activity } from 'lucide-react';
import { motion } from 'motion/react';
import type { GPUMetrics } from '@/types/metrics';
import { MetricCard } from './MetricCard';
import { ProgressBar } from '../charts/ProgressBar';
import styles from '@/styles/components/metrics/GPUMetricsGrid.module.css';

interface GPUMetricsGridProps {
  gpus: GPUMetrics[];
}

// Get temperature color
function getTempColor(temp: number): string {
  if (temp >= 80) return '#ef4444';
  if (temp >= 65) return '#f59e0b';
  return '#10b981';
}

// Get utilization color
function getUtilColor(util: number): string {
  if (util >= 90) return '#ef4444';
  if (util >= 70) return '#f59e0b';
  return '#5B4FC4';
}

export function GPUMetricsGrid({ gpus }: GPUMetricsGridProps) {
  return (
    <MetricCard title="GPU Cluster (4x RTX 6000 Pro)" icon={<Cpu />}>
      <div className={styles.grid}>
        {gpus.map((gpu, index) => (
          <motion.div
            key={gpu.id}
            className={styles.gpuCard}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: index * 0.05, duration: 0.3 }}
          >
            <div className={styles.gpuHeader}>
              <span className={styles.gpuName}>GPU {gpu.id}</span>
              <span
                className={styles.gpuUtil}
                style={{ color: getUtilColor(gpu.utilization) }}
              >
                {gpu.utilization.toFixed(0)}%
              </span>
            </div>

            <div className={styles.gpuStats}>
              {/* Temperature */}
              <div className={styles.statRow}>
                <Thermometer
                  className={styles.statIcon}
                  style={{ color: getTempColor(gpu.temperature) }}
                />
                <span className={styles.statValue}>
                  {gpu.temperature.toFixed(0)}°C
                </span>
              </div>

              {/* Power */}
              <div className={styles.statRow}>
                <Activity className={styles.statIcon} />
                <span className={styles.statValue}>
                  {gpu.power.toFixed(0)}W
                </span>
              </div>
            </div>

            {/* Memory Bar */}
            <div className={styles.memorySection}>
              <ProgressBar
                value={gpu.memoryUsed}
                max={gpu.memoryTotal}
                unit="GB"
                size="sm"
                variant="lmcache"
                showValue={false}
              />
              <span className={styles.memoryText}>
                {gpu.memoryUsed.toFixed(0)}/{gpu.memoryTotal}GB
              </span>
            </div>
          </motion.div>
        ))}
      </div>
    </MetricCard>
  );
}
