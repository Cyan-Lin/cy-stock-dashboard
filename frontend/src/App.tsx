import { useState, useMemo } from 'react'
import TopBar from './components/TopBar'
import DashboardChart from './components/DashboardChart'
import {
  getMockPriceBars,
  getMockMargin,
  getMockSecondPanel,
  calc60MA,
  type Symbol,
  type Timeframe,
} from './data/mockData'

export default function App() {
  const [symbol, setSymbol] = useState<Symbol>('TWII')
  const [timeframe, setTimeframe] = useState<Timeframe>('D')

  const priceBars = useMemo(() => getMockPriceBars(symbol, timeframe), [symbol, timeframe])
  const marginBars = useMemo(() => getMockMargin(symbol), [symbol])
  const secondBars = useMemo(() => getMockSecondPanel(symbol, timeframe), [symbol, timeframe])
  const ma60 = useMemo(() => calc60MA(priceBars), [priceBars])

  const lastBar = priceBars[priceBars.length - 1]
  const prevBar = priceBars[priceBars.length - 2]
  const change = lastBar && prevBar ? lastBar.close - prevBar.close : 0
  const changePct = prevBar ? (change / prevBar.close) * 100 : 0

  return (
    <div
      className="flex flex-col"
      style={{
        height: '100dvh',
        background: 'var(--color-background)',
        color: 'var(--color-foreground)',
        fontFamily: 'Inter, sans-serif',
      }}
    >
      <TopBar
        symbol={symbol}
        timeframe={timeframe}
        onSymbolChange={setSymbol}
        onTimeframeChange={setTimeframe}
        lastPrice={lastBar?.close ?? 0}
        change={change}
        changePct={changePct}
      />

      {/* Single ECharts instance fills remaining height — no scrolling needed */}
      <div className="flex-1 min-h-0">
        <DashboardChart
          priceBars={priceBars}
          marginBars={marginBars}
          secondBars={secondBars}
          ma60={ma60}
          timeframe={timeframe}
        />
      </div>
    </div>
  )
}
