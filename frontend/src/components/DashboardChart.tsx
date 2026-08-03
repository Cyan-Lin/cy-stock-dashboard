import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import type { OHLCBar, MarginBar, SecondPanelBar, Timeframe } from '../data/mockData'

const BULL_COLOR = '#26A69A'
const BEAR_COLOR = '#EF5350'
const MA60_COLOR = '#F59E0B'
const GRID_COLOR = '#1E293B'
const AXIS_LABEL_COLOR = '#94A3B8'
const CROSSHAIR_COLOR = '#475569'
const BALANCE_COLOR = '#38BDF8'
const MARGIN_RATIO_COLOR = '#F59E0B'
const CLEANUP_COLOR = '#A78BFA'
const RATIO_COLOR = '#22C55E'
const K_COLOR = '#F59E0B'
const D_COLOR = '#60A5FA'
const OB_COLOR = '#EF4444'
const OS_COLOR = '#38BDF8'

const TOOLTIP_BG = '#1E293B'
const TOOLTIP_BORDER = '#334155'

interface DashboardChartProps {
  priceBars: OHLCBar[]
  marginBars: MarginBar[]
  secondBars: SecondPanelBar[]
  ma60: (number | null)[]
  timeframe: Timeframe
}

// Grid layout (% of chart height):
//  0 Price candles : top=24       → bottom=47%
//  1 Volume strip  : top=54%      → bottom=40%
//  2 Margin panel  : top=62%      → bottom=22%
//  3 Dynamic panel : top=80%      → bottom=3%
//  Slider          : bottom=2, h=18

const GRIDS = [
  { left: 68, right: 68, top: 24,    bottom: '47%' },
  { left: 68, right: 68, top: '54%', bottom: '40%' },
  { left: 68, right: 68, top: '62%', bottom: '22%' },
  { left: 68, right: 68, top: '80%', bottom: '3%'  },
]

const X_AXIS_BASE = {
  type: 'category' as const,
  axisLine: { lineStyle: { color: GRID_COLOR } },
  axisTick: { show: false },
  splitLine: { show: false },
}

const Y_AXIS_SILENT = {
  axisLine: { show: false },
  axisTick: { show: false },
  splitLine: { show: false },
}

