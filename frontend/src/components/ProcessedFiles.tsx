// Created by Metrum AI for Solidigm

import { useState } from 'react';
import { FileText, RefreshCw, Check, Loader2, AlertCircle } from 'lucide-react';
import styles from '@/styles/components/ProcessedFiles.module.css';

interface ProcessedVideo {
  video_id: string;
  filename: string;
  word_count: number;
  analysis_count: number;
  chunk_count: number;
  status: 'processing' | 'completed' | 'failed';
}

interface ProcessedFilesProps {
  files: ProcessedVideo[];
  selectedFile: ProcessedVideo | null;
  onFileSelect: (file: ProcessedVideo) => void;
  onRefresh: () => void;
}

export function ProcessedFiles({ files, selectedFile, onFileSelect, onRefresh }: ProcessedFilesProps) {
  const [maxFiles] = useState(10);
  const displayFiles = files.slice(-maxFiles).reverse();

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <div className={styles.headerIcon}>
            <FileText className={styles.headerIconInner} />
          </div>
          <h3 className={styles.title}>Context Files</h3>
          <span className={styles.badge}>{displayFiles.length}</span>
        </div>
        <button onClick={onRefresh} className={styles.refreshButton}>
          <RefreshCw className={styles.refreshIcon} />
        </button>
      </div>

      <div className={styles.list}>
        {displayFiles.length === 0 ? (
          <div className={styles.emptyState}>
            <div className={styles.emptyIcon}>
              <FileText className={styles.emptyIconInner} />
            </div>
            <p className={styles.emptyText}>No processed videos</p>
            <p className={styles.emptySubtext}>Upload a video to start</p>
          </div>
        ) : (
          displayFiles.map((file) => {
            const isSelected = selectedFile?.video_id === file.video_id;
            return (
              <button
                key={file.video_id}
                onClick={() => file.status === 'completed' && onFileSelect(file)}
                disabled={file.status !== 'completed'}
                className={`${styles.fileItem} ${isSelected ? styles.fileItemSelected : ''}`}
              >
                {file.status === 'processing' && (
                  <Loader2 className={`${styles.loadingIcon} animate-spin`} />
                )}
                {file.status === 'completed' && (
                  <div className={`${styles.fileIcon} ${isSelected ? styles.fileIconSelected : styles.fileIconDefault}`}>
                    {isSelected ? (
                      <Check className={styles.fileIconInner} />
                    ) : (
                      <FileText className={styles.fileIconInner} />
                    )}
                  </div>
                )}
                {file.status === 'failed' && (
                  <AlertCircle className={styles.errorIcon} />
                )}

                <div className={styles.fileInfo}>
                  <p className={styles.fileName}>{file.video_id}</p>
                  <div className={styles.fileStats}>
                    <span className={styles.fileStat}>
                      {file.status === 'processing' ? 'Analyzing...' : `${(file.word_count / 1000).toFixed(1)}k words`}
                    </span>
                    {file.status === 'completed' && (
                      <div className={styles.fileProgress}>
                        <div
                          className={styles.fileProgressBar}
                          style={{ width: `${Math.min(100, (file.word_count / 10000) * 100)}%` }}
                        />
                      </div>
                    )}
                  </div>
                </div>
              </button>
            );
          })
        )}
      </div>

      {selectedFile && (
        <div className={styles.footer}>
          <div className={styles.footerRow}>
            <span className={styles.footerLabel}>Selected:</span>
            <span className={styles.footerValue}>{selectedFile.word_count.toLocaleString()} words</span>
          </div>
        </div>
      )}
    </div>
  );
}
