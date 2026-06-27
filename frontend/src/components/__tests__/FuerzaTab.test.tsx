import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { FuerzaTab } from '../FuerzaTab'

// ---------------------------------------------------------------------------
// Mock API
// ---------------------------------------------------------------------------
vi.mock('../../api/client', () => ({
  getStrength: vi.fn(),
}))

import { getStrength } from '../../api/client'

// ---------------------------------------------------------------------------
// Mock data — 48 teams, Argentina first (top strength)
// ---------------------------------------------------------------------------
function makeEntry(team: string, score: number, group: string, att: number, def: number) {
  return { team, group, score, att, def }
}

const MOCK_RANKING = [
  makeEntry('Argentina', 1.82, 'A', 2.15, 0.72),
  makeEntry('France', 1.74, 'B', 2.10, 0.78),
  makeEntry('Brazil', 1.68, 'C', 2.02, 0.80),
  makeEntry('Spain', 1.62, 'D', 1.95, 0.83),
  makeEntry('Portugal', 1.55, 'E', 1.88, 0.86),
  makeEntry('England', 1.48, 'F', 1.80, 0.90),
  ...Array.from({ length: 42 }, (_, i) =>
    makeEntry(
      `Team${i + 7}`,
      1.4 - i * 0.02,
      String.fromCharCode(65 + (i % 12)),
      1.5 - i * 0.01,
      0.95 + i * 0.01,
    ),
  ),
]

function renderFuerzaTab() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <FuerzaTab />
    </QueryClientProvider>,
  )
}

// ---------------------------------------------------------------------------
// Tests — AC20
// ---------------------------------------------------------------------------
describe('FuerzaTab (AC20)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getStrength).mockResolvedValue({ ranking: MOCK_RANKING })
  })

  it('shows loading skeleton initially', () => {
    vi.mocked(getStrength).mockReturnValue(new Promise(() => {}))
    renderFuerzaTab()
    expect(screen.getByRole('generic', { name: /cargando/i })).toBeInTheDocument()
  })

  it('renders table with data-testid="strength-table" after load', async () => {
    renderFuerzaTab()
    await waitFor(() => {
      expect(screen.getByTestId('strength-table')).toBeInTheDocument()
    })
  })

  it('renders exactly 48 data rows (+ header = 49 total rows)', async () => {
    renderFuerzaTab()
    await waitFor(() => {
      expect(screen.getByTestId('strength-table')).toBeInTheDocument()
    })
    const rows = screen.getAllByRole('row')
    expect(rows.length).toBe(49) // 1 header + 48 data
  })

  it('Argentina appears in top 5', async () => {
    renderFuerzaTab()
    await waitFor(() => {
      expect(screen.getByTestId('strength-table')).toBeInTheDocument()
    })
    const rows = screen.getAllByRole('row')
    const top5 = rows.slice(1, 6).map((r) => r.textContent ?? '')
    expect(top5.some((t) => t.includes('Argentina'))).toBe(true)
  })

  it('Argentina is in row 1 (position 1)', async () => {
    renderFuerzaTab()
    await waitFor(() => {
      expect(screen.getByTestId('strength-table')).toBeInTheDocument()
    })
    const rows = screen.getAllByRole('row')
    expect(rows[1].textContent).toContain('Argentina')
  })

  it('each row has att and def numeric values (2 decimal places)', async () => {
    renderFuerzaTab()
    await waitFor(() => {
      expect(screen.getByTestId('strength-table')).toBeInTheDocument()
    })
    // Argentina row: att=2.15, def=0.72
    const rows = screen.getAllByRole('row')
    const argRow = rows[1].textContent ?? ''
    expect(argRow).toMatch(/2\.15/)
    expect(argRow).toMatch(/0\.72/)
  })

  it('team names are displayed', async () => {
    renderFuerzaTab()
    await waitFor(() => {
      expect(screen.getByText('Argentina')).toBeInTheDocument()
      expect(screen.getByText('France')).toBeInTheDocument()
      expect(screen.getByText('Brazil')).toBeInTheDocument()
    })
  })

  it('calls getStrength once on mount', async () => {
    renderFuerzaTab()
    await waitFor(() => {
      expect(getStrength).toHaveBeenCalledTimes(1)
    })
  })

  it('table has # Equipo Grupo Fuerza Ataque Defensa headers', async () => {
    renderFuerzaTab()
    await waitFor(() => {
      expect(screen.getByTestId('strength-table')).toBeInTheDocument()
    })
    const headers = screen.getAllByRole('columnheader')
    const headerTexts = headers.map((h) => h.textContent ?? '')
    expect(headerTexts).toContain('#')
    expect(headerTexts).toContain('Equipo')
    expect(headerTexts).toContain('Grupo')
    expect(headerTexts).toContain('Fuerza')
    expect(headerTexts).toContain('Ataque')
    expect(headerTexts).toContain('Defensa')
  })

  it('shows error banner with retry when getStrength fails', async () => {
    vi.mocked(getStrength).mockRejectedValue(new Error('Server Error'))
    renderFuerzaTab()
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: /reintentar/i })).toBeInTheDocument()
  })
})
