import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type BarShapeProps,
  type TooltipContentProps,
} from 'recharts'
import {
  categoryMix,
  channels,
  currentFiscalYear,
  fiscalYearBounds,
  inventory,
  isPartialYear,
  salesTrend,
  scorecard,
  stockPools,
  yearLabel,
} from '../data'
import { count, days, money, moneyFull, monthLabel, pct, shortMonth, signedPct } from '../format'
import type { ChartTheme } from '../theme'
import { ChartCard, LegendItem } from './ChartCard'
import { TooltipCard } from './ChartTooltip'

/** "FY2027 YTD" -> "FY27 YTD" so six years fit on a phone-width axis. */
const shortYear = (label: string) => label.replace('FY20', 'FY')

const axisTick = (theme: ChartTheme) => ({ fill: theme.muted, fontSize: 12 })

/** A column whose data end is rounded (6px) and whose baseline end is square, for either sign. */
function RoundedColumn(props: BarShapeProps) {
  const { x, y, width, height, fill, fillOpacity } = props
  if (!height || !width) return null
  const top = Math.min(y, y + height)
  const h = Math.abs(height)
  const r = Math.min(6, h, width / 2)
  const value = Number((props.payload as { value?: number } | undefined)?.value ?? props.value ?? 0)
  const d =
    value >= 0
      ? `M${x},${top + h} V${top + r} Q${x},${top} ${x + r},${top} H${x + width - r} Q${x + width},${top} ${x + width},${top + r} V${top + h} Z`
      : `M${x},${top} V${top + h - r} Q${x},${top + h} ${x + r},${top + h} H${x + width - r} Q${x + width},${top + h} ${x + width},${top + h - r} V${top} Z`
  return <path d={d} fill={fill} fillOpacity={fillOpacity} />
}

/** A horizontal bar, rounded at the data end (right) and square at the baseline (left). */
function RoundedBar(props: BarShapeProps) {
  const { x, y, width, height, fill } = props
  if (!height || !width) return null
  const r = Math.min(6, width, height / 2)
  const d = `M${x},${y} H${x + width - r} Q${x + width},${y} ${x + width},${y + r} V${y + height - r} Q${x + width},${y + height} ${x + width - r},${y + height} H${x} Z`
  return <path d={d} fill={fill} />
}

// ---------------------------------------------------------------------------------------------
// Comp store sales growth by fiscal year
// ---------------------------------------------------------------------------------------------

