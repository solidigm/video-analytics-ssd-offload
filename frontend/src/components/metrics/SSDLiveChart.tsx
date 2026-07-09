// Created by Metrum AI for Solidigm

import { useEffect, useRef, useLayoutEffect } from 'react';
import * as echarts from 'echarts';

interface SSDLiveChartProps {
  readHistory: number[];
  writeHistory: number[];
}

export function SSDLiveChart({ readHistory, writeHistory }: SSDLiveChartProps) {
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

    // Initialize chart
    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current, undefined, {
        renderer: 'canvas',
      });
    }

    const chart = chartInstance.current;

    // Use MB/s directly for display
    const readData = [...readHistory];
    const writeData = [...writeHistory];

    // Pad arrays to always show 20 points
    const padArray = (arr: number[], length: number) => {
      if (arr.length >= length) return arr.slice(-length);
      return [...Array(length - arr.length).fill(null), ...arr];
    };

    const paddedRead = padArray(readData, 20);
    const paddedWrite = padArray(writeData, 20);

    const option: echarts.EChartsOption = {
      animation: true,
      animationDuration: 300,
      animationEasing: 'cubicOut',
      grid: {
        top: 8,
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
        max: (value) => Math.max(10, Math.ceil(value.max * 1.2)),
        splitNumber: 3,
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
          formatter: (value: number) => `${value}`,
        },
      },
      series: [
        {
          name: 'Read',
          type: 'line',
          data: paddedRead,
          smooth: 0.4,
          symbol: 'none',
          lineStyle: {
            width: 2.5,
            color: '#10b981',
            shadowColor: 'rgba(16, 185, 129, 0.5)',
            shadowBlur: 8,
          },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(16, 185, 129, 0.35)' },
              { offset: 0.5, color: 'rgba(16, 185, 129, 0.15)' },
              { offset: 1, color: 'rgba(16, 185, 129, 0.02)' },
            ]),
          },
          z: 2,
        },
        {
          name: 'Write',
          type: 'line',
          data: paddedWrite,
          smooth: 0.4,
          symbol: 'none',
          lineStyle: {
            width: 2.5,
            color: '#f59e0b',
            shadowColor: 'rgba(245, 158, 11, 0.5)',
            shadowBlur: 8,
          },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(245, 158, 11, 0.3)' },
              { offset: 0.5, color: 'rgba(245, 158, 11, 0.12)' },
              { offset: 1, color: 'rgba(245, 158, 11, 0.02)' },
            ]),
          },
          z: 1,
        },
      ],
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
          const read = params[0]?.value;
          const write = params[1]?.value;
          if (read === null && write === null) return '';
          return `
            <div style="line-height: 1.6">
              <div style="color: #10b981">Read: ${read !== null ? read.toFixed(1) : '—'} MB/s</div>
              <div style="color: #f59e0b">Write: ${write !== null ? write.toFixed(1) : '—'} MB/s</div>
            </div>
          `;
        },
      },
    };

    chart.setOption(option, { notMerge: false });

    // Handle resize
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
  }, [readHistory, writeHistory]);

  // Cleanup on unmount
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
        minHeight: '120px',
      }}
    />
  );
}
