// Created by Metrum AI for Solidigm

import { useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Clock, MessageSquare } from 'lucide-react';
import type { Message } from '@/pages/Home';
import styles from '@/styles/components/ResponsePanel.module.css';

interface ResponsePanelProps {
  variant: 'baseline' | 'lmcache';
  messages: Message[];
  isLoading: boolean;
  latestTTFT: number | null;
  bestTTFT: number | null;
}

const DEMO_USER_QUERY = "What defensive formations were used in last night's game and how effective were they?";

const DEMO_RESPONSE = `In last night's game, the defense showed multiple two-high safety looks, primarily to limit explosive plays and disguise coverage. The identifiable looks included:

Cover 2 (Zone): Two deep safeties splitting the field with corners squatting in the flats, used mainly on early downs and against quick-game concepts.

Two-High Pre-Snap Rotations: Safeties aligned in a two-high shell before rotating post-snap into single-high or man looks to disguise intentions.

These two-high shells were most frequently shown in obvious passing situations and against spread formations, with occasional post-snap rotation to counter quarterback reads.`;

export function ResponsePanel({
  variant,
  messages,
  isLoading,
  latestTTFT,
  bestTTFT,
}: ResponsePanelProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isLmcache = variant === 'lmcache';

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const title = isLmcache ? 'SSD Cache' : 'Baseline';
  const subtitle = isLmcache ? 'Solidigm NVMe Offload' : 'Standard GPU Memory';

  // Use demo messages when no real messages
  const displayMessages = messages.length > 0 ? messages : [
    {
      id: 'demo-user',
      role: 'user' as const,
      content: DEMO_USER_QUERY,
      timestamp: Date.now(),
    },
    {
      id: 'demo-assistant',
      role: 'assistant' as const,
      content: DEMO_RESPONSE,
      timestamp: Date.now(),
      ttft: isLmcache ? 0.4 : 13.4,
      cacheHit: isLmcache,
    },
  ];

  return (
    <motion.div
      className={`${styles.panel} ${isLmcache ? styles.panelLmcache : styles.panelBaseline}`}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.4, 0, 0.2, 1] }}
    >
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <div className={`${styles.indicator} ${isLmcache ? styles.indicatorLmcache : styles.indicatorBaseline}`} />
          <div className={styles.titleGroup}>
            <h3 className={styles.title}>{title}</h3>
            <span className={styles.subtitle}>{subtitle}</span>
          </div>
        </div>

        <div className={styles.metrics}>
          <AnimatePresence mode="wait">
            {latestTTFT !== null && (
              <motion.div
                key={`ttft-${latestTTFT}`}
                className={styles.metric}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                transition={{ duration: 0.2 }}
              >
                <span className={styles.metricLabel}>TTFT</span>
                <span className={`${styles.metricValue} ${isLmcache ? styles.metricValueLmcache : styles.metricValueBaseline}`}>
                  {latestTTFT.toFixed(2)}s
                </span>
              </motion.div>
            )}
          </AnimatePresence>
          {bestTTFT !== null && (
            <div className={styles.metric}>
              <span className={styles.metricLabel}>Best</span>
              <span className={styles.metricValueSmall}>
                {bestTTFT.toFixed(2)}s
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className={`${styles.messages} scrollbar-thin`}>
        <AnimatePresence initial={false}>
          {displayMessages.map((message, index) => (
              <motion.div
                key={message.id}
                className={styles.messageRow}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{
                  duration: 0.3,
                  ease: [0.4, 0, 0.2, 1],
                  delay: index === displayMessages.length - 1 ? 0.05 : 0
                }}
              >
                {message.role === 'user' ? (
                  <div className={styles.userMessage}>
                    <span className={styles.userLabel}>Q</span>
                    <p className={styles.userText}>{message.content}</p>
                  </div>
                ) : (
                  <div className={styles.assistantMessage}>
                    {message.ttft !== undefined && (
                      <div className={styles.responseMeta}>
                        <Clock className={styles.metaIcon} />
                        <span className={styles.metaText}>{message.ttft.toFixed(3)}s</span>
                        {message.cacheHit && (
                          <span className={styles.cacheBadge}>SSD Cache</span>
                        )}
                      </div>
                    )}
                    <p className={styles.assistantText}>{message.content}</p>
                  </div>
                )}
              </motion.div>
            ))}
          </AnimatePresence>

        <AnimatePresence>
          {isLoading && (
            <motion.div
              className={styles.loadingRow}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.2 }}
            >
              <div className={styles.loadingIndicator}>
                <span className={styles.loadingDot} style={{ animationDelay: '0ms' }} />
                <span className={styles.loadingDot} style={{ animationDelay: '150ms' }} />
                <span className={styles.loadingDot} style={{ animationDelay: '300ms' }} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        <div ref={messagesEndRef} />
      </div>
    </motion.div>
  );
}
