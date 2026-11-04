import { describe, expect, it } from 'vitest';
import { renderChart, calculateMetrics } from '@/app/monitor/utils/common';
import { ChartDataItem, ChartProps } from '@/app/monitor/types';

describe('renderChart with multi-series by (instance_id, name)', () => {
  it('correctly parses multi-series responses grouped by name into distinct value1, value2 series with finite numeric values', () => {
    // Simulated VictoriaMetrics Prometheus range query result for:
    // avg(redfish_voltage_volts_gauge{instance_id=~"MDA1..."}) by (instance_id, name)
    const mockChartData: ChartDataItem[] = [
      {
        metric: {
          instance_id: 'MDA12345',
          name: 'Voltage_12V',
        },
        values: [
          [1700000000, '12.1'],
          [1700000060, '12.12'],
        ],
      },
      {
        metric: {
          instance_id: 'MDA12345',
          name: 'Voltage_3V3',
        },
        values: [
          [1700000000, '3.31'],
          [1700000060, '3.30'],
        ],
      },
    ];

    const mockInstanceRow: ChartProps[] = [
      {
        instance_id_values: ['MDA12345'],
        instance_name: 'server-01',
        instance_id_keys: ['instance_id'],
        dimensions: [{ name: 'name', description: 'Sensor Name' }],
        title: '电压 (Voltage)',
      },
    ];

    const rendered = renderChart(mockChartData, mockInstanceRow);

    // Verify rendered output structure
    expect(rendered).toHaveLength(2);
    expect(rendered[0]).toMatchObject({
      time: 1700000000,
      title: '电压 (Voltage)',
      value1: 12.1,
      value2: 3.31,
    });
    expect(rendered[1]).toMatchObject({
      time: 1700000060,
      title: '电压 (Voltage)',
      value1: 12.12,
      value2: 3.3,
    });

    // Verify seriesMetrics and details for both series
    expect(rendered[0].seriesMetrics?.value1).toEqual({
      instance_id: 'MDA12345',
      name: 'Voltage_12V',
    });
    expect(rendered[0].seriesMetrics?.value2).toEqual({
      instance_id: 'MDA12345',
      name: 'Voltage_3V3',
    });
    expect(rendered[0].details?.value1).toEqual([
      { name: 'name', label: 'Sensor Name', value: 'Voltage_12V' },
    ]);
    expect(rendered[0].details?.value2).toEqual([
      { name: 'name', label: 'Sensor Name', value: 'Voltage_3V3' },
    ]);

    // Verify calculateMetrics operates correctly on each series key
    const metrics1 = calculateMetrics(rendered as any, 'value1');
    expect(metrics1.latestValue).toBe(12.12);
    expect(metrics1.maxValue).toBe(12.12);
    expect(metrics1.minValue).toBe(12.1);

    const metrics2 = calculateMetrics(rendered as any, 'value2');
    expect(metrics2.latestValue).toBe(3.3);
    expect(metrics2.maxValue).toBe(3.31);
    expect(metrics2.minValue).toBe(3.3);
  });

  it('handles multi-series where series have dimensions declared in config.dimensions', () => {
    const mockChartData: ChartDataItem[] = [
      {
        metric: {
          instance_id: 'MDA12345',
          name: 'Sensor_A',
        },
        values: [
          [1700000000, '12.1'],
        ],
      },
      {
        metric: {
          instance_id: 'MDA12345',
          name: 'Sensor_B',
        },
        values: [
          [1700000000, '3.31'],
        ],
      },
    ];

    const mockInstanceRowWithDimensions: ChartProps[] = [
      {
        instance_id_values: ['MDA12345'],
        instance_name: 'server-01',
        instance_id_keys: ['instance_id'],
        dimensions: [{ name: 'name', description: 'Sensor Name' }],
        title: 'IPMI Voltage',
      },
    ];

    const rendered = renderChart(mockChartData, mockInstanceRowWithDimensions);

    expect(rendered).toHaveLength(1);
    expect(rendered[0].value1).toBe(12.1);
    expect(rendered[0].value2).toBe(3.31);
    expect(rendered[0].seriesMetrics?.value1).toEqual({
      instance_id: 'MDA12345',
      name: 'Sensor_A',
    });
    expect(rendered[0].seriesMetrics?.value2).toEqual({
      instance_id: 'MDA12345',
      name: 'Sensor_B',
    });
  });

  it('handles single-series by (instance_id) health metrics identically to multi-series', () => {
    const mockChartData: ChartDataItem[] = [
      {
        metric: {
          instance_id: 'MDA12345',
        },
        values: [
          [1700000000, '1'],
          [1700000060, '1'],
        ],
      },
    ];

    const mockInstanceRow: ChartProps[] = [
      {
        instance_id_values: ['MDA12345'],
        instance_name: 'server-01',
        instance_id_keys: ['instance_id'],
        dimensions: [],
        title: '系统健康',
      },
    ];

    const rendered = renderChart(mockChartData, mockInstanceRow);
    expect(rendered).toHaveLength(2);
    expect(rendered[0].value1).toBe(1);
    expect(rendered[1].value1).toBe(1);
  });
});
