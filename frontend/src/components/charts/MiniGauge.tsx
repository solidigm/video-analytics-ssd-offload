// Created by Metrum AI for Solidigm

import { useRef, useEffect } from 'react';
import * as echarts from 'echarts';
import styles from '@/styles/components/charts/MiniGauge.module.css';

interface MiniGaugeProps {
  value: number;
  max?: number;
  label?: string;
  unit?: string;
  color?: string;
  size?: number;
}

export function MiniGauge({
  value,
  max = 100,
  label,
  unit = '%',
  color = '#5B4FC4',
  size = 80,
}: MiniGaugeProps) {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!chartRef.current) return;

    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current, undefined, {
        renderer: 'svg',
      });
    }

    const option: echarts.EChartsOption = {
      animation: true,
      animationDuration: 600,
      animationEasing: 'cubicOut',
      series: [
        {
          type: 'gauge',
          startAngle: 220,
          endAngle: -40,
          min: 0,
          max,
          radius: '100%',
          center: ['50%', '55%'],
          progress: {
            show: true,
            width: 8,
            itemStyle: {
              color,
            },
          },
          axisLine: {
            lineStyle: {
              width: 8,
              color: [[1, 'rgba(0, 0, 0, 0.06)']],
            },
          },
          axisTick: { show: false },
          splitLine: { show: false },
          axisLabel: { show: false },
          pointer: { show: false },
          title: { show: false },
          detail: {
            valueAnimation: true,
            offsetCenter: [0, '10%'],
            fontSize: 16,
            fontWeight: 600,
            fontFamily: 'Geist Mono, monospace',
            formatter: `{value}${unit}`,
            color: '#1d1d1f',
          },
          data: [{ value: Math.round(value * 10) / 10 }],
        },
      ],
    };

    chartInstance.current.setOption(option, true);
  }, [value, max, color, unit]);

  useEffect(() => {
    return () => {
      chartInstance.current?.dispose();
    };
  }, []);

  return (
    <div className={styles.container}>
      <div
        ref={chartRef}
        className={styles.chart}
        style={{ width: size, height: size }}
      />
      {label && <span className={styles.label}>{label}</span>}
    </div>
  );
}
