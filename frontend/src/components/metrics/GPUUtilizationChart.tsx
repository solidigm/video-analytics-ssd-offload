// Created by Metrum AI for Solidigm

import { useEffect, useRef, useLayoutEffect } from 'react';
import * as echarts from 'echarts';

interface GPUUtilizationChartProps {
  utilizationHistory: number[][]; // [gpu0[], gpu1[], gpu2[], gpu3[]]
}

const GPU_COLORS = ['#6366f1', '#8b5cf6', '#a855f7', '#ec4899'];

export function GPUUtilizationChart({ utilizationHistory }: GPUUtilizationChartProps) {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);

  // Initialize chart after layout
  useLayoutEffect(() => {
    if (!chartRef.current) return;

    // Delay init to ensure container has dimensions
    const timer = setTimeout(() => {
      if (!chartRef.current) return;

      if (!chartInstance.current) {
        chartInstance.current = echarts.init(chartRef.current, undefined, {
          renderer: 'canvas',
        });
      }
      chartInstance.current.resize();
    }, 50);

    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!chartRef.current) return;

    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current, undefined, {
        renderer: 'canvas',
      });
    }

    const chart = chartInstance.current;

    // Pad arrays to always show 20 points
    const padArray = (arr: number[], length: number) => {
      if (arr.length >= length) return arr.slice(-length);
      return [...Array(length - arr.length).fill(null), ...arr];
    };

    const paddedData = utilizationHistory.map(arr => padArray(arr, 20));

    const option: echarts.EChartsOption = {
      animation: true,
      animationDuration: 300,
      animationEasing: 'cubicOut',
      grid: {
        top: 24,
        right: 8,
        bottom: 24,
        left: 36,
        containLabel: false,
      },
      xAxis: {
        type: 'category',
        data: Array.from({ length: 20 }, (_, i) => i),
        show: false,
        boundaryGap: false,
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 100,
        splitNumber: 4,
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: {
          lineStyle: {
            color: 'rgba(255, 255, 255, 0.06)',
            type: 'dashed',
          },
        },
        axisLabel: {
          color: 'rgba(255, 255, 255, 0.4)',
          fontSize: 9,
          fontFamily: 'Geist Mono, monospace',
          formatter: (value: number) => `${value}%`,
        },
      },
      series: paddedData.map((data, i) => ({
        name: `GPU ${i}`,
        type: 'line',
        data,
        smooth: 0.4,
        symbol: 'none',
        lineStyle: {
          width: 2,
          color: GPU_COLORS[i],
          shadowColor: `${GPU_COLORS[i]}80`,
          shadowBlur: 6,
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: `${GPU_COLORS[i]}40` },
            { offset: 0.5, color: `${GPU_COLORS[i]}15` },
            { offset: 1, color: `${GPU_COLORS[i]}02` },
          ]),
        },
        z: 4 - i,
      })),
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        borderColor: 'rgba(255, 255, 255, 0.1)',
        borderWidth: 1,
        padding: [8, 12],
        textStyle: {
          fontFamily: 'Geist Mono, monospace',
          fontSize: 11,
          color: '#e2e8f0',
        },
        formatter: (params: any) => {
          const lines = params
            .filter((p: any) => p.value !== null)
            .map((p: any) => `<div style="color: ${GPU_COLORS[p.seriesIndex]}">GPU ${p.seriesIndex}: ${p.value?.toFixed(0) || '—'}%</div>`)
            .join('');
          return `<div style="line-height: 1.6">${lines}</div>`;
        },
      },
    };

    chart.setOption(option, { notMerge: false });

    const handleResize = () => chart.resize();
    window.addEventListener('resize', handleResize);

    // Use ResizeObserver for container size changes
    const resizeObserver = new ResizeObserver(() => {
      chart.resize();
    });
    if (chartRef.current) {
      resizeObserver.observe(chartRef.current);
    }

    return () => {
      window.removeEventListener('resize', handleResize);
      resizeObserver.disconnect();
    };
  }, [utilizationHistory]);

  useEffect(() => {
    return () => {
      if (chartInstance.current) {
        chartInstance.current.dispose();
        chartInstance.current = null;
      }
    };
  }, []);

  return (
    <div
      ref={chartRef}
      style={{
        width: '100%',
        height: '100%',
        minHeight: '100px',
      }}
    />
  );
}
