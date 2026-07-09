// Created by Metrum AI for Solidigm

import { ArrowDown, ArrowUp, Activity, Layers, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { motion } from 'motion/react';
import type { SSDMetrics } from '@/types/metrics';
import { SSDLiveChart } from './SSDLiveChart';
import styles from '@/styles/components/metrics/SSDMetricsCard.module.css';
import solidigmDriveImg from '@/assets/Solidigm_drive.png';

interface SSDMetricsCardProps {
  ssd: SSDMetrics;
}

// Format delta with sign and styling info
function formatDelta(delta: number | undefined): { text: string; isPositive: boolean; isNeutral: boolean } {
  if (delta === undefined || Math.abs(delta) < 0.01) {
    return { text: '—', isPositive: false, isNeutral: true };
  }
  const sign = delta > 0 ? '+' : '';
  const formattedValue = `${sign}${delta.toFixed(1)}`;

  // For throughput, positive = good (more speed)
  return {
    text: formattedValue,
    isPositive: delta > 0,
    isNeutral: false
  };
}

export function SSDMetricsCard({ ssd }: SSDMetricsCardProps) {
  const readDelta = formatDelta(ssd.deltaRead);
  const writeDelta = formatDelta(ssd.deltaWrite);

  const readHistory = ssd.readHistory || [];
  const writeHistory = ssd.writeHistory || [];

  return (
    <div className={styles.card}>
      {/* Header */}
      <div className={styles.header}>
        <img
          src={solidigmDriveImg}
          alt="Solidigm NVMe SSD"
          className={styles.headerDriveImg}
        />
        <div className={styles.headerText}>
          <h3 className={styles.title}>Solidigm NVMe SSD</h3>
          <span className={styles.subtitle}>D7-PS1010 Performance</span>
        </div>
      </div>

      {/* Chart Hero Section - Always show chart with lines */}
      <div className={styles.chartContainer}>
        <SSDLiveChart readHistory={readHistory} writeHistory={writeHistory} />
        {/* Chart Legend */}
        <div className={styles.chartLegend}>
          <div className={styles.legendItem}>
            <span className={styles.legendDotRead} />
            <span className={styles.legendLabel}>Read</span>
          </div>
          <div className={styles.legendItem}>
            <span className={styles.legendDotWrite} />
            <span className={styles.legendLabel}>Write</span>
          </div>
        </div>
      </div>

      {/* Throughput Stats */}
      <div className={styles.statsGrid}>
        {/* Read Throughput */}
        <div className={styles.statBlock}>
          <div className={styles.statHeader}>
            <ArrowDown className={styles.statIconRead} />
            <span className={styles.statLabel}>READ</span>
          </div>
          <motion.div
            className={styles.statValue}
            key={ssd.readThroughput}
            initial={{ opacity: 0.6 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2 }}
          >
            {ssd.readThroughput.toFixed(1)}
            <span className={styles.statUnit}>MB/s</span>
          </motion.div>
          <div className={styles.statMeta}>
            <span className={styles.avgChip}>
              Avg: {ssd.avgReadThroughput ? ssd.avgReadThroughput.toFixed(1) : '—'}
            </span>
            <span className={`${styles.deltaChip} ${
              readDelta.isNeutral ? styles.deltaNeutral :
              readDelta.isPositive ? styles.deltaPositive : styles.deltaNegative
            }`}>
              {readDelta.isNeutral ? (
                <Minus className={styles.deltaIcon} />
              ) : readDelta.isPositive ? (
                <TrendingUp className={styles.deltaIcon} />
              ) : (
                <TrendingDown className={styles.deltaIcon} />
              )}
              {readDelta.text}
            </span>
          </div>
        </div>

        {/* Write Throughput */}
        <div className={styles.statBlock}>
          <div className={styles.statHeader}>
            <ArrowUp className={styles.statIconWrite} />
            <span className={styles.statLabel}>WRITE</span>
          </div>
          <motion.div
            className={styles.statValue}
            key={ssd.writeThroughput}
            initial={{ opacity: 0.6 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2 }}
          >
            {ssd.writeThroughput.toFixed(1)}
            <span className={styles.statUnit}>MB/s</span>
          </motion.div>
          <div className={styles.statMeta}>
            <span className={styles.avgChip}>
              Avg: {ssd.avgWriteThroughput ? ssd.avgWriteThroughput.toFixed(1) : '—'}
            </span>
            <span className={`${styles.deltaChip} ${
              writeDelta.isNeutral ? styles.deltaNeutral :
              writeDelta.isPositive ? styles.deltaPositive : styles.deltaNegative
            }`}>
              {writeDelta.isNeutral ? (
                <Minus className={styles.deltaIcon} />
              ) : writeDelta.isPositive ? (
                <TrendingUp className={styles.deltaIcon} />
              ) : (
                <TrendingDown className={styles.deltaIcon} />
              )}
              {writeDelta.text}
            </span>
          </div>
        </div>
      </div>

      {/* Footer: IOPS + Queue */}
      <div className={styles.footer}>
        <div className={styles.footerItem}>
          <Activity className={styles.footerIcon} />
          <span className={styles.footerLabel}>IOPS</span>
          <span className={styles.footerValue}>
            R: {ssd.readIOPS !== undefined ? ssd.readIOPS.toFixed(0) : '—'}
          </span>
          <span className={styles.footerValue}>
            W: {ssd.writeIOPS !== undefined ? ssd.writeIOPS.toFixed(0) : '—'}
          </span>
        </div>
        <div className={styles.footerDivider} />
        <div className={styles.footerItem}>
          <Layers className={styles.footerIcon} />
          <span className={styles.footerLabel}>Queue</span>
          <span className={styles.footerValueAccent}>{ssd.ioQueueDepth}</span>
        </div>
      </div>
    </div>
  );
}
