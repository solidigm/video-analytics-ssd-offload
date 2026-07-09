// Created by Metrum AI for Solidigm

import { useState, useEffect, useImperativeHandle, forwardRef, useRef } from 'react';
import { Play, Plus, Check, RefreshCw, Clock, HardDrive, Copy, X, FileText } from 'lucide-react';
import styles from '@/styles/components/ContextSelector.module.css';
import { UploadModal } from './UploadModal';
import defaultThumbnail from '@/assets/thumbnail.jpg';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export interface Document {
  id: string;
  name: string;
  type: 'video' | 'book' | 'demo';
  videoIds?: string[];
  wordCount: number;
  selected: boolean;
  durationSeconds?: number;
  fileSizeBytes?: number;
  description?: string;
  thumbnailUrl?: string;
  tokenEstimate?: number;
  kvCacheMb?: number;
  analysisReport?: string;
  analysisStatus?: 'idle' | 'processing' | 'completed';
}

interface ContextSelectorProps {
  onContextChange: (context: string, selectedDocs: Document[]) => void;
  gameCount: number;
  onGameCountChange: (count: number) => void;
  disableSelection?: boolean;
  onLoadingChange?: (loading: boolean) => void;
}

export interface ContextSelectorRef {
  selectFiles: (fileIds: string[]) => Promise<string>;
  getSelectedIds: () => string[];
}

