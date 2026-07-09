// Created by Metrum AI for Solidigm

import { useState, useEffect, useRef } from 'react';
import { Header } from '@/components/Header';
import { ComparisonArena } from '@/components/ComparisonArena';
import { ContextSelector, type ContextSelectorRef } from '@/components/ContextSelector';
import { ScenarioPanel, type ScenarioData } from '@/components/ScenarioPanel';
import { CommandBar } from '@/components/CommandBar';
import { MetricsPanel } from '@/components/MetricsPanel';
import { AnalyticsDashboard } from '@/components/AnalyticsDashboard';
import { MultiUserConfig, type MultiUserSettings } from '@/components/MultiUserConfig';
import { MultiUserResults } from '@/components/MultiUserResults';
import { fetchAllSystemMetrics, startMultiUserBenchmark, stopMultiUserBenchmark } from '@/services/metricsService';
import type { LLMMetrics, GPUMetrics, SSDMetrics, CPUMetrics, GPUHistory } from '@/types/metrics';
import { DEFAULT_GPU_METRICS, DEFAULT_SSD_METRICS, DEFAULT_CPU_METRICS } from '@/types/metrics';
import styles from '@/styles/pages/Home.module.css';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  ttft?: number;
  tokensPerSec?: number;
  cacheHit?: boolean;
}

