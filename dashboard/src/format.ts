const compactCurrency = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  notation: 'compact',
  maximumFractionDigits: 1,
})
const wholeCurrency = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
})
const integer = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })
const oneDecimal = new Intl.NumberFormat('en-US', { maximumFractionDigits: 1, minimumFractionDigits: 1 })

export const money = (v: number) => compactCurrency.format(v)
export const moneyFull = (v: number) => wholeCurrency.format(v)
export const count = (v: number) => integer.format(v)
export const days = (v: number) => `${oneDecimal.format(v)} days`

/** 0.39525 -> "39.5%" */
export const pct = (v: number, digits = 1) => `${(v * 100).toFixed(digits)}%`

/** 0.0629 -> "+6.29%"; growth figures always carry a sign. */
export const signedPct = (v: number, digits = 2) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v * 100).toFixed(digits)}%`

/** A change in a rate, in percentage points: 0.012 -> "+1.2 pts" */
export const pts = (v: number) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v * 100).toFixed(1)} pts`

export const monthLabel = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString('en-US', { month: 'short', year: 'numeric' })

export const shortMonth = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString('en-US', { month: 'short', year: '2-digit' })

export const longDate = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
