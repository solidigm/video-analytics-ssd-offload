// Created by Metrum AI for Solidigm

import { motion } from 'motion/react';
import type { LLMMetrics, GPUMetrics, SSDMetrics, CPUMetrics, GPUHistory } from '@/types/metrics';
import { LLMMetricsCard } from './metrics/LLMMetricsCard';
import { GPUPowerChartCard } from './metrics/GPUPowerChartCard';
import { GPUUtilizationChartCard } from './metrics/GPUUtilizationChartCard';
import { SSDMetricsCard } from './metrics/SSDMetricsCard';
import { CPUMetricsCard } from './metrics/CPUMetricsCard';
import styles from '@/styles/components/MetricsPanel.module.css';

interface MetricsPanelProps {
  llm: LLMMetrics;
  gpus: GPUMetrics[];
  gpuHistory: GPUHistory;
  ssd: SSDMetrics;
  cpu: CPUMetrics;
}

export function MetricsPanel({ llm, gpus, gpuHistory, ssd, cpu }: MetricsPanelProps) {
  return (
    <motion.aside
      className={styles.panel}
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.4, ease: [0.4, 0, 0.2, 1] }}
    >
      <div className={styles.content}>
        <SSDMetricsCard ssd={ssd} />
        <GPUPowerChartCard gpus={gpus} history={gpuHistory} />
        <GPUUtilizationChartCard gpus={gpus} history={gpuHistory} />
        <CPUMetricsCard cpu={cpu} />
        <LLMMetricsCard metrics={llm} />
      </div>
    </motion.aside>
  );
}
