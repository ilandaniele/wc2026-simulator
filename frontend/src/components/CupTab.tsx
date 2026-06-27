import { useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { simulateTournament, type SimulationResult } from '../api/client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type SortKey = keyof SimulationResult
type SortDir = 'asc' | 'desc'

// 8-column definition matching spec
const TABLE_COLS: Array<{ key: SortKey; label: string; pct?: boolean }> = [
  { key: 'team', label: 'Equipo' },
  { key: 'group', label: 'Grupo' },
  { key: 'ko', label: 'R32', pct: true },
  { key: 'r16', label: 'R16', pct: true },
  { key: 'qf', label: 'QF', pct: true },
  { key: 'sf', label: 'SF', pct: true },
  { key: 'final', label: 'Final', pct: true },
  { key: 'champ', label: 'Campeón', pct: true },
]

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function fmt(v: number): string {
  return (v * 100).toFixed(1) + '%'
}

function champColor(champ: number): string {
  if (champ > 0.15) return 'var(--violet)'
  if (champ > 0.08) return 'color-mix(in srgb, var(--violet) 70%, transparent)'
  if (champ > 0.03) return 'color-mix(in srgb, var(--violet) 40%, transparent)'
  return 'transparent'
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------
function Skeleton() {
  return (
    <div aria-busy="true" aria-label="Cargando datos del torneo">
      <div
        style={{
          height: '2rem',
          width: '60%',
          background: 'var(--line)',
          borderRadius: '4px',
          marginBottom: '1rem',
        }}
      />
      {Array.from({ length: 8 }).map((_, i) => (
        <div
          key={i}
          style={{
            height: '2rem',
            background: 'var(--line)',
            borderRadius: '4px',
            marginBottom: '0.5rem',
            opacity: 1 - i * 0.1,
          }}
        />
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// CupTab
// ---------------------------------------------------------------------------
export function CupTab() {
  const [sortKey, setSortKey] = useState<SortKey>('champ')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['tournament', 2500, 0.05],
    queryFn: () =>
      simulateTournament({ n: 2500, rho: 0.05, model_id: 'current' }),
    staleTime: 5 * 60_000,
  })

  const handleSort = useCallback(
    (key: SortKey) => {
      if (key === sortKey) {
        setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
      } else {
        setSortKey(key)
        setSortDir('desc')
      }
    },
    [sortKey],
  )

  if (isLoading) return <Skeleton />

  if (isError) {
    const msg =
      error instanceof Error ? error.message : 'Error al cargar los datos'
    return (
      <div role="alert" style={{ padding: '1rem' }}>
        <div
          style={{
            background: 'color-mix(in srgb, var(--red) 15%, var(--card))',
            border: '1px solid var(--red)',
            borderRadius: '8px',
            padding: '1rem 1.25rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
          }}
        >
          <span style={{ color: 'var(--red)', fontWeight: 500 }}>
            Error al cargar datos del torneo
          </span>
          <button
            type="button"
            onClick={() => void refetch()}
            style={{
              padding: '0.375rem 0.875rem',
              background: 'var(--red)',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontWeight: 500,
            }}
          >
            Reintentar
          </button>
        </div>
        <p
          style={{
            color: 'var(--dim)',
            fontSize: '0.8125rem',
            marginTop: '0.5rem',
          }}
        >
          {msg}
        </p>
      </div>
    )
  }

  const results = data?.results ?? []
  const sorted = [...results].sort((a, b) => {
    const av = a[sortKey]
    const bv = b[sortKey]
    const cmp =
      typeof av === 'string' && typeof bv === 'string'
        ? av.localeCompare(bv)
        : (av as number) - (bv as number)
    return sortDir === 'asc' ? cmp : -cmp
  })

  const arrow = (key: SortKey) =>
    key === sortKey ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''

  return (
    <div style={{ overflowX: 'auto' }}>
      <table
        data-testid="cup-table"
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: '0.875rem',
        }}
      >
        <thead>
          <tr style={{ borderBottom: '2px solid var(--line)' }}>
            <th
              style={{
                padding: '0.5rem 0.75rem',
                textAlign: 'left',
                color: 'var(--dim)',
                fontWeight: 600,
                fontSize: '0.75rem',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                width: '2rem',
              }}
            >
              #
            </th>
            {TABLE_COLS.map((col) => (
              <th
                key={col.key}
                onClick={() => handleSort(col.key)}
                style={{
                  padding: '0.5rem 0.75rem',
                  textAlign: col.pct ? 'right' : 'left',
                  color: sortKey === col.key ? 'var(--violet)' : 'var(--dim)',
                  fontWeight: 600,
                  fontSize: '0.75rem',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  cursor: 'pointer',
                  userSelect: 'none',
                  whiteSpace: 'nowrap',
                }}
              >
                {col.label}
                {arrow(col.key)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, idx) => (
            <tr
              key={row.team}
              style={{
                borderBottom: '1px solid var(--line)',
                background: champColor(row.champ),
              }}
            >
              <td
                style={{
                  padding: '0.5rem 0.75rem',
                  color: 'var(--dim)',
                  fontSize: '0.8125rem',
                }}
              >
                {idx + 1}
              </td>
              {TABLE_COLS.map((col) => {
                const val = row[col.key]
                return (
                  <td
                    key={col.key}
                    style={{
                      padding: '0.5rem 0.75rem',
                      textAlign: col.pct ? 'right' : 'left',
                      color: 'var(--txt)',
                      fontWeight: col.key === 'team' ? 500 : 400,
                    }}
                  >
                    {col.pct ? fmt(val as number) : String(val)}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
