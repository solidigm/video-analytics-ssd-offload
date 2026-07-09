// Created by Metrum AI for Solidigm

import { useState, useRef } from 'react';
import { FileText, Upload, Rocket, Trash2, CheckCircle, Loader2, File } from 'lucide-react';
import styles from '@/styles/components/ContextPanel.module.css';

interface ContextPanelProps {
  context: string;
  setContext: (context: string) => void;
  onSendBoth: () => void;
  onClear: () => void;
  isLoading: boolean;
}

interface UploadedFile {
  name: string;
  size: number;
  wordCount: number;
  content: string;
}

export function ContextPanel({
  context,
  setContext,
  onSendBoth,
  onClear,
  isLoading,
}: ContextPanelProps) {
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;
    setIsUploading(true);
    for (const file of Array.from(files)) {
      if (file.type === 'text/plain' || file.name.endsWith('.txt')) {
        const content = await file.text();
        const wordCount = content.split(/\s+/).filter(w => w.length > 0).length;
        const newFile: UploadedFile = {
          name: file.name,
          size: file.size,
          wordCount,
          content,
        };
        setUploadedFiles((prev: UploadedFile[]) => [...prev, newFile]);
        const newContext = context + (context ? '\n\n---\n\n' : '') + content;
        setContext(newContext);
      }
    }
    setIsUploading(false);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const removeFile = (fileName: string) => {
    const file = uploadedFiles.find(f => f.name === fileName);
    if (file) {
      setUploadedFiles((prev: UploadedFile[]) => prev.filter(f => f.name !== fileName));
      const newContext = context.replace(file.content, '').replace(/\n\n---\n\n/g, '\n\n');
      setContext(newContext);
    }
  };

  const totalWords = uploadedFiles.reduce((sum, f) => sum + f.wordCount, 0);

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <FileText className={styles.headerIcon} />
          <h3 className={styles.title}>Shared Context (Inference Files)</h3>
          {uploadedFiles.length > 0 && (
            <span className={styles.badge}>
              {uploadedFiles.length} file{uploadedFiles.length > 1 ? 's' : ''} | {totalWords.toLocaleString()} words
            </span>
          )}
        </div>
        <div className={styles.headerRight}>
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt"
            multiple
            onChange={handleFileUpload}
            style={{ display: 'none' }}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className={styles.uploadButton}
          >
            {isUploading ? (
              <Loader2 className={`${styles.uploadIcon} animate-spin`} />
            ) : (
              <Upload className={styles.uploadIcon} />
            )}
            Upload Analysis Files
          </button>
        </div>
      </div>

      {/* Uploaded Files List */}
      {uploadedFiles.length > 0 && (
        <div className={styles.fileList}>
          {uploadedFiles.map((file) => (
            <div key={file.name} className={styles.fileItem}>
              <File className={styles.fileIcon} />
              <span className={styles.fileName}>{file.name}</span>
              <span className={styles.fileStats}>({file.wordCount.toLocaleString()} words)</span>
              <button onClick={() => removeFile(file.name)} className={styles.removeButton}>
                <Trash2 className={styles.removeIcon} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Context Preview */}
      <textarea
        value={context}
        onChange={(e) => setContext(e.target.value)}
        placeholder="Upload inference files above or paste your video analysis context here..."
        className={`${styles.textarea} scrollbar-thin`}
      />

      {/* Action Buttons */}
      <div className={styles.actions}>
        <button
          onClick={onSendBoth}
          disabled={isLoading || !context.trim()}
          className={styles.sendButton}
        >
          {isLoading ? (
            <Loader2 className={`${styles.sendIcon} animate-spin`} />
          ) : (
            <Rocket className={styles.sendIcon} />
          )}
          Send to Both Servers
        </button>
        <button onClick={onClear} className={styles.clearButton}>
          <Trash2 className={styles.clearIcon} />
          Clear (Flush Cache Test)
        </button>
      </div>

      {/* Status Info */}
      {context.trim() && (
        <div className={styles.status}>
          <CheckCircle className={styles.statusIcon} />
          <span>Context loaded: {context.split(/\s+/).filter(w => w.length > 0).length.toLocaleString()} words ready for inference</span>
        </div>
      )}
    </div>
  );
}
