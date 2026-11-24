export interface Delta {
  text: string
  /** Whether this change is good news. Decides the color; the arrow shows the direction. */
  good: boolean
  direction: 'up' | 'down' | 'flat'
  versus: string
}

/** Build a delta from two values. `kind` decides how the change is written. */
export function makeDelta(
  current: number | null | undefined,
  previous: number | null | undefined,
  versus: string,
  kind: 'relative' | 'points' | 'days',
  higherIsBetter = true,
): Delta | undefined {
  if (current == null || previous == null || previous === 0) return undefined
  const change = kind === 'relative' ? current / previous - 1 : current - previous
  // Compare at display precision so a change that prints as 0.0 shows as flat, not up or down.
  const rounded = kind === 'days' ? Math.round(change * 10) / 10 : Math.round(change * 1000) / 1000
  const direction = rounded > 0 ? 'up' : rounded < 0 ? 'down' : 'flat'
  const sign = rounded > 0 ? '+' : rounded < 0 ? '−' : ''
  const text =
    kind === 'relative'
      ? `${sign}${Math.abs(change * 100).toFixed(1)}%`
      : kind === 'points'
        ? `${sign}${Math.abs(change * 100).toFixed(1)} pts`
        : `${sign}${Math.abs(change).toFixed(1)} days`
  return { text, direction, good: higherIsBetter ? change > 0 : change < 0, versus }
}
