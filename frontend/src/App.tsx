import { useState, useMemo, useEffect } from 'react'
import TopBar from './components/TopBar'
import DashboardChart from './components/DashboardChart'
import { fetchPrices } from './api/prices'
import { fetchMargin } from './api/margin'
import {
  getMockSecondPanel,
  type MarginBar,
  type OHLCBar,
  type Symbol,
  type Timeframe,
} from './data/mockData'

export default function App() {
  const [symbol, setSymbol] = useState<Symbol>('TWII')
  const [timeframe, setTimeframe] = useState<Timeframe>('D')

  const [priceBars, setPriceBars] = useState<OHLCBar[]>([])
  const [ma60, setMa60] = useState<(number | null)[]>([])
  const [priceError, setPriceError] = useState<string | null>(null)
  const [marginBars, setMarginBars] = useState<MarginBar[]>([])

  const secondBars = useMemo(() => getMockSecondPanel(symbol, timeframe), [symbol, timeframe])

  useEffect(() => {
    let cancelled = false

    fetchPrices(symbol, timeframe)
      .then(({ bars, ma60 }) => {
        if (cancelled) return
        setPriceBars(bars)
        setMa60(ma60)
        setPriceError(null)
      })
      .catch((err: Error) => {
        if (cancelled) return
        setPriceError(err.message)
      })

    return () => {
      cancelled = true
    }
  }, [symbol, timeframe])

  useEffect(() => {
    let cancelled = false

    fetchMargin(symbol, timeframe)
      .then((bars) => {
        if (cancelled) return
        setMarginBars(bars)
      })
      .catch(() => {
        if (cancelled) return
        setMarginBars([])
      })

    return () => {
      cancelled = true
    }
  }, [symbol, timeframe])

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
        {priceError ? (
          <div className="flex items-center justify-center h-full text-sm" style={{ color: 'var(--color-destructive)' }}>
            資料載入失敗：{priceError}
          </div>
        ) : priceBars.length === 0 ? (
          <div className="flex items-center justify-center h-full text-sm" style={{ color: 'var(--color-border)' }}>
            載入中…
          </div>
        ) : (
          <DashboardChart
            priceBars={priceBars}
            marginBars={marginBars}
            secondBars={secondBars}
            ma60={ma60}
            timeframe={timeframe}
          />
        )}
      </div>
    </div>
  )
}
