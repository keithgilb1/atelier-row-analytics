import { useSyncExternalStore } from 'react'

// Chart colors from the Atelier Row Design System. SVG chart marks need concrete colors, so the
// light and dark sets live here and the rest of the page uses the matching CSS custom properties in
// index.css. The design system has one accent (Bleu Nuit) and a quiet brass, so the three categorical
// slots are Bleu Nuit, brass and a lighter steel blue: they step apart in lightness as well as hue, so
// they stay distinct without color vision. An entity keeps its slot everywhere: Store (and Los Angeles)
// is slot 1, Online (and Miami) slot 2, New York City slot 3.
//
// The design system ships a light theme only. The dark set is built from its ink ramp, with lighter
// steps of the same hues (nuit-400, brass-300, oxblood-300) derived so marks keep their contrast.
const light = {
  surface: '#FAFBFB', // porcelain-0
  ink: '#14171A', // ink-900
  inkSecondary: '#58626A', // slate-600
  muted: '#58626A', // slate-600 (slate-500 is below 4.5:1 at tick sizes)
  grid: '#E8ECED', // mist-100
  axis: '#A0A9AF', // platinum-400
  series: ['#2C3B4F', '#85703F', '#7C92AA'], // nuit-500, brass-600, nuit-400
  positive: '#2C3B4F', // nuit-500
  negative: '#7A2E37', // oxblood-600
  highlightWash: 'rgba(44, 59, 79, 0.06)', // nuit-500 at 6%
}

const dark: typeof light = {
  surface: '#1E2226',
  ink: '#FAFBFB', // porcelain-0
  inkSecondary: '#C1C8CC', // platinum-300
  muted: '#A0A9AF', // platinum-400
  grid: '#2E3439',
  axis: '#58626A', // slate-600
  series: ['#CAD7DF', '#C9AE6E', '#7C92AA'], // glacier-200, brass-300, nuit-400
  positive: '#CAD7DF', // glacier-200
  negative: '#D58A93', // oxblood-300
  highlightWash: 'rgba(202, 215, 223, 0.07)', // glacier-200 at 7%
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
