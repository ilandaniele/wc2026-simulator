import { useQueries } from '@tanstack/react-query'
import {
  simulateMatch,
  simulateModal,
  type SimulateMatchResponse,
  type SimulateModalResponse,
} from '../api/client'

// ---------------------------------------------------------------------------
// Schedule — WC2026 fixture from group stage finale through R32.
// score: [h, a] when the match is confirmed; undefined = upcoming prediction.
// ---------------------------------------------------------------------------
interface ScheduledMatch {
  home: string
  away: string
  label?: string
  score?: [number, number]
}

interface MatchDay {
  date: string
  title: string
  matches: ScheduledMatch[]
}

const SCHEDULE: MatchDay[] = [
  {
    date: '2026-06-27',
    title: 'Fase de grupos – Jornada final (J, K, L)',
    matches: [
      { home: 'Algeria',  away: 'Austria',    label: 'Grupo J', score: [3, 3] },
      { home: 'Jordan',   away: 'Argentina',  label: 'Grupo J', score: [0, 2] },
      { home: 'Colombia', away: 'Portugal',   label: 'Grupo K', score: [0, 0] },
      { home: 'DR Congo', away: 'Uzbekistan', label: 'Grupo K', score: [3, 1] },
      { home: 'Panama',   away: 'England',    label: 'Grupo L', score: [0, 2] },
      { home: 'Croatia',  away: 'Ghana',      label: 'Grupo L', score: [2, 1] },
    ],
  },
  {
    date: '2026-06-28',
    title: 'Ronda de 32 – Partido 73',
    matches: [
      { home: 'Canada', away: 'South Africa', label: 'Partido 73', score: [1, 0] },
    ],
  },
  {
    date: '2026-06-29',
    title: 'Ronda de 32 – Día 1 (continuación)',
    matches: [
      { home: 'Brazil',       away: 'Japan',    label: 'Partido 74' },
      { home: 'Germany',      away: 'Paraguay', label: 'Partido 75' },
      { home: 'Netherlands',  away: 'Morocco',  label: 'Partido 76' },
    ],
  },
  {
    date: '2026-06-30',
    title: 'Ronda de 32 – Día 2',
    matches: [
      { home: "Côte d'Ivoire", away: 'Norway',  label: 'Partido 77' },
      { home: 'France',        away: 'Sweden',  label: 'Partido 78' },
      { home: 'Mexico',        away: 'Ecuador', label: 'Partido 79' },
    ],
  },
  {
    date: '2026-07-01',
    title: 'Ronda de 32 – Día 3',
    matches: [
      { home: 'England',  away: 'DR Congo',              label: 'Partido 80' },
      { home: 'Belgium',  away: 'Senegal',               label: 'Partido 81' },
      { home: 'USA',      away: 'Bosnia and Herzegovina', label: 'Partido 82' },
    ],
  },
  {
    date: '2026-07-02',
    title: 'Ronda de 32 – Día 4',
    matches: [
      { home: 'Spain',        away: 'Austria',   label: 'Partido 83' },
      { home: 'Portugal',     away: 'Croatia',   label: 'Partido 84' },
      { home: 'Switzerland',  away: 'Algeria',   label: 'Partido 85' },
    ],
  },
  {
    date: '2026-07-03',
    title: 'Ronda de 32 – Día 5',
    matches: [
      { home: 'Australia', away: 'Egypt',       label: 'Partido 86' },
      { home: 'Argentina', away: 'Cabo Verde',  label: 'Partido 87' },
      { home: 'Colombia',  away: 'Ghana',       label: 'Partido 88' },
    ],
  },
]

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
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

function formatDate(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  const date = new Date(y, m - 1, d)
  return date.toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long' })
}

function isToday(iso: string): boolean {
  const now = new Date()
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  return iso === today
}

function isPast(iso: string): boolean {
  const now = new Date()
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  return iso < today
}

