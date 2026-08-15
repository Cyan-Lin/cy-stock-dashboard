// Mock data for UI prototype — replace with real API responses

export type Timeframe = 'D' | 'W' | 'M'
export type Symbol = 'TWII' | 'TPEx'

export interface OHLCBar {
  date: string   // 'YYYY-MM-DD'
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface MarginBar {
  date: string
  marginBalance: number   // 融資餘額（億）
  marginRatio: number     // 融資維持率（%）
  cleanupIndex: number    // 籌碼洗淨指標
}

export interface SecondPanelBar {
  date: string
  shortLongRatio: number  // 資券比（%）
  kValue?: number         // KD K值（月K 專用）
  dValue?: number         // KD D值（月K 專用）
}

function seedRand(seed: number) {
  let s = seed
  return () => {
    s = (s * 1664525 + 1013904223) & 0xffffffff
    return (s >>> 0) / 0xffffffff
  }
}

function generateBars(count: number, basePrice: number, seed = 42): OHLCBar[] {
  const r = seedRand(seed)
  const bars: OHLCBar[] = []
  let price = basePrice
  const startDate = new Date('2023-01-02')

  for (let i = 0; i < count; i++) {
    const d = new Date(startDate)
    d.setDate(startDate.getDate() + i)
    const change = (r() - 0.5) * 200
    const open = price
    const close = price + change
    const high = Math.max(open, close) + r() * 100
    const low = Math.min(open, close) - r() * 100
    bars.push({
      date: d.toISOString().slice(0, 10),
      open: Math.round(open),
      high: Math.round(high),
      low: Math.round(low),
      close: Math.round(close),
      volume: Math.floor(r() * 5e9 + 1e9),
    })
    price = close
  }
  return bars
}

function generateMargin(dates: string[], seed = 99): MarginBar[] {
  const r = seedRand(seed)
  let balance = 2200
  return dates.map((date) => {
    balance += (r() - 0.5) * 80
    return {
      date,
      marginBalance: Math.max(800, Math.round(balance * 10) / 10),
      marginRatio: Math.round((155 + (r() - 0.5) * 30) * 10) / 10,
      cleanupIndex: Math.round((r() - 0.5) * 20 * 100) / 100,
    }
  })
}

function generateSecondPanel(dates: string[], includeKD: boolean, seed = 77): SecondPanelBar[] {
  const r = seedRand(seed)
  let k = 50
  return dates.map((date) => {
    const d = (r() - 0.5) * 10
    k = Math.min(100, Math.max(0, k + d))
    return {
      date,
      shortLongRatio: Math.round((8 + (r() - 0.5) * 6) * 10) / 10,
      ...(includeKD ? { kValue: Math.round(k * 10) / 10, dValue: Math.round((k - r() * 5) * 10) / 10 } : {}),
    }
  })
}

const twiiDailyBars = generateBars(300, 17500, 11)
const tpexDailyBars = generateBars(300, 200, 22)

export function getMockPriceBars(symbol: Symbol, _timeframe: Timeframe): OHLCBar[] {
  return symbol === 'TWII' ? twiiDailyBars : tpexDailyBars
}

export function getMockMargin(symbol: Symbol): MarginBar[] {
  const bars = getMockPriceBars(symbol, 'D')
  return generateMargin(bars.map(b => b.date), symbol === 'TWII' ? 99 : 88)
}

export function getMockSecondPanel(symbol: Symbol, timeframe: Timeframe): SecondPanelBar[] {
  const bars = getMockPriceBars(symbol, timeframe)
  return generateSecondPanel(bars.map(b => b.date), timeframe === 'M', symbol === 'TWII' ? 77 : 66)
}
