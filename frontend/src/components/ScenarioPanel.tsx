// Created by Metrum AI for Solidigm

import { useState } from 'react';
import { motion } from 'motion/react';
import { Sparkles, Users, Archive, Zap, ClockIcon } from 'lucide-react';
import styles from '@/styles/components/ScenarioPanel.module.css';

export interface ScenarioData {
  id: string;
  query: string;
  allQueries: string[];
  contextFiles: string[];
}

interface Scenario {
  id: string;
  label: string;
  sublabel: string;
  queries: string[];
  icon: React.ReactNode;
  accent: string;
  contextFiles: string[];
}

// Rotating questions for each scenario
const WARM_CACHE_QUERIES = [
  'Using context from this game, detail key plays, turning points, offensive/defensive strategies, and momentum shifts. How did each drive end? 512 tokens.',
  'Analyze all scoring drives from this game. What worked: tempo, formations, play types? Compare stalled drives vs successful ones. Red zone execution? 512 tokens.',
  'How did offensive and defensive game plans evolve in this game? First half vs second half adjustments? Did teams change their run/pass balance? Coverage schemes? 512 tokens.',
  'From this game, analyze 3rd down efficiency, 4th down decisions, two-minute drill execution, and goal-line situations. Who executed better in pressure moments? 512 tokens.',
  'Catalog all explosive plays (20+ yards) from this game. What set them up: coverage busts, misdirection, power runs? Defensive breakdowns? 512 tokens.',
];

const COLD_CACHE_QUERIES = [
  'Analyze these 5 recent 2025 games from the context. Which players performed best overall (top rushers, receivers, defenders)? What formations were most effective for each team? Summarize key trends in 512 tokens using the full context provided.',
  'From these 5 recent games in the context, identify the standout players (most TDs, yards, tackles). Which offensive and defensive formations worked best? Highlight any emerging patterns in play-calling. Limit to 512 tokens.',
  'Break down play-calling patterns in these 5 games: run/pass splits by down and distance, favorite formations on 3rd down, red zone tendencies. What\'s predictable? What\'s working? 512 tokens.',
  'Evaluate recent team form from these 5 games. Is the offense trending up or down? Red zone efficiency? 3rd down conversion trends? Defensive consistency? Key momentum shifts? 512 tokens.',
  'In these 5 recent games, which offensive/defensive matchups were most exploited? Did any player consistently beat their assignment? Coverage weaknesses? 512 tokens.',
  'From these 5 games, which personnel groupings were most productive? Analyze success rates of different receiver/RB/TE combinations. Which players elevated others? 512 tokens.',
  'Analyze formation effectiveness across these 5 games. Which offensive sets (shotgun, I-form, spread, 11 personnel, 21 personnel) had highest success rate? What defensive fronts worked best? 512 tokens.',
];

const LONG_CONTEXT_QUERIES = [
  'Analyze the provided season (10 games). How did offensive and defensive performance trend over time? Early season vs late season efficiency? Points per game trajectory? 512 tokens.',
  'From the provided games, identify the team MVP and top 5 impact players. Who was most consistent? Who had clutch performances? Statistical leaders across all games? 512 tokens.',
  'Track formation usage evolution across the provided games. Did offensive/defensive schemes change? Which formations became more/less frequent? What worked best by season phase? 512 tokens.',
  'Break down wins vs losses across the season. What differentiates winning games: turnover margin, rushing success, defensive stops? Common factors in defeats? 512 tokens.',
  'Based on the season context, what are this team\'s core strengths (run game, pass rush, red zone D) and critical weaknesses (3rd down D, penalties, turnovers)? Season-long patterns? 512 tokens.',
  'From the season context, define the offensive identity: run-first or pass-heavy? RPO usage? Best-performing play concepts? How does identity shift by opponent or game situation? 512 tokens.',
];

