import { useSyncExternalStore } from 'react'

// Chart colors. SVG chart marks need concrete colors, so the light and dark sets live here and the
// rest of the page uses the matching CSS custom properties in index.css. The categorical slots are
// a colorblind-safe order (validated for any pair of the first three slots in both modes), and an
// entity keeps its slot everywhere: Store is always slot 1, Online slot 2, and each boutique has
// its own slot.
const light = {
  surface: '#fcfcfb',
  ink: '#0b0b0b',
  inkSecondary: '#52514e',
  muted: '#898781',
  grid: '#e1e0d9',
  axis: '#c3c2b7',
  series: ['#2a78d6', '#eb6834', '#1baf7a'],
  positive: '#2a78d6',
  negative: '#e34948',
  highlightWash: 'rgba(42, 120, 214, 0.07)',
}

const dark: typeof light = {
  surface: '#1a1a19',
  ink: '#f0efec',
  inkSecondary: '#c3c2b7',
  muted: '#898781',
  grid: '#2c2c2a',
  axis: '#383835',
  series: ['#3987e5', '#d95926', '#199e70'],
  positive: '#3987e5',
  negative: '#e66767',
  highlightWash: 'rgba(57, 135, 229, 0.12)',
}

export type ChartTheme = typeof light

const query = '(prefers-color-scheme: dark)'

function subscribe(onChange: () => void) {
  const mql = window.matchMedia(query)
  mql.addEventListener('change', onChange)
  return () => mql.removeEventListener('change', onChange)
}

export function useChartTheme(): ChartTheme {
  const isDark = useSyncExternalStore(subscribe, () => window.matchMedia(query).matches, () => false)
  return isDark ? dark : light
}
