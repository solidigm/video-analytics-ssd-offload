// Created by Metrum AI for Solidigm

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Users, Play, X, Zap, BookOpen, AlertTriangle, Eye, Square } from 'lucide-react';
import { getActiveBenchmark, stopActiveBenchmark } from '@/services/metricsService';
import styles from '@/styles/components/MultiUserConfig.module.css';

export type ContextMode = 'quick' | 'long_context';

export interface MultiUserSettings {
  numUsers: number;
  contextMode: ContextMode;
}

interface MultiUserConfigProps {
  open: boolean;
  onClose: () => void;
  onStart: (settings: MultiUserSettings) => void;
  onViewActive?: (runId: string, numUsers: number, contextMode?: string) => void;
}

export function MultiUserConfig({ open, onClose, onStart, onViewActive }: MultiUserConfigProps) {
  const [numUsers, setNumUsers] = useState(10);
  const [contextMode, setContextMode] = useState<ContextMode>('quick');

  // Active benchmark detection
  const [activeBenchmark, setActiveBenchmark] = useState<{
    run_id: string; num_users: number; elapsed: number; context_mode?: string;
  } | null>(null);
  const [stopping, setStopping] = useState(false);

  // Check for active benchmark when dialog opens
  useEffect(() => {
    if (!open) {
      setActiveBenchmark(null);
      setStopping(false);
      return;
    }
    getActiveBenchmark().then((data) => {
      if (data.active && data.run_id) {
        setActiveBenchmark({
          run_id: data.run_id,
          num_users: data.num_users ?? 0,
          elapsed: data.elapsed ?? 0,
          context_mode: data.context_mode,
        });
      } else {
        setActiveBenchmark(null);
      }
    }).catch(() => setActiveBenchmark(null));
  }, [open]);

  const handleStop = async () => {
    setStopping(true);
    await stopActiveBenchmark();
    setActiveBenchmark(null);
    setStopping(false);
  };

  const handleView = () => {
    if (activeBenchmark && onViewActive) {
      onViewActive(activeBenchmark.run_id, activeBenchmark.num_users, activeBenchmark.context_mode);
    }
  };

  const handleStart = () => {
    onStart({ numUsers, contextMode });
  };

  const previewCount = Math.min(numUsers, 40);
  const overflow = numUsers - previewCount;

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className={styles.overlay}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          <motion.div
            className={styles.dialog}
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.3, type: 'spring', damping: 25 }}
          >
            {/* Header */}
            <div className={styles.header}>
              <div className={styles.headerLeft}>
                <div className={styles.headerIconWrap}>
                  <Users className={styles.headerIcon} />
                </div>
                <div>
                  <h2 className={styles.title}>Multi-User Simulation</h2>
                  <p className={styles.subtitle}>Burst mode · All users send simultaneously</p>
                </div>
              </div>
              <button className={styles.closeButton} onClick={onClose}>
                <X size={18} />
              </button>
            </div>

            {/* Body */}
            <div className={styles.body}>
              {/* Active Benchmark Banner */}
              {activeBenchmark && (
                <div className={styles.activeBanner}>
                  <div className={styles.activeBannerLeft}>
                    <AlertTriangle size={16} />
                    <span>
                      A benchmark is already running ({activeBenchmark.num_users} users, {Math.round(activeBenchmark.elapsed)}s)
                    </span>
                  </div>
                  <div className={styles.activeBannerActions}>
                    {onViewActive && (
                      <button className={styles.viewButton} onClick={handleView}>
                        <Eye size={14} /> View
                      </button>
                    )}
                    <button className={styles.stopActiveButton} onClick={handleStop} disabled={stopping}>
                      <Square size={14} /> {stopping ? 'Stopping...' : 'Stop'}
                    </button>
                  </div>
                </div>
              )}

              {/* Number of Users - Slider */}
              <div className={styles.section}>
                <div className={styles.labelRow}>
                  <label className={styles.label}>Number of Users</label>
                  <span className={styles.sliderValue}>{numUsers}</span>
                </div>
                <input
                  type="range"
                  min={10}
                  max={500}
                  step={10}
                  value={numUsers}
                  onChange={(e) => setNumUsers(Number(e.target.value))}
                  className={styles.slider}
                />
                <div className={styles.sliderLabels}>
                  <span>10</span>
                  <span>250</span>
                  <span>500</span>
                </div>
              </div>

              {/* Context Mode Toggle */}
              <div className={styles.section}>
                <label className={styles.label}>Context Mode</label>
                <div className={styles.modeToggle}>
                  <button
                    className={`${styles.modeBtn} ${contextMode === 'quick' ? styles.modeBtnActive : ''}`}
                    onClick={() => setContextMode('quick')}
                  >
                    <Zap size={14} />
                    Quick
                  </button>
                  <button
                    className={`${styles.modeBtn} ${contextMode === 'long_context' ? styles.modeBtnActive : ''}`}
                    onClick={() => setContextMode('long_context')}
                  >
                    <BookOpen size={14} />
                    Long Context
                  </button>
                </div>
                <p className={styles.modeHint}>
                  {contextMode === 'quick'
                    ? '5\u201310 games · ~30k tokens · Fast benchmarks'
                    : '8\u201316 games · ~180k tokens · Showcases SSD offloading'}
                </p>
              </div>

              {/* Preview */}
              <div className={styles.preview}>
                <div className={styles.previewLabel}>Simulation Preview</div>
                <div className={styles.previewUsers}>
                  {Array.from({ length: previewCount }).map((_, i) => (
                    <motion.div
                      key={i}
                      className={styles.previewUser}
                      initial={{ opacity: 0, scale: 0 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ delay: i * 0.015, type: 'spring', damping: 15 }}
                    >
                      <Users size="1em" />
                    </motion.div>
                  ))}
                  {overflow > 0 && (
                    <motion.span
                      className={styles.previewOverflow}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: previewCount * 0.015 }}
                    >
                      +{overflow}
                    </motion.span>
                  )}
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className={styles.footer}>
              <button className={styles.cancelButton} onClick={onClose}>
                Cancel
              </button>
              <button
                className={styles.startButton}
                onClick={handleStart}
                disabled={!!activeBenchmark}
              >
                <Play size={16} />
                Start Benchmark
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
