import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import LazyMetricItem from '../lazyMetricItem';
import { renderChart, calculateMetrics } from '@/app/monitor/utils/common';
import type { MetricItem, ChartDataItem } from '@/app/monitor/types';

vi.mock('@/utils/i18n', () => ({
  useTranslation: () => ({
    t: (key: string) => key
  })
}));

vi.mock('@/app/monitor/hooks/useUnitTransform', () => ({
  useUnitTransform: () => ({
    findUnitNameById: (unit: string) => unit || ''
  })
}));

vi.mock('@/app/monitor/components/charts/lineChart', () => ({
  default: ({ data, metric }: { data: any[]; metric: any }) => (
    <div data-testid="line-chart" data-points={data.length} data-metric={metric?.name}>
      {data.length === 0 ? 'EMPTY_STATE' : `CHART_RENDERED_${data.length}`}
    </div>
  )
}));

describe('LazyMetricItem & Metric Render Pipeline', () => {
  beforeEach(() => {
    // Mock IntersectionObserver
    class MockIntersectionObserver {
      observe = vi.fn();
      unobserve = vi.fn();
      disconnect = vi.fn();
    }
    window.IntersectionObserver = MockIntersectionObserver as any;
  });

  afterEach(() => {
    cleanup();
  });

  it('renders loaded chart data even when isInViewport is false', () => {
    const metricItem: MetricItem = {
      id: 2710,
      metric_group: 1,
      metric_object: 28,
      name: 'ipmi_power_watts',
      type: 'number',
      display_name: 'Power',
      displayUnit: 'watts',
      unit: 'watts',
      dimensions: [{ name: 'name', description: 'name' }],
      viewData: [
        { time: 1726851200, value1: 280 },
        { time: 1726851260, value1: 280 }
      ]
    };

    render(
      <LazyMetricItem
        item={metricItem}
        isLoading={false}
        isLoaded={true}
        isCancelled={false}
        isInViewport={false}
        onVisible={vi.fn()}
        onSearchClick={vi.fn()}
        onPolicyClick={vi.fn()}
        onXRangeChange={vi.fn()}
        onVisibilityChange={vi.fn()}
      />
    );

    const chart = screen.getByTestId('line-chart');
    expect(chart.textContent).toBe('CHART_RENDERED_2');
    expect(chart.getAttribute('data-points')).toBe('2');
  });

  it('unpacks realistic query_by_metric_range IPMI metrics correctly into non-empty viewData', () => {
    const instanceId = '172.18.0.14';
    const instanceRow = [
      {
        instance_id_values: [instanceId],
        instance_name: 'IPMI-Server-14',
        instance_id_keys: ['instance_id'],
        dimensions: [{ name: 'name', description: 'name' }],
        title: 'Power'
      }
    ];

    // 1. Power (id=2710)
    const powerResponseData: ChartDataItem[] = [
      {
        metric: { instance_id: instanceId, name: 'pwr_consumption' },
        values: [
          [1726851200, '280.0'],
          [1726851260, '282.5']
        ]
      }
    ];
    const powerViewData = renderChart(powerResponseData, instanceRow);
    expect(powerViewData.length).toBe(2);
    expect(powerViewData[0].value1).toBe(280);
    expect(powerViewData[1].value1).toBe(282.5);
    expect(calculateMetrics(powerViewData as any, 'value1').latestValue).toBe(282.5);

    // 2. Voltage (id=2711)
    const voltageResponseData: ChartDataItem[] = [
      {
        metric: { instance_id: instanceId, name: 'voltage_12v' },
        values: [
          [1726851200, '12.1'],
          [1726851260, '12.08']
        ]
      },
      {
        metric: { instance_id: instanceId, name: 'voltage_5v' },
        values: [
          [1726851200, '5.02'],
          [1726851260, '5.01']
        ]
      }
    ];
    const voltageViewData = renderChart(voltageResponseData, instanceRow);
    expect(voltageViewData.length).toBe(2);
    expect(voltageViewData[0].value1).toBe(12.1);
    expect(voltageViewData[0].value2).toBe(5.02);
    expect(calculateMetrics(voltageViewData as any, 'value1').latestValue).toBe(12.08);

    // 3. Chassis power state (id=2709)
    const chassisResponseData: ChartDataItem[] = [
      {
        metric: { instance_id: instanceId },
        values: [
          [1726851200, '2.0'],
          [1726851260, '2.0']
        ]
      }
    ];
    const chassisViewData = renderChart(chassisResponseData, instanceRow);
    expect(chassisViewData.length).toBe(2);
    expect(chassisViewData[0].value1).toBe(2);
    expect(calculateMetrics(chassisViewData as any, 'value1').latestValue).toBe(2);
  });
});
