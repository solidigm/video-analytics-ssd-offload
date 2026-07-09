// Created by Metrum AI for Solidigm

import { RotateCcw, Info, Eraser } from 'lucide-react';
import { useRef, useState } from 'react';
import styles from '@/styles/components/Header.module.css';
import SolidigmLogo from '@/assets/Solidigm_White.png';
import MetrumLogo from '@/assets/Metrum_White.svg';

interface HeaderProps {
  onReset: () => void;
  onAnalytics?: () => void;
  onVideoUpload: (file: File) => void;
  isUploading?: boolean;
  onFlush?: () => void;
  isFlushing?: boolean;
}

export function Header({ onReset, onVideoUpload, onFlush, isFlushing = false }: HeaderProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [showInfo, setShowInfo] = useState(false);
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      onVideoUpload(file);
    }
  };

  return (
    <header className={`solidigm-bg ${styles.header}`}>
      <div className={styles.container}>
        {/* Left: Logos */}
        <div className={styles.logoArea}>
          <img
            src={MetrumLogo}
            alt="Metrum AI"
            className={styles.logo}
          />
          <img
            src={SolidigmLogo}
            alt="Solidigm"
            className={styles.logo}
          />
        </div>

        {/* Center: Title */}
        <div className={styles.centerTitle}>
          <h1 className={styles.mainTitle}>Tactical Sports Analytics</h1>
        </div>

        {/* Right: Actions */}
        <div className={styles.actions}>
          <input
            ref={fileInputRef}
            type="file"
            accept="video/*"
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />

          <button onClick={onReset} className={styles.resetButton} title="Reset All">
            <RotateCcw className={styles.resetIcon} />
          </button>

          {/* Flush GPU Caches button */}
          {onFlush && (
            <button
              onClick={onFlush}
              className={`${styles.flushButton} ${isFlushing ? styles.flushButtonActive : ''}`}
              title="Flush GPU Caches"
              disabled={isFlushing}
            >
              <Eraser className={`${styles.flushIcon} ${isFlushing ? styles.flushIconSpin : ''}`} />
            </button>
          )}

          {/* Info Button with Hover Dropdown */}
          <div
            className={styles.infoContainer}
            onMouseEnter={() => setShowInfo(true)}
            onMouseLeave={() => setShowInfo(false)}
          >
            <button className={styles.infoButton} title="System Info">
              <Info className={styles.infoIcon} />
            </button>
            {showInfo && (
              <div className={styles.infoDropdown}>
                <div className={styles.infoDropdownHeader}>
                  <Info className={styles.infoDropdownIcon} />
                  <span>System Info</span>
                </div>
                <div className={styles.infoDropdownContent}>
                  <div className={styles.infoRow}>
                    <span className={styles.infoLabel}>LLM Model:</span>
                    <span className={styles.infoValue}>MegaBeam-Mistral-7B-300k</span>
                  </div>
                  {/* <div className={styles.infoRow}>
                    <span className={styles.infoLabel}>LLM Serving backend:</span>
                    <span className={styles.infoValue}>NVIDIA Dynamo</span>
                  </div> */}
                  <div className={styles.infoRow}>
                    <span className={styles.infoLabel}>VLM Model:</span>
                    <span className={styles.infoValue}>Qwen3-VL-30B-A3B-Thinking</span>
                  </div>
                  <div className={styles.infoRowHighlight}>
                    <span className={styles.infoLabelHighlight}>KV Cache offload SSD:</span>
                    <span className={styles.infoValueHighlight}>Solidigm D7-PS1030</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
