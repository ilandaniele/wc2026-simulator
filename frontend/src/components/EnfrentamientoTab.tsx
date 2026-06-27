import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { getTeams, simulateH2H, type H2HResponse } from '../api/client'

// ---------------------------------------------------------------------------
// CI Bar visualisation
// ---------------------------------------------------------------------------
interface CIBarProps {
  result: H2HResponse
}

function CIBar({ result }: CIBarProps) {
  const { ci_lower, ci_median, ci_upper, top_scorelines } = result

  // Normalise to 0–1 range for bar drawing
  const lo = ci_lower
  const med = ci_median
  const hi = ci_upper

  // Display the range bar from ci_lower to ci_upper with median marker
  const loPos = lo * 100
  const hiPos = hi * 100
  const medPos = med * 100

  return (
    <div data-testid="h2h-result">
      {/* Probability summary */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: '0.75rem',
          marginBottom: '1.5rem',
        }}
      >
        {[
          { label: result.home, value: result.ci_median, desc: 'probabilidad de victoria' },
          { label: 'Empate', value: 1 - result.ci_lower - result.ci_upper, desc: 'probabilidad de empate' },
          { label: result.away, value: 1 - result.ci_median, desc: 'probabilidad de victoria' },
        ].map((item) => (
          <div
            key={item.label}
            style={{
              background: 'var(--card)',
              border: '1px solid var(--line)',
              borderRadius: '8px',
              padding: '0.875rem 1rem',
              textAlign: 'center',
            }}
          >
            <div style={{ fontSize: '0.75rem', color: 'var(--dim)', marginBottom: '0.25rem' }}>
              {item.label}
            </div>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--txt)' }}>
              {(item.value * 100).toFixed(1)}%
            </div>
            <div style={{ fontSize: '0.6875rem', color: 'var(--dim)', marginTop: '0.125rem' }}>
              {item.desc}
            </div>
          </div>
        ))}
      </div>

      {/* CI bar */}
      <div style={{ marginBottom: '1.5rem' }}>
        <div
          style={{
            fontSize: '0.75rem',
            color: 'var(--dim)',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            fontWeight: 600,
            marginBottom: '0.5rem',
          }}
        >
          Intervalo de confianza — {result.home} win %
        </div>
        <div
          style={{
            position: 'relative',
            height: '2rem',
            background: 'var(--line)',
            borderRadius: '6px',
            overflow: 'hidden',
          }}
        >
          {/* CI band */}
          <div
            style={{
              position: 'absolute',
              left: `${loPos}%`,
              width: `${hiPos - loPos}%`,
              height: '100%',
              background: 'color-mix(in srgb, var(--violet) 30%, transparent)',
            }}
          />
          {/* Median marker */}
          <div
            style={{
              position: 'absolute',
              left: `${medPos}%`,
              top: 0,
              bottom: 0,
              width: '3px',
              background: 'var(--violet)',
              transform: 'translateX(-50%)',
            }}
          />
        </div>
        {/* Labels */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: '0.75rem',
            color: 'var(--dim)',
            marginTop: '0.375rem',
          }}
        >
          <span>
            Lo: <strong style={{ color: 'var(--txt)' }}>{(lo * 100).toFixed(1)}%</strong>
          </span>
          <span>
            Med: <strong style={{ color: 'var(--violet)' }}>{(med * 100).toFixed(1)}%</strong>
          </span>
          <span>
            Hi: <strong style={{ color: 'var(--txt)' }}>{(hi * 100).toFixed(1)}%</strong>
          </span>
        </div>
      </div>

      {/* Top scorelines */}
      {top_scorelines.length > 0 && (
        <div>
          <div
            style={{
              fontSize: '0.75rem',
              color: 'var(--dim)',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              fontWeight: 600,
              marginBottom: '0.625rem',
            }}
          >
            Resultados más probables
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
            {top_scorelines.map((s) => (
              <div
                key={`${s.h}-${s.a}`}
                style={{
                  background: 'var(--card)',
                  border: '1px solid var(--line)',
                  borderRadius: '6px',
                  padding: '0.375rem 0.75rem',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  minWidth: '3.5rem',
                }}
              >
                <span style={{ fontWeight: 700, fontSize: '1.0625rem', color: 'var(--txt)' }}>
                  {s.h}–{s.a}
                </span>
                <span style={{ fontSize: '0.6875rem', color: 'var(--dim)' }}>
                  {(s.prob * 100).toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// EnfrentamientoTab
// ---------------------------------------------------------------------------
export function EnfrentamientoTab() {
  const [home, setHome] = useState('Spain')
  const [away, setAway] = useState('Germany')
  const [knockout, setKnockout] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  const { data: teamsData } = useQuery({
    queryKey: ['teams'],
    queryFn: getTeams,
    staleTime: 10 * 60_000,
  })

  const teams = teamsData?.teams ?? []

  const mutation = useMutation({
    mutationFn: () =>
      simulateH2H({ home, away, knockout, top_k: 6 }),
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitted(true)
    mutation.mutate()
  }

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
        Enfrentamiento
      </h2>

      {/* Form */}
      <form
        onSubmit={handleSubmit}
        style={{
          background: 'var(--card)',
          border: '1px solid var(--line)',
          borderRadius: '10px',
          padding: '1.25rem',
          marginBottom: '1.5rem',
          display: 'flex',
          flexWrap: 'wrap',
          gap: '1rem',
          alignItems: 'flex-end',
        }}
      >
        {/* Home select */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          <label
            htmlFor="h2h-home"
            style={{ fontSize: '0.75rem', color: 'var(--dim)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}
          >
            Local
          </label>
          <select
            id="h2h-home"
            value={home}
            onChange={(e) => setHome(e.target.value)}
            style={{
              padding: '0.5rem 0.75rem',
              borderRadius: '6px',
              border: '1px solid var(--line)',
              background: 'var(--bg)',
              color: 'var(--txt)',
              fontSize: '0.875rem',
              cursor: 'pointer',
              minWidth: '160px',
            }}
          >
            {teams.length > 0
              ? teams.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))
              : <option value="Spain">Spain</option>}
          </select>
        </div>

        {/* Away select */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          <label
            htmlFor="h2h-away"
            style={{ fontSize: '0.75rem', color: 'var(--dim)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}
          >
            Visitante
          </label>
          <select
            id="h2h-away"
            value={away}
            onChange={(e) => setAway(e.target.value)}
            style={{
              padding: '0.5rem 0.75rem',
              borderRadius: '6px',
              border: '1px solid var(--line)',
              background: 'var(--bg)',
              color: 'var(--txt)',
              fontSize: '0.875rem',
              cursor: 'pointer',
              minWidth: '160px',
            }}
          >
            {teams.length > 0
              ? teams.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))
              : <option value="Germany">Germany</option>}
          </select>
        </div>

        {/* Knockout checkbox */}
        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            fontSize: '0.875rem',
            color: 'var(--txt)',
            cursor: 'pointer',
            marginBottom: '0.125rem',
          }}
        >
          <input
            type="checkbox"
            checked={knockout}
            onChange={(e) => setKnockout(e.target.checked)}
            style={{ width: '1rem', height: '1rem', cursor: 'pointer' }}
          />
          Eliminación directa
        </label>

        {/* Submit */}
        <button
          type="submit"
          disabled={mutation.isPending}
          style={{
            padding: '0.5rem 1.25rem',
            background: 'var(--violet)',
            color: '#fff',
            border: 'none',
            borderRadius: '6px',
            fontSize: '0.875rem',
            fontWeight: 600,
            cursor: mutation.isPending ? 'wait' : 'pointer',
            opacity: mutation.isPending ? 0.7 : 1,
          }}
        >
          {mutation.isPending ? 'Simulando…' : 'Simular'}
        </button>
      </form>

      {/* Results */}
      {mutation.isPending && (
        <div aria-busy="true" aria-label="Simulando enfrentamiento">
          <div
            style={{
              height: '200px',
              background: 'var(--card)',
              border: '1px solid var(--line)',
              borderRadius: '10px',
            }}
          />
        </div>
      )}

      {mutation.isError && submitted && (
        <div role="alert" style={{ color: 'var(--red)', padding: '0.75rem' }}>
          Error al simular el enfrentamiento
        </div>
      )}

      {mutation.data && !mutation.isPending && (
        <div
          style={{
            background: 'var(--card)',
            border: '1px solid var(--line)',
            borderRadius: '10px',
            padding: '1.25rem',
          }}
        >
          <CIBar result={mutation.data} />
        </div>
      )}
    </div>
  )
}
