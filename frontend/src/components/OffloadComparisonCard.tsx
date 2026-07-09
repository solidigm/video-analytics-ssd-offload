// Created by Metrum AI for Solidigm

import { motion } from 'motion/react';
import { Zap, Database, Clock, TrendingDown, Sparkles } from 'lucide-react';
import styles from '@/styles/components/OffloadComparisonCard.module.css';

interface MetricData {
  label: string;
  shortLabel: string;
  baseline: string;
  optimized: string;
  delta: string;
  icon: React.ReactNode;
  improvement: boolean; // true = lower is better (TTFT, Power), false = higher is better (Cache)
}

const METRICS: MetricData[] = [
  {
    label: 'Time To First Token',
    shortLabel: 'TTFT',
    baseline: '13.4s',
    optimized: '0.4s',
    delta: '-96%',
    icon: <Clock />,
    improvement: true,
  },
  {
    label: 'Cache Hit Rate',
    shortLabel: 'Cache',
    baseline: '0%',
    optimized: '93%',
    delta: '+93%',
    icon: <Database />,
    improvement: false,
  },
  {
    label: 'System Power',
    shortLabel: 'Power',
    baseline: '1352w',
    optimized: '854w',
    delta: '-37%',
    icon: <Zap />,
    improvement: true,
  },
];

export function OffloadComparisonCard() {
  return (
    <motion.div
      className={styles.container}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1] }}
    >
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <span className={styles.headerLabel}>Performance Comparison</span>
        </div>
        <div className={styles.headerBadge}>
          <Sparkles className={styles.headerBadgeIcon} />
          <span>SSD Offload</span>
        </div>
      </div>

      {/* Comparison Grid */}
      <div className={styles.comparisonGrid}>
        {/* Baseline Column */}
        <div className={styles.column}>
          <div className={styles.columnHeader}>
            <span className={styles.columnBadge}>Baseline</span>
            <span className={styles.columnSubtitle}>Standard GPU Memory</span>
          </div>
          <div className={styles.metricsStack}>
            {METRICS.map((metric, idx) => (
              <motion.div
                key={`baseline-${idx}`}
                className={styles.metricRow}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.1, duration: 0.3 }}
              >
                <div className={styles.metricIcon}>{metric.icon}</div>
                <div className={styles.metricInfo}>
                  <span className={styles.metricLabel}>{metric.shortLabel}</span>
                </div>
                <span className={styles.metricValueBaseline}>{metric.baseline}</span>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Delta Column (Center) */}
        <div className={styles.deltaColumn}>
          <div className={styles.deltaHeader}>
            <TrendingDown className={styles.deltaHeaderIcon} />
          </div>
          {METRICS.map((metric, idx) => (
            <motion.div
              key={`delta-${idx}`}
              className={`${styles.deltaCell} ${metric.improvement ? styles.deltaCellGood : styles.deltaCellGreat}`}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.2 + idx * 0.1, duration: 0.3, ease: [0.34, 1.56, 0.64, 1] }}
            >
              <span className={styles.deltaValue}>{metric.delta}</span>
            </motion.div>
          ))}
        </div>

        {/* Optimized Column */}
        <div className={`${styles.column} ${styles.columnOptimized}`}>
          <div className={styles.columnHeader}>
            <span className={`${styles.columnBadge} ${styles.columnBadgeOptimized}`}>
              <Sparkles className={styles.columnBadgeIcon} />
              Solidigm SSD
            </span>
            <span className={styles.columnSubtitle}>KV Cache Offload</span>
          </div>
          <div className={styles.metricsStack}>
            {METRICS.map((metric, idx) => (
              <motion.div
                key={`optimized-${idx}`}
                className={`${styles.metricRow} ${styles.metricRowOptimized}`}
                initial={{ opacity: 0, x: 8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.1, duration: 0.3 }}
              >
                <div className={`${styles.metricIcon} ${styles.metricIconOptimized}`}>{metric.icon}</div>
                <div className={styles.metricInfo}>
                  <span className={styles.metricLabel}>{metric.shortLabel}</span>
                </div>
                <span className={styles.metricValueOptimized}>{metric.optimized}</span>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
