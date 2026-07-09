// Created by Metrum AI for Solidigm

import { useRef, useEffect } from 'react';
import { Clock, Zap, Trophy, Send } from 'lucide-react';
import type { Message } from '@/pages/Home';
import styles from '@/styles/components/InferencePanel.module.css';

interface InferencePanelProps {
  variant: 'baseline' | 'lmcache';
  messages: Message[];
  isLoading: boolean;
  latestTTFT: number | null;
  bestTTFT: number | null;
  query: string;
  onQueryChange: (query: string) => void;
  onSend: () => void;
}

export function InferencePanel({
  variant,
  messages,
  isLoading,
  latestTTFT,
  bestTTFT,
  query,
  onQueryChange,
  onSend,
}: InferencePanelProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isBaseline = variant === 'baseline';

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const accentColor = isBaseline ? 'var(--color-baseline)' : 'var(--color-lmcache)';

  return (
    <div className={`card ${isBaseline ? 'baseline-panel' : 'lmcache-panel'} ${styles.panel}`}>
      {/* Header */}
      <div className={`${styles.header} ${isBaseline ? styles.headerBaseline : styles.headerLmcache}`}>
        <div className={styles.headerLeft}>
          <div
            className={`${styles.indicator} animate-pulse`}
            style={{ backgroundColor: accentColor }}
          />
          <h3 className={styles.title} style={{ color: accentColor }}>
            {isBaseline ? 'Baseline vLLM' : 'LMCache + SSD'}
          </h3>
        </div>

        <div className={styles.headerRight}>
          {latestTTFT !== null && (
            <div className={styles.ttftDisplay}>
              <Clock className={styles.ttftIcon} />
              <span className={styles.ttftValue} style={{ color: accentColor }}>
                {latestTTFT.toFixed(2)}s
              </span>
            </div>
          )}

          <div className={`${styles.queryBadge} ${isBaseline ? styles.queryBadgeBaseline : styles.queryBadgeLmcache}`}>
            <Zap className={styles.queryIcon} style={{ color: accentColor }} />
            <span className={styles.queryCount} style={{ color: accentColor }}>
              {messages.filter(m => m.role === 'user').length}
            </span>
          </div>
        </div>
      </div>

      {/* Best TTFT */}
      {bestTTFT !== null && (
        <div className={`${styles.bestTtft} ${isBaseline ? styles.bestTtftBaseline : styles.bestTtftLmcache}`}>
          <Trophy className={styles.bestTtftIcon} style={{ color: accentColor }} />
          <span className={styles.bestTtftLabel}>Best:</span>
          <span className={styles.bestTtftValue} style={{ color: accentColor }}>
            {bestTTFT.toFixed(3)}s
          </span>
        </div>
      )}

      {/* Messages */}
      <div className={`${styles.messages} scrollbar-thin`}>
        {messages.length === 0 ? (
          <div className={styles.emptyState}>
            <div className={styles.emptyContent}>
              <div
                className={styles.emptyIcon}
                style={{
                  borderColor: isBaseline ? 'rgba(237, 28, 36, 0.4)' : 'rgba(118, 185, 0, 0.4)',
                  backgroundColor: isBaseline ? 'rgba(237, 28, 36, 0.08)' : 'rgba(118, 185, 0, 0.08)'
                }}
              >
                <Zap className={styles.emptyIconInner} style={{ color: accentColor }} />
              </div>
              <p className={styles.emptyText}>Ready for queries</p>
              <p className={styles.emptySubtext}>
                {isBaseline ? 'Standard inference' : 'KV cache on SSD'}
              </p>
            </div>
          </div>
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              className={`${styles.messageRow} ${message.role === 'user' ? styles.messageRowUser : styles.messageRowAssistant} animate-fadeIn`}
            >
              <div
                className={`${styles.messageBubble} ${
                  message.role === 'user'
                    ? styles.messageBubbleUser
                    : `${styles.messageBubbleAssistant} ${isBaseline ? styles.messageBubbleAssistantBaseline : styles.messageBubbleAssistantLmcache}`
                }`}
              >
                {message.role === 'assistant' && message.ttft !== undefined && (
                  <div className={styles.messageMeta}>
                    <Clock className={styles.metaIcon} />
                    <span>TTFT: {message.ttft.toFixed(3)}s</span>
                    {message.cacheHit && (
                      <span className={styles.cacheHitBadge}>Cache Hit</span>
                    )}
                  </div>
                )}
                <p className={styles.messageContent}>{message.content}</p>
              </div>
            </div>
          ))
        )}

        {isLoading && (
          <div className={`${styles.loadingRow} animate-fadeIn`}>
            <div className={`${styles.loadingBubble} ${isBaseline ? styles.loadingBubbleBaseline : styles.loadingBubbleLmcache}`}>
              <div className={styles.loadingContent}>
                <div className={styles.loadingDots}>
                  {[0, 150, 300].map((delay) => (
                    <span
                      key={delay}
                      className={`${styles.loadingDot} animate-bounce`}
                      style={{
                        backgroundColor: accentColor,
                        animationDelay: `${delay}ms`
                      }}
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

      {/* Input */}
      <div className={styles.inputArea}>
        <div className={styles.inputRow}>
          <input
            type="text"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && onSend()}
            placeholder="Ask a question..."
            className={styles.input}
            disabled={isLoading}
          />
          <button
            onClick={onSend}
            disabled={isLoading || !query.trim()}
            className={styles.sendButton}
            style={{ backgroundColor: accentColor }}
          >
            <Send className={styles.sendIcon} />
          </button>
        </div>
      </div>
    </div>
  );
}
