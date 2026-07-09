// Created by Metrum AI for Solidigm

import { useRef, useEffect } from 'react';
import { Clock, Zap, Trophy } from 'lucide-react';
import type { Message } from '@/pages/Home';
import styles from '@/styles/components/ChatPanel.module.css';

interface ChatPanelProps {
  title: string;
  variant: 'baseline' | 'offload';
  messages: Message[];
  isLoading: boolean;
  latestTTFT: number | null;
  bestTTFT: number | null;
  queryCount: number;
}

export function ChatPanel({
  title,
  variant,
  messages,
  isLoading,
  latestTTFT,
  bestTTFT,
  queryCount,
}: ChatPanelProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isBaseline = variant === 'baseline';

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className={`${styles.container} ${isBaseline ? styles.containerBaseline : styles.containerLmcache}`}>
      {/* Header */}
      <div className={`${styles.header} ${isBaseline ? styles.headerBaseline : styles.headerLmcache}`}>
        <div className={styles.headerLeft}>
          <div className={`${styles.indicator} ${isBaseline ? styles.indicatorBaseline : styles.indicatorLmcache}`}></div>
          <h3 className={`${styles.title} ${isBaseline ? styles.titleBaseline : styles.titleLmcache}`}>
            {title}
          </h3>
        </div>
        <div className={styles.headerRight}>
          <div className={styles.ttftDisplay}>
            <Clock className={styles.ttftIcon} />
            <span className={`${styles.ttftValue} ${isBaseline ? styles.ttftValueBaseline : styles.ttftValueLmcache}`}>
              {latestTTFT !== null ? `${latestTTFT.toFixed(2)}s` : '--'}
            </span>
          </div>
          <div className={styles.queryBadge}>
            <Zap className={`${styles.queryIcon} ${isBaseline ? styles.queryIconBaseline : styles.queryIconLmcache}`} />
            <span className={styles.queryCount}>{queryCount}</span>
          </div>
        </div>
      </div>

      {/* Best TTFT */}
      {bestTTFT !== null && (
        <div className={`${styles.bestTtft} ${isBaseline ? styles.bestTtftBaseline : styles.bestTtftLmcache}`}>
          <Trophy className={`${styles.bestTtftIcon} ${isBaseline ? styles.bestTtftIconBaseline : styles.bestTtftIconLmcache}`} />
          <span className={styles.bestTtftLabel}>Best TTFT:</span>
          <span className={`${styles.bestTtftValue} ${isBaseline ? styles.bestTtftValueBaseline : styles.bestTtftValueLmcache}`}>
            {bestTTFT.toFixed(3)}s
          </span>
        </div>
      )}

      {/* Messages */}
      <div className={styles.messages}>
        {messages.length === 0 ? (
          <div className={styles.emptyState}>
            <div className={styles.emptyContent}>
              <div className={styles.emptyIcon}>
                <Zap className={`${styles.emptyIconInner} ${isBaseline ? styles.emptyIconBaseline : styles.emptyIconLmcache}`} />
              </div>
              <p className={styles.emptyText}>Waiting for query...</p>
              <p className={styles.emptySubtext}>
                {isBaseline ? 'Standard vLLM inference' : 'Solidigm SSD KV Cache Offload'}
              </p>
            </div>
          </div>
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              className={`${styles.messageRow} ${message.role === 'user' ? styles.messageRowUser : styles.messageRowAssistant}`}
            >
              <div className={`${styles.messageBubble} ${
                message.role === 'user'
                  ? styles.messageBubbleUser
                  : `${styles.messageBubbleAssistant} ${isBaseline ? styles.messageBubbleAssistantBaseline : styles.messageBubbleAssistantLmcache}`
              }`}>
                {message.role === 'assistant' && message.ttft !== undefined && (
                  <div className={styles.messageMeta}>
                    <Clock className={styles.metaIcon} />
                    <span>TTFT: {message.ttft.toFixed(3)}s</span>
                    {message.cacheHit && (
                      <span className={styles.cacheHitBadge}>Cache Hit</span>
                    )}
                  </div>
                )}
                <p className={`${styles.messageContent} ${message.role === 'user' ? '' : styles.messageContentAssistant}`}>
                  {message.content}
                </p>
              </div>
            </div>
          ))
        )}

        {isLoading && (
          <div className={`${styles.messageRow} ${styles.messageRowAssistant}`}>
            <div className={`${styles.loadingBubble} ${isBaseline ? styles.loadingBubbleBaseline : styles.loadingBubbleLmcache}`}>
              <div className={styles.loadingContent}>
                <div className={styles.loadingDots}>
                  {[0, 1, 2].map((i) => (
                    <span
                      key={i}
                      className={`${styles.loadingDot} ${isBaseline ? styles.loadingDotBaseline : styles.loadingDotLmcache} animate-bounce`}
                      style={{ animationDelay: `${i * 150}ms` }}
                    />
                  ))}
                </div>
                <span className={styles.loadingText}>Processing...</span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
}
