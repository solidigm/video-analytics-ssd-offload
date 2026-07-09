// Created by Metrum AI for Solidigm

import type { ReactNode } from 'react';
import { motion } from 'motion/react';
import styles from '@/styles/components/metrics/MetricCard.module.css';

interface MetricCardProps {
  title: string;
  icon?: ReactNode;
  children: ReactNode;
  variant?: 'default' | 'compact';
}

export function MetricCard({ title, icon, children, variant = 'default' }: MetricCardProps) {
  return (
    <motion.div
      className={`${styles.card} ${variant === 'compact' ? styles.cardCompact : ''}`}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
    >
      <div className={styles.header}>
        {icon && <span className={styles.icon}>{icon}</span>}
        <h4 className={styles.title}>{title}</h4>
      </div>
      <div className={styles.content}>{children}</div>
    </motion.div>
  );
}
