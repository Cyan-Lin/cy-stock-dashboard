import type { Symbol, Timeframe } from '../data/mockData'

interface TopBarProps {
  symbol: Symbol
  timeframe: Timeframe
  onSymbolChange: (s: Symbol) => void
  onTimeframeChange: (t: Timeframe) => void
  lastPrice: number
  change: number
  changePct: number
}

const SYMBOLS: Symbol[] = ['TWII', 'TPEx']
const TIMEFRAMES: { value: Timeframe; label: string }[] = [
  { value: 'D', label: '日K' },
  { value: 'W', label: '週K' },
  { value: 'M', label: '月K' },
]

const SYMBOL_LABELS: Record<Symbol, string> = {
  TWII: '台股加權',
  TPEx: '上櫃指數',
}

export default function TopBar({
  symbol,
  timeframe,
  onSymbolChange,
  onTimeframeChange,
  lastPrice,
  change,
  changePct,
}: TopBarProps) {
  const isUp = change >= 0

  const priceNode = (
    <div className="flex items-baseline gap-2">
      <span className="text-base font-bold" style={{ color: 'var(--color-foreground)' }}>
        {lastPrice.toLocaleString()}
      </span>
      <span
        className="text-xs font-semibold"
        style={{ color: isUp ? 'var(--color-accent)' : 'var(--color-destructive)' }}
      >
        {isUp ? '+' : ''}{change.toFixed(0)} ({isUp ? '+' : ''}{changePct.toFixed(2)}%)
      </span>
    </div>
  )

  return (
    <header
      className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 border-b shrink-0"
      style={{
        background: 'var(--color-primary)',
        borderColor: 'var(--color-border)',
      }}
    >
      {/* Symbol selector */}
      <div className="flex gap-1">
        {SYMBOLS.map((s) => (
          <button
            key={s}
            onClick={() => onSymbolChange(s)}
            className="px-3 py-1 rounded text-xs font-semibold transition-colors duration-150 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#22C55E] focus-visible:ring-offset-1 focus-visible:ring-offset-[#0F172A]"
            style={{
              background: symbol === s ? 'var(--color-accent)' : 'var(--color-secondary)',
              color: symbol === s ? '#000' : 'var(--color-foreground)',
            }}
          >
            {SYMBOL_LABELS[s]}
          </button>
        ))}
      </div>

      {/* Divider + Price — sm (640px)+ only, inline with symbol */}
      <div className="hidden sm:block w-px h-5 opacity-30" style={{ background: 'var(--color-border)' }} />
      <div className="hidden sm:flex">{priceNode}</div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Timeframe selector */}
      <div className="flex gap-1">
        {TIMEFRAMES.map(({ value, label }) => (
          <button
            key={value}
            onClick={() => onTimeframeChange(value)}
            className="px-2 py-1 rounded text-xs font-medium transition-colors duration-150 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#22C55E] focus-visible:ring-offset-1 focus-visible:ring-offset-[#0F172A]"
            style={{
              background: timeframe === value ? 'var(--color-secondary)' : 'transparent',
              color: timeframe === value ? 'var(--color-accent)' : 'var(--color-foreground)',
              border: `1px solid ${timeframe === value ? 'var(--color-border)' : 'transparent'}`,
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Price — mobile only, wraps to second row */}
      <div className="flex sm:hidden w-full">{priceNode}</div>
    </header>
  )
}
