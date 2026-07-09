// Created by Metrum AI for Solidigm

import { Film, Clock, ChevronRight } from 'lucide-react';
import styles from '@/styles/components/VideoTimeline.module.css';

interface VideoClip {
  id: string;
  startTime: number;
  endTime: number;
  label: string;
}

interface VideoTimelineProps {
  clips: VideoClip[];
  currentTime: number;
  selectedClip: VideoClip | null;
  onClipSelect: (clip: VideoClip) => void;
  onTimeChange: (time: number) => void;
  formatTime: (seconds: number) => string;
}

export function VideoTimeline({
  clips,
  currentTime,
  selectedClip,
  onClipSelect,
  onTimeChange,
  formatTime,
}: VideoTimelineProps) {
  const totalDuration = clips.length > 0 ? clips[clips.length - 1].endTime : 0;
  const progressPercent = totalDuration > 0 ? (currentTime / totalDuration) * 100 : 0;

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <Film className={styles.headerIcon} />
        <h3 className={styles.headerTitle}>Video Timeline</h3>
        <span className={styles.separator}>|</span>
        <span className={styles.timestamp}>
          Current: {formatTime(currentTime)} / {formatTime(totalDuration)}
        </span>
      </div>

      {/* Timeline Bar */}
      <div
        className={styles.timeline}
        onClick={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const percent = (e.clientX - rect.left) / rect.width;
          onTimeChange(percent * totalDuration);
        }}
      >
        <div
          className={styles.progress}
          style={{ width: `${progressPercent}%` }}
        />
        <div
          className={styles.handle}
          style={{ left: `calc(${progressPercent}% - 8px)` }}
        />
      </div>

      {/* Clip Segments */}
      <div className={`${styles.clips} scrollbar-thin`}>
        {clips.map((clip) => (
          <button
            key={clip.id}
            onClick={() => onClipSelect(clip)}
            className={`${styles.clip} ${selectedClip?.id === clip.id ? styles.clipSelected : ''}`}
          >
            <Clock className={styles.clipIcon} />
            <span className={styles.clipTime}>{formatTime(clip.startTime)}</span>
            <ChevronRight className={styles.clipArrow} />
            <span className={styles.clipTime}>{formatTime(clip.endTime)}</span>
            <span className={styles.clipLabel}>{clip.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
