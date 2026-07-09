// Created by Metrum AI for Solidigm

import { Play, Zap, Clock, TrendingUp, Repeat, Flame, Sparkles } from 'lucide-react';
import styles from '@/styles/components/ScenarioSelector.module.css';

interface Scenario {
  id: string;
  name: string;
  description: string;
  query: string;
  icon: React.ReactNode;
  iconBg: string;
  iconColor: string;
}

const SCENARIOS: Scenario[] = [
  {
    id: 'play-analysis',
    name: 'Play Analysis',
    description: 'Analyze the offensive formation',
    query: 'Analyze the offensive formation and identify the play type. What are the key players to watch?',
    icon: <Play className={styles.icon} />,
    iconBg: 'rgba(0, 102, 204, 0.1)',
    iconColor: 'var(--solidigm-blue-secondary)',
  },
  {
    id: 'player-tracking',
    name: 'Player Tracking',
    description: 'Track player movements',
    query: 'Track the movement patterns of the quarterback and receivers. Describe their routes and timing.',
    icon: <TrendingUp className={styles.icon} />,
    iconBg: 'rgba(119, 60, 238, 0.1)',
    iconColor: 'var(--solidigm-accent)',
  },
  {
    id: 'game-summary',
    name: 'Game Summary',
    description: 'Summarize key moments',
    query: 'Provide a comprehensive summary of the key moments, scores, and turning points in this game footage.',
    icon: <Clock className={styles.icon} />,
    iconBg: 'rgba(118, 185, 0, 0.1)',
    iconColor: 'var(--color-lmcache)',
  },
  {
    id: 'tactical-breakdown',
    name: 'Tactical Breakdown',
    description: 'Deep tactical analysis',
    query: 'Break down the defensive strategy used. What coverage schemes are employed and how effective are they?',
    icon: <Zap className={styles.icon} />,
    iconBg: 'rgba(244, 211, 94, 0.15)',
    iconColor: 'var(--naples-yellow)',
  },
  {
    id: 'highlight-reel',
    name: 'Highlight Reel',
    description: 'Find exciting plays',
    query: 'Identify the most exciting and impactful plays from this footage. Describe each highlight in detail.',
    icon: <Flame className={styles.icon} />,
    iconBg: 'rgba(237, 28, 36, 0.1)',
    iconColor: 'var(--color-baseline)',
  },
];

interface ScenarioSelectorProps {
  selectedScenario: string | null;
  onSelectScenario: (scenario: Scenario) => void;
  onRunScenario: () => void;
  isRunning: boolean;
}

export function ScenarioSelector({
  selectedScenario,
  onSelectScenario,
  onRunScenario,
  isRunning
}: ScenarioSelectorProps) {
  return (
    <div className={`card ${styles.container}`}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <Sparkles className={styles.headerIcon} />
          <h3 className={styles.title}>Quick Scenarios</h3>
        </div>
        <button
          onClick={onRunScenario}
          disabled={!selectedScenario || isRunning}
          className={`btn-solidigm ${styles.runButton}`}
        >
          <Repeat className={`${styles.runIcon} ${isRunning ? 'animate-spin' : ''}`} />
          {isRunning ? 'Running...' : 'Run Selected'}
        </button>
      </div>

      <div className={styles.grid}>
        {SCENARIOS.map((scenario) => (
          <button
            key={scenario.id}
            onClick={() => onSelectScenario(scenario)}
            className={`scenario-card ${styles.scenarioButton} ${selectedScenario === scenario.id ? 'selected' : ''}`}
          >
            <div
              className={styles.iconWrapper}
              style={{ backgroundColor: scenario.iconBg, color: scenario.iconColor }}
            >
              {scenario.icon}
            </div>
            <h4 className={styles.name}>{scenario.name}</h4>
            <p className={styles.description}>{scenario.description}</p>
          </button>
        ))}
      </div>
    </div>
  );
}

export type { Scenario };
export { SCENARIOS };