// ---------------------------------------------------------------------------
// All unique match pairs for React Query (deduplication handled by queryKey)
// ---------------------------------------------------------------------------
const ALL_PAIRS: [string, string][] = SCHEDULE.flatMap(day =>
  day.matches.map(m => [m.home, m.away] as [string, string]),
)

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------
function CardSkeleton({ home, away }: { home: string; away: string }) {
  return (
    <div aria-busy="true" aria-label={`Cargando ${home} vs ${away}`} style={{ background: 'var(--card)', border: '1px solid var(--line)', borderRadius: '10px', padding: '1rem 1.25rem', minHeight: '120px' }}>
      <div style={{ fontWeight: 600, marginBottom: '0.75rem', color: 'var(--txt)', fontSize: '0.9375rem' }}>
        {home} <span style={{ color: 'var(--dim)' }}>vs</span> {away}
      </div>
      <div style={{ height: '1.5rem', background: 'var(--line)', borderRadius: '4px', marginBottom: '0.5rem' }} />
      <div style={{ height: '1rem', width: '60%', background: 'var(--line)', borderRadius: '4px' }} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Prediction card — upcoming match
// ---------------------------------------------------------------------------
interface PredCardProps {
  home: string
  away: string
  label?: string
  matchData: SimulateMatchResponse | undefined
  modalData: SimulateModalResponse | undefined
  isLoading: boolean
  isError: boolean
}

function PredCard({ home, away, label, matchData, modalData, isLoading, isError }: PredCardProps) {
  const testId = `match-card-${home.replace(/\s+/g, '-')}-${away.replace(/\s+/g, '-')}`
  if (isLoading) return <CardSkeleton home={home} away={away} />
  if (isError || !matchData) {
    return (
      <div data-testid={testId} style={{ background: 'var(--card)', border: '1px solid var(--red)', borderRadius: '10px', padding: '1rem 1.25rem' }}>
        {label && <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--dim)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.4rem' }}>{label}</div>}
        <div style={{ fontWeight: 600, marginBottom: '0.5rem', color: 'var(--txt)' }}>{home} vs {away}</div>
        <span style={{ color: 'var(--red)', fontSize: '0.875rem' }}>Error al cargar predicciones</span>
      </div>
    )
  }

  const [rH, rD, rA] = roundProbs(matchData.pH, matchData.pD, matchData.pA)
  const topScore = modalData?.scorelines[0]

  return (
    <div data-testid={testId} style={{ background: 'var(--card)', border: '1px solid var(--line)', borderRadius: '10px', padding: '1rem 1.25rem' }}>
      {label && <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--dim)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.4rem' }}>{label}</div>}
      <div style={{ fontWeight: 600, marginBottom: '0.875rem', color: 'var(--txt)', fontSize: '0.9375rem' }}>
        {home} <span style={{ color: 'var(--dim)', fontWeight: 400 }}>vs</span> {away}
      </div>
      <div style={{ display: 'flex', borderRadius: '6px', overflow: 'hidden', height: '1.75rem', marginBottom: '0.5rem' }} aria-label={`${home} ${rH}%, Empate ${rD}%, ${away} ${rA}%`}>
        <div title={`${home}: ${rH}%`} style={{ width: `${rH}%`, background: 'var(--green)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: '0.75rem', fontWeight: 700, overflow: 'hidden' }}>{rH > 8 ? `${rH}%` : ''}</div>
        <div title={`Empate: ${rD}%`} style={{ width: `${rD}%`, background: 'var(--dim)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: '0.75rem', fontWeight: 700, overflow: 'hidden' }}>{rD > 8 ? `${rD}%` : ''}</div>
        <div title={`${away}: ${rA}%`} style={{ width: `${rA}%`, background: 'var(--red)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: '0.75rem', fontWeight: 700, overflow: 'hidden' }}>{rA > 8 ? `${rA}%` : ''}</div>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--dim)', marginBottom: '0.625rem' }}>
        <span>{home} {rH}%</span>
        <span>Empate {rD}%</span>
        <span>{away} {rA}%</span>
      </div>
      {topScore && (
        <div style={{ fontSize: '0.8125rem', color: 'var(--dim)' }}>
          <span style={{ fontWeight: 500 }}>Resultado más probable: </span>
          <span style={{ color: 'var(--txt)', fontWeight: 600, background: 'var(--line)', padding: '0.125rem 0.5rem', borderRadius: '4px' }}>{topScore.h}–{topScore.a}</span>
          <span style={{ marginLeft: '0.375rem' }}>({(topScore.prob * 100).toFixed(1)}%)</span>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Result card — match already played
// ---------------------------------------------------------------------------
interface ResultCardProps {
  home: string
  away: string
  label?: string
  score: [number, number]
  matchData: SimulateMatchResponse | undefined
}

function ResultCard({ home, away, label, score, matchData }: ResultCardProps) {
  const [h, a] = score
  const homeWon = h > a
  const awayWon = a > h

  return (
    <div style={{ background: 'var(--card)', border: '1px solid var(--line)', borderRadius: '10px', padding: '1rem 1.25rem', opacity: 0.85 }}>
      {label && <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--dim)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.4rem' }}>{label}</div>}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' }}>
        <span style={{ fontWeight: homeWon ? 700 : 400, color: homeWon ? 'var(--txt)' : 'var(--dim)', fontSize: '0.9375rem', flex: 1 }}>{home}</span>
        <span style={{ fontWeight: 700, fontSize: '1.25rem', color: 'var(--txt)', letterSpacing: '0.1em', minWidth: '4rem', textAlign: 'center' }}>{h} – {a}</span>
        <span style={{ fontWeight: awayWon ? 700 : 400, color: awayWon ? 'var(--txt)' : 'var(--dim)', fontSize: '0.9375rem', flex: 1, textAlign: 'right' }}>{away}</span>
      </div>
      {matchData && (
        <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: 'var(--dim)' }}>
          Modelo: {(matchData.pH * 100).toFixed(0)}% · {(matchData.pD * 100).toFixed(0)}% · {(matchData.pA * 100).toFixed(0)}%
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// HoyTab — full WC2026 schedule view
// ---------------------------------------------------------------------------
export function HoyTab() {
  const allQueries = useQueries({
    queries: ALL_PAIRS.map(([home, away]) => ({
      queryKey: ['match', home, away],
      queryFn: () => simulateMatch({ home, away, n_per_draw: 30, rho: 0.05 }),
      staleTime: 5 * 60_000,
    })),
  })

  const modalQueries = useQueries({
    queries: ALL_PAIRS.map(([home, away]) => ({
      queryKey: ['modal', home, away],
      queryFn: () => simulateModal({ home, away, top_k: 3 }),
      staleTime: 5 * 60_000,
    })),
  })

  // Build index from "home|away" → query index for O(1) lookup
  const pairIndex = new Map(ALL_PAIRS.map(([h, a], i) => [`${h}|${a}`, i]))

  return (
    <div>
      {SCHEDULE.filter(day => !isPast(day.date)).map(day => {
        const past = isPast(day.date)
        const today = isToday(day.date)

        return (
          <div key={day.date} style={{ marginBottom: '2rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
              <h2 style={{ fontSize: '0.9375rem', fontWeight: 700, color: today ? 'var(--violet)' : past ? 'var(--dim)' : 'var(--txt)', margin: 0, textTransform: 'capitalize' }}>
                {formatDate(day.date)}
              </h2>
              {today && (
                <span style={{ fontSize: '0.7rem', fontWeight: 700, background: 'var(--violet)', color: '#fff', padding: '0.15rem 0.5rem', borderRadius: '4px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Hoy</span>
              )}
              <span style={{ fontSize: '0.8rem', color: 'var(--dim)', fontWeight: 500 }}>{day.title}</span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '0.75rem' }}>
              {day.matches.map(m => {
                const idx = pairIndex.get(`${m.home}|${m.away}`) ?? -1
                const matchData = idx >= 0 ? allQueries[idx]?.data : undefined
                const modalData = idx >= 0 ? modalQueries[idx]?.data : undefined
                const isLoading = idx >= 0 ? (allQueries[idx]?.isLoading ?? true) : false
                const isError = idx >= 0 ? (allQueries[idx]?.isError ?? false) : false

                if (m.score) {
                  return (
                    <ResultCard
                      key={`${m.home}|${m.away}`}
                      home={m.home}
                      away={m.away}
                      label={m.label}
                      score={m.score}
                      matchData={matchData}
                    />
                  )
                }
                return (
                  <PredCard
                    key={`${m.home}|${m.away}`}
                    home={m.home}
                    away={m.away}
                    label={m.label}
                    matchData={matchData}
                    modalData={modalData}
                    isLoading={isLoading}
                    isError={isError}
                  />
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}