const SCENARIOS: Scenario[] = [
  {
    id: 'Cold Cache',
    label: 'Recent Games',
    sublabel: 'Cold-Cache',
    queries: COLD_CACHE_QUERIES,
    icon: <ClockIcon />,
    accent: '#60a5fa',
    contextFiles: ['video-fff13889-1d58-439b-add1-166d3e11a486', 'video-ea768ef9-6afe-43b3-8621-2d31b0e8da2b', 'video-8f76f59c-ae4b-4cee-8be8-dc571a624d4d', 'video-fe795a80-2e64-4db9-978b-4ebc7f970086', 'video-eeff0470-f242-4785-ba5d-9e024cff1554'],
  },
  {
    id: 'warm-cache',
    label: 'In-Game Analysis',
    sublabel: 'Warm-Cache',
    queries: WARM_CACHE_QUERIES,
    icon: <Zap />,
    accent: '#f97316',
    contextFiles: ['video-d7c8b9a0-1234-5678-9abc-def012345678'], // 2025 Week 11: Alphas vs Nighthawks
  },
  {
    id: 'long-context',
    label: 'Season Archive',
    sublabel: 'Long Context',
    queries: LONG_CONTEXT_QUERIES,
    icon: <Archive />,
    accent: '#a78bfa',
    contextFiles: ['video-6e3c2bed-1184-439b-9b23-3d62b3fb328c', 'video-0a56a001-b863-4051-8a83-59b0a531163b', 'video-1b91ffee-70fd-479a-856f-b515a26dd647', 'video-4745a017-1e09-468a-9fcb-ceadd5b247e9', 'video-f4506687-24a6-4204-889b-0dd1d9d31b59', 'video-93e84315-73dc-4f7c-ba18-e0ea56a49388', 'video-0e170fa5-f7df-462c-a253-533c43894061', 'video-08c6b486-d5ff-456d-8283-0d9fc62c1017', 'video-0d0f87c6-122b-4245-a3bc-fa70bddf6804', 'video-566cd30f-6f10-4453-bbdb-a8d2262cca38'],
  },
  {
    id: 'multi-user',
    label: 'Multi-User',
    sublabel: 'Simulation',
    queries: [],
    icon: <Users />,
    accent: '#8b5cf6',
    contextFiles: [],
  },
];

interface ScenarioPanelProps {
  onSelect: (data: ScenarioData) => void;
  onMultiUserSelect?: () => void;
  disabled?: boolean;
}

export function ScenarioPanel({ onSelect, onMultiUserSelect, disabled }: ScenarioPanelProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [queryIndexes, setQueryIndexes] = useState<Record<string, number>>({});

  const handleSelect = (scenario: Scenario) => {
    setSelectedId(scenario.id);

    // Multi-user scenario triggers its own flow
    if (scenario.id === 'multi-user') {
      onMultiUserSelect?.();
      return;
    }

    // Get current index for this scenario (default to 0)
    const currentIndex = queryIndexes[scenario.id] || 0;

    // Get the query based on current index
    const query = scenario.queries[currentIndex];

    // Determine context files to use
    let contextFiles = scenario.contextFiles;

    // Update the index for next click (rotate through queries)
    const nextIndex = (currentIndex + 1) % scenario.queries.length;
    setQueryIndexes(prev => ({
      ...prev,
      [scenario.id]: nextIndex,
    }));

    onSelect({
      id: scenario.id,
      query: query,
      allQueries: scenario.queries,
      contextFiles: contextFiles,
    });
  };

  return (
    <div className={`card ${styles.container}`}>
      <div className={styles.header}>
        <div className={styles.headerIconWrap}>
          <Sparkles className={styles.headerIcon} />
        </div>
        <h3 className={styles.title}>Scenarios</h3>
      </div>

      <div className={styles.scenarios}>
        {SCENARIOS.map((scenario, index) => {
          const isSelected = selectedId === scenario.id;
          return (
            <motion.button
              key={scenario.id}
              className={`${styles.scenarioButton} ${isSelected ? styles.selected : ''} ${scenario.id === 'multi-user' ? styles.multiUserButton : ''}`}
              onClick={() => handleSelect(scenario)}
              disabled={disabled}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05, duration: 0.2 }}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              style={{
                '--accent-color': scenario.accent,
              } as React.CSSProperties}
            >
              <span className={styles.scenarioIcon}>{scenario.icon}</span>
              <span className={styles.textGroup}>
                <span className={styles.scenarioLabel}>{scenario.label}</span>
                <span className={styles.categoryTag}>{scenario.sublabel}</span>
              </span>
              {isSelected && <span className={styles.activeIndicator} />}
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}
