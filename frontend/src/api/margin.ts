import type { MarginBar, Symbol, Timeframe } from '../data/mockData'

const INTERVAL_MAP: Record<Timeframe, 'daily' | 'weekly' | 'monthly'> = {
  D: 'daily',
  W: 'weekly',
  M: 'monthly',
}

interface ApiMarginBar {
  symbol: string
  date: string
  margin_amount_100m: number | null
  margin_maintenance_ratio: number | null
  chip_washout: number | null
}

export async function fetchMargin(symbol: Symbol, timeframe: Timeframe): Promise<MarginBar[]> {
  const params = new URLSearchParams({
    symbol,
    interval: INTERVAL_MAP[timeframe],
    limit: '20000',
  })
  const res = await fetch(`/api/margin?${params}`)

  if (res.status === 404) return []
  if (!res.ok) throw new Error(`GET /api/margin failed: ${res.status}`)

  const rows: ApiMarginBar[] = await res.json()

  // API 回傳為 date DESC，圖表需要 ascending。
  // 不可篩掉任何一列——DashboardChart 用陣列 index 對齊主圖 x-axis，
  // 少一列就會讓後面所有日期跟主圖錯位（十字線指到錯誤的日期）。
  return [...rows].reverse().map((r) => ({
    date: r.date,
    marginBalance: r.margin_amount_100m,
    marginRatio: r.margin_maintenance_ratio,
    cleanupIndex: r.chip_washout,
  }))
}
