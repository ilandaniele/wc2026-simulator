import { useQuery } from '@tanstack/react-query'
import { getStrength } from '../api/client'

// ---------------------------------------------------------------------------
// FuerzaTab — Strength ranking
// ---------------------------------------------------------------------------
export function FuerzaTab() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['strength'],
    queryFn: getStrength,
    staleTime: 10 * 60_000,
  })

  if (isLoading) {
    return (
      <div aria-busy="true" aria-label="Cargando ranking de equipos">
        {Array.from({ length: 10 }).map((_, i) => (
          <div
            key={i}
            style={{
              height: '2.5rem',
              background: 'var(--card)',
              border: '1px solid var(--line)',
              borderRadius: '6px',
              marginBottom: '0.5rem',
              opacity: 1 - i * 0.08,
            }}
          />
        ))}
      </div>
    )
  }

  if (isError) {
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
          }}
        >
          <span style={{ color: 'var(--red)', fontWeight: 500 }}>
            Error al cargar el ranking
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
      </div>
    )
  }

  const ranking = data?.ranking ?? []

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
        Ranking de fuerza
      </h2>

      <div style={{ overflowX: 'auto' }}>
        <table
          data-testid="strength-table"
          style={{
            width: '100%',
            borderCollapse: 'collapse',
            fontSize: '0.875rem',
          }}
        >
          <thead>
            <tr style={{ borderBottom: '2px solid var(--line)' }}>
              {['#', 'Equipo', 'Grupo', 'Fuerza', 'Ataque', 'Defensa'].map((h) => (
                <th
                  key={h}
                  style={{
                    padding: '0.5rem 0.75rem',
                    textAlign: h === '#' || h === 'Equipo' || h === 'Grupo' ? 'left' : 'right',
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
            {ranking.map((entry, idx) => (
              <tr
                key={entry.team}
                style={{
                  borderBottom: '1px solid var(--line)',
                  background:
                    idx < 5
                      ? 'color-mix(in srgb, var(--violet) 6%, transparent)'
                      : 'transparent',
                }}
              >
                <td
                  style={{
                    padding: '0.5rem 0.75rem',
                    color: 'var(--dim)',
                    fontWeight: idx < 5 ? 600 : 400,
                  }}
                >
                  {idx + 1}
                </td>
                <td
                  style={{
                    padding: '0.5rem 0.75rem',
                    fontWeight: 500,
                    color: 'var(--txt)',
                  }}
                >
                  {entry.team}
                </td>
                <td
                  style={{
                    padding: '0.5rem 0.75rem',
                    color: 'var(--dim)',
                    fontSize: '0.8125rem',
                  }}
                >
                  {entry.group}
                </td>
                <td
                  style={{
                    padding: '0.5rem 0.75rem',
                    textAlign: 'right',
                    fontWeight: 600,
                    color: idx < 5 ? 'var(--violet)' : 'var(--txt)',
                  }}
                >
                  {entry.score.toFixed(2)}
                </td>
                <td
                  style={{
                    padding: '0.5rem 0.75rem',
                    textAlign: 'right',
                    color: 'var(--txt)',
                  }}
                >
                  {entry.att.toFixed(2)}
                </td>
                <td
                  style={{
                    padding: '0.5rem 0.75rem',
                    textAlign: 'right',
                    color: 'var(--txt)',
                  }}
                >
                  {entry.def.toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
