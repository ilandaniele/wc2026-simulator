import { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient, useQueries } from '@tanstack/react-query'
import { simulateTournament, getR32, putR32Result, simulateModal, type SimulationResult, type R32Match, type Scoreline } from '../api/client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type SortKey = keyof SimulationResult
type SortDir = 'asc' | 'desc'
type CupView = 'tabla' | 'r32'

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
      <div style={{ height: '2rem', width: '60%', background: 'var(--line)', borderRadius: '4px', marginBottom: '1rem' }} />
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} style={{ height: '2rem', background: 'var(--line)', borderRadius: '4px', marginBottom: '0.5rem', opacity: 1 - i * 0.1 }} />
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// R32 match card
// ---------------------------------------------------------------------------
interface R32CardProps {
  match: R32Match
  onResult: (matchId: number, scoreH: number, scoreA: number) => void
  saving: boolean
  scorelines?: Scoreline[]
}

function R32Card({ match, onResult, saving, scorelines }: R32CardProps) {
  const [editH, setEditH] = useState<string>(match.score_h !== null ? String(match.score_h) : '')
  const [editA, setEditA] = useState<string>(match.score_a !== null ? String(match.score_a) : '')
  const [editing, setEditing] = useState(false)

  const pHPct = (match.pH * 100).toFixed(0)
  const pDPct = (match.pD * 100).toFixed(0)
  const pAPct = (match.pA * 100).toFixed(0)

  const homeWins = match.played && match.score_h !== null && match.score_a !== null && match.score_h > match.score_a
  const awayWins = match.played && match.score_h !== null && match.score_a !== null && match.score_a > match.score_h

  function handleSave() {
    const h = parseInt(editH, 10)
    const a = parseInt(editA, 10)
    if (!isNaN(h) && !isNaN(a) && h >= 0 && a >= 0) {
      onResult(match.id, h, a)
      setEditing(false)
    }
  }

  return (
    <div style={{
      background: 'var(--card)',
      border: '1px solid var(--line)',
      borderRadius: '10px',
      overflow: 'hidden',
      marginBottom: '0.75rem',
    }}>
      {/* Match header — slot labels */}
      <div style={{
        padding: '0.4rem 0.75rem',
        borderBottom: '1px solid var(--line)',
        fontSize: '0.7rem',
        color: 'var(--dim)',
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: '0.06em',
        display: 'flex',
        justifyContent: 'space-between',
        background: match.uncertain ? 'color-mix(in srgb, var(--violet) 8%, var(--card))' : undefined,
      }}>
        <span>{match.home_slot}</span>
        <span style={{ color: match.uncertain ? 'var(--violet)' : 'var(--dim)' }}>
          {match.uncertain ? '⚠ pendiente' : `Match ${match.id}`}
        </span>
        <span>{match.away_slot}</span>
      </div>

      {/* Main content */}
      <div style={{ padding: '0.75rem 1rem' }}>
        {/* Teams + score/prediction */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {/* Home team */}
          <div style={{ flex: 1 }}>
            <div style={{
              fontWeight: homeWins ? 700 : 500,
              fontSize: '0.9rem',
              color: homeWins ? 'var(--txt)' : awayWins ? 'var(--dim)' : 'var(--txt)',
            }}>
              {match.home}
            </div>
            {match.home_coach && (
              <div style={{ fontSize: '0.7rem', color: 'var(--dim)', marginTop: '0.15rem' }}>
                DT: {match.home_coach}
              </div>
            )}
          </div>

          {/* Score / prediction */}
          <div style={{ textAlign: 'center', minWidth: '80px' }}>
            {match.played && match.score_h !== null && match.score_a !== null ? (
              <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--txt)', letterSpacing: '0.1em' }}>
                {match.score_h} – {match.score_a}
              </div>
            ) : (
              <div style={{ fontSize: '0.75rem', color: 'var(--dim)', fontWeight: 500 }}>
                <span style={{ color: 'var(--txt)', fontWeight: 600 }}>{pHPct}%</span>
                {' · '}
                <span>{pDPct}%</span>
                {' · '}
                <span style={{ color: 'var(--txt)', fontWeight: 600 }}>{pAPct}%</span>
              </div>
            )}
            {match.played && (
              <div style={{ fontSize: '0.65rem', color: 'var(--dim)', marginTop: '0.1rem' }}>
                {pHPct}% · {pDPct}% · {pAPct}%
              </div>
            )}
          </div>

          {/* Away team */}
          <div style={{ flex: 1, textAlign: 'right' }}>
            <div style={{
              fontWeight: awayWins ? 700 : 500,
              fontSize: '0.9rem',
              color: awayWins ? 'var(--txt)' : homeWins ? 'var(--dim)' : 'var(--txt)',
            }}>
              {match.away}
            </div>
            {match.away_coach && (
              <div style={{ fontSize: '0.7rem', color: 'var(--dim)', marginTop: '0.15rem' }}>
                DT: {match.away_coach}
              </div>
            )}
          </div>
        </div>

        {/* Probability bar */}
        {!match.played && (
          <div style={{ marginTop: '0.5rem', height: '4px', borderRadius: '2px', overflow: 'hidden', display: 'flex', background: 'var(--line)' }}>
            <div style={{ width: `${pHPct}%`, background: 'var(--violet)', transition: 'width 0.3s' }} />
            <div style={{ width: `${pDPct}%`, background: 'var(--dim)' }} />
            <div style={{ width: `${pAPct}%`, background: 'color-mix(in srgb, var(--violet) 50%, var(--line))' }} />
          </div>
        )}

        {/* Top-2 probable scorelines */}
        {!match.played && scorelines && scorelines.length > 0 && (
          <div style={{ marginTop: '0.4rem', fontSize: '0.75rem', color: 'var(--dim)' }}>
            {scorelines.slice(0, 2).map((s, i) => (
              <span key={i}>
                {i > 0 && <span style={{ margin: '0 0.4rem' }}>·</span>}
                <span style={{ color: 'var(--dim)', fontWeight: 500 }}>{i === 0 ? '1°' : '2°'} </span>
                <span style={{ color: 'var(--txt)', fontWeight: 700, background: 'var(--line)', padding: '0.1rem 0.4rem', borderRadius: '3px' }}>
                  {s.h}–{s.a}
                </span>
                <span style={{ marginLeft: '0.2rem' }}>({(s.prob * 100).toFixed(1)}%)</span>
              </span>
            ))}
          </div>
        )}

        {/* Score entry */}
        {editing ? (
          <div style={{ marginTop: '0.6rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <input
              type="number"
              min="0"
              max="99"
              value={editH}
              onChange={e => setEditH(e.target.value)}
              style={{ width: '3rem', textAlign: 'center', padding: '0.25rem', border: '1px solid var(--line)', borderRadius: '4px', background: 'var(--card)', color: 'var(--txt)', fontSize: '1rem' }}
            />
            <span style={{ color: 'var(--dim)' }}>–</span>
            <input
              type="number"
              min="0"
              max="99"
              value={editA}
              onChange={e => setEditA(e.target.value)}
              style={{ width: '3rem', textAlign: 'center', padding: '0.25rem', border: '1px solid var(--line)', borderRadius: '4px', background: 'var(--card)', color: 'var(--txt)', fontSize: '1rem' }}
            />
            <button onClick={handleSave} disabled={saving} style={{ padding: '0.25rem 0.75rem', background: 'var(--violet)', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600 }}>
              {saving ? '…' : 'Guardar'}
            </button>
            <button onClick={() => setEditing(false)} style={{ padding: '0.25rem 0.5rem', background: 'transparent', color: 'var(--dim)', border: '1px solid var(--line)', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem' }}>
              ✕
            </button>
          </div>
        ) : (
          <div style={{ marginTop: '0.4rem', textAlign: 'right' }}>
            <button
              onClick={() => {
                setEditH(match.score_h !== null ? String(match.score_h) : '')
                setEditA(match.score_a !== null ? String(match.score_a) : '')
                setEditing(true)
              }}
              style={{ padding: '0.2rem 0.6rem', background: 'transparent', color: 'var(--dim)', border: '1px solid var(--line)', borderRadius: '4px', cursor: 'pointer', fontSize: '0.75rem' }}
            >
              {match.played ? 'Editar resultado' : 'Ingresar resultado'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// R32 bracket view
// ---------------------------------------------------------------------------
function R32View() {
  const queryClient = useQueryClient()
  const [autofilling, setAutofilling] = useState(false)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['r32'],
    queryFn: getR32,
    staleTime: 2 * 60_000,
  })

  const mutation = useMutation({
    mutationFn: ({ id, h, a }: { id: number; h: number; a: number }) =>
      putR32Result(id, h, a),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['r32'] })
    },
  })

  const matches = data?.matches ?? []

  // Fetch top-2 probable scorelines for each non-uncertain unplayed match
  const modalQueries = useQueries({
    queries: matches.map(m => ({
      queryKey: ['r32modal', m.home, m.away],
      queryFn: () => simulateModal({ home: m.home, away: m.away, top_k: 2 }),
      enabled: !m.uncertain && !m.played,
      staleTime: 10 * 60_000,
    })),
  })

  async function handleAutoFill() {
    setAutofilling(true)
    try {
      const jobs: Promise<unknown>[] = []
      matches.forEach((m, i) => {
        if (!m.played && !m.uncertain) {
          const top = modalQueries[i]?.data?.scorelines?.[0]
          if (top) jobs.push(putR32Result(m.id, top.h, top.a))
        }
      })
      await Promise.all(jobs)
      void queryClient.invalidateQueries({ queryKey: ['r32'] })
    } finally {
      setAutofilling(false)
    }
  }

  if (isLoading) return <Skeleton />
  if (isError) return <div style={{ color: 'var(--red)', padding: '1rem' }}>Error al cargar R32</div>

  const played = matches.filter(m => m.played).length
  const unplayed = matches.filter((m, i) => !m.played && !m.uncertain && modalQueries[i]?.data?.scorelines?.[0])
  const modalLoading = modalQueries.some(q => q.isLoading)

  return (
    <div>
      <div style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
        <p style={{ fontSize: '0.8rem', color: 'var(--dim)', margin: 0 }}>
          {played > 0 ? `${played}/16 partidos jugados` : 'Bracket proyectado · ingresá resultados reales a medida que se juegan'}
        </p>
        {unplayed.length > 0 && (
          <button
            onClick={() => void handleAutoFill()}
            disabled={autofilling || modalLoading}
            style={{ padding: '0.3rem 0.75rem', background: 'var(--violet)', color: '#fff', border: 'none', borderRadius: '6px', cursor: autofilling || modalLoading ? 'not-allowed' : 'pointer', fontWeight: 600, fontSize: '0.8rem', opacity: autofilling || modalLoading ? 0.6 : 1 }}
          >
            {autofilling ? 'Completando…' : `Completar ${unplayed.length} con más probable`}
          </button>
        )}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '0' }}>
        {matches.map((m, i) => (
          <R32Card
            key={m.id}
            match={m}
            onResult={(id, h, a) => mutation.mutate({ id, h, a })}
            saving={mutation.isPending}
            scorelines={modalQueries[i]?.data?.scorelines}
          />
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// CupTab — main component with sub-tab switcher
// ---------------------------------------------------------------------------
export function CupTab() {
  const [view, setView] = useState<CupView>('tabla')
  const [sortKey, setSortKey] = useState<SortKey>('champ')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['tournament', 2500, 0.05],
    queryFn: () => simulateTournament({ n: 2500, rho: 0.05, model_id: 'current' }),
    staleTime: 5 * 60_000,
  })

  const handleSort = useCallback(
    (key: SortKey) => {
      if (key === sortKey) {
        setSortDir(d => (d === 'asc' ? 'desc' : 'asc'))
      } else {
        setSortKey(key)
        setSortDir('desc')
      }
    },
    [sortKey],
  )

  const tabStyle = (active: boolean): React.CSSProperties => ({
    padding: '0.375rem 1rem',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: 600,
    fontSize: '0.8125rem',
    background: active ? 'var(--violet)' : 'transparent',
    color: active ? '#fff' : 'var(--dim)',
    transition: 'background 0.15s, color 0.15s',
  })

  return (
    <div>
      {/* Sub-tab switcher */}
      <div style={{ display: 'flex', gap: '0.25rem', marginBottom: '1rem', background: 'var(--card)', border: '1px solid var(--line)', borderRadius: '8px', padding: '0.25rem', width: 'fit-content' }}>
        <button style={tabStyle(view === 'tabla')} onClick={() => setView('tabla')}>Pronósticos</button>
        <button style={tabStyle(view === 'r32')} onClick={() => setView('r32')}>Ronda de 32</button>
      </div>

      {view === 'r32' ? (
        <R32View />
      ) : (
        <>
          {isLoading && <Skeleton />}
          {isError && (
            <div role="alert" style={{ padding: '1rem' }}>
              <div style={{ background: 'color-mix(in srgb, var(--red) 15%, var(--card))', border: '1px solid var(--red)', borderRadius: '8px', padding: '1rem 1.25rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}>
                <span style={{ color: 'var(--red)', fontWeight: 500 }}>Error al cargar datos del torneo</span>
                <button type="button" onClick={() => void refetch()} style={{ padding: '0.375rem 0.875rem', background: 'var(--red)', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 500 }}>
                  Reintentar
                </button>
              </div>
              <p style={{ color: 'var(--dim)', fontSize: '0.8125rem', marginTop: '0.5rem' }}>
                {error instanceof Error ? error.message : 'Error desconocido'}
              </p>
            </div>
          )}
          {!isLoading && !isError && (() => {
            const results = data?.results ?? []
            const sorted = [...results].sort((a, b) => {
              const av = a[sortKey]
              const bv = b[sortKey]
              const cmp = typeof av === 'string' && typeof bv === 'string'
                ? av.localeCompare(bv)
                : (av as number) - (bv as number)
              return sortDir === 'asc' ? cmp : -cmp
            })
            const arrow = (key: SortKey) => key === sortKey ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''
            return (
              <div style={{ overflowX: 'auto' }}>
                <table data-testid="cup-table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid var(--line)' }}>
                      <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', color: 'var(--dim)', fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', width: '2rem' }}>#</th>
                      {TABLE_COLS.map(col => (
                        <th key={col.key} onClick={() => handleSort(col.key)} style={{ padding: '0.5rem 0.75rem', textAlign: col.pct ? 'right' : 'left', color: sortKey === col.key ? 'var(--violet)' : 'var(--dim)', fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', cursor: 'pointer', userSelect: 'none', whiteSpace: 'nowrap' }}>
                          {col.label}{arrow(col.key)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sorted.map((row, idx) => (
                      <tr key={row.team} style={{ borderBottom: '1px solid var(--line)', background: champColor(row.champ) }}>
                        <td style={{ padding: '0.5rem 0.75rem', color: 'var(--dim)', fontSize: '0.8125rem' }}>{idx + 1}</td>
                        {TABLE_COLS.map(col => {
                          const val = row[col.key]
                          return (
                            <td key={col.key} style={{ padding: '0.5rem 0.75rem', textAlign: col.pct ? 'right' : 'left', color: 'var(--txt)', fontWeight: col.key === 'team' ? 500 : 400 }}>
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
          })()}
        </>
      )}
    </div>
  )
}
