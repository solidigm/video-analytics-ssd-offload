// Created by Metrum AI for Solidigm

import { useRef, useEffect } from 'react';
import * as echarts from 'echarts';
import { Clock, TrendingUp } from 'lucide-react';
import styles from '@/styles/components/TTFTChart.module.css';

interface TTFTChartProps {
  baselineHistory: number[];
  lmcacheHistory: number[];
  latestBaseline: number | null;
  latestLmcache: number | null;
}

export function TTFTChart({
  baselineHistory,
  lmcacheHistory,
  latestBaseline,
  latestLmcache
}: TTFTChartProps) {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);

  // Prepare data
  const displayCount = 8;
  const baselineData = [...baselineHistory].slice(-displayCount);
  const lmcacheData = [...lmcacheHistory].slice(-displayCount);

  while (baselineData.length < displayCount) baselineData.unshift(0);
  while (lmcacheData.length < displayCount) lmcacheData.unshift(0);

  const speedup = latestBaseline && latestLmcache && latestLmcache > 0
    ? (latestBaseline / latestLmcache).toFixed(1)
    : null;

  const hasData = baselineHistory.length > 0 || lmcacheHistory.length > 0;

  // Initialize and update chart
  useEffect(() => {
    if (!chartRef.current || !hasData) return;

    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current, undefined, {
        renderer: 'svg'
      });
    }

    const option: echarts.EChartsOption = {
      animation: true,
      animationDuration: 400,
      animationEasing: 'cubicOut',
      grid: {
        left: 8,
        right: 8,
        top: 8,
        bottom: 8,
        containLabel: false
      },
      xAxis: {
        type: 'category',
        data: Array.from({ length: displayCount }, (_, i) => i + 1),
        show: false
      },
      yAxis: {
        type: 'value',
        show: false
      },
      series: [
        {
          name: 'Baseline',
          type: 'bar',
          data: baselineData,
          barWidth: 12,
          barGap: '20%',
          itemStyle: {
            color: {
              type: 'linear',
              x: 0, y: 1, x2: 0, y2: 0,
              colorStops: [
                { offset: 0, color: '#475569' },
                { offset: 1, color: '#64748B' }
              ]
            },
            borderRadius: [3, 3, 0, 0]
          },
          emphasis: {
            itemStyle: {
              color: '#64748B'
            }
          }
        },
        {
          name: 'LMCache',
          type: 'bar',
          data: lmcacheData,
          barWidth: 12,
          itemStyle: {
            color: {
              type: 'linear',
              x: 0, y: 1, x2: 0, y2: 0,
              colorStops: [
                { offset: 0, color: '#4f00b4' },
                { offset: 1, color: '#5B4FC4' }
              ]
            },
            borderRadius: [3, 3, 0, 0]
          },
          emphasis: {
            itemStyle: {
              color: '#5B4FC4'
            }
          }
        }
      ],
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(255, 255, 255, 0.96)',
        borderColor: 'rgba(0, 0, 0, 0.08)',
        borderWidth: 1,
        padding: [8, 12],
        textStyle: {
          fontFamily: 'Geist Mono, monospace',
          fontSize: 12,
          color: '#1d1d1f'
        },
        formatter: (params: any) => {
          const baseline = params[0]?.value || 0;
          const lmcache = params[1]?.value || 0;
          if (baseline === 0 && lmcache === 0) return '';
          return `
            <div style="font-family: Geist, Inter, sans-serif; font-size: 11px; color: #666; margin-bottom: 4px;">Query ${params[0].dataIndex + 1}</div>
            <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 2px;">
              <span style="width: 8px; height: 8px; background: #64748B; border-radius: 2px;"></span>
              <span style="font-family: Geist Mono, monospace;">${baseline.toFixed(3)}s</span>
            </div>
            <div style="display: flex; align-items: center; gap: 6px;">
              <span style="width: 8px; height: 8px; background: #5B4FC4; border-radius: 2px;"></span>
              <span style="font-family: Geist Mono, monospace;">${lmcache.toFixed(3)}s</span>
            </div>
          `;
        }
      }
    };

    chartInstance.current.setOption(option, true);

    // Handle resize
    const handleResize = () => chartInstance.current?.resize();
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [baselineData, lmcacheData, hasData]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      chartInstance.current?.dispose();
    };
  }, []);

  return (
    <div className={`card ${styles.container}`}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <Clock className={styles.headerIcon} />
          <h3 className={styles.title}>TTFT Comparison</h3>
        </div>
        {speedup && (
          <div className={styles.speedupBadge}>
            <TrendingUp className={styles.speedupIcon} />
            <span className={styles.speedupText}>{speedup}x faster</span>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className={styles.legend}>
        <div className={styles.legendItem}>
          <div className={`${styles.legendDot} ${styles.legendDotBaseline}`}></div>
          <span className={styles.legendLabel}>Baseline</span>
          {latestBaseline !== null && (
            <span className={`${styles.legendValue} ${styles.legendValueBaseline}`}>
              {latestBaseline.toFixed(2)}s
            </span>
          )}
        </div>
        <div className={styles.legendItem}>
          <div className={`${styles.legendDot} ${styles.legendDotLmcache}`}></div>
          <span className={styles.legendLabel}>LMCache</span>
          {latestLmcache !== null && (
            <span className={`${styles.legendValue} ${styles.legendValueLmcache}`}>
              {latestLmcache.toFixed(2)}s
            </span>
          )}
        </div>
      </div>

      {/* Chart Area */}
      <div className={styles.chartArea}>
        {hasData ? (
          <div ref={chartRef} className={styles.chartContainer} />
        ) : (
          <div className={styles.emptyState}>
            <div className={styles.emptyContent}>
              <Clock className={styles.emptyIcon} />
              <p className={styles.emptyText}>Send queries to see comparison</p>
            </div>
          </div>
        )}
      </div>

      {/* X-Axis Labels */}
      <div className={styles.axisLabels}>
        <span className={styles.axisLabel}>Older</span>
        <span className={styles.axisLabel}>Latest</span>
      </div>
    </div>
  );
}
