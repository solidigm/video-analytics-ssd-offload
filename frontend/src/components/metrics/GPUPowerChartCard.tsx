// Created by Metrum AI for Solidigm

import { useState } from 'react';
import { Zap, ChevronDown, ChevronUp } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import type { GPUMetrics, GPUHistory } from '@/types/metrics';
import { GPUPowerChart } from './GPUPowerChart';
import styles from '@/styles/components/metrics/GPUPowerChartCard.module.css';

interface GPUPowerChartCardProps {
  gpus: GPUMetrics[];
  history: GPUHistory;
}

const GPU_COLORS = ['#ef4444', '#f97316', '#fbbf24', '#a3e635'];

export function GPUPowerChartCard({ gpus, history }: GPUPowerChartCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Calculate total power and average
  const totalPower = gpus.reduce((sum, gpu) => sum + gpu.power, 0);
  const avgTotalPower = gpus.reduce((sum, gpu) => sum + (gpu.avgPower || gpu.power), 0);

  return (
    <div className={styles.card}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <div className={styles.iconWrap}>
            <Zap className={styles.icon} />
          </div>
          <div className={styles.headerText}>
            <h3 className={styles.title}>GPU Power</h3>
            <span className={styles.subtitle}>4x NVIDIA RTX PRO 6000 Blackwell GPUs </span>
          </div>
        </div>
        <div className={styles.totalBadge}>
          <span className={styles.totalValue}>{totalPower.toFixed(0)}</span>
          <span className={styles.totalUnit}>W</span>
        </div>
      </div>

      {/* Chart - Always show chart with lines */}
      <div className={styles.chartContainer}>
        <GPUPowerChart powerHistory={history.power} />
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
                    key={gpu.power}
                    initial={{ opacity: 0.6 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.2 }}
                  >
                    {gpu.power.toFixed(0)}
                    <span className={styles.statUnit}>W</span>
                  </motion.div>
                </div>
              ))}
            </div>

            {/* Footer */}
            <div className={styles.footer}>
              <div className={styles.footerItem}>
                <span className={styles.footerLabel}>Total</span>
                <span className={styles.footerValue}>{totalPower.toFixed(0)}W</span>
              </div>
              <div className={styles.footerDivider} />
              <div className={styles.footerItem}>
                <span className={styles.footerLabel}>Avg</span>
                <span className={styles.footerValueAccent}>{avgTotalPower.toFixed(0)}W</span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
