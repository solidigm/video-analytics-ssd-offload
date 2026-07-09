// Created by Metrum AI for Solidigm

import { useState } from 'react';
import { Cpu, ChevronDown, ChevronUp } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import type { GPUMetrics, GPUHistory } from '@/types/metrics';
import { GPUUtilizationChart } from './GPUUtilizationChart';
import styles from '@/styles/components/metrics/GPUUtilizationChartCard.module.css';

interface GPUUtilizationChartCardProps {
  gpus: GPUMetrics[];
  history: GPUHistory;
}

const GPU_COLORS = ['#6366f1', '#8b5cf6', '#a855f7', '#ec4899'];

export function GPUUtilizationChartCard({ gpus, history }: GPUUtilizationChartCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Calculate average utilization across all GPUs
  const avgUtilization = gpus.reduce((sum, gpu) => sum + gpu.utilization, 0) / gpus.length;

  return (
    <div className={styles.card}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <div className={styles.iconWrap}>
            <Cpu className={styles.icon} />
          </div>
          <div className={styles.headerText}>
            <h3 className={styles.title}>GPU Utilization</h3>
            <span className={styles.subtitle}>4x NVIDIA RTX PRO 6000 Blackwell GPUs</span>
          </div>
        </div>
        <div className={styles.avgBadge}>
          <span className={styles.avgValue}>{avgUtilization.toFixed(0)}</span>
          <span className={styles.avgUnit}>%</span>
        </div>
      </div>

      {/* Chart - Always show chart with lines */}
      <div className={styles.chartContainer}>
        <GPUUtilizationChart utilizationHistory={history.utilization} />
        {/* Legend */}
        <div className={styles.chartLegend}>
          {gpus.map((gpu, i) => (
            <div key={gpu.id} className={styles.legendItem}>
              <span
                className={styles.legendDot}
                style={{ background: GPU_COLORS[i], boxShadow: `0 0 6px ${GPU_COLORS[i]}80` }}
              />
              <span className={styles.legendLabel}>GPU {i}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Expand/Collapse Button */}
      <button
        className={styles.expandButton}
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <span className={styles.expandLabel}>
          {isExpanded ? 'Hide Details' : 'Show Details'}
        </span>
        {isExpanded ? (
          <ChevronUp className={styles.expandIcon} />
        ) : (
          <ChevronDown className={styles.expandIcon} />
        )}
      </button>

      {/* Collapsible Stats Section */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: 'easeInOut' }}
            className={styles.collapsibleSection}
          >
            {/* Stats Grid - 2x2 for 4 GPUs */}
            <div className={styles.statsGrid}>
              {gpus.map((gpu, i) => (
                <div key={gpu.id} className={styles.statBlock}>
                  <div className={styles.statHeader}>
                    <span
                      className={styles.gpuIndicator}
                      style={{ background: GPU_COLORS[i] }}
                    />
                    <span className={styles.statLabel}>GPU {i}</span>
                  </div>
                  <motion.div
                    className={styles.statValue}
                    key={gpu.utilization}
                    initial={{ opacity: 0.6 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.2 }}
                  >
                    {gpu.utilization.toFixed(0)}
                    <span className={styles.statUnit}>%</span>
                  </motion.div>
                </div>
              ))}
            </div>

            {/* Footer with temps */}
            <div className={styles.footer}>
              {gpus.map((gpu, i) => (
                <div key={gpu.id} className={styles.footerItem}>
                  <span
                    className={styles.tempIndicator}
                    style={{ background: GPU_COLORS[i] }}
                  />
                  <span className={styles.tempValue}>{gpu.temperature.toFixed(0)}°C</span>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
