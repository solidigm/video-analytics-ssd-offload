// Created by Metrum AI for Solidigm

import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Send, Loader2, ChevronDown } from 'lucide-react';
import styles from '@/styles/components/CommandBar.module.css';

interface CommandBarProps {
  query: string;
  onQueryChange: (query: string) => void;
  onSend: () => void;
  isLoading: boolean;
  hasContext: boolean;
  contextWords: number;
  suggestedQueries?: string[];
  onSelectQuery?: (query: string) => void;
}

export function CommandBar({
  query,
  onQueryChange,
  onSend,
  isLoading,
  hasContext,
  contextWords,
  suggestedQueries = [],
  onSelectQuery
}: CommandBarProps) {
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  const handleSelectQuery = (q: string) => {
    onSelectQuery?.(q);
    setShowDropdown(false);
  };

  return (
    <motion.div
      className={styles.container}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1], delay: 0.2 }}
    >
      {/* Input Area */}
      <motion.div className={styles.inputWrapper}>
        {/* Token count badge commented out
        <AnimatePresence>
          {hasContext && (
            <motion.div
              className={styles.contextBadge}
              initial={{ opacity: 0, scale: 0.8, x: -8 }}
              animate={{ opacity: 1, scale: 1, x: 0 }}
              exit={{ opacity: 0, scale: 0.8, x: -8 }}
              transition={{ duration: 0.2 }}
            >
              <span className={styles.contextDot}></span>
              <span>{contextWords.toLocaleString()} tokens</span>
            </motion.div>
          )}
        </AnimatePresence>
        */}

        <textarea
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question about the video content..."
          className={styles.input}
          disabled={isLoading}
          rows={2}
        />

        {/* Dropdown toggle for suggested queries */}
        {suggestedQueries.length > 0 && (
          <div className={styles.dropdownContainer} ref={dropdownRef}>
            <button
              type="button"
              className={styles.dropdownToggle}
              onClick={() => setShowDropdown(!showDropdown)}
              disabled={isLoading}
            >
              <ChevronDown className={`${styles.dropdownIcon} ${showDropdown ? styles.dropdownIconOpen : ''}`} />
            </button>
          </div>
        )}

        {/* Dropdown menu - positioned relative to inputWrapper */}
        <AnimatePresence>
          {showDropdown && suggestedQueries.length > 0 && (
            <motion.div
              className={styles.dropdown}
              initial={{ opacity: 0, y: -8, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -8, scale: 0.95 }}
              transition={{ duration: 0.15 }}
            >
              <div className={styles.dropdownHeader}>Select a query</div>
              <div className={styles.dropdownList}>
                {suggestedQueries.map((q, i) => (
                  <button
                    key={i}
                    className={`${styles.dropdownItem} ${q === query ? styles.dropdownItemActive : ''}`}
                    onClick={() => handleSelectQuery(q)}
                  >
                    <span className={styles.dropdownItemNumber}>{i + 1}</span>
                    <span className={styles.dropdownItemText}>{q}</span>
                  </button>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <motion.button
          onClick={onSend}
          disabled={isLoading || !query.trim()}
          className={styles.sendButton}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
        >
          {isLoading ? (
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
            >
              <Loader2 className={styles.sendIcon} />
            </motion.div>
          ) : (
            <Send className={styles.sendIcon} />
          )}
        </motion.button>
      </motion.div>

      {/* Status Line */}
      <div className={styles.statusLine}>
        <span className={styles.statusText}>
        </span>
        <AnimatePresence>
          {isLoading && (
            <motion.span
              className={styles.statusLoading}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              Processing...
            </motion.span>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
