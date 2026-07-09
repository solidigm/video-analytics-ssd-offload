// Created by Metrum AI for Solidigm

import { Zap, Database, HardDrive } from 'lucide-react';
import type { LLMMetrics } from '@/types/metrics';
import { MetricCard } from './MetricCard';
import styles from '@/styles/components/metrics/LLMMetricsCard.module.css';

interface LLMMetricsCardProps {
  metrics: LLMMetrics;
}

interface ServiceMetrics {
  name: string;
  generationTput: number;
  promptTput: number;
  cacheHit: number;
  kvCacheUsage: number;
  color: string;
}

export function LLMMetricsCard({ metrics }: LLMMetricsCardProps) {
  const { generationThroughput, cacheHitRate } = metrics;
  const promptThroughput = metrics.promptThroughput || { baseline: 0, lmcache: 0, vlm: 0 };
  const kvCacheUsage = metrics.kvCacheUsage || { baseline: 0, lmcache: 0, vlm: 0 };
  const cacheHitRates = metrics.cacheHitRates || {
    baseline: 0,
    lmcache: cacheHitRate,
    vlm: 0,
  };

  const services: ServiceMetrics[] = [
    {
      name: 'Baseline',
      generationTput: generationThroughput.baseline,
      promptTput: promptThroughput.baseline,
      cacheHit: cacheHitRates.baseline,
      kvCacheUsage: kvCacheUsage.baseline ?? 0,
      color: 'var(--color-baseline)',
    },
    {
      name: 'SSD Cache',
      generationTput: generationThroughput.lmcache,
      promptTput: promptThroughput.lmcache,
      cacheHit: cacheHitRates.lmcache,
      kvCacheUsage: kvCacheUsage.lmcache ?? 0,
      color: 'var(--color-lmcache)',
    },
    {
      name: 'VLM',
      generationTput: generationThroughput.vlm || 0,
      promptTput: promptThroughput.vlm || 0,
      cacheHit: cacheHitRates.vlm,
      kvCacheUsage: kvCacheUsage.vlm ?? 0,
      color: 'var(--solidigm-blue-secondary)',
    },
  ];

  const hasAnyActivity = services.some(s => s.generationTput > 0 || s.promptTput > 0);

  return (
    <MetricCard title="Model Performance" icon={<Zap />}>
      <div className={styles.liveStatus}>
        <span className={`${styles.liveDot} ${hasAnyActivity ? styles.liveDotActive : ''}`} />
        <span className={styles.liveLabel}>{hasAnyActivity ? 'Active' : 'Polling'}</span>
      </div>
      <div className={styles.servicesGrid}>
        {services.map((service) => (
          <div key={service.name} className={styles.serviceSection}>
            <div className={styles.serviceName} style={{ color: service.color }}>
              {service.name}
            </div>
            <div className={styles.serviceMetrics}>
              <div className={styles.metricItem}>
                <div className={styles.metricHeader}>
                  <Zap className={styles.metricIcon} />
                  <span className={styles.metricLabel}>Throughput</span>
                </div>
                <div className={styles.throughputRow}>
                  <span className={styles.throughputValue}>
                    {service.generationTput.toFixed(0)}
                  </span>
                  <span className={styles.throughputUnit}>tok/s</span>
                </div>
              </div>

              <div className={styles.metricItem}>
                <div className={styles.metricHeader}>
                  <Database className={styles.metricIcon} />
                  <span className={styles.metricLabel}>Cache Hit</span>
                </div>
                <div className={styles.cacheHitRow}>
                  <span className={styles.cacheHitValue}>
                    {service.cacheHit.toFixed(0)}%
                  </span>
                  <div className={styles.cacheHitBar}>
                    <div
                      className={styles.cacheHitFill}
                      style={{ width: `${Math.max(0, Math.min(service.cacheHit, 100))}%`, background: service.color }}
                    />
                  </div>
                </div>
              </div>

              <div className={styles.metricItem}>
                <div className={styles.metricHeader}>
                  <HardDrive className={styles.metricIcon} />
                  <span className={styles.metricLabel}>KV Cache</span>
                </div>
                <div className={styles.cacheHitRow}>
                  <span className={styles.cacheHitValue}>
                    {service.kvCacheUsage.toFixed(0)}%
                  </span>
                  <div className={styles.cacheHitBar}>
                    <div
                      className={styles.cacheHitFill}
                      style={{ width: `${Math.max(0, Math.min(service.kvCacheUsage, 100))}%`, background: service.color }}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </MetricCard>
  );
}
