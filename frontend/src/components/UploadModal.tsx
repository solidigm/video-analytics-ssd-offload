// Created by Metrum AI for Solidigm

import { useState, useRef, useEffect } from 'react';
import { Upload, X, FileVideo, FileJson, Check, Loader2, Folder, Keyboard } from 'lucide-react';
import styles from '@/styles/components/UploadModal.module.css';

interface UploadModalProps {
    isOpen: boolean;
    onClose: () => void;
    onUploadComplete: () => void;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

type UploadMode = 'file' | 'path';

export function UploadModal({ isOpen, onClose, onUploadComplete }: UploadModalProps) {
    const [mode, setMode] = useState<UploadMode>('file');

    // File Mode State
    const [videoFile, setVideoFile] = useState<File | null>(null);
    const [contextFile, setContextFile] = useState<File | null>(null);
    const [isDragging, setIsDragging] = useState(false);

    // Path Mode State
    const [videoPath, setVideoPath] = useState('');
    const [contextPath, setContextPath] = useState('');

    // Common State
    const [isUploading, setIsUploading] = useState(false);
    const [progress, setProgress] = useState(0);
    const [status, setStatus] = useState<string>('');

    const fileInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        if (!isOpen) {
            // Reset state when closed
            setVideoFile(null);
            setContextFile(null);
            setVideoPath('');
            setContextPath('');
            setProgress(0);
            setStatus('');
            setIsUploading(false);
            setMode('file');
        }
    }, [isOpen]);

    if (!isOpen) return null;

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);

        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            const droppedFiles = Array.from(e.dataTransfer.files);

            const video = droppedFiles.find(f => f.type.startsWith('video/') || f.name.endsWith('.mkv'));
            const context = droppedFiles.find(f => f.name.endsWith('.json'));

            if (video) setVideoFile(video);
            if (context) setContextFile(context);

            // Auto switch to file mode if drop happened
            setMode('file');
        }
    };

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files.length > 0) {
            const files = Array.from(e.target.files);
            const video = files.find(f => f.type.startsWith('video/') || f.name.endsWith('.mkv'));
            if (video) setVideoFile(video);
        }
    };

    const handleContextSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files.length > 0) {
            setContextFile(e.target.files[0]);
        }
    };

    const handleUpload = async () => {
        setIsUploading(true);
        setStatus(mode === 'file' ? 'Uploading video...' : 'Processing paths...');
        setProgress(10);

        const formData = new FormData();

        if (mode === 'file') {
            if (!videoFile) return;
            formData.append('file', videoFile);
            if (contextFile) {
                formData.append('context', contextFile);
            }
        } else {
            if (!videoPath) return;
            formData.append('video_path', videoPath);
            if (contextPath) {
                formData.append('context_path', contextPath);
            }
        }

        try {
            const xhr = new XMLHttpRequest();
            xhr.open('POST', `${API_BASE}/api/v1/videos`);

            xhr.upload.onprogress = (event) => {
                if (event.lengthComputable) {
                    const percentComplete = (event.loaded / event.total) * 100;
                    setProgress(Math.round(percentComplete * 0.9));
                }
            };

            xhr.onload = () => {
                if (xhr.status === 200) {
                    setProgress(100);
                    setStatus('Success!');
                    setTimeout(() => {
                        onUploadComplete();
                        onClose();
                    }, 1000);
                } else {
                    try {
                        const err = JSON.parse(xhr.responseText);
                        setStatus(`Failed: ${err.detail || xhr.statusText}`);
                    } catch (e) {
                        setStatus(`Failed: ${xhr.statusText}`);
                    }
                    setIsUploading(false);
                }
            };

            xhr.onerror = () => {
                setStatus('Upload failed (Network error)');
                setIsUploading(false);
            };

            xhr.send(formData);
        } catch (error) {
            console.error(error);
            setStatus('Upload failed');
            setIsUploading(false);
        }
    };

    const canSubmit = mode === 'file' ? !!videoFile : !!videoPath;

    return (
        <div className={styles.overlay} onClick={(e) => e.target === e.currentTarget && onClose()}>
            <div className={styles.modal}>
                <div className={styles.header}>
                    <h2 className={styles.title}>Add Game Video</h2>
                    <button className={styles.closeButton} onClick={onClose}>
                        <X size={20} />
                    </button>
                </div>

                {/* Tabs */}
                <div style={{ display: 'flex', borderBottom: '1px solid #e2e8f0' }}>
                    <button
                        style={{
                            flex: 1, padding: '1rem', border: 'none', background: mode === 'file' ? 'white' : '#f8fafc',
                            borderBottom: mode === 'file' ? '2px solid #4338ca' : 'none',
                            color: mode === 'file' ? '#4338ca' : '#64748b', fontWeight: 500, cursor: 'pointer',
                            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem'
                        }}
                        onClick={() => !isUploading && setMode('file')}
                    >
                        <Upload size={16} /> Upload File
                    </button>
                    <button
                        style={{
                            flex: 1, padding: '1rem', border: 'none', background: mode === 'path' ? 'white' : '#f8fafc',
                            borderBottom: mode === 'path' ? '2px solid #4338ca' : 'none',
                            color: mode === 'path' ? '#4338ca' : '#64748b', fontWeight: 500, cursor: 'pointer',
                            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem'
                        }}
                        onClick={() => !isUploading && setMode('path')}
                    >
                        <Folder size={16} /> Local Path
                    </button>
                </div>

                <div className={styles.body}>
                    {mode === 'file' ? (
                        <>
                            {/* Drop Zone */}
                            {!videoFile ? (
                                <div
                                    className={`${styles.dropZone} ${isDragging ? styles.dropZoneActive : ''}`}
                                    onDragOver={handleDragOver}
                                    onDragLeave={handleDragLeave}
                                    onDrop={handleDrop}
                                    onClick={() => fileInputRef.current?.click()}
                                >
                                    <div className={styles.dropZoneContent}>
                                        <Upload className={styles.uploadIcon} />
                                        <div>
                                            <p className={styles.dropText}>Click or drag video file here</p>
                                            <p className={styles.dropSubtext}>Supports MP4, MKV, WEBM</p>
                                        </div>
                                    </div>
                                    <input
                                        ref={fileInputRef}
                                        type="file"
                                        accept="video/*,.mkv"
                                        hidden
                                        onChange={handleFileSelect}
                                    />
                                </div>
                            ) : (
                                <div className={styles.fileList}>
                                    <div className={styles.fileItem}>
                                        <FileVideo className={styles.fileIcon} />
                                        <div style={{ flex: 1, overflow: 'hidden' }}>
                                            <span className={styles.fileName}>{videoFile.name}</span>
                                        </div>
                                        <span className={styles.fileSize}>{(videoFile.size / (1024 * 1024)).toFixed(1)} MB</span>
                                        {!isUploading && (
                                            <button className={styles.removeFile} onClick={() => setVideoFile(null)}>
                                                <X size={16} />
                                            </button>
                                        )}
                                    </div>
                                </div>
                            )}

                            {/* Context File Option */}
                            {videoFile && !isUploading && (
                                <div style={{ marginTop: '1rem' }}>
                                    <p className={styles.dropSubtext} style={{ marginBottom: '0.5rem' }}>
                                        Optional: Add Context (JSON)
                                    </p>
                                    {!contextFile ? (
                                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                                            <label
                                                className={styles.cancelButton}
                                                style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.5rem', width: '100%', justifyContent: 'center' }}
                                            >
                                                <FileJson size={14} /> Select Context.json
                                                <input type="file" accept=".json" hidden onChange={handleContextSelect} />
                                            </label>
                                        </div>
                                    ) : (
                                        <div className={styles.fileItem}>
                                            <FileJson className={styles.fileIcon} />
                                            <span className={styles.fileName}>{contextFile.name}</span>
                                            <button className={styles.removeFile} onClick={() => setContextFile(null)}>
                                                <X size={16} />
                                            </button>
                                        </div>
                                    )}
                                </div>
                            )}
                        </>
                    ) : (
                        // Path Mode
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                            <div>
                                <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '14px', fontWeight: 500, color: '#334155' }}>
                                    Video Path (Absolute Path)
                                </label>
                                <input
                                    type="text"
                                    placeholder="/home/fgpu/videos/game.mp4"
                                    value={videoPath}
                                    onChange={(e) => setVideoPath(e.target.value)}
                                    style={{
                                        width: '100%',
                                        padding: '0.75rem',
                                        borderRadius: '8px',
                                        border: '1px solid #cbd5e1',
                                        fontFamily: 'monospace',
                                        fontSize: '13px'
                                    }}
                                />
                                <p className={styles.dropSubtext} style={{ marginTop: '0.5rem' }}>
                                    Path on the host machine.
                                </p>
                            </div>

                            <div>
                                <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '14px', fontWeight: 500, color: '#334155' }}>
                                    Context Path (Optional)
                                </label>
                                <input
                                    type="text"
                                    placeholder="/home/fgpu/videos/context.json"
                                    value={contextPath}
                                    onChange={(e) => setContextPath(e.target.value)}
                                    style={{
                                        width: '100%',
                                        padding: '0.75rem',
                                        borderRadius: '8px',
                                        border: '1px solid #cbd5e1',
                                        fontFamily: 'monospace',
                                        fontSize: '13px'
                                    }}
                                />
                            </div>
                        </div>
                    )}

                    {/* Progress */}
                    {isUploading && (
                        <div>
                            <div className={styles.progressBar}>
                                <div className={styles.progressFill} style={{ width: `${progress}%` }} />
                            </div>
                            <p className={styles.uploadStatus}>
                                {status}
                                {progress === 100 && <Check size={14} style={{ display: 'inline', marginLeft: 4 }} />}
                            </p>
                        </div>
                    )}
                </div>

                <div className={styles.footer}>
                    <button className={styles.cancelButton} onClick={onClose} disabled={isUploading}>
                        Cancel
                    </button>
                    <button
                        className={styles.uploadButton}
                        onClick={handleUpload}
                        disabled={!canSubmit || isUploading}
                    >
                        {isUploading ? <Loader2 className="animate-spin" size={16} /> : (mode === 'file' ? <Upload size={16} /> : <Check size={16} />)}
                        {mode === 'file' ? 'Upload' : 'Add Path'}
                    </button>
                </div>
            </div>
        </div>
    );
}