export default function DashboardChart({
  priceBars, marginBars, secondBars, ma60, timeframe,
}: DashboardChartProps) {
  const dates = priceBars.map(b => b.date)
  const isMonthly = timeframe === 'M'

  const option: EChartsOption = {
    backgroundColor: 'transparent',
    animation: false,

    // KEY: single instance → axisPointer.link works across all grids
    axisPointer: {
      link: [{ xAxisIndex: 'all' }],
      label: {
        backgroundColor: TOOLTIP_BG,
        color: '#F8FAFC',
        fontSize: 13,
      },
    },

    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        lineStyle: { color: CROSSHAIR_COLOR, width: 1, type: 'dashed' as const },
      },
      backgroundColor: TOOLTIP_BG,
      borderColor: TOOLTIP_BORDER,
      borderWidth: 1,
      textStyle: { color: '#F8FAFC', fontSize: 13 },
      formatter: (params: unknown) => {
        if (!Array.isArray(params) || !params.length) return ''
        const p = params as Array<{ axisValue: string; seriesName: string; data: unknown }>
        const date = p[0].axisValue
        const candle = p.find(x => x.seriesName === 'K線')
        if (!candle) return `<div style="font-size:13px;color:#94A3B8">${date}</div>`
        const [o, c, l, h] = candle.data as number[]
        const color = c >= o ? BULL_COLOR : BEAR_COLOR
        return `<div style="font-size:13px;line-height:1.8">
          <div style="color:#94A3B8;margin-bottom:2px">${date}</div>
          <div>開 <span style="color:${color}">${o.toLocaleString()}</span>　高 <span style="color:${color}">${h.toLocaleString()}</span></div>
          <div>低 <span style="color:${color}">${l.toLocaleString()}</span>　收 <span style="color:${color};font-weight:600">${c.toLocaleString()}</span></div>
        </div>`
      },
    },

    title: [
      { text: 'K線',     left: 8, top: 6,     textStyle: { color: AXIS_LABEL_COLOR, fontSize: 13, fontWeight: 500 } },
      { text: '融資動向', left: 8, top: '62%', textStyle: { color: AXIS_LABEL_COLOR, fontSize: 13, fontWeight: 500 } },
      { text: isMonthly ? 'KD + 資券比' : '資券比', left: 8, top: '80%', textStyle: { color: AXIS_LABEL_COLOR, fontSize: 13, fontWeight: 500 } },
    ],

    legend: [
      {
        data: ['融資餘額', '融資維持率', '籌碼洗淨'],
        top: '62%', right: 8,
        itemWidth: 14, itemHeight: 2,
        textStyle: { color: AXIS_LABEL_COLOR, fontSize: 12 },
      },
      {
        data: isMonthly ? ['K值', 'D值', '資券比'] : ['資券比'],
        top: '80%', right: 8,
        itemWidth: 14, itemHeight: 2,
        textStyle: { color: AXIS_LABEL_COLOR, fontSize: 12 },
      },
    ],

    grid: GRIDS,

    xAxis: [
      { ...X_AXIS_BASE, data: dates, gridIndex: 0, axisLabel: { show: false } },
      { ...X_AXIS_BASE, data: dates, gridIndex: 1, axisLabel: { show: false } },
      { ...X_AXIS_BASE, data: dates, gridIndex: 2, axisLabel: { show: false } },
      {
        ...X_AXIS_BASE, data: dates, gridIndex: 3,
        axisLabel: { color: AXIS_LABEL_COLOR, fontSize: 12, interval: Math.floor(dates.length / 6) },
      },
    ],

    yAxis: [
      // Grid 0: price
      {
        gridIndex: 0, scale: true,
        axisLine: { show: false }, axisTick: { show: false },
        axisLabel: { color: AXIS_LABEL_COLOR, fontSize: 12 },
        splitLine: { lineStyle: { color: GRID_COLOR, type: 'dashed' as const } },
      },
      // Grid 1: volume (no labels needed)
      { gridIndex: 1, scale: true, ...Y_AXIS_SILENT, axisLabel: { show: false } },
      // Grid 2: margin balance (left)
      {
        gridIndex: 2, scale: true, name: '億元',
        nameTextStyle: { color: AXIS_LABEL_COLOR, fontSize: 12 },
        axisLine: { show: false }, axisTick: { show: false },
        axisLabel: { color: AXIS_LABEL_COLOR, fontSize: 12 },
        splitLine: { lineStyle: { color: GRID_COLOR, type: 'dashed' as const } },
      },
      // Grid 2: margin ratio / cleanup (right)
      {
        gridIndex: 2, scale: true, name: '%', position: 'right',
        nameTextStyle: { color: AXIS_LABEL_COLOR, fontSize: 12 },
        axisLine: { show: false }, axisTick: { show: false },
        axisLabel: { color: AXIS_LABEL_COLOR, fontSize: 12 },
        splitLine: { show: false },
      },
      // Grid 3: 資券比 (left)
      {
        gridIndex: 3, scale: true, name: '%',
        nameTextStyle: { color: AXIS_LABEL_COLOR, fontSize: 12 },
        axisLine: { show: false }, axisTick: { show: false },
        axisLabel: { color: AXIS_LABEL_COLOR, fontSize: 12 },
        splitLine: { lineStyle: { color: GRID_COLOR, type: 'dashed' as const } },
      },
      // Grid 3: KD 0-100 (right, monthly only) — index 5
      ...(isMonthly ? [{
        gridIndex: 3, min: 0, max: 100, name: 'KD', position: 'right' as const,
        nameTextStyle: { color: AXIS_LABEL_COLOR, fontSize: 12 },
        axisLine: { show: false }, axisTick: { show: false },
        axisLabel: { color: AXIS_LABEL_COLOR, fontSize: 12 },
        splitLine: { show: false },
      }] : []),
    ],

    // Single dataZoom syncs all 4 x-axes simultaneously
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1, 2, 3], start: 60, end: 100 },
      {
        type: 'slider', xAxisIndex: [0, 1, 2, 3],
        bottom: 2, height: 18,
        borderColor: GRID_COLOR,
        fillerColor: 'rgba(51,65,85,0.4)',
        handleStyle: { color: '#475569' },
        textStyle: { color: AXIS_LABEL_COLOR, fontSize: 12 },
      },
    ],

    series: [
      {
        name: 'K線', type: 'candlestick', xAxisIndex: 0, yAxisIndex: 0,
        data: priceBars.map(b => [b.open, b.close, b.low, b.high]),
        itemStyle: { color: BULL_COLOR, color0: BEAR_COLOR, borderColor: BULL_COLOR, borderColor0: BEAR_COLOR },
      },
      ...(timeframe === 'W' ? [{
        name: '60MA', type: 'line' as const, xAxisIndex: 0, yAxisIndex: 0,
        data: ma60, smooth: true, symbol: 'none',
        lineStyle: { color: MA60_COLOR, width: 1.5 },
        tooltip: { show: false },
      }] : []),
      {
        name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
        data: priceBars.map(b => ({
          value: b.volume,
          itemStyle: { color: b.close >= b.open ? 'rgba(38,166,154,0.5)' : 'rgba(239,83,80,0.5)' },
        })),
      },
      {
        name: '融資餘額', type: 'bar', xAxisIndex: 2, yAxisIndex: 2,
        data: marginBars.map(b => b.marginBalance),
        itemStyle: { color: 'rgba(56,189,248,0.4)', borderColor: BALANCE_COLOR, borderWidth: 1 },
        barMaxWidth: 6,
      },
      {
        name: '融資維持率', type: 'line', xAxisIndex: 2, yAxisIndex: 3,
        data: marginBars.map(b => b.marginRatio), smooth: true, symbol: 'none',
        lineStyle: { color: MARGIN_RATIO_COLOR, width: 1.5 },
        markLine: {
          silent: true, symbol: 'none',
          data: [{ yAxis: 140, lineStyle: { color: OB_COLOR, type: 'dashed' as const, width: 1 } }],
          label: { formatter: '140%', color: OB_COLOR, fontSize: 12 },
        },
      },
      {
        name: '籌碼洗淨', type: 'line', xAxisIndex: 2, yAxisIndex: 3,
        data: marginBars.map(b => b.cleanupIndex), smooth: true, symbol: 'none',
        lineStyle: { color: CLEANUP_COLOR, width: 1 },
      },
      {
        name: '資券比', type: 'bar', xAxisIndex: 3, yAxisIndex: 4,
        data: secondBars.map(b => b.shortLongRatio),
        itemStyle: { color: 'rgba(34,197,94,0.35)', borderColor: RATIO_COLOR, borderWidth: 1 },
        barMaxWidth: 6,
      },
      ...(isMonthly ? [
        {
          name: 'K值', type: 'line' as const, xAxisIndex: 3, yAxisIndex: 5,
          data: secondBars.map(b => b.kValue ?? null), smooth: true, symbol: 'none',
          lineStyle: { color: K_COLOR, width: 1.5 },
          markLine: {
            silent: true, symbol: 'none',
            data: [
              { yAxis: 80, lineStyle: { color: OB_COLOR, type: 'dashed' as const, width: 1 } },
              { yAxis: 20, lineStyle: { color: OS_COLOR, type: 'dashed' as const, width: 1 } },
            ],
            label: { show: false },
          },
        },
        {
          name: 'D值', type: 'line' as const, xAxisIndex: 3, yAxisIndex: 5,
          data: secondBars.map(b => b.dValue ?? null), smooth: true, symbol: 'none',
          lineStyle: { color: D_COLOR, width: 1.5 },
        },
      ] : []),
    ],
  }

  return (
    <ReactECharts
      option={option}
      notMerge={true}
      style={{ width: '100%', height: '100%' }}
      opts={{ renderer: 'canvas' }}
    />
  )
}
