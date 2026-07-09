// Created by Metrum AI for Solidigm

import { motion, AnimatePresence } from 'motion/react';
import { Clock, Zap, TrendingUp } from 'lucide-react';
import type { Message } from '@/pages/Home';
import styles from '@/styles/components/ComparisonArena.module.css';

interface ComparisonArenaProps {
  // Baseline (left panel)
  baselineMessages: Message[];
  isBaselineLoading: boolean;
  baselineTTFT: number | null;
  bestBaselineTTFT: number | null;
  // LMCache/SSD (right panel)
  lmcacheMessages: Message[];
  isLmcacheLoading: boolean;
  lmcacheTTFT: number | null;
  bestLmcacheTTFT: number | null;
  // Computed
  speedup: number | null;
  cacheHitRate: number;
  // GPU Power (live from metrics)
  baselinePower?: number;
  lmcachePower?: number;
  // Energy-based efficiency for Column 3 (null = use instantaneous fallback)
  energyEfficiency?: number | null;
  // Best-performing metrics (all-time best across all queries)
  bestSpeedup?: number | null;
  // TTFT pair that produced best speedup (so displayed values match the Xx faster)
  ttftAtBestSpeedup?: { baseline: number; lmcache: number } | null;
  // Average power across the scenario
  avgBaselinePower?: number | null;
  avgLmcachePower?: number | null;
  // Power pair that produced best efficiency (so displayed values match the Xx more efficient)
  powerAtBestEfficiency?: { baseline: number; lmcache: number } | null;
}


