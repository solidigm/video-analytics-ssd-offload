// Created by Metrum AI for Solidigm

import { forwardRef } from 'react';
import { Play } from 'lucide-react';
import styles from '@/styles/components/VideoPlayer.module.css';

interface VideoPlayerProps {
  src?: string;
  currentTime: number;
  onTimeUpdate: (time: number) => void;
}

export const VideoPlayer = forwardRef<HTMLVideoElement, VideoPlayerProps>(
  function VideoPlayer({ src, currentTime, onTimeUpdate }, ref) {
    return (
      <div className={styles.container}>
        {src ? (
          <video
            ref={ref}
            src={src}
            className={styles.video}
            onTimeUpdate={(e) => onTimeUpdate(e.currentTarget.currentTime)}
          />
        ) : (
          <div className={styles.placeholder}>
            <div className={styles.placeholderContent}>
              <Play className={styles.placeholderIcon} />
              <p className={styles.placeholderText}>No video loaded</p>
              <p className={styles.placeholderSubtext}>Upload a video or select from processed files</p>
            </div>
          </div>
        )}
      </div>
    );
  }
);
