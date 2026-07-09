// Created by Metrum AI for Solidigm

import { Info } from 'lucide-react';
import styles from '@/styles/components/InfoCard.module.css';

export function InfoCard() {
  return (
    <div className={`card ${styles.container}`}>
      <div className={styles.header}>
        <div className={styles.iconWrap}>
          <Info className={styles.icon} />
        </div>
        <h3 className={styles.title}>Info</h3>
      </div>

      <div className={styles.details}>
        <p className={styles.detailRow}>
          <span className={styles.label}>LLM Model:</span>
          <span className={styles.value}>MegaBeam-Mistral-7B-300k</span>
        </p>
        <p className={styles.detailRow}>
          <span className={styles.label}>LLM Serving backend:</span>
          <span className={styles.value}>NVIDIA Dynamo</span>
        </p>
        <p className={styles.detailRow}>
          <span className={styles.label}>Vision Language Model:</span>
          <span className={styles.value}>Qwen3-VL-30B-A3B-Thinking</span>
        </p>
        <div className={styles.highlightRow}>
          <span className={styles.highlightLabel}>KV Cache offload SSD:</span>
          <span className={styles.highlightValue}>Solidigm D7-PS1030</span>
        </div>
      </div>
    </div>
  );
}
