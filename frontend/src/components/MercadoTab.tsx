import { useQueries, useQuery } from '@tanstack/react-query'
import { getMarketOdds, simulateMatch, type MarketOddsEntry } from '../api/client'

// ---------------------------------------------------------------------------
// De-vig helpers (American odds → implied prob → normalised)
// ---------------------------------------------------------------------------

/** American odds → raw implied probability */
function americanToImplied(american: number): number {
  if (american > 0) return 100 / (american + 100)
  return Math.abs(american) / (Math.abs(american) + 100)
}

/** De-vig: normalise three implied probs to sum to 1.0 */
function devig(h: number, d: number | null, a: number): [number, number | null, number] {
  const pH = americanToImplied(h)
  const pA = americanToImplied(a)

  if (d === null) {
    const total = pH + pA
    return [pH / total, null, pA / total]
  }

  const pD = americanToImplied(d)
  const total = pH + pD + pA
  return [pH / total, pD / total, pA / total]
}

// ---------------------------------------------------------------------------
// Edge cell
// ---------------------------------------------------------------------------
interface EdgeCellProps {
  edge: number
}

function EdgeCell({ edge }: EdgeCellProps) {
  const pp = edge * 100
  const color =
    pp > 2 ? 'var(--green)' : pp < -2 ? 'var(--red)' : 'var(--txt)'
  const bg =
    pp > 2
      ? 'color-mix(in srgb, var(--green) 12%, transparent)'
      : pp < -2
        ? 'color-mix(in srgb, var(--red) 12%, transparent)'
        : 'transparent'

  return (
    <td
      style={{
        padding: '0.5rem 0.75rem',
        textAlign: 'right',
        color,
        background: bg,
        fontWeight: Math.abs(pp) > 2 ? 600 : 400,
        fontSize: '0.875rem',
      }}
    >
      {pp > 0 ? '+' : ''}
      {pp.toFixed(1)}pp
    </td>
  )
}

// ---------------------------------------------------------------------------
// Match edge table
// ---------------------------------------------------------------------------
interface MatchEdgeProps {
  entry: MarketOddsEntry
}

function MatchEdgeTable({ entry }: MatchEdgeProps) {
  const { data: matchData, isLoading } = useQuery({
    queryKey: ['match', entry.home, entry.away],
    queryFn: () =>
      simulateMatch({ home: entry.home, away: entry.away, n_per_draw: 30, rho: 0.05 }),
    staleTime: 5 * 60_000,
  })

  const [mktH, mktD, mktA] = devig(entry.h, entry.d, entry.a)

  const rows: Array<{
    label: string
    model: number | null
    market: number | null
    edge: number | null
  }> = [
    {
      label: entry.home,
      model: matchData?.pH ?? null,
      market: mktH,
      edge: matchData ? matchData.pH - mktH : null,
    },
    {
      label: 'Empate',
      model: matchData?.pD ?? null,
      market: mktD,
      edge: matchData && mktD !== null ? matchData.pD - mktD : null,
    },
    {
      label: entry.away,
      model: matchData?.pA ?? null,
      market: mktA,
      edge: matchData ? matchData.pA - mktA : null,
    },
  ].filter((r) => r.market !== null)

  return (
    <div
      style={{
        background: 'var(--card)',
        border: '1px solid var(--line)',
        borderRadius: '10px',
        overflow: 'hidden',
        marginBottom: '1.25rem',
      }}
    >
      {/* Match header */}
      <div
        style={{
          padding: '0.75rem 1rem',
          borderBottom: '1px solid var(--line)',
          fontWeight: 600,
          fontSize: '0.9375rem',
          color: 'var(--txt)',
        }}
      >
        {entry.home}{' '}
        <span style={{ color: 'var(--dim)', fontWeight: 400 }}>vs</span>{' '}
        {entry.away}
      </div>

      {/* Table */}
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--line)' }}>
            {['Resultado', 'Modelo %', 'Mercado %', 'Edge (pp)'].map((h) => (
              <th
                key={h}
                style={{
                  padding: '0.5rem 0.75rem',
                  textAlign: h === 'Resultado' ? 'left' : 'right',
                  color: 'var(--dim)',
                  fontWeight: 600,
                  fontSize: '0.75rem',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {isLoading
            ? [0, 1, 2].map((i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--line)' }}>
                  {[0, 1, 2, 3].map((j) => (
                    <td key={j} style={{ padding: '0.5rem 0.75rem' }}>
                      <div
                        style={{
                          height: '1rem',
                          background: 'var(--line)',
                          borderRadius: '4px',
                        }}
                      />
                    </td>
                  ))}
                </tr>
              ))
            : rows.map((row) => (
                <tr
                  key={row.label}
                  style={{ borderBottom: '1px solid var(--line)' }}
                >
                  <td
                    style={{
                      padding: '0.5rem 0.75rem',
                      fontWeight: 500,
                      color: 'var(--txt)',
                    }}
                  >
                    {row.label}
                  </td>
                  <td
                    style={{
                      padding: '0.5rem 0.75rem',
                      textAlign: 'right',
                      color: 'var(--txt)',
                    }}
                  >
                    {row.model !== null ? (row.model * 100).toFixed(1) + '%' : '—'}
                  </td>
                  <td
                    style={{
                      padding: '0.5rem 0.75rem',
                      textAlign: 'right',
                      color: 'var(--txt)',
                    }}
                  >
                    {row.market !== null ? (row.market * 100).toFixed(1) + '%' : '—'}
                  </td>
                  {row.edge !== null ? (
                    <EdgeCell edge={row.edge} />
                  ) : (
                    <td
                      style={{
                        padding: '0.5rem 0.75rem',
                        textAlign: 'right',
                        color: 'var(--dim)',
                      }}
                    >
                      —
                    </td>
                  )}
                </tr>
              ))}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// MercadoTab
// ---------------------------------------------------------------------------
export function MercadoTab() {
  const { data: oddsData, isLoading, isError } = useQuery({
    queryKey: ['market-odds'],
    queryFn: getMarketOdds,
    staleTime: 5 * 60_000,
  })

  // Prefetch match simulations — but we can defer to MatchEdgeTable
  useQueries({
    queries: (oddsData?.odds ?? []).map((entry) => ({
      queryKey: ['match', entry.home, entry.away],
      queryFn: () =>
        simulateMatch({ home: entry.home, away: entry.away, n_per_draw: 30, rho: 0.05 }),
      staleTime: 5 * 60_000,
      enabled: !!oddsData,
    })),
  })

  if (isLoading) {
    return (
      <div aria-busy="true" aria-label="Cargando cuotas de mercado">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            style={{
              height: '160px',
              background: 'var(--card)',
              border: '1px solid var(--line)',
              borderRadius: '10px',
              marginBottom: '1.25rem',
            }}
          />
        ))}
      </div>
    )
  }

  if (isError) {
    return (
      <div role="alert" style={{ color: 'var(--red)', padding: '1rem' }}>
        Error al cargar las cuotas de mercado
      </div>
    )
  }

  const entries = oddsData?.odds ?? []

  return (
    <div>
      <h2
        style={{
          fontSize: '1rem',
          fontWeight: 600,
          color: 'var(--txt)',
          marginBottom: '1rem',
          marginTop: 0,
        }}
      >
        Modelo vs Mercado
      </h2>
      {entries.map((entry) => (
        <MatchEdgeTable key={`${entry.home}-${entry.away}`} entry={entry} />
      ))}
    </div>
  )
}
