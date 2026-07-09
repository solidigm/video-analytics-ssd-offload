// Created by Metrum AI for Solidigm

import { useState, useEffect } from 'react';
import { FileText, RefreshCw, Check, Database, HardDrive } from 'lucide-react';
import styles from '@/styles/components/FileSelector.module.css';

interface InferenceFile {
  video_id: string;
  filename: string;
  word_count: number;
  analysis_count: number;
  chunk_count: number;
}

interface FileSelectorProps {
  onFileSelect: (file: InferenceFile, content: string) => void;
  apiBaseUrl: string;
}

export function FileSelector({ onFileSelect, apiBaseUrl }: FileSelectorProps) {
  const [files, setFiles] = useState<InferenceFile[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchFiles = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/api/v1/videos`);
      if (!response.ok) throw new Error('Failed to fetch files');

      const data = await response.json();

      const inferenceFiles: InferenceFile[] = data.videos.map((v: any) => ({
        video_id: v.video_id,
        filename: `${v.video_id}_no_of_words_${v.word_count || 0}.txt`,
        word_count: v.word_count || 0,
        analysis_count: v.analysis_count,
        chunk_count: v.chunk_count,
      }));
      setFiles(inferenceFiles);
    } catch (err) {
      setError('Could not load inference files. Ensure API is running.');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const loadFileContent = async (file: InferenceFile) => {
    setSelectedFile(file.video_id);
    try {
      const response = await fetch(
        `${apiBaseUrl}/api/v1/videos/${file.video_id}/export`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ video_id: file.video_id, output_format: 'txt' }),
        }
      );
      if (!response.ok) throw new Error('Failed to load file');

      const detailResponse = await fetch(`${apiBaseUrl}/api/v1/videos/${file.video_id}`);
      const detail = await detailResponse.json();

      let content = `Video Analysis: ${file.video_id}\n`;
      content += `Total Analyses: ${file.analysis_count}\n`;
      content += `Chunks: ${file.chunk_count}\n\n`;

      for (const chunkId of detail.chunks || []) {
        const chunkResponse = await fetch(
          `${apiBaseUrl}/api/v1/videos/${file.video_id}/chunks/${chunkId}`
        );
        if (chunkResponse.ok) {
          const chunkData = await chunkResponse.json();
          content += chunkData.analysis + '\n\n';
        }
      }
      onFileSelect(file, content);
    } catch (err) {
      console.error('Error loading file content:', err);
    }
  };

  useEffect(() => {
    fetchFiles();
  }, []);

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <Database className={styles.headerIcon} />
          <h3 className={styles.title}>Processed Video Files</h3>
        </div>
        <button
          onClick={fetchFiles}
          disabled={isLoading}
          className={styles.refreshButton}
        >
          <RefreshCw className={`${styles.refreshIcon} ${isLoading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {error && <div className={styles.error}>{error}</div>}

      <div className={`${styles.list} scrollbar-thin`}>
        {files.length === 0 && !isLoading && !error && (
          <div className={styles.emptyState}>
            <HardDrive className={styles.emptyIcon} />
            <p className={styles.emptyText}>No processed videos yet</p>
            <p className={styles.emptySubtext}>Upload videos through the pipeline to generate inference files</p>
          </div>
        )}
        {files.map((file) => {
          const isSelected = selectedFile === file.video_id;
          return (
            <button
              key={file.video_id}
              onClick={() => loadFileContent(file)}
              className={`${styles.fileItem} ${isSelected ? styles.fileItemSelected : ''}`}
            >
              <div className={styles.fileInfo}>
                <FileText className={`${styles.fileIcon} ${isSelected ? styles.fileIconSelected : ''}`} />
                <div className={styles.fileDetails}>
                  <p className={styles.fileName}>{file.filename}</p>
                  <p className={styles.fileStats}>
                    {file.analysis_count} analyses | {file.chunk_count} chunks
                  </p>
                </div>
              </div>
              <div className={styles.fileRight}>
                <span className={styles.wordCount}>
                  {file.word_count.toLocaleString()} words
                </span>
                {isSelected && <Check className={styles.checkIcon} />}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