export function ComparisonArena({
  baselineMessages,
  isBaselineLoading,
  baselineTTFT,
  bestBaselineTTFT,
  lmcacheMessages,
  isLmcacheLoading,
  lmcacheTTFT,
  bestLmcacheTTFT,
  speedup,
  cacheHitRate,
  baselinePower = 0,
  lmcachePower = 0,
  energyEfficiency = null,
  bestSpeedup = null,
  ttftAtBestSpeedup = null,
  avgBaselinePower = null,
  avgLmcachePower = null,
  powerAtBestEfficiency = null,
}: ComparisonArenaProps) {
  // No auto-scroll - user controls scrolling manually like ChatGPT

  // Use actual messages - no demo fallback
  const baselineDisplay = baselineMessages;
  const lmcacheDisplay = lmcacheMessages;

  // Middle panel: show only run-derived TTFT and avg GPU power (no live updates so numbers stay stable)
  const displayBaselineTTFT = (ttftAtBestSpeedup?.baseline ?? baselineTTFT) ?? null;
  const displayLmcacheTTFT = (ttftAtBestSpeedup?.lmcache ?? lmcacheTTFT) ?? null;
  const displayBaselinePower = (powerAtBestEfficiency?.baseline ?? avgBaselinePower) ?? null;
  const displayLmcachePower = (powerAtBestEfficiency?.lmcache ?? avgLmcachePower) ?? null;

  // Speedup / efficiency: prefer best all-time, fall back to current run
  const ttftSpeedup = bestSpeedup ?? speedup ?? null;
  const powerEfficiency = energyEfficiency ?? (
    (displayLmcachePower != null && displayLmcachePower > 0 && displayBaselinePower != null)
      ? displayBaselinePower / displayLmcachePower
      : null
  );

  return (
    <motion.div
      className={styles.arena}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.6 }}
    >
      {/* ===== LATENCY + POWER IMPACT BAR ===== */}
      <div className={styles.impactBar}>
        <div className={styles.impactHeader}>
          <h2 className={styles.impactTitle}>Latency + Power Impact</h2>
          <p className={styles.impactSubtitle}>Baseline vs NVMe KV Offload</p>
        </div>

        <div className={styles.impactGrid}>
          {/* Column 1: Baseline (two stacked cards) */}
          <motion.div
            className={styles.baselineColumn}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.4 }}
          >
            {/* TTFT Card */}
            <div className={styles.baselineCard}>
              <div className={styles.metricRow}>
                <div className={styles.metricLeft}>
                  <div className={styles.metricIconWrap}>
                    <Clock className={styles.metricIcon} />
                  </div>
                  <div className={styles.metricInfo}>
                    <span className={styles.metricLabel}>TTFT</span>
                    <span className={styles.metricSublabel}>BASELINE</span>
                  </div>
                </div>
                <div className={styles.metricRight}>
                  {displayBaselineTTFT !== null ? (
                    <>
                      <span className={styles.metricValueDark}>{displayBaselineTTFT.toFixed(1)}</span>
                      <span className={styles.metricUnitDark}>s</span>
                    </>
                  ) : (
                    <span className={styles.idlePulse}>
                      <span className={styles.idleLine} />
                      <span className={styles.idleDot} />
                    </span>
                  )}
                </div>
              </div>
            </div>
            {/* GPU Power Card */}
            <div className={styles.baselineCard}>
              <div className={styles.metricRow}>
                <div className={styles.metricLeft}>
                  <div className={styles.metricIconWrap}>
                    <Zap className={styles.metricIcon} />
                  </div>
                  <div className={styles.metricInfo}>
                    <span className={styles.metricLabel}>GPU Power</span>
                    <span className={styles.metricSublabel}>BASELINE</span>
                  </div>
                </div>
                <div className={styles.metricRight}>
                  {displayBaselinePower != null && displayBaselinePower > 0 ? (
                    <>
                      <span className={styles.metricValueDark}>{Math.round(displayBaselinePower)}</span>
                      <span className={styles.metricUnitDark}>W</span>
                    </>
                  ) : (
                    <span className={styles.idlePulse}>
                      <span className={styles.idleLine} />
                      <span className={styles.idleDot} />
                    </span>
                  )}
                </div>
              </div>
            </div>
          </motion.div>

          {/* Column 2: NVMe KV Offload (two stacked cards) */}
          <motion.div
            className={styles.offloadColumn}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.4 }}
          >
            {/* TTFT Card */}
            <div className={styles.offloadCard}>
              <div className={styles.metricRow}>
                <div className={styles.metricLeft}>
                  <div className={styles.metricIconWrap}>
                    <Clock className={styles.metricIcon} />
                  </div>
                  <div className={styles.metricInfo}>
                    <span className={styles.metricLabel}>TTFT</span>
                    <span className={`${styles.metricSublabel} ${styles.metricSublabelPurple}`}>NVMe KV OFFLOAD</span>
                  </div>
                </div>
                <div className={styles.metricRight}>
                  {displayLmcacheTTFT !== null ? (
                    <>
                      <span className={styles.metricValuePurple}>{displayLmcacheTTFT.toFixed(1)}</span>
                      <span className={styles.metricUnitPurple}>s</span>
                    </>
                  ) : (
                    <span className={`${styles.idlePulse} ${styles.idlePulsePurple}`}>
                      <span className={styles.idleLine} />
                      <span className={styles.idleDot} />
                    </span>
                  )}
                </div>
              </div>
            </div>
            {/* GPU Power Card */}
            <div className={styles.offloadCard}>
              <div className={styles.metricRow}>
                <div className={styles.metricLeft}>
                  <div className={styles.metricIconWrap}>
                    <Zap className={styles.metricIcon} />
                  </div>
                  <div className={styles.metricInfo}>
                    <span className={styles.metricLabel}>GPU Power</span>
                    <span className={`${styles.metricSublabel} ${styles.metricSublabelPurple}`}>KV cache offload</span>
                  </div>
                </div>
                <div className={styles.metricRight}>
                  {displayLmcachePower != null && displayLmcachePower > 0 ? (
                    <>
                      <span className={styles.metricValuePurple}>{Math.round(displayLmcachePower)}</span>
                      <span className={styles.metricUnitPurple}>W</span>
                    </>
                  ) : (
                    <span className={`${styles.idlePulse} ${styles.idlePulsePurple}`}>
                      <span className={styles.idleLine} />
                      <span className={styles.idleDot} />
                    </span>
                  )}
                </div>
              </div>
            </div>
          </motion.div>

          {/* Column 3: Comparison (two stacked cards) */}
          <motion.div
            className={styles.comparisonColumn}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.4 }}
          >
            {/* TTFT Speedup */}
            <div className={styles.comparisonCard}>
              <div className={styles.comparisonLeft}>
                <TrendingUp className={styles.comparisonIcon} />
                <div className={styles.comparisonTextGroup}>
                  <span className={styles.comparisonText}>
                    NVMe KV offload achieves {ttftSpeedup !== null ? `${ttftSpeedup.toFixed(1)}×` : '—×'} lower
                  </span>
                  <span className={styles.comparisonText}>first-token latency than baseline</span>
                </div>
              </div>
              <span className={styles.comparisonValue}>
                {ttftSpeedup !== null ? `${ttftSpeedup.toFixed(1)}x` : (
                  <span className={`${styles.idlePulse} ${styles.idlePulseWhite}`}>
                    <span className={styles.idleLine} />
                    <span className={styles.idleDot} />
                  </span>
                )}
              </span>
            </div>
            {/* Power Efficiency */}
            <div className={styles.comparisonCard}>
              <div className={styles.comparisonLeft}>
                <Zap className={styles.comparisonIcon} />
                <div className={styles.comparisonTextGroup}>
                  <span className={styles.comparisonText}>
                    NVMe KV offload consumes {powerEfficiency !== null ? `${powerEfficiency.toFixed(1)}×` : '—×'} less
                  </span>
                  <span className={styles.comparisonText}>GPU power than baseline</span>
                </div>
              </div>
              <span className={styles.comparisonValue}>
                {powerEfficiency !== null ? `${powerEfficiency.toFixed(1)}x` : (
                  <span className={`${styles.idlePulse} ${styles.idlePulseWhite}`}>
                    <span className={styles.idleLine} />
                    <span className={styles.idleDot} />
                  </span>
                )}
              </span>
            </div>
          </motion.div>
        </div>
      </div>

      {/* ===== CHAT PANELS ===== */}
      <div className={styles.panelsContainer}>
        {/* Baseline Panel */}
        <div className={styles.panelBaseline}>
          <div className={styles.panelHeader}>
            <div className={styles.panelIndicator} />
            <span className={styles.panelTitle}>GPU Memory</span>
            {baselineTTFT !== null && (
              <div className={styles.panelTTFT}>
                <Clock className={styles.panelTTFTIcon} />
                <span>{baselineTTFT.toFixed(2)}s</span>
              </div>
            )}
          </div>
          <div className={`${styles.messagesArea} scrollbar-thin`}>
            {baselineDisplay.length === 0 && !isBaselineLoading ? (
              <div className={styles.emptyState}>
                <span className={styles.emptyText}>Select a scenario to begin</span>
              </div>
            ) : (
              <AnimatePresence initial={false}>
                {baselineDisplay.map((message) => (
                  <motion.div
                    key={message.id}
                    className={styles.messageRow}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3 }}
                  >
                    {message.role === 'user' ? (
                      <div className={styles.userMessage}>
                        <p className={styles.userText}>{message.content}</p>
                      </div>
                    ) : (
                      <>
                        {message.ttft !== undefined && (
                          <div className={styles.responseMeta}>
                            <span className={styles.metaText}>{message.ttft.toFixed(2)}s</span>
                          </div>
                        )}
                        <div className={styles.assistantMessage}>
                          <p className={styles.assistantText}>{message.content}</p>
                        </div>
                      </>
                    )}
                  </motion.div>
                ))}
              </AnimatePresence>
            )}
            {isBaselineLoading && (
              <div className={styles.loadingIndicator}>
                <span className={styles.loadingDot} style={{ animationDelay: '0ms' }} />
                <span className={styles.loadingDot} style={{ animationDelay: '150ms' }} />
                <span className={styles.loadingDot} style={{ animationDelay: '300ms' }} />
              </div>
            )}
          </div>
        </div>

        {/* Center Divider */}
        <div className={styles.centerDivider}>
          <div className={styles.dividerLine} />
          <div className={styles.dividerGlow} />
        </div>

        {/* SSD Cache Panel */}
        <div className={styles.panelSSD}>
          <div className={styles.panelHeaderSSD}>
            <div className={styles.panelIndicatorSSD} />
            <span className={styles.panelTitleSSD}>NVMe KV Offload</span>
            {lmcacheTTFT !== null && (
              <div className={styles.panelTTFTSSD}>
                <Clock className={styles.panelTTFTIcon} />
                <span>{lmcacheTTFT.toFixed(2)}s</span>
              </div>
            )}
          </div>
          <div className={`${styles.messagesAreaSSD} scrollbar-thin`}>
            {lmcacheDisplay.length === 0 && !isLmcacheLoading ? (
              <div className={styles.emptyStateSSD}>
                <span className={styles.emptyTextSSD}>Select a scenario to begin</span>
              </div>
            ) : (
              <AnimatePresence initial={false}>
                {lmcacheDisplay.map((message) => (
                  <motion.div
                    key={message.id}
                    className={styles.messageRow}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3 }}
                  >
                    {message.role === 'user' ? (
                      <div className={styles.userMessageSSD}>
                        <p className={styles.userText}>{message.content}</p>
                      </div>
                    ) : (
                      <>
                        {message.ttft !== undefined && (
                          <div className={styles.responseMetaSSD}>
                            <span className={styles.metaDot}>&#8226;</span>
                            <span className={styles.metaTextSSD}>{message.ttft.toFixed(2)}s</span>
                            {message.cacheHit && (
                              <span className={styles.cacheBadge}>KV cache offload</span>
                            )}
                          </div>
                        )}
                        <div className={styles.assistantMessageSSD}>
                          <p className={styles.assistantText}>{message.content}</p>
                        </div>
                      </>
                    )}
                  </motion.div>
                ))}
              </AnimatePresence>
            )}
            {isLmcacheLoading && (
              <div className={styles.loadingIndicatorSSD}>
                <span className={styles.loadingDotSSD} style={{ animationDelay: '0ms' }} />
                <span className={styles.loadingDotSSD} style={{ animationDelay: '150ms' }} />
                <span className={styles.loadingDotSSD} style={{ animationDelay: '300ms' }} />
              </div>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
