import { useQueries } from '@tanstack/react-query'
import {
  simulateMatch,
  simulateModal,
  type SimulateMatchResponse,
  type SimulateModalResponse,
} from '../api/client'

// ---------------------------------------------------------------------------
// Today's matches (J/K/L groups, 2026-06-27)
// ---------------------------------------------------------------------------
const TODAY_MATCHES: Array<[string, string]> = [
  ['Algeria', 'Austria'],
  ['Jordan', 'Argentina'],
  ['Colombia', 'Portugal'],
  ['DR Congo', 'Uzbekistan'],
  ['Panama', 'England'],
  ['Croatia', 'Ghana'],
]

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Round probabilities to integers summing to exactly 100. */
function roundProbs(pH: number, pD: number, pA: number): [number, number, number] {
  const raw = [pH * 100, pD * 100, pA * 100]
  const floored = raw.map(Math.floor) as [number, number, number]
  const remainder = 100 - (floored[0] + floored[1] + floored[2])
  const fracs = raw.map((v, i) => ({ i, frac: v - floored[i] }))
  fracs.sort((a, b) => b.frac - a.frac)
  for (let k = 0; k < remainder; k++) {
    floored[fracs[k].i]++
  }
  return floored
}

// ---------------------------------------------------------------------------
// Match card skeleton
// ---------------------------------------------------------------------------
function CardSkeleton({ home, away }: { home: string; away: string }) {
  return (
    <div
      aria-busy="true"
      aria-label={`Cargando ${home} vs ${away}`}
      style={{
        background: 'var(--card)',
        border: '1px solid var(--line)',
        borderRadius: '10px',
        padding: '1rem 1.25rem',
        minHeight: '120px',
      }}
    >
      <div
        style={{
          fontWeight: 600,
          marginBottom: '0.75rem',
          color: 'var(--txt)',
          fontSize: '0.9375rem',
        }}
      >
        {home} <span style={{ color: 'var(--dim)' }}>vs</span> {away}
      </div>
      <div
        style={{
          height: '1.5rem',
          background: 'var(--line)',
          borderRadius: '4px',
          marginBottom: '0.5rem',
        }}
      />
      <div
        style={{
          height: '1rem',
          width: '60%',
          background: 'var(--line)',
          borderRadius: '4px',
        }}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Match card — renders one match result
// ---------------------------------------------------------------------------
interface MatchCardProps {
  home: string
  away: string
  matchData: SimulateMatchResponse | undefined
  modalData: SimulateModalResponse | undefined
  isLoading: boolean
  isError: boolean
}

function MatchCard({
  home,
  away,
  matchData,
  modalData,
  isLoading,
  isError,
}: MatchCardProps) {
  const testId = `match-card-${home.replace(/\s+/g, '-')}-${away.replace(/\s+/g, '-')}`

  if (isLoading) return <CardSkeleton home={home} away={away} />

  if (isError || !matchData) {
    return (
      <div
        data-testid={testId}
        style={{
          background: 'var(--card)',
          border: '1px solid var(--red)',
          borderRadius: '10px',
          padding: '1rem 1.25rem',
        }}
      >
        <div style={{ fontWeight: 600, marginBottom: '0.5rem', color: 'var(--txt)' }}>
          {home} vs {away}
        </div>
        <span style={{ color: 'var(--red)', fontSize: '0.875rem' }}>
          Error al cargar predicciones
        </span>
      </div>
    )
  }

  const [rH, rD, rA] = roundProbs(matchData.pH, matchData.pD, matchData.pA)
  const topScore = modalData?.scorelines[0]

  return (
    <div
      data-testid={testId}
      style={{
        background: 'var(--card)',
        border: '1px solid var(--line)',
        borderRadius: '10px',
        padding: '1rem 1.25rem',
      }}
    >
      {/* Header */}
      <div
        style={{
          fontWeight: 600,
          marginBottom: '0.875rem',
          color: 'var(--txt)',
          fontSize: '0.9375rem',
        }}
      >
        {home}{' '}
        <span style={{ color: 'var(--dim)', fontWeight: 400 }}>vs</span> {away}
      </div>

      {/* Probability bar */}
      <div
        style={{
          display: 'flex',
          borderRadius: '6px',
          overflow: 'hidden',
          height: '1.75rem',
          marginBottom: '0.5rem',
        }}
        aria-label={`${home} ${rH}%, Empate ${rD}%, ${away} ${rA}%`}
      >
        <div
          title={`${home}: ${rH}%`}
          style={{
            width: `${rH}%`,
            background: 'var(--green)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontSize: '0.75rem',
            fontWeight: 700,
            minWidth: rH > 5 ? undefined : 0,
            overflow: 'hidden',
          }}
        >
          {rH > 8 ? `${rH}%` : ''}
        </div>
        <div
          title={`Empate: ${rD}%`}
          style={{
            width: `${rD}%`,
            background: 'var(--dim)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontSize: '0.75rem',
            fontWeight: 700,
            overflow: 'hidden',
          }}
        >
          {rD > 8 ? `${rD}%` : ''}
        </div>
        <div
          title={`${away}: ${rA}%`}
          style={{
            width: `${rA}%`,
            background: 'var(--red)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontSize: '0.75rem',
            fontWeight: 700,
            overflow: 'hidden',
          }}
        >
          {rA > 8 ? `${rA}%` : ''}
        </div>
      </div>

      {/* Label row */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: '0.75rem',
          color: 'var(--dim)',
          marginBottom: '0.625rem',
        }}
      >
        <span>
          {home} {rH}%
        </span>
        <span>Empate {rD}%</span>
        <span>
          {away} {rA}%
        </span>
      </div>

      {/* Top scoreline */}
      {topScore && (
        <div style={{ fontSize: '0.8125rem', color: 'var(--dim)' }}>
          <span style={{ fontWeight: 500 }}>Resultado más probable: </span>
          <span
            style={{
              color: 'var(--txt)',
              fontWeight: 600,
              background: 'var(--line)',
              padding: '0.125rem 0.5rem',
              borderRadius: '4px',
            }}
          >
            {topScore.h}–{topScore.a}
          </span>
          <span style={{ marginLeft: '0.375rem' }}>
            ({(topScore.prob * 100).toFixed(1)}%)
          </span>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// HoyTab
// ---------------------------------------------------------------------------
export function HoyTab() {
  const matchQueries = useQueries({
    queries: TODAY_MATCHES.map(([home, away]) => ({
      queryKey: ['match', home, away],
      queryFn: () =>
        simulateMatch({ home, away, n_per_draw: 30, rho: 0.05 }),
      staleTime: 5 * 60_000,
    })),
  })

  const modalQueries = useQueries({
    queries: TODAY_MATCHES.map(([home, away]) => ({
      queryKey: ['modal', home, away],
      queryFn: () => simulateModal({ home, away, top_k: 3 }),
      staleTime: 5 * 60_000,
    })),
  })

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
        Partidos de hoy
      </h2>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
          gap: '1rem',
        }}
      >
        {TODAY_MATCHES.map(([home, away], i) => (
          <MatchCard
            key={`${home}-${away}`}
            home={home}
            away={away}
            matchData={matchQueries[i]?.data}
            modalData={modalQueries[i]?.data}
            isLoading={matchQueries[i]?.isLoading ?? true}
            isError={matchQueries[i]?.isError ?? false}
          />
        ))}
      </div>
    </div>
  )
}