export interface Metrics {
  baselineTTFT: number | null;
  lmcacheTTFT: number | null;
  speedup: number | null;
  baselineGenTput: number;
  lmcacheGenTput: number;
  vlmGenTput: number;
  baselinePromptTput: number;
  lmcachePromptTput: number;
  vlmPromptTput: number;
  baselineKvCache: number;
  lmcacheKvCache: number;
  vlmKvCache: number;
  diskRead: number;
  diskWrite: number;
  cacheHitRate: number;
  cacheHitRates: {
    baseline: number;
    lmcache: number;
    vlm: number;
  };
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';
// Use backend proxy for streaming chat (avoids browser CORS issues)
const USE_BACKEND_PROXY = true;

export default function Home() {
  const [showAnalytics, setShowAnalytics] = useState(false);

  // Ref to programmatically select context files
  const contextSelectorRef = useRef<ContextSelectorRef>(null);

  // Manual flush state
  const [isFlushing, setIsFlushing] = useState(false);

  // Context loading state (scenario file loading)
  const [isContextLoading, setIsContextLoading] = useState(false);

  // Energy accumulation ref (avoids stale closure issues in polling interval)
  const inferenceEnergyRef = useRef({
    baselineWs: 0,      // Watt-seconds accumulated
    lmcacheWs: 0,       // Watt-seconds accumulated
    lastPollTime: 0,
    baselineActive: false,
    lmcacheActive: false,
    peakEfficiency: 0,   // All-time max efficiency across all runs (reset only by Reset button)
  });

  // Derived energy efficiency for Column 3 display (null = use instantaneous fallback)
  const [energyEfficiency, setEnergyEfficiency] = useState<number | null>(null);

  // Multi-user benchmark state
  const [multiUserStatus, setMultiUserStatus] = useState<'idle' | 'configuring' | 'results' | 'completed'>('idle');
  const [multiUserSettings, setMultiUserSettings] = useState<MultiUserSettings | null>(null);
  const [multiUserRunId, setMultiUserRunId] = useState<string | null>(null);

  // Chat state
  const [baselineMessages, setBaselineMessages] = useState<Message[]>([]);
  const [lmcacheMessages, setLmcacheMessages] = useState<Message[]>([]);
  const [sharedQuery, setSharedQuery] = useState('');
  const [sharedContext, setSharedContext] = useState('');
  const [selectedDocs, setSelectedDocs] = useState<any[]>([]);
  const [selectedContextFileIds, setSelectedContextFileIds] = useState<string[]>([]);
  const [suggestedQueries, setSuggestedQueries] = useState<string[]>([]);

  // Context state
  const [gameCount, setGameCount] = useState(3);
  const [activeScenarioId, setActiveScenarioId] = useState<string | undefined>(undefined);


  // Loading states
  const [isBaselineLoading, setIsBaselineLoading] = useState(false);
  const [isLmcacheLoading, setIsLmcacheLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  // TTFT history
  const [ttftHistory, setTtftHistory] = useState<{ baseline: number[]; lmcache: number[] }>({
    baseline: [],
    lmcache: [],
  });

  // Metrics
  const [metrics, setMetrics] = useState<Metrics>({
    baselineTTFT: null,
    lmcacheTTFT: null,
    speedup: null,
    baselineGenTput: 0,
    lmcacheGenTput: 0,
    vlmGenTput: 0,
    baselinePromptTput: 0,
    lmcachePromptTput: 0,
    vlmPromptTput: 0,
    baselineKvCache: 0,
    lmcacheKvCache: 0,
    vlmKvCache: 0,
    diskRead: 0,
    diskWrite: 0,
    cacheHitRate: 0,
    cacheHitRates: {
      baseline: 0,
      lmcache: 0,
      vlm: 0,
    },
  });

  const metricsRef = useRef(metrics);
  useEffect(() => { metricsRef.current = metrics; }, [metrics]);

  // System metrics for right sidebar
  const [gpuMetrics, setGpuMetrics] = useState<GPUMetrics[]>(
    Array.from({ length: 4 }, (_, i) => ({ ...DEFAULT_GPU_METRICS, id: i, name: `H100 GPU ${i}` }))
  );
  const [ssdMetrics, setSsdMetrics] = useState<SSDMetrics>(DEFAULT_SSD_METRICS);
  const [cpuMetrics, setCpuMetrics] = useState<CPUMetrics>(DEFAULT_CPU_METRICS);
  const [gpuHistory, setGpuHistory] = useState<GPUHistory>({
    power: [[], [], [], []],
    utilization: [[], [], [], []],
  });

  // Track power consumption history for energy calculations
  const [powerHistory, setPowerHistory] = useState<{
    baseline: { power: number; timestamp: number }[];
    lmcache: { power: number; timestamp: number }[];
  }>({ baseline: [], lmcache: [] });

  // Total energy tracking (in Watt-hours)
  const [totalEnergy, setTotalEnergy] = useState<{
    baseline: number;
    lmcache: number;
  }>({ baseline: 0, lmcache: 0 });

  // Best TTFT
  const [bestBaselineTTFT, setBestBaselineTTFT] = useState<number | null>(null);
  const [bestLmcacheTTFT, setBestLmcacheTTFT] = useState<number | null>(null);

  // Average GPU power during query runtime
  const avgPowerRef = useRef({ baselineSum: 0, lmcacheSum: 0, sampleCount: 0 });
  const [avgBaselinePower, setAvgBaselinePower] = useState<number | null>(null);
  const [avgLmcachePower, setAvgLmcachePower] = useState<number | null>(null);

  // Upload video
  const handleVideoUpload = async (file: File) => {
    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${API_BASE}/api/v1/videos/upload`, {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        console.log('Video uploaded successfully');
      }
    } catch (error) {
      console.error('Upload failed:', error);
    } finally {
      setIsUploading(false);
    }
  };

  // Send query to LLM via backend proxy (streaming)
  const compactContextForModel = (context: string, maxChars: number): { text: string; truncated: boolean } => {
    if (!context || context.length <= maxChars) {
      return { text: context, truncated: false };
    }

    const marker = '=== GAME ANALYSIS:';
    if (!context.includes(marker)) {
      return { text: context.slice(0, maxChars), truncated: true };
    }

    const sections = context
      .split(marker)
      .map(section => section.trim())
      .filter(Boolean)
      .map(section => `${marker} ${section}`);

    if (sections.length === 0) {
      return { text: context.slice(0, maxChars), truncated: true };
    }

    const separator = '\n\n';
    const separatorChars = separator.length * Math.max(sections.length - 1, 0);
    const usableBudget = Math.max(maxChars - separatorChars, 0);
    const perSectionBudget = Math.max(Math.floor(usableBudget / sections.length), 800);

    const compactedSections = sections.map(section => {
      if (section.length <= perSectionBudget) {
        return section;
      }

      const headBudget = Math.max(Math.floor(perSectionBudget * 0.8), 600);
      const tailBudget = Math.max(perSectionBudget - headBudget - 32, 0);

      if (tailBudget >= 120) {
        return `${section.slice(0, headBudget)}\n...[section truncated]...\n${section.slice(-tailBudget)}`;
      }

      return section.slice(0, perSectionBudget);
    });

    let compacted = compactedSections.join(separator);
    if (compacted.length > maxChars) {
      compacted = compacted.slice(0, maxChars);
    }

    return { text: compacted, truncated: true };
  };

  const sendQuery = async (
    endpoint: 'baseline' | 'lmcache',
    setMessages: React.Dispatch<React.SetStateAction<Message[]>>,
    setLoading: React.Dispatch<React.SetStateAction<boolean>>,
    queryText: string,
    contextOverride?: string
  ): Promise<{ ttft: number; tokensPerSec: number }> => {
    if (!queryText.trim()) return { ttft: 0, tokensPerSec: 0 };

    const userMessage: Message = {
      id: `${Date.now()}-${endpoint}-user`,
      role: 'user',
      content: queryText,
      timestamp: Date.now(),
    };

    setMessages(prev => [...prev, userMessage]);
    setLoading(true);

    const startTime = performance.now();
    let ttftRecorded = false;
    let ttft = 0;

    const url = `${API_BASE}/api/v1/chat/stream/${endpoint}`;

    try {
      const effectiveContext = contextOverride !== undefined ? contextOverride : sharedContext;

      const MAX_CONTEXT_CHARS = 650000;
      const { text: truncatedContext, truncated: wasTruncated } = compactContextForModel(
        effectiveContext || '',
        MAX_CONTEXT_CHARS,
      );

      let messageContent: string;
      if (truncatedContext) {
        messageContent = `You are an expert American football analyst and coaching strategist. Your role is to provide detailed, data-driven analysis of game film, player performance, formations, and tactical trends.

INSTRUCTIONS:
1. You MUST answer the question using the game context provided below. The context contains detailed play-by-play analysis from real game footage.
2. Extract and reference specific plays, player names, formations, scores, time ranges, and tactical details directly from the context.
3. DO NOT use any information that is not present in the context below.
4. Always provide a substantive answer from available evidence in the context. If one part has limited data, briefly say that and continue with what is available.
5. Structure your response clearly with evidence-backed points.
6. Do not assume the league, conference, or level of play — use only the team names, player names, and details present in the context.

--- BEGIN GAME CONTEXT ---
${truncatedContext}
--- END GAME CONTEXT ---

Using the game context above, provide a thorough analysis for the following:
${queryText}`;
      } else {
        messageContent = queryText;
      }

      const contextTokens = Math.floor(messageContent.length / 4);
      console.log(`[${endpoint}] Sending request:`, {
        contextChars: messageContent.length,
        estimatedTokens: contextTokens,
        wasTruncated,
        isOverLimit: contextTokens > 200000,
      });

      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'aws-prototyping/MegaBeam-Mistral-7B-300k',
          messages: [
            {
              role: 'user',
              content: messageContent,
            },
          ],
          max_tokens: 512,
          temperature: 0.3,
          stream: true,
        }),
      });

      if (!response.ok) {
        const errorBody = await response.text().catch(() => '');
        throw new Error(`Request failed (${response.status}): ${errorBody || 'No response body'}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('Streaming response body is not available');
      }

      const decoder = new TextDecoder();
      let fullContent = '';
      const assistantMessageId = `${Date.now()}-${endpoint}-assistant`;
      let buffer = '';

      const processLine = (line: string) => {
        if (!line.startsWith('data:')) return;

        const data = line.slice(5).trim();
        if (!data || data === '[DONE]') return;

        let parsed: any;
        try {
          parsed = JSON.parse(data);
        } catch {
          return;
        }

        if (parsed.error) {
          throw new Error(parsed.error);
        }

        const content = parsed.choices?.[0]?.delta?.content || '';
        if (!content) return;

        if (!ttftRecorded) {
          ttft = performance.now() - startTime;
          ttftRecorded = true;
        }

        fullContent += content;

        setMessages(prev => {
          const existing = prev.find(m => m.id === assistantMessageId);
          if (existing) {
            return prev.map(m => (m.id === assistantMessageId ? { ...m, content: fullContent } : m));
          }

          return [
            ...prev,
            {
              id: assistantMessageId,
              role: 'assistant',
              content: fullContent,
              timestamp: Date.now(),
              ttft: ttft / 1000,
              cacheHit: endpoint === 'lmcache',
            },
          ];
        });
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const rawLine of lines) {
          processLine(rawLine.trim());
        }
      }

      if (buffer.trim()) {
        processLine(buffer.trim());
      }

      if (!fullContent.trim()) {
        throw new Error('No response content received from model');
      }

      const totalTime = performance.now() - startTime;
      const tokenEstimate = Math.max(fullContent.split(/\s+/).filter(Boolean).length * 1.3, 1);
      const tokensPerSec = totalTime > 0 ? tokenEstimate / (totalTime / 1000) : 0;

      return { ttft: ttft / 1000, tokensPerSec };
    } catch (error) {
      console.error('Query error:', error);
      const errorMsg = error instanceof Error ? error.message : 'Unknown error';
      setMessages(prev => [
        ...prev,
        {
          id: `${Date.now()}-${endpoint}-error`,
          role: 'assistant',
          content: `Request failed: ${errorMsg}`,
          timestamp: Date.now(),
        },
      ]);
      return { ttft: 0, tokensPerSec: 0 };
    } finally {
      // Mark this engine as done for energy tracking + fast-inference fallback
      const ref = inferenceEnergyRef.current;
      const totalTimeSeconds = (performance.now() - startTime) / 1000;

      if (endpoint === 'baseline') {
        ref.baselineActive = false;
        if (ref.baselineWs === 0 && totalTimeSeconds > 0) {
          ref.baselineWs = (gpuMetrics[1]?.power || 0) * totalTimeSeconds;
        }
      } else {
        ref.lmcacheActive = false;
        if (ref.lmcacheWs === 0 && totalTimeSeconds > 0) {
          ref.lmcacheWs = (gpuMetrics[0]?.power || 0) * totalTimeSeconds;
        }
      }

      if (ref.baselineWs > 0 && ref.lmcacheWs > 0) {
        const ratio = ref.baselineWs / ref.lmcacheWs;
        ref.peakEfficiency = Math.max(ref.peakEfficiency, ratio);
        setEnergyEfficiency(ref.peakEfficiency);
      }

      setLoading(false);
    }
  };

  // Send to both servers
  const sendToBoth = async (queryOverride?: string, contextOverride?: string) => {
    const queryToSend = queryOverride || sharedQuery;
    if (!queryToSend.trim()) return;

    // Clear query immediately for better UX
    setSharedQuery('');

    // Reset per-run energy accumulators but preserve all-time peak
    const prevPeak = inferenceEnergyRef.current.peakEfficiency;
    inferenceEnergyRef.current = {
      baselineWs: 0, lmcacheWs: 0,
      lastPollTime: Date.now(),
      baselineActive: true, lmcacheActive: true,
      peakEfficiency: prevPeak,
    };

    // Reset average power accumulator for this query
    avgPowerRef.current = { baselineSum: 0, lmcacheSum: 0, sampleCount: 0 };
    setAvgBaselinePower(null);
    setAvgLmcachePower(null);

    // For cold-start scenarios, add a unique nonce so LMCache disk cache never matches
    const COLD_SCENARIOS = new Set(['cold cache', 'cold-cache']);
    const isColdStart = !!(activeScenarioId && COLD_SCENARIOS.has(activeScenarioId.trim().toLowerCase()));
    const effectiveContext = contextOverride !== undefined ? contextOverride : sharedContext;
    const saltedContext = isColdStart
      ? `[sid-${Date.now()}-${Math.random().toString(36).slice(2, 8)}]\n${effectiveContext}`
      : effectiveContext;

    const baselineTask = sendQuery('baseline', setBaselineMessages, setIsBaselineLoading, queryToSend, saltedContext);
    const lmcacheTask = sendQuery('lmcache', setLmcacheMessages, setIsLmcacheLoading, queryToSend, saltedContext);

    const [baselineResult, lmcacheResult] = await Promise.all([baselineTask, lmcacheTask]);

    // Finalize average power from accumulated samples
    const pRef = avgPowerRef.current;
    if (pRef.sampleCount > 0) {
      setAvgBaselinePower(pRef.baselineSum / pRef.sampleCount);
      setAvgLmcachePower(pRef.lmcacheSum / pRef.sampleCount);
    }

    const speedup = baselineResult.ttft > 0 && lmcacheResult.ttft > 0
      ? baselineResult.ttft / lmcacheResult.ttft
      : null;

    setMetrics(prev => ({
      ...prev,
      baselineTTFT: baselineResult.ttft,
      lmcacheTTFT: lmcacheResult.ttft,
      speedup,
      baselineGenTput: baselineResult.tokensPerSec,
      lmcacheGenTput: lmcacheResult.tokensPerSec,
    }));

    // Update history
    if (baselineResult.ttft > 0) {
      setTtftHistory(prev => ({
        ...prev,
        baseline: [...prev.baseline.slice(-9), baselineResult.ttft],
      }));
      setBestBaselineTTFT(prev =>
        prev === null ? baselineResult.ttft : Math.min(prev, baselineResult.ttft)
      );
    }
    if (lmcacheResult.ttft > 0) {
      setTtftHistory(prev => ({
        ...prev,
        lmcache: [...prev.lmcache.slice(-9), lmcacheResult.ttft],
      }));
      setBestLmcacheTTFT(prev =>
        prev === null ? lmcacheResult.ttft : Math.min(prev, lmcacheResult.ttft)
      );
    }
  };

  // Manual flush handler
  const handleFlush = async () => {
    setIsFlushing(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/cache/flush-baseline`, { method: 'POST' });
      if (!response.ok) {
        const body = await response.text().catch(() => '');
        console.warn(`[Flush] Failed (${response.status}): ${body || 'no response body'}`);
      } else {
        console.log('[Flush] Baseline cache flushed successfully');
      }
    } catch (e) {
      console.warn('[Flush] Flush failed:', e);
    } finally {
      setIsFlushing(false);
    }
  };

  // Send comparison via backend API (non-streaming, persists to DB)
  const sendViaBackend = async (queryText: string, contextOverride?: string) => {
    if (!queryText.trim()) return;

    setIsBaselineLoading(true);
    setIsLmcacheLoading(true);

    // Reset per-run energy accumulators but preserve all-time peak
    const prevPeak = inferenceEnergyRef.current.peakEfficiency;
    inferenceEnergyRef.current = {
      baselineWs: 0, lmcacheWs: 0,
      lastPollTime: Date.now(),
      baselineActive: true, lmcacheActive: true,
      peakEfficiency: prevPeak,
    };

    const userMessage: Message = {
      id: `${Date.now()}-user`,
      role: 'user',
      content: queryText,
      timestamp: Date.now(),
    };
    setBaselineMessages(prev => [...prev, userMessage]);
    setLmcacheMessages(prev => [...prev, { ...userMessage, id: `${Date.now()}-lmcache-user` }]);

    try {
      const response = await fetch(`${API_BASE}/api/v1/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: queryText,
          llm_target: 'both',
          context: (contextOverride !== undefined ? contextOverride : sharedContext) || undefined,
        }),
      });

      if (response.ok) {
        const data = await response.json();

        const lmcacheTtft = data.lmcache.latency_ms / 1000;
        const baselineTtft = data.baseline.latency_ms / 1000;

        setLmcacheMessages(prev => [...prev, {
          id: `${Date.now()}-lmcache-assistant`,
          role: 'assistant',
          content: data.lmcache.response,
          timestamp: Date.now(),
          ttft: lmcacheTtft,
          cacheHit: data.lmcache.cache_hit,
        }]);

        setBaselineMessages(prev => [...prev, {
          id: `${Date.now()}-baseline-assistant`,
          role: 'assistant',
          content: data.baseline.response,
          timestamp: Date.now(),
          ttft: baselineTtft,
          cacheHit: false,
        }]);

        const speedup = baselineTtft > 0 && lmcacheTtft > 0
          ? baselineTtft / lmcacheTtft
          : null;

        setMetrics(prev => ({
          ...prev,
          baselineTTFT: baselineTtft,
          lmcacheTTFT: lmcacheTtft,
          speedup,
          cacheHitRate: data.lmcache.cache_hit ? 93 : 0,
          cacheHitRates: {
            ...prev.cacheHitRates,
            lmcache: data.lmcache.cache_hit ? 93 : 0,
          },
        }));

        setTtftHistory(prev => ({
          baseline: [...prev.baseline.slice(-9), baselineTtft],
          lmcache: [...prev.lmcache.slice(-9), lmcacheTtft],
        }));

        setBestBaselineTTFT(prev =>
          prev === null ? baselineTtft : Math.min(prev, baselineTtft)
        );
        setBestLmcacheTTFT(prev =>
          prev === null ? lmcacheTtft : Math.min(prev, lmcacheTtft)
        );

        // Finalize energy tracking using returned latency as time
        const ref = inferenceEnergyRef.current;
        ref.baselineActive = false;
        ref.lmcacheActive = false;
        const baselineSec = data.baseline.latency_ms / 1000;
        const lmcacheSec = data.lmcache.latency_ms / 1000;
        if (ref.baselineWs === 0 && baselineSec > 0) {
          ref.baselineWs = (gpuMetrics[1]?.power || 0) * baselineSec;
        }
        if (ref.lmcacheWs === 0 && lmcacheSec > 0) {
          ref.lmcacheWs = (gpuMetrics[0]?.power || 0) * lmcacheSec;
        }
        if (ref.baselineWs > 0 && ref.lmcacheWs > 0) {
          const ratio = ref.baselineWs / ref.lmcacheWs;
          ref.peakEfficiency = Math.max(ref.peakEfficiency, ratio);
          setEnergyEfficiency(ref.peakEfficiency);
        }

      } else {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Request failed');
      }
    } catch (error) {
      console.error('Backend chat error:', error);
      const errorMsg = error instanceof Error ? error.message : 'Unknown error';
      setBaselineMessages(prev => [...prev, {
        id: `${Date.now()}-baseline-error`,
        role: 'assistant',
        content: `Error: ${errorMsg}. Ensure backend is running at ${API_BASE}`,
        timestamp: Date.now(),
      }]);
      setLmcacheMessages(prev => [...prev, {
        id: `${Date.now()}-lmcache-error`,
        role: 'assistant',
        content: `Error: ${errorMsg}. Ensure backend is running at ${API_BASE}`,
        timestamp: Date.now(),
      }]);
    } finally {
      setIsBaselineLoading(false);
      setIsLmcacheLoading(false);
    }
  };

  // Handle scenario selection - auto-select context files and populate query input
  const handleScenarioSelect = async (data: ScenarioData) => {
    // Track active scenario
    setActiveScenarioId(data.id);


    // Clear previous messages
    setBaselineMessages([]);
    setLmcacheMessages([]);

    // Reset all panel values to blank until a new question is triggered
    setAvgBaselinePower(null);
    setAvgLmcachePower(null);
    avgPowerRef.current = { baselineSum: 0, lmcacheSum: 0, sampleCount: 0 };
    setMetrics({
      baselineTTFT: null,
      lmcacheTTFT: null,
      speedup: null,
      baselineGenTput: 0,
      lmcacheGenTput: 0,
      vlmGenTput: 0,
      baselinePromptTput: 0,
      lmcachePromptTput: 0,
      vlmPromptTput: 0,
      baselineKvCache: 0,
      lmcacheKvCache: 0,
      vlmKvCache: 0,
      diskRead: 0,
      diskWrite: 0,
      cacheHitRate: 0,
      cacheHitRates: {
        baseline: 0,
        lmcache: 0,
        vlm: 0,
      },
    });
    setBestBaselineTTFT(null);
    setBestLmcacheTTFT(null);
    setTtftHistory({ baseline: [], lmcache: [] });
    setEnergyEfficiency(null);
    inferenceEnergyRef.current = {
      baselineWs: 0, lmcacheWs: 0, lastPollTime: 0,
      baselineActive: false, lmcacheActive: false,
      peakEfficiency: 0,
    };

    // Set the query in the input and provide all queries for dropdown
    setSharedQuery(data.query);
    setSuggestedQueries(data.allQueries);

    // Auto-select the context files for this scenario
    if (contextSelectorRef.current && data.contextFiles.length > 0) {
      try {
        console.log(`[Scenario] Loading context for ${data.contextFiles.length} files...`);
        await contextSelectorRef.current.selectFiles(data.contextFiles);
        console.log(`[Scenario] Context loaded, ready to send`);
      } catch (error) {
        console.error('[Scenario] Failed to load scenario context:', error);
      }
    }
  };

  // Clear all
  const clearAll = () => {
    setBaselineMessages([]);
    setLmcacheMessages([]);
    setSharedQuery('');
    setSharedContext('');
    setSelectedDocs([]);
    setSuggestedQueries([]);
    setActiveScenarioId(undefined);
    // Reset multi-user state
    if (multiUserRunId) {
      stopMultiUserBenchmark(multiUserRunId).catch(() => {});
    }
    setMultiUserStatus('idle');
    setMultiUserSettings(null);
    setMultiUserRunId(null);
    setBestBaselineTTFT(null);
    setBestLmcacheTTFT(null);
    setTtftHistory({ baseline: [], lmcache: [] });
    setMetrics({
      baselineTTFT: null,
      lmcacheTTFT: null,
      speedup: null,
      baselineGenTput: 0,
      lmcacheGenTput: 0,
      vlmGenTput: 0,
      baselinePromptTput: 0,
      lmcachePromptTput: 0,
      vlmPromptTput: 0,
      baselineKvCache: 0,
      lmcacheKvCache: 0,
      vlmKvCache: 0,
      diskRead: 0,
      diskWrite: 0,
      cacheHitRate: 0,
      cacheHitRates: {
        baseline: 0,
        lmcache: 0,
        vlm: 0,
      },
    });
    // Reset energy tracking (full reset including all-time peak)
    inferenceEnergyRef.current = {
      baselineWs: 0, lmcacheWs: 0, lastPollTime: 0,
      baselineActive: false, lmcacheActive: false,
      peakEfficiency: 0,
    };
    setEnergyEfficiency(null);
    setAvgBaselinePower(null);
    setAvgLmcachePower(null);
    avgPowerRef.current = { baselineSum: 0, lmcacheSum: 0, sampleCount: 0 };
  };

  // Multi-user handlers
  const handleMultiUserSelect = () => {
    setMultiUserStatus('configuring');
    // Clear normal chat state
    setBaselineMessages([]);
    setLmcacheMessages([]);
    setSharedQuery('');
    setSuggestedQueries([]);
    setActiveScenarioId('multi-user');
  };

  const handleMultiUserStart = async (settings: MultiUserSettings) => {
    setMultiUserSettings(settings);
    try {
      const data = await startMultiUserBenchmark(settings.numUsers, settings.contextMode);
      setMultiUserRunId(data.run_id);
      setMultiUserStatus('results');
    } catch (error) {
      console.error('Failed to start benchmark:', error);
      setMultiUserSettings(null);
    }
  };

  const handleViewActiveBenchmark = (runId: string, numUsers: number, contextMode?: string) => {
    setMultiUserRunId(runId);
    setMultiUserSettings({ numUsers, contextMode: (contextMode as 'quick' | 'long_context') ?? 'long_context' });
    setMultiUserStatus('results');
  };

  const handleBenchmarkCompleted = () => {
    setMultiUserStatus('completed');
  };

  const handleMultiUserReset = async () => {
    if (multiUserRunId) {
      await stopMultiUserBenchmark(multiUserRunId).catch(() => {});
    }
    setMultiUserStatus('idle');
    setMultiUserSettings(null);
    setMultiUserRunId(null);
    setActiveScenarioId(undefined);
  };

  // Fetch vLLM metrics
  useEffect(() => {
    const fetchVllmMetrics = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/v1/metrics/vllm`);
        if (response.ok) {
          const data = await response.json();
          setMetrics(prev => {
            const pickNumber = (value: unknown, fallback: number) =>
              typeof value === 'number' && Number.isFinite(value) ? value : fallback;

            // Use the most relevant cache hit rate per service:
            // - Baseline: prefix cache only (no external/SSD cache)
            // - SSD Cache (lmcache): external cache hit rate (SSD offloading via LMCache)
            // - VLM: total combined rate (prefix + mm cache)
            const lmcacheCacheHit = pickNumber(data?.lmcache?.external_cache_hit_rate_pct, pickNumber(data?.lmcache?.cache_hit_rate_pct, prev.cacheHitRates.lmcache));
            const baselineCacheHit = pickNumber(data?.baseline?.prefix_cache_hit_rate_pct, pickNumber(data?.baseline?.cache_hit_rate_pct, prev.cacheHitRates.baseline));
            const vlmCacheHit = pickNumber(data?.vlm?.cache_hit_rate_pct, prev.cacheHitRates.vlm);

            return {
              ...prev,
              cacheHitRate: lmcacheCacheHit,
              cacheHitRates: {
                baseline: baselineCacheHit,
                lmcache: lmcacheCacheHit,
                vlm: vlmCacheHit,
              },
              baselineGenTput: pickNumber(data?.baseline?.generation_tps, prev.baselineGenTput),
              lmcacheGenTput: pickNumber(data?.lmcache?.generation_tps, prev.lmcacheGenTput),
              vlmGenTput: pickNumber(data?.vlm?.generation_tps, prev.vlmGenTput),
              baselinePromptTput: pickNumber(data?.baseline?.prompt_tps, prev.baselinePromptTput),
              lmcachePromptTput: pickNumber(data?.lmcache?.prompt_tps, prev.lmcachePromptTput),
              vlmPromptTput: pickNumber(data?.vlm?.prompt_tps, prev.vlmPromptTput),
              baselineKvCache: pickNumber(data?.baseline?.kv_cache_usage_pct, prev.baselineKvCache),
              lmcacheKvCache: pickNumber(data?.lmcache?.kv_cache_usage_pct, prev.lmcacheKvCache),
              vlmKvCache: pickNumber(data?.vlm?.kv_cache_usage_pct, prev.vlmKvCache),
              diskRead: pickNumber(data?.lmcache?.prompt_tokens, prev.diskRead),
              diskWrite: pickNumber(data?.lmcache?.generation_tokens, prev.diskWrite),
            };
          });
        }
      } catch (error) {
        console.log('Metrics fetch failed');
      }
    };

    fetchVllmMetrics();
    const interval = setInterval(fetchVllmMetrics, 2000);
    return () => clearInterval(interval);
  }, []);

  // Fetch system metrics (GPU, SSD, CPU) and track energy consumption
  useEffect(() => {
    const fetchSystemMetrics = async () => {
      try {
        const m = metricsRef.current;
        const llmMetrics: LLMMetrics = {
          ttft: {
            baseline: m.baselineTTFT,
            lmcache: m.lmcacheTTFT,
          },
          speedup: m.speedup,
          generationThroughput: {
            baseline: m.baselineGenTput,
            lmcache: m.lmcacheGenTput,
            vlm: m.vlmGenTput,
          },
          promptThroughput: {
            baseline: m.baselinePromptTput,
            lmcache: m.lmcachePromptTput,
            vlm: m.vlmPromptTput,
          },
          kvCacheUsage: {
            baseline: m.baselineKvCache,
            lmcache: m.lmcacheKvCache,
            vlm: m.vlmKvCache,
          },
          cacheHitRate: m.cacheHitRate,
          cacheHitRates: m.cacheHitRates,
        };

        const systemData = await fetchAllSystemMetrics(llmMetrics);
        setGpuMetrics(systemData.gpus);
        setSsdMetrics(systemData.ssd);
        setCpuMetrics(systemData.cpu);
        setGpuHistory(systemData.gpuHistory);

        // Track power history for energy calculation
        const now = Date.now();
        const baselinePwr = systemData.gpus[1]?.power || 0;
        const lmcachePwr = systemData.gpus[0]?.power || 0;

        // Accumulate GPU power samples during active inference for averaging
        const eRefPower = inferenceEnergyRef.current;
        if (eRefPower.baselineActive || eRefPower.lmcacheActive) {
          avgPowerRef.current.baselineSum += baselinePwr;
          avgPowerRef.current.lmcacheSum += lmcachePwr;
          avgPowerRef.current.sampleCount += 1;
        }

        // Accumulate energy during active inference (for Column 3 efficiency)
        const eRef = inferenceEnergyRef.current;
        const deltaSec = eRef.lastPollTime > 0 ? (now - eRef.lastPollTime) / 1000 : 0;
        if (deltaSec > 0 && deltaSec < 10) {
          if (eRef.baselineActive) eRef.baselineWs += baselinePwr * deltaSec;
          if (eRef.lmcacheActive) eRef.lmcacheWs += lmcachePwr * deltaSec;
        }
        if (eRef.baselineActive || eRef.lmcacheActive) {
          eRef.lastPollTime = now;
        }
        // Only compute efficiency after both queries have completed (not during inference)
        if (eRef.baselineWs > 0 && eRef.lmcacheWs > 0 && !eRef.baselineActive && !eRef.lmcacheActive) {
          const ratio = eRef.baselineWs / eRef.lmcacheWs;
          eRef.peakEfficiency = Math.max(eRef.peakEfficiency, ratio);
          setEnergyEfficiency(eRef.peakEfficiency);
        }

        setPowerHistory(prev => {
          const newBaseline = [...prev.baseline.slice(-100), { power: baselinePwr, timestamp: now }];
          const newLmcache = [...prev.lmcache.slice(-100), { power: lmcachePwr, timestamp: now }];

          // Calculate energy consumed since last reading (Watt-seconds -> Watt-hours)
          if (prev.baseline.length > 0 && prev.lmcache.length > 0) {
            const lastBaseline = prev.baseline[prev.baseline.length - 1];
            const lastLmcache = prev.lmcache[prev.lmcache.length - 1];

            const baselineDeltaHours = (now - lastBaseline.timestamp) / 3600000; // ms to hours
            const lmcacheDeltaHours = (now - lastLmcache.timestamp) / 3600000;

            const avgBaselinePower = (baselinePwr + lastBaseline.power) / 2;
            const avgLmcachePower = (lmcachePwr + lastLmcache.power) / 2;

            setTotalEnergy(prevEnergy => ({
              baseline: prevEnergy.baseline + (avgBaselinePower * baselineDeltaHours),
              lmcache: prevEnergy.lmcache + (avgLmcachePower * lmcacheDeltaHours),
            }));
          }

          return { baseline: newBaseline, lmcache: newLmcache };
        });
      } catch (error) {
        console.log('System metrics fetch failed');
      }
    };

    fetchSystemMetrics();
    const interval = setInterval(fetchSystemMetrics, 2000);
    return () => clearInterval(interval);
  }, []);

  // Show analytics dashboard
  if (showAnalytics) {
    return (
      <AnalyticsDashboard
        onClose={() => setShowAnalytics(false)}
        metrics={metrics}
        queryHistory={ttftHistory}
      />
    );
  }

  const isLoading = isBaselineLoading || isLmcacheLoading;
  const contextWords = sharedContext ? sharedContext.split(/\s+/).length : 0;

  // Prepare LLM metrics for sidebar
  const llmMetrics: LLMMetrics = {
    ttft: {
      baseline: metrics.baselineTTFT,
      lmcache: metrics.lmcacheTTFT,
    },
    speedup: metrics.speedup,
    generationThroughput: {
      baseline: metrics.baselineGenTput,
      lmcache: metrics.lmcacheGenTput,
      vlm: metrics.vlmGenTput,
    },
    promptThroughput: {
      baseline: metrics.baselinePromptTput,
      lmcache: metrics.lmcachePromptTput,
      vlm: metrics.vlmPromptTput,
    },
    kvCacheUsage: {
      baseline: metrics.baselineKvCache,
      lmcache: metrics.lmcacheKvCache,
      vlm: metrics.vlmKvCache,
    },
    cacheHitRate: metrics.cacheHitRate,
    cacheHitRates: metrics.cacheHitRates,
  };

  const baselinePower = gpuMetrics[1]?.power || 0;
  const lmcachePower = gpuMetrics[0]?.power || 0;
  const energySavedWh = totalEnergy.baseline - totalEnergy.lmcache;

  return (
    <div className={styles.container}>
      <Header
        onReset={clearAll}
        onAnalytics={() => setShowAnalytics(true)}
        onVideoUpload={handleVideoUpload}
        isUploading={isUploading}
        onFlush={handleFlush}
        isFlushing={isFlushing}
      />

      {/* Main Content - Three Column Layout */}
      <div className={styles.main}>
        <div className={styles.layout}>
          {/* Left Sidebar: Context + Scenarios */}
          <aside className={styles.leftSidebar}>
            <ScenarioPanel
              onSelect={handleScenarioSelect}
              onMultiUserSelect={handleMultiUserSelect}
              disabled={isLoading || isFlushing || multiUserStatus === 'results'}
            />

            <ContextSelector
              ref={contextSelectorRef}
              onContextChange={(ctx, docs) => {
                setSharedContext(ctx);
                setSelectedDocs(docs);
                if (contextSelectorRef.current) {
                  const ids = contextSelectorRef.current.getSelectedIds();
                  setSelectedContextFileIds(ids);
                }
              }}
              onLoadingChange={setIsContextLoading}
              gameCount={gameCount}
              onGameCountChange={setGameCount}
              disableSelection={multiUserStatus === 'results' || multiUserStatus === 'configuring'}
            />
          </aside>

          {/* Middle: Comparison Arena or Multi-User Results */}
          <div className={styles.panels}>
            {(multiUserStatus === 'results' || multiUserStatus === 'completed') && multiUserSettings && multiUserRunId ? (
              <MultiUserResults
                settings={multiUserSettings}
                runId={multiUserRunId}
                gpuPower={{ baseline: gpuMetrics[1]?.power || 0, lmcache: gpuMetrics[0]?.power || 0 }}
                onReset={handleMultiUserReset}
                onStop={() => stopMultiUserBenchmark(multiUserRunId)}
                onBenchmarkCompleted={handleBenchmarkCompleted}
              />
            ) : (
              <ComparisonArena
                baselineMessages={baselineMessages}
                isBaselineLoading={isBaselineLoading}
                baselineTTFT={metrics.baselineTTFT}
                bestBaselineTTFT={bestBaselineTTFT}
                lmcacheMessages={lmcacheMessages}
                isLmcacheLoading={isLmcacheLoading}
                lmcacheTTFT={metrics.lmcacheTTFT}
                bestLmcacheTTFT={bestLmcacheTTFT}
                speedup={metrics.speedup}
                cacheHitRate={metrics.cacheHitRate}
                baselinePower={baselinePower}
                lmcachePower={lmcachePower}
                energyEfficiency={energyEfficiency}
                avgBaselinePower={avgBaselinePower}
                avgLmcachePower={avgLmcachePower}
              />
            )}
          </div>

          {/* Right Sidebar: Metrics */}
          <aside className={styles.rightSidebar}>
            <MetricsPanel
              llm={llmMetrics}
              gpus={gpuMetrics}
              gpuHistory={gpuHistory}
              ssd={ssdMetrics}
              cpu={cpuMetrics}
            />
          </aside>
        </div>
      </div>

      {/* Floating Command Bar - hidden during multi-user benchmark */}
      {multiUserStatus === 'idle' && (
        <CommandBar
          query={sharedQuery}
          onQueryChange={setSharedQuery}
          onSend={() => sendToBoth()}
          isLoading={isLoading || isFlushing || isContextLoading}
          hasContext={contextWords > 0}
          contextWords={contextWords}
          suggestedQueries={suggestedQueries}
          onSelectQuery={(q) => setSharedQuery(q)}
        />
      )}

      {/* Multi-User Configuration Dialog */}
      <MultiUserConfig
        open={multiUserStatus === 'configuring'}
        onClose={handleMultiUserReset}
        onStart={handleMultiUserStart}
        onViewActive={handleViewActiveBenchmark}
      />
    </div>
  );
}