export function CompGrowthChart({ theme, selected }: { theme: ChartTheme; selected: string }) {
  const rows = scorecard
    .filter((r) => r.comp_store_sales_growth != null)
    .map((r) => ({ fy: r.fiscal_year, label: yearLabel(r.fiscal_year), value: r.comp_store_sales_growth as number }))

  // Clean 5-point ticks that cover every bar.
  const lo = Math.min(0, ...rows.map((r) => r.value))
  const hi = Math.max(0, ...rows.map((r) => r.value))
  const compTicks: number[] = []
  for (let t = Math.floor(lo / 0.05) * 0.05; t <= Math.ceil(hi / 0.05) * 0.05 + 1e-9; t += 0.05) {
    compTicks.push(Math.round(t * 100) / 100)
  }

  return (
    <ChartCard
      title="Comp store sales growth"
      subtitle="Boutiques open 13+ full fiscal months, same days as last year. Online is excluded."
      metricNames={['comp_store_sales_growth']}
      table={{
        columns: ['Fiscal year', 'Comp store sales growth', 'Comp sales growth (all channels)'],
        rows: scorecard
          .filter((r) => r.comp_store_sales_growth != null)
          .map((r) => [yearLabel(r.fiscal_year), signedPct(r.comp_store_sales_growth!), signedPct(r.comp_sales_growth!)]),
      }}
    >
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={rows} margin={{ top: 24, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke={theme.grid} />
          <XAxis dataKey="label" tickFormatter={shortYear} tickLine={false} axisLine={false} tick={axisTick(theme)} interval={0} />
          <YAxis
            ticks={compTicks}
            domain={[compTicks[0], compTicks.at(-1)!]}
            tickFormatter={(v: number) => signedPct(v, 0)}
            tickLine={false}
            axisLine={false}
            tick={axisTick(theme)}
            width={48}
          />
          <ReferenceLine y={0} stroke={theme.axis} />
          <Tooltip
            cursor={{ fill: theme.highlightWash }}
            content={(p: TooltipContentProps) =>
              p.active && p.payload?.length ? (
                <TooltipCard
                  title={String(p.label)}
                  rows={[{ label: 'Comp store sales growth', value: signedPct(Number(p.payload[0].value)) }]}
                />
              ) : null
            }
          />
          <Bar dataKey="value" maxBarSize={24} shape={RoundedColumn} isAnimationActive={false}>
            {rows.map((r) => (
              <Cell
                key={r.fy}
                fill={r.value >= 0 ? theme.positive : theme.negative}
                fillOpacity={r.fy === selected ? 1 : 0.35}
              />
            ))}
            <LabelList
              dataKey="value"
              position="top"
              content={(p) => {
                const { x, y, width, height, value, index } = p as {
                  x: number; y: number; width: number; height: number; value: number; index: number
                }
                if (rows[index]?.fy !== selected) return null
                const below = value < 0
                return (
                  <text
                    x={x + width / 2}
                    y={below ? y + height + 16 : y - 8}
                    textAnchor="middle"
                    fill={theme.ink}
                    fontSize={13}
                    fontWeight={500}
                  >
                    {signedPct(value)}
                  </text>
                )
              }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

// ---------------------------------------------------------------------------------------------
// Monthly net sales by channel
// ---------------------------------------------------------------------------------------------

export function SalesTrendChart({ theme, selected }: { theme: ChartTheme; selected: string }) {
  const byMonth = new Map<string, { month: string; Store: number; Online: number }>()
  for (const r of salesTrend) {
    const row = byMonth.get(r.month) ?? { month: r.month, Store: 0, Online: 0 }
    row[r.channel as 'Store' | 'Online'] = r.net_sales
    byMonth.set(r.month, row)
  }
  const rows = [...byMonth.values()]
  const { start, end } = fiscalYearBounds(selected)
  const inYear = rows.filter((r) => r.month >= start && r.month <= end)
  const colors = { Store: theme.series[0], Online: theme.series[1] }
  const lastMonth = rows.at(-1)?.month ?? ''

  return (
    <ChartCard
      title="Net sales by month"
      subtitle={
        <>
          Boutiques and online, stacked. {yearLabel(selected)} is shaded.
          {isPartialYear(selected) && ` ${monthLabel(lastMonth)} is month to date.`}
        </>
      }
      metricNames={['net_sales']}
      className="span-2"
      legend={channels.map((c) => <LegendItem key={c} color={colors[c]} label={c === 'Store' ? 'Boutiques' : 'Online'} />)}
      table={{
        columns: ['Month', 'Boutiques', 'Online', 'Total'],
        rows: [...rows].reverse().map((r) => [monthLabel(r.month), moneyFull(r.Store), moneyFull(r.Online), moneyFull(r.Store + r.Online)]),
      }}
    >
      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke={theme.grid} />
          {inYear.length > 0 && (
            <ReferenceArea x1={inYear[0].month} x2={inYear.at(-1)!.month} fill={theme.highlightWash} fillOpacity={1} />
          )}
          <XAxis
            dataKey="month"
            tickFormatter={shortMonth}
            tickLine={false}
            axisLine={{ stroke: theme.axis }}
            tick={axisTick(theme)}
            minTickGap={32}
          />
          <YAxis tickFormatter={money} tickLine={false} axisLine={false} tick={axisTick(theme)} width={56} />
          <Tooltip
            cursor={{ stroke: theme.muted, strokeWidth: 1 }}
            content={(p: TooltipContentProps) => {
              if (!p.active || !p.payload?.length) return null
              const row = p.payload[0].payload as { month: string; Store: number; Online: number }
              return (
                <TooltipCard
                  title={monthLabel(row.month)}
                  rows={[
                    { label: 'Total', value: moneyFull(row.Store + row.Online) },
                    { label: 'Boutiques', value: moneyFull(row.Store), color: colors.Store },
                    { label: 'Online', value: moneyFull(row.Online), color: colors.Online },
                  ]}
                />
              )
            }}
          />
          {channels.map((c) => (
            <Area
              key={c}
              type="monotone"
              dataKey={c}
              stackId="sales"
              stroke={colors[c]}
              strokeWidth={2}
              fill={colors[c]}
              fillOpacity={0.12}
              activeDot={{ r: 4, stroke: theme.surface, strokeWidth: 2 }}
              isAnimationActive={false}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

// ---------------------------------------------------------------------------------------------
// Sell-through by boutique
// ---------------------------------------------------------------------------------------------

export function SellThroughChart({ theme, selected }: { theme: ChartTheme; selected: string }) {
  // The first fiscal year holds one month of history, so it is left off. The current year stays in,
  // flagged as year to date.
  const years = [...new Set(inventory.map((r) => r.fiscal_year))]
    .sort()
    .filter((fy) => !isPartialYear(fy) || fy === currentFiscalYear)
  const rows = years.map((fy) => {
    const row: Record<string, string | number> = { fy, label: yearLabel(fy) }
    for (const r of inventory.filter((i) => i.fiscal_year === fy)) row[r.stock_pool] = r.sell_through_rate
    return row
  })
  const colorOf = (pool: string) => theme.series[stockPools.indexOf(pool)]
  const selectedLabel = yearLabel(selected)

  return (
    <ChartCard
      title="Sell-through by boutique"
      subtitle={
        <>
          Units sold ÷ (opening stock + units received). Online orders ship from New York stock.
          {isPartialYear(currentFiscalYear) &&
            ` ${yearLabel(currentFiscalYear)} covers a shorter window, so it runs below full years.`}
        </>
      }
      metricNames={['sell_through_rate']}
      legend={stockPools.map((p) => <LegendItem key={p} color={colorOf(p)} label={p} shape="line" />)}
      table={{
        columns: ['Fiscal year', ...stockPools],
        rows: rows.map((r) => [String(r.label), ...stockPools.map((p) => pct(Number(r[p])))]),
      }}
    >
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={rows} margin={{ top: 8, right: 36, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke={theme.grid} />
          <ReferenceLine x={selectedLabel} stroke={theme.axis} />
          <XAxis dataKey="label" tickFormatter={shortYear} tickLine={false} axisLine={{ stroke: theme.axis }} tick={axisTick(theme)} interval={0} />
          <YAxis
            domain={[0.7, 1]}
            ticks={[0.7, 0.8, 0.9, 1]}
            tickFormatter={(v: number) => pct(v, 0)}
            tickLine={false}
            axisLine={false}
            tick={axisTick(theme)}
            width={44}
          />
          <Tooltip
            cursor={{ stroke: theme.muted, strokeWidth: 1 }}
            content={(p: TooltipContentProps) =>
              p.active && p.payload?.length ? (
                <TooltipCard
                  title={String(p.label)}
                  rows={stockPools.map((pool) => ({
                    label: pool,
                    color: colorOf(pool),
                    value: pct(Number((p.payload[0].payload as Record<string, number>)[pool])),
                  }))}
                />
              ) : null
            }
          />
          {stockPools.map((pool) => (
            <Line
              key={pool}
              dataKey={pool}
              stroke={colorOf(pool)}
              strokeWidth={2}
              dot={{ r: 4, fill: colorOf(pool), stroke: theme.surface, strokeWidth: 2 }}
              activeDot={{ r: 5, stroke: theme.surface, strokeWidth: 2 }}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

// ---------------------------------------------------------------------------------------------
// Category mix for the selected year
// ---------------------------------------------------------------------------------------------

export function CategoryMixChart({ theme, selected }: { theme: ChartTheme; selected: string }) {
  const rows = categoryMix
    .filter((r) => r.fiscal_year === selected)
    .sort((a, b) => b.net_sales - a.net_sales)
  const total = rows.reduce((s, r) => s + r.net_sales, 0)

  return (
    <ChartCard
      title={`Net sales by model, ${yearLabel(selected)}`}
      subtitle="Ranked by net sales. Hover a bar for units, margin and days to sell."
      metricNames={['net_sales', 'gross_margin_pct', 'average_days_to_sell']}
      table={{
        columns: ['Model', 'Net sales', 'Share', 'Units', 'Gross margin %', 'Avg days to sell'],
        rows: rows.map((r) => [
          r.model_category,
          moneyFull(r.net_sales),
          pct(r.net_sales / total),
          count(r.units_sold),
          pct(r.gross_margin_pct),
          r.average_days_to_sell.toFixed(1),
        ]),
      }}
    >
      <ResponsiveContainer width="100%" height={Math.max(220, rows.length * 34)}>
        <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 56, bottom: 0, left: 0 }} barCategoryGap={8}>
          <XAxis type="number" hide />
          <YAxis
            type="category"
            dataKey="model_category"
            tickLine={false}
            axisLine={false}
            tick={{ fill: theme.inkSecondary, fontSize: 13 }}
            width={104}
          />
          <Tooltip
            cursor={{ fill: theme.highlightWash }}
            content={(p: TooltipContentProps) => {
              if (!p.active || !p.payload?.length) return null
              const r = p.payload[0].payload as (typeof rows)[number]
              return (
                <TooltipCard
                  title={r.model_category}
                  rows={[
                    { label: `net sales · ${pct(r.net_sales / total)} of total`, value: moneyFull(r.net_sales) },
                    { label: 'units', value: count(r.units_sold) },
                    { label: 'gross margin', value: pct(r.gross_margin_pct) },
                    { label: 'to sell, on average', value: days(r.average_days_to_sell) },
                  ]}
                />
              )
            }}
          />
          <Bar dataKey="net_sales" fill={theme.series[0]} maxBarSize={20} shape={RoundedBar} isAnimationActive={false}>
            <LabelList
              dataKey="net_sales"
              position="right"
              formatter={(v) => money(Number(v))}
              style={{ fill: theme.inkSecondary, fontSize: 12 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}
