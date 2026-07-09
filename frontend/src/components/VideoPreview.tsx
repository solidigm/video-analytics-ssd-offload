// Created by Metrum AI for Solidigm

import { Play, Volume2, Maximize } from 'lucide-react';
import styles from '@/styles/components/VideoPreview.module.css';

export function VideoPreview() {
  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <Play className={styles.headerIcon} />
          <span className={styles.headerTitle}>Preview</span>
        </div>
        <span className={styles.badge}>Soon</span>
      </div>

      <div className={styles.preview}>
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}>
            <Play className={styles.emptyIconInner} />
          </div>
          <p className={styles.emptyText}>Video clips</p>
          <p className={styles.emptySubtext}>Coming soon</p>
        </div>
      </div>

      <div className={styles.controls}>
        <span className={styles.timestamp}>0:00 / 0:00</span>
        <div className={styles.controlButtons}>
          <button className={styles.controlButton} disabled>
            <Volume2 className={styles.controlButtonIcon} />
          </button>
          <button className={styles.controlButton} disabled>
            <Maximize className={styles.controlButtonIcon} />
          </button>
        </div>
      </div>
    </div>
  );
}
