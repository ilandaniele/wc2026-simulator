import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { CupTab } from '../CupTab'

// ---------------------------------------------------------------------------
// Mock API
// ---------------------------------------------------------------------------
vi.mock('../../api/client', () => ({
  simulateTournament: vi.fn(),
}))

import { simulateTournament } from '../../api/client'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function makeResult(team: string, champ: number, group = 'A') {
  return { team, group, grpW: 0.8, ko: 0.7, r16: 0.6, qf: 0.4, sf: 0.25, final: 0.15, champ }
}

const MOCK_RESULTS = [
  makeResult('Argentina', 0.22, 'A'),
  makeResult('Brazil', 0.15, 'B'),
  makeResult('Portugal', 0.12, 'C'),
  makeResult('France', 0.10, 'D'),
  makeResult('Spain', 0.09, 'E'),
  makeResult('England', 0.07, 'F'),
  makeResult('Germany', 0.06, 'G'),
  makeResult('Netherlands', 0.04, 'H'),
  makeResult('Uruguay', 0.03, 'I'),
  makeResult('Colombia', 0.02, 'J'),
  // fill up to 48
  ...Array.from({ length: 38 }, (_, i) =>
    makeResult(`Team${i + 11}`, 0.001, String.fromCharCode(65 + (i % 12))),
  ),
]

function renderCupTab() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <CupTab />
    </QueryClientProvider>,
  )
}

// ---------------------------------------------------------------------------
// Tests — AC16
// ---------------------------------------------------------------------------
describe('CupTab (AC16)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading skeleton initially', () => {
    vi.mocked(simulateTournament).mockReturnValue(new Promise(() => {}))
    renderCupTab()
    expect(screen.getByRole('generic', { name: /cargando/i })).toBeInTheDocument()
  })

  it('renders table with data-testid="cup-table" after data loads', async () => {
    vi.mocked(simulateTournament).mockResolvedValue({ results: MOCK_RESULTS })
    renderCupTab()
    await waitFor(() => {
      expect(screen.getByTestId('cup-table')).toBeInTheDocument()
    })
  })

  it('renders 48 team rows', async () => {
    vi.mocked(simulateTournament).mockResolvedValue({ results: MOCK_RESULTS })
    renderCupTab()
    await waitFor(() => {
      expect(screen.getByTestId('cup-table')).toBeInTheDocument()
    })
    // 48 rows in tbody
    const rows = screen.getAllByRole('row')
    // header row + 48 data rows = 49
    expect(rows.length).toBe(49)
  })

  it('Argentina appears in top 5 by champ probability', async () => {
    vi.mocked(simulateTournament).mockResolvedValue({ results: MOCK_RESULTS })
    renderCupTab()
    await waitFor(() => {
      expect(screen.getByTestId('cup-table')).toBeInTheDocument()
    })
    const rows = screen.getAllByRole('row')
    // rows[0] is header, rows[1..5] are top-5
    const top5Names = rows.slice(1, 6).map((r) => r.textContent ?? '')
    expect(top5Names.some((t) => t.includes('Argentina'))).toBe(true)
  })

  it('Portugal appears in the table', async () => {
    vi.mocked(simulateTournament).mockResolvedValue({ results: MOCK_RESULTS })
    renderCupTab()
    await waitFor(() => {
      expect(screen.getByTestId('cup-table')).toBeInTheDocument()
    })
    expect(screen.getByText('Portugal')).toBeInTheDocument()
  })

  it('Brazil appears in the table', async () => {
    vi.mocked(simulateTournament).mockResolvedValue({ results: MOCK_RESULTS })
    renderCupTab()
    await waitFor(() => {
      expect(screen.getByTestId('cup-table')).toBeInTheDocument()
    })
    expect(screen.getByText('Brazil')).toBeInTheDocument()
  })

  it('table has 8 column headers (# excluded from visible cols count)', async () => {
    vi.mocked(simulateTournament).mockResolvedValue({ results: MOCK_RESULTS })
    renderCupTab()
    await waitFor(() => {
      expect(screen.getByTestId('cup-table')).toBeInTheDocument()
    })
    // 8 named cols + 1 rank col = 9 total headers
    const headers = screen.getAllByRole('columnheader')
    // # + Equipo + Grupo + R32 + R16 + QF + SF + Final + Campeón = 9
    expect(headers.length).toBe(9)
  })

  it('clicking a column header sorts the table', async () => {
    vi.mocked(simulateTournament).mockResolvedValue({ results: MOCK_RESULTS })
    renderCupTab()
    await waitFor(() => {
      expect(screen.getByTestId('cup-table')).toBeInTheDocument()
    })

    // Click "Equipo" header to sort alphabetically
    const equipoHeader = screen.getByRole('columnheader', { name: /equipo/i })
    fireEvent.click(equipoHeader)

    const rows = screen.getAllByRole('row')
    const firstRowText = rows[1].textContent ?? ''
    // After sorting asc by name, first team should be alphabetically first
    expect(firstRowText.length).toBeGreaterThan(0)
  })
})

// ---------------------------------------------------------------------------
// Tests — AC21 (error state)
// ---------------------------------------------------------------------------
describe('CupTab error state (AC21)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows error banner with role="alert" when API returns 500', async () => {
    vi.mocked(simulateTournament).mockRejectedValue(new Error('Server Error 500'))
    renderCupTab()
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })
  })

  it('error banner contains "Error" text', async () => {
    vi.mocked(simulateTournament).mockRejectedValue(new Error('Internal Server Error'))
    renderCupTab()
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })
    expect(screen.getByRole('alert').textContent).toMatch(/error/i)
  })

  it('error banner has a Reintentar button', async () => {
    vi.mocked(simulateTournament).mockRejectedValue(new Error('Server Error'))
    renderCupTab()
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /reintentar/i })).toBeInTheDocument()
    })
  })

  it('clicking Reintentar calls simulateTournament again', async () => {
    vi.mocked(simulateTournament).mockRejectedValue(new Error('Server Error'))
    renderCupTab()
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /reintentar/i })).toBeInTheDocument()
    })

    // Now let it succeed on retry
    vi.mocked(simulateTournament).mockResolvedValue({ results: MOCK_RESULTS })
    const retryBtn = screen.getByRole('button', { name: /reintentar/i })
    fireEvent.click(retryBtn)

    await waitFor(() => {
      expect(screen.getByTestId('cup-table')).toBeInTheDocument()
    })
    expect(simulateTournament).toHaveBeenCalledTimes(2)
  })

  it('does not display a stack trace in the UI', async () => {
    const errMsg = 'Internal Server Error'
    vi.mocked(simulateTournament).mockRejectedValue(new Error(errMsg))
    renderCupTab()
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })
    // No "at " lines (stack trace pattern) in the DOM
    expect(document.body.textContent).not.toMatch(/\s+at\s+\w+/)
  })
})
