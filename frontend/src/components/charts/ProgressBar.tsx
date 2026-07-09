// Created by Metrum AI for Solidigm

import styles from '@/styles/components/charts/ProgressBar.module.css';

interface ProgressBarProps {
  value: number;        // Current value
  max: number;          // Max value
  label?: string;       // Label text
  showValue?: boolean;  // Show numeric value
  unit?: string;        // Unit (GB, %, etc)
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'lmcache' | 'baseline';
  size?: 'sm' | 'md' | 'lg';
}

export function ProgressBar({
  value,
  max,
  label,
  showValue = true,
  unit = '',
  variant = 'default',
  size = 'md',
}: ProgressBarProps) {
  const percentage = Math.min((value / max) * 100, 100);

  // Determine color based on percentage if variant is default
  const getAutoVariant = () => {
    if (variant !== 'default') return variant;
    if (percentage >= 90) return 'danger';
    if (percentage >= 70) return 'warning';
    return 'success';
  };

  const finalVariant = getAutoVariant();

  return (
    <div className={styles.container}>
      {(label || showValue) && (
        <div className={styles.header}>
          {label && <span className={styles.label}>{label}</span>}
          {showValue && (
            <span className={styles.value}>
              {value.toFixed(1)}{unit} / {max}{unit}
            </span>
          )}
        </div>
      )}
      <div className={`${styles.track} ${styles[`track${size.charAt(0).toUpperCase() + size.slice(1)}`]}`}>
        <div
          className={`${styles.fill} ${styles[`fill${finalVariant.charAt(0).toUpperCase() + finalVariant.slice(1)}`]}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