export const ContextSelector = forwardRef<ContextSelectorRef, ContextSelectorProps>(function ContextSelector({
  onContextChange,
  gameCount,
  onGameCountChange,
  disableSelection = false,
  onLoadingChange,
}, ref) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selectedDocs, setSelectedDocs] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(false);
  const [modalDoc, setModalDoc] = useState<Document | null>(null);
  const [showUploadModal, setShowUploadModal] = useState(false);

  useEffect(() => {
    onLoadingChange?.(isLoading);
  }, [isLoading, onLoadingChange]);

  // Store a promise resolver for when context loading completes (resolves with context string)
  const loadingResolverRef = useRef<((context: string) => void) | null>(null);

  useImperativeHandle(ref, () => ({
    selectFiles: async (fileIds: string[]) => {
      if (fileIds.length === 0) {
        setSelectedDocs(new Set());
        return '';
      }

      // Create a promise that will resolve with the loaded context string
      return new Promise<string>((resolve) => {
        loadingResolverRef.current = resolve;
        setSelectedDocs(new Set(fileIds));
      });
    },
    getSelectedIds: () => Array.from(selectedDocs),
  }), [selectedDocs]);

  const pickBestCompletedAnalysis = (analyses: any[] = []) => (
    analyses.find((a: any) => a.analysis_type === 'seeded_context' && a.status === 'completed' && a.coaching_report) ||
    analyses.find((a: any) => a.analysis_type === 'uploaded_context' && a.status === 'completed' && a.coaching_report) ||
    analyses.find((a: any) => a.status === 'completed' && a.coaching_report) ||
    null
  );

  const extractReportText = (analyses: any[] = []) => {
    const best = pickBestCompletedAnalysis(analyses);
    return typeof best?.coaching_report === 'string' ? best.coaching_report.trim() : '';
  };

  const pickPreferredVideoRecord = (current: any, candidate: any) => {
    const currentReport = extractReportText(current.analyses || []);
    const candidateReport = extractReportText(candidate.analyses || []);
    const currentHasReport = currentReport.length > 0;
    const candidateHasReport = candidateReport.length > 0;

    if (currentHasReport !== candidateHasReport) {
      return candidateHasReport ? candidate : current;
    }

    const currentProcessing = (current.analyses || []).some((a: any) => a.status === 'processing');
    const candidateProcessing = (candidate.analyses || []).some((a: any) => a.status === 'processing');

    if (currentProcessing !== candidateProcessing) {
      return candidateProcessing ? candidate : current;
    }

    const currentCreated = Date.parse(current.created_at || '') || 0;
    const candidateCreated = Date.parse(candidate.created_at || '') || 0;
    return candidateCreated > currentCreated ? candidate : current;
  };

  const fetchDocuments = async () => {
    setIsLoading(true);
    const docs: Document[] = [];

    try {
      // Fetch videos with detailed info from new API
      const videoResponse = await fetch(`${API_BASE}/api/v1/videos/list/detailed`);
      if (videoResponse.ok) {
        const data = await videoResponse.json();
        const groupedVideos = new Map<string, { best: any; allIds: string[] }>();

        for (const video of data.videos || []) {
          const dedupeKey = [
            (video.filename || '').trim().toLowerCase(),
            String(video.duration_seconds || 0),
            String(video.file_size_bytes || 0),
          ].join('::');

          const existing = groupedVideos.get(dedupeKey);
          if (!existing) {
            groupedVideos.set(dedupeKey, { best: video, allIds: [video.id] });
          } else {
            existing.allIds.push(video.id);
            existing.best = pickPreferredVideoRecord(existing.best, video);
            groupedVideos.set(dedupeKey, existing);
          }
        }

        for (const { best, allIds } of groupedVideos.values()) {
          const completedAnalysis = pickBestCompletedAnalysis(best.analyses || []);
          const processingAnalysis = (best.analyses || []).find((a: any) => a.status === 'processing');
          const hasCompletedReport = !!completedAnalysis?.coaching_report;
          const reportText = typeof completedAnalysis?.coaching_report === 'string'
            ? completedAnalysis.coaching_report.trim()
            : '';
          const analysisDesc = reportText
            ? `${reportText.substring(0, 150)}...`
            : '';

          docs.push({
            id: `video-${best.id}`,
            name: best.filename,
            type: 'video',
            videoIds: Array.from(new Set(allIds)),
            wordCount: best.token_estimate || 0,
            selected: false,
            durationSeconds: best.duration_seconds || 0,
            fileSizeBytes: best.file_size_bytes || 0,
            description: analysisDesc
              || (processingAnalysis
                ? 'Analysis in progress...'
                : `Video uploaded on ${new Date(best.created_at).toLocaleDateString()}`),
            thumbnailUrl: best.thumbnail_url ? `${API_BASE}${best.thumbnail_url}` : undefined,
            tokenEstimate: best.token_estimate,
            kvCacheMb: best.kv_cache_mb,
            analysisReport: reportText || undefined,
            analysisStatus: hasCompletedReport
              ? 'completed'
              : processingAnalysis
                ? 'processing'
                : 'idle',
          });
        }
      }

      // Fetch books if available
      try {
        const bookResponse = await fetch(`${API_BASE}/api/v1/context/books`);
        if (bookResponse.ok) {
          const bookData = await bookResponse.json();
          for (const book of bookData.books || []) {
            docs.push({
              id: `book-${book.book_id}`,
              name: book.filename,
              type: 'book',
              wordCount: book.word_count || 0,
              selected: false,
            });
          }
        }
      } catch (e) {
        // Books endpoint may not exist
      }
    } catch (error) {
      console.error('Failed to fetch documents:', error);
    }

    // Sort: videos by token count descending, non-videos at end
    docs.sort((a, b) => {
      if (a.type === 'video' && b.type !== 'video') return -1;
      if (a.type !== 'video' && b.type === 'video') return 1;
      const aTokens = a.tokenEstimate || a.wordCount || 0;
      const bTokens = b.tokenEstimate || b.wordCount || 0;
      return bTokens - aTokens;
    });

    setDocuments(docs);
    setIsLoading(false);
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  // Poll while any video is still processing so reports appear automatically.
  useEffect(() => {
    const hasProcessing = documents.some(
      (d) => d.type === 'video' && d.analysisStatus === 'processing',
    );
    if (!hasProcessing) return;

    const interval = setInterval(() => {
      fetchDocuments();
    }, 5000);

    return () => clearInterval(interval);
  }, [documents]);

  const toggleDocument = (docId: string) => {
    if (disableSelection) return;
    const newSelected = new Set(selectedDocs);
    if (newSelected.has(docId)) {
      newSelected.delete(docId);
    } else {
      newSelected.add(docId);
    }
    setSelectedDocs(newSelected);
  };

  const openModal = (doc: Document) => {
    setModalDoc(doc);
  };

  const closeModal = () => {
    setModalDoc(null);
  };

  // Keep modal content in sync with refreshed document metadata.
  useEffect(() => {
    if (!modalDoc) return;
    const updated = documents.find((d) => d.id === modalDoc.id);
    if (!updated) return;

    const shouldUpdate =
      updated.analysisReport !== modalDoc.analysisReport
      || updated.description !== modalDoc.description
      || updated.tokenEstimate !== modalDoc.tokenEstimate
      || updated.kvCacheMb !== modalDoc.kvCacheMb
      || updated.analysisStatus !== modalDoc.analysisStatus;

    if (shouldUpdate) {
      setModalDoc(updated);
    }
  }, [documents, modalDoc]);

  const loadContext = async () => {
    setIsLoading(true);
    let combinedContext = '';
    const selectedDocsList: Document[] = [];

    for (const docId of Array.from(selectedDocs)) {
      const fallbackVideoDoc: Document = {
        id: docId,
        name: docId.replace('video-', ''),
        type: 'video',
        videoIds: [docId.replace('video-', '')],
        wordCount: 0,
        selected: true,
      };

      const doc = documents.find(d => d.id === docId) || (docId.startsWith('video-') ? fallbackVideoDoc : null);
      if (!doc) continue;

      selectedDocsList.push(doc);

      try {
        if (doc.type === 'demo') {
          continue;
        }
        if (doc.type === 'book') {
          const bookId = docId.replace('book-', '');
          const response = await fetch(`${API_BASE}/api/v1/context/books/${bookId}`);
          if (response.ok) {
            const data = await response.json();
            combinedContext += `\n\n--- ${doc.name} ---\n${data.content}`;
          }
        } else if (doc.type === 'video') {
          // Fetch full coaching report. Try all duplicate video IDs for this filename
          // so one failed duplicate does not hide valid completed context.
          const primaryVideoId = docId.replace('video-', '');
          const candidateVideoIds = Array.from(new Set([...(doc.videoIds || []), primaryVideoId]));

          let reportText = '';
          for (const candidateVideoId of candidateVideoIds) {
            const response = await fetch(`${API_BASE}/api/v1/videos/${candidateVideoId}/analyses`);
            if (!response.ok) {
              console.error(`Failed to fetch analyses for ${candidateVideoId}: ${response.status}`);
              continue;
            }

            const analyses = await response.json();
            const bestAnalysis = pickBestCompletedAnalysis(analyses);
            reportText = typeof bestAnalysis?.coaching_report === 'string'
              ? bestAnalysis.coaching_report.trim()
              : '';
            if (reportText) break;
          }

          if (reportText) {
            console.log(`Loaded context for ${doc.name}: ${reportText.length} chars`);
            combinedContext += `\n\n=== GAME ANALYSIS: ${doc.name} ===\n`;
            combinedContext += `The following is a detailed play-by-play breakdown from game footage analysis.\n\n`;
            combinedContext += reportText;
          } else {
            console.warn(`No completed analysis with coaching report found for ${doc.name}`);
          }
        }
      } catch (error) {
        console.error(`Failed to load ${doc.name}:`, error);
      }
    }

    const trimmedContext = combinedContext.trim();
    onContextChange(trimmedContext, selectedDocsList);
    setIsLoading(false);

    // Resolve the loading promise with the actual context string
    if (loadingResolverRef.current) {
      loadingResolverRef.current(trimmedContext);
      loadingResolverRef.current = null;
    }
  };

  useEffect(() => {
    if (selectedDocs.size > 0) {
      loadContext();
    } else {
      onContextChange('', []);
    }
  }, [selectedDocs]);

  // Compute totals from selected documents
  const selectedDocsList = documents.filter(d => selectedDocs.has(d.id));

  const totalTokens = selectedDocsList.reduce((sum, d) => sum + (d.tokenEstimate || d.wordCount || 0), 0);

  const totalDurationSeconds = selectedDocsList.reduce((sum, d) => sum + (d.durationSeconds || 0), 0);

  const totalFileSizeBytes = selectedDocsList.reduce((sum, d) => sum + (d.fileSizeBytes || 0), 0);

  const totalKvCacheMb = selectedDocsList.reduce((sum, d) => sum + (d.kvCacheMb || 0), 0);

  const formatTokens = (count: number) => {
    if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}m`;
    if (count >= 1_000) return `${(count / 1_000).toFixed(1)}k`;
    return `${count}`;
  };

  const formatDuration = (seconds: number) => {
    if (seconds <= 0) return null;
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const formatTotalDuration = (seconds: number) => {
    if (seconds <= 0) return null;
    const hours = seconds / 3600;
    if (hours >= 1) return `${hours.toFixed(1)} hrs`;
    const minutes = seconds / 60;
    return `${minutes.toFixed(0)} min`;
  };

  const formatFileSize = (bytes: number) => {
    if (bytes <= 0) return null;
    const gb = bytes / (1024 * 1024 * 1024);
    if (gb >= 1) return `${gb.toFixed(1)} GB`;
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(0)} MB`;
  };

  // Generate summary text
  const generateSummary = () => {
    const count = selectedDocsList.length;
    if (count === 0) return null;

    const videoCount = selectedDocsList.filter(d => d.type === 'video' || d.type === 'demo').length;
    const bookCount = selectedDocsList.filter(d => d.type === 'book').length;

    const parts: string[] = [];
    if (videoCount > 0) parts.push(`${videoCount} game${videoCount > 1 ? 's' : ''}`);
    if (bookCount > 0) parts.push(`${bookCount} book${bookCount > 1 ? 's' : ''}`);

    return parts.join(' + ') + ' selected';
  };

  return (
    <div className={`card ${styles.container}`}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <h3 className={styles.title}>Games Context</h3>
        </div>
        <div className={styles.headerActions}>
          <button className={styles.addButton} title="Add" onClick={() => setShowUploadModal(true)}>
            <Plus className={styles.addIcon} />
          </button>
          <button onClick={fetchDocuments} className={styles.refreshButton} title="Refresh">
            <RefreshCw className={`${styles.refreshIcon} ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>
      <p className={styles.subtitle}>Select multiple games for context</p>

      {/* Game List */}
      <div className={`${styles.documentList} scrollbar-thin`}>
        {documents.length === 0 && !isLoading && (
          <div className={styles.emptyState}>
            <Play className={styles.emptyIcon} />
            <p className={styles.emptyText}>No games available</p>
          </div>
        )}

        {documents.map((doc) => {
          const isSelected = selectedDocs.has(doc.id);
          return (
            <button
              key={doc.id}
              onClick={() => toggleDocument(doc.id)}
              onDoubleClick={() => openModal(doc)}
              className={`${styles.documentItem} ${isSelected ? styles.documentItemSelected : ''}`}
            >
              {/* Selection indicator */}
              <span className={`${styles.selectionLine} ${isSelected ? styles.selectionLineActive : ''}`} />

              {/* Left - Video Preview */}
              <div className={styles.previewColumn}>
                <img
                  src={doc.thumbnailUrl || defaultThumbnail}
                  alt={doc.name}
                  className={styles.thumbnailImage}
                  onError={(e) => {
                    (e.target as HTMLImageElement).src = defaultThumbnail;
                  }}
                />
                <span className={styles.previewMeta}>
                  {doc.durationSeconds ? formatDuration(doc.durationSeconds) : '--:--'} / {doc.fileSizeBytes ? formatFileSize(doc.fileSizeBytes) : '--'}
                </span>
              </div>

              {/* Right - Info */}
              <div className={styles.infoColumn}>
                <h4 className={`${styles.documentName} ${isSelected ? styles.documentNameSelected : ''}`}>{doc.name}</h4>
                <p className={styles.description}>
                  {doc.description || 'Video content with game highlights and key moments'}
                </p>
                <div className={styles.tokenRow}>
                  <span className={styles.tokenCount}>
                    {doc.tokenEstimate ? `${doc.tokenEstimate.toLocaleString()} tokens` : doc.wordCount ? `${doc.wordCount.toLocaleString()} tokens` : ''}
                  </span>
                  {doc.kvCacheMb && (
                    <span className={styles.kvCacheSize}>
                      Estimated KV cache: {doc.kvCacheMb >= 1000 ? `${(doc.kvCacheMb / 1024).toFixed(1)} GB` : `${doc.kvCacheMb.toFixed(0)} MB`}
                    </span>
                  )}
                </div>
              </div>

              {/* Right dot indicator */}
              <span className={`${styles.timelineDot} ${isSelected ? styles.timelineDotActive : ''}`} />
            </button>
          );
        })}
      </div>

      <div className={styles.footer}>
        <div className={styles.footerStats}>
          <div className={styles.footerStatItem}>
            <div className={styles.footerStatContent}>
              <span className={styles.footerStatLabel}>Tokens</span>
              <span className={styles.footerStatValue}>{totalTokens > 0 ? formatTokens(totalTokens) : '0'}</span>
            </div>
            <button className={styles.copyButton} title="Copy">
              <Copy className={styles.copyIcon} />
            </button>
          </div>
          <div className={styles.footerStatItem}>
            <div className={styles.footerStatContent}>
              <span className={styles.footerStatLabel}>Estimated KV Cache</span>
              <span className={styles.footerStatValue}>
                {totalKvCacheMb >= 1024
                  ? `${(totalKvCacheMb / 1024).toFixed(1)} GB`
                  : totalKvCacheMb > 0
                    ? `${totalKvCacheMb.toFixed(0)} MB`
                    : '0 GB'}
              </span>
            </div>
          </div>
        </div>
        <span className={styles.footerNote}>* Estimated KV cache for MegaBeam-Mistral-7B-300k Model</span>
      </div>

      {/* Video Details Modal */}
      {modalDoc && (
        <div className={styles.modalOverlay} onClick={closeModal}>
          <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
            {/* Modal Header */}
            <div className={styles.modalHeader}>
              <h2 className={styles.modalTitle}>Video Details: {modalDoc.name}</h2>
              <button className={styles.modalClose} onClick={closeModal}>
                <X className={styles.modalCloseIcon} />
              </button>
            </div>

            {/* Modal Body - Vertical Layout */}
            <div className={styles.modalBody}>
              {/* Compact Header: Thumbnail + Stats */}
              <div className={styles.modalCompactHeader}>
                {/* Small Thumbnail */}
                <div className={styles.modalThumbSmall}>
                  <img
                    src={modalDoc.thumbnailUrl || defaultThumbnail}
                    alt={modalDoc.name}
                    className={styles.modalThumbImg}
                    onError={(e) => {
                      (e.target as HTMLImageElement).src = defaultThumbnail;
                    }}
                  />
                </div>

                {/* Stats Row */}
                <div className={styles.modalStatsRow}>
                  <div className={styles.modalStatChip}>
                    <Clock className={styles.modalStatChipIcon} />
                    <span className={styles.modalStatChipValue}>{modalDoc.durationSeconds ? formatDuration(modalDoc.durationSeconds) : '--:--'}</span>
                  </div>
                  <div className={styles.modalStatChip}>
                    <HardDrive className={styles.modalStatChipIcon} />
                    <span className={styles.modalStatChipValue}>{modalDoc.fileSizeBytes ? formatFileSize(modalDoc.fileSizeBytes) : '--'}</span>
                  </div>
                  <div className={styles.modalStatChip}>
                    <FileText className={styles.modalStatChipIcon} />
                    <span className={styles.modalStatChipValue}>{(modalDoc.tokenEstimate || modalDoc.wordCount)?.toLocaleString() || '0'} tokens</span>
                  </div>
                  {modalDoc.kvCacheMb && (
                    <div className={styles.modalStatChipAccent}>
                      <span className={styles.modalStatChipValue}>Estimated KV cache: {modalDoc.kvCacheMb >= 1024 ? `${(modalDoc.kvCacheMb / 1024).toFixed(1)} GB` : `${modalDoc.kvCacheMb.toFixed(0)} MB`}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Full-Width Analysis Report - Main Content */}
              <div className={styles.modalAnalysisSection}>
                <h3 className={styles.modalAnalysisTitle}>Analysis Report</h3>
                <div className={`${styles.modalAnalysisContent} scrollbar-thin`}>
                  <p className={styles.modalAnalysisText}>
                    {modalDoc.analysisReport || modalDoc.description || 'No analysis available yet. Run video analysis to generate a report.'}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      <UploadModal
        isOpen={showUploadModal}
        onClose={() => setShowUploadModal(false)}
        onUploadComplete={() => {
          fetchDocuments();
          // Maybe show a toast
        }}
      />
    </div>
  );
});
