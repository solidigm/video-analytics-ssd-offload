// Created by Metrum AI for Solidigm

import { useRef, useState, useEffect } from 'react';
import { Upload, Film, Loader2, FolderOpen, Check, AlertCircle } from 'lucide-react';
import styles from '@/styles/components/VideoUpload.module.css';

interface VideoUploadProps {
  onUpload: (file: File) => void;
  isUploading: boolean;
}

interface UploadJob {
  job_id: string;
  video_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export function VideoUpload({ onUpload, isUploading }: VideoUploadProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [showPathInput, setShowPathInput] = useState(false);
  const [pathValue, setPathValue] = useState('');
  const [pathLoading, setPathLoading] = useState(false);
  const [pathError, setPathError] = useState('');
  const [jobs, setJobs] = useState<UploadJob[]>([]);

  useEffect(() => {
    const activeJobs = jobs.filter(j => j.status === 'queued' || j.status === 'processing');
    if (activeJobs.length === 0) return;

    const pollJobs = async () => {
      const updated = await Promise.all(
        jobs.map(async (job) => {
          if (job.status === 'completed' || job.status === 'failed') return job;
          try {
            const resp = await fetch(`${API_BASE}/api/v1/jobs/${job.job_id}`);
            if (resp.ok) {
              const data = await resp.json();
              return { ...job, status: data.status };
            }
          } catch {}
          return job;
        })
      );
      setJobs(updated);
    };
    const interval = setInterval(pollJobs, 3000);
    return () => clearInterval(interval);
  }, [jobs]);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) onUpload(file);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onUpload(file);
  };

  const handlePathSubmit = async () => {
    if (!pathValue.trim()) return;
    setPathLoading(true);
    setPathError('');

    try {
      let containerPath = pathValue;
      if (pathValue.startsWith('/home/fgpu')) {
        containerPath = '/host' + pathValue;
      }

      const response = await fetch(`${API_BASE}/api/v1/videos/upload-path?path=${encodeURIComponent(containerPath)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      const data = await response.json();

      if (response.ok) {
        if (data.job_id) {
          setJobs(prev => [...prev, { job_id: data.job_id, video_id: data.video_id, status: 'queued' }]);
        }
        setPathValue('');
        setShowPathInput(false);
      } else {
        setPathError(data.detail || 'Failed');
      }
    } catch (err) {
      console.error('Path upload error:', err);
      setPathError(`Connection error: ${err instanceof Error ? err.message : 'Unknown'}`);
    } finally {
      setPathLoading(false);
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <div className={styles.headerIcon}>
            <Film className={styles.headerIconInner} />
          </div>
          <h3 className={styles.title}>Video Upload</h3>
        </div>
        <button
          onClick={() => setShowPathInput(!showPathInput)}
          className={`${styles.pathButton} ${showPathInput ? styles.pathButtonActive : styles.pathButtonInactive}`}
          title="Load from path"
        >
          <FolderOpen className={styles.pathIcon} />
        </button>
      </div>

      {showPathInput ? (
        <div className={styles.pathForm}>
          <input
            type="text"
            value={pathValue}
            onChange={(e) => setPathValue(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handlePathSubmit()}
            placeholder="/home/fgpu/video.mp4"
            className={styles.pathInput}
          />
          {pathError && (
            <p className={styles.pathError}>
              <AlertCircle className={styles.pathErrorIcon} /> {pathError}
            </p>
          )}
          <button
            onClick={handlePathSubmit}
            disabled={pathLoading || !pathValue.trim()}
            className={styles.pathSubmit}
          >
            {pathLoading && <Loader2 className={`${styles.loadingIcon} animate-spin`} />}
            {pathLoading ? 'Loading...' : 'Load Video'}
          </button>
        </div>
      ) : (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`${styles.dropzone} ${dragOver ? styles.dropzoneActive : ''} ${isUploading ? styles.dropzoneDisabled : ''}`}
        >
          <input ref={fileInputRef} type="file" accept="video/*" onChange={handleFileSelect} style={{ display: 'none' }} />
          <div className={styles.dropzoneContent}>
            {isUploading ? (
              <>
                <Loader2 className={`${styles.uploadIcon} animate-spin`} />
                <span className={styles.uploadText}>Uploading...</span>
              </>
            ) : (
              <>
                <Upload className={styles.uploadIcon} />
                <span className={styles.uploadText}>Drop or click</span>
              </>
            )}
          </div>
        </div>
      )}

      {jobs.length > 0 && (
        <div className={styles.jobList}>
          {jobs.slice(-3).map((job) => (
            <div key={job.job_id} className={styles.jobItem}>
              {job.status === 'processing' && <Loader2 className={`${styles.jobIcon} ${styles.jobIconProcessing} animate-spin`} />}
              {job.status === 'completed' && <Check className={`${styles.jobIcon} ${styles.jobIconCompleted}`} />}
              {job.status === 'failed' && <AlertCircle className={`${styles.jobIcon} ${styles.jobIconFailed}`} />}
              {job.status === 'queued' && <Loader2 className={`${styles.jobIcon} ${styles.jobIconQueued} animate-spin`} />}
              <span className={styles.jobName}>{job.video_id}</span>
              <span className={`${styles.jobStatus} ${
                job.status === 'completed' ? styles.jobStatusCompleted :
                job.status === 'failed' ? styles.jobStatusFailed :
                styles.jobStatusPending
              }`}>
                {job.status}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
