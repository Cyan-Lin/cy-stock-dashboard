import type { OHLCBar, Symbol, Timeframe } from '../data/mockData'

const INTERVAL_MAP: Record<Timeframe, 'daily' | 'weekly' | 'monthly'> = {
  D: 'daily',
  W: 'weekly',
  M: 'monthly',
}

interface ApiPriceBar {
  symbol: string
  date: string
  open: number | null
  high: number | null
  low: number | null
  close: number | null
  volume: number | null
  ma60: number | null
}

export interface PriceSeries {
  bars: OHLCBar[]
  ma60: (number | null)[]
}

export async function fetchPrices(symbol: Symbol, timeframe: Timeframe): Promise<PriceSeries> {
  const params = new URLSearchParams({
    symbol,
    interval: INTERVAL_MAP[timeframe],
    limit: '20000',
  })
  const res = await fetch(`/api/prices?${params}`)

  if (res.status === 404) return { bars: [], ma60: [] }
  if (!res.ok) throw new Error(`GET /api/prices failed: ${res.status}`)

  const rows: ApiPriceBar[] = await res.json()

  // API 回傳為 date DESC，圖表需要 ascending
  const ascending = [...rows].reverse().filter(
    (r) => r.open !== null && r.high !== null && r.low !== null && r.close !== null,
  )

  return {
    bars: ascending.map((r) => ({
      date: r.date,
      open: r.open as number,
      high: r.high as number,
      low: r.low as number,
      close: r.close as number,
      volume: r.volume ?? 0,
    })),
    ma60: ascending.map((r) => r.ma60),
  }
}
