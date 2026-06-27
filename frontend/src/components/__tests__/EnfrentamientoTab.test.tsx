import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { EnfrentamientoTab } from '../EnfrentamientoTab'

// ---------------------------------------------------------------------------
// Mock API
// ---------------------------------------------------------------------------
vi.mock('../../api/client', () => ({
  getTeams: vi.fn(),
  simulateH2H: vi.fn(),
}))

import { getTeams, simulateH2H } from '../../api/client'

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------
const MOCK_TEAMS = Array.from({ length: 48 }, (_, i) =>
  i === 0 ? 'Spain' : i === 1 ? 'Germany' : `Team${i}`,
)

const MOCK_H2H = {
  home: 'Spain',
  away: 'Germany',
  ci_lower: 0.38,
  ci_median: 0.52,
  ci_upper: 0.66,
  top_scorelines: [
    { h: 2, a: 1, prob: 0.12 },
    { h: 1, a: 0, prob: 0.10 },
    { h: 1, a: 1, prob: 0.09 },
    { h: 2, a: 0, prob: 0.08 },
    { h: 0, a: 1, prob: 0.07 },
    { h: 3, a: 1, prob: 0.06 },
  ],
}

function renderEnfrentamientoTab() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <EnfrentamientoTab />
    </QueryClientProvider>,
  )
}

// ---------------------------------------------------------------------------
// Tests — AC19
// ---------------------------------------------------------------------------
describe('EnfrentamientoTab (AC19)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getTeams).mockResolvedValue({ teams: MOCK_TEAMS })
    vi.mocked(simulateH2H).mockResolvedValue(MOCK_H2H)
  })

  it('renders Local and Visitante selects', () => {
    renderEnfrentamientoTab()
    expect(screen.getByLabelText(/local/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/visitante/i)).toBeInTheDocument()
  })

  it('renders Simular button', () => {
    renderEnfrentamientoTab()
    expect(screen.getByRole('button', { name: /simular/i })).toBeInTheDocument()
  })

  it('renders knockout checkbox', () => {
    renderEnfrentamientoTab()
    expect(screen.getByRole('checkbox')).toBeInTheDocument()
  })

  it('default home is Spain and away is Germany', async () => {
    renderEnfrentamientoTab()
    // The selects default to Spain/Germany — they render as options
    await waitFor(() => {
      const homeSelect = screen.getByLabelText(/local/i) as HTMLSelectElement
      expect(homeSelect.value).toBe('Spain')
    })
    const awaySelect = screen.getByLabelText(/visitante/i) as HTMLSelectElement
    expect(awaySelect.value).toBe('Germany')
  })

  it('clicking Simular calls simulateH2H', async () => {
    renderEnfrentamientoTab()
    const btn = screen.getByRole('button', { name: /simular/i })
    fireEvent.click(btn)
    await waitFor(() => {
      expect(simulateH2H).toHaveBeenCalledWith({
        home: 'Spain',
        away: 'Germany',
        knockout: false,
        top_k: 6,
      })
    })
  })

  it('shows CI bar with data-testid="h2h-result" after simulation', async () => {
    renderEnfrentamientoTab()
    const btn = screen.getByRole('button', { name: /simular/i })
    fireEvent.click(btn)
    await waitFor(() => {
      expect(screen.getByTestId('h2h-result')).toBeInTheDocument()
    })
  })

  it('displays ci_lower, ci_median, ci_upper values', async () => {
    renderEnfrentamientoTab()
    const btn = screen.getByRole('button', { name: /simular/i })
    fireEvent.click(btn)
    await waitFor(() => {
      expect(screen.getByTestId('h2h-result')).toBeInTheDocument()
    })
    const result = screen.getByTestId('h2h-result')
    // ci_lower = 0.38 → 38.0%, ci_median = 0.52 → 52.0%, ci_upper = 0.66 → 66.0%
    expect(result.textContent).toMatch(/38\.0%/)
    expect(result.textContent).toMatch(/52\.0%/)
    expect(result.textContent).toMatch(/66\.0%/)
  })

  it('displays top scorelines after simulation', async () => {
    renderEnfrentamientoTab()
    const btn = screen.getByRole('button', { name: /simular/i })
    fireEvent.click(btn)
    await waitFor(() => {
      expect(screen.getByTestId('h2h-result')).toBeInTheDocument()
    })
    // Top scoreline is 2-1
    expect(screen.getByTestId('h2h-result').textContent).toMatch(/2–1/)
  })

  it('sends knockout=true when checkbox is checked', async () => {
    renderEnfrentamientoTab()
    const checkbox = screen.getByRole('checkbox')
    fireEvent.click(checkbox)
    const btn = screen.getByRole('button', { name: /simular/i })
    fireEvent.click(btn)
    await waitFor(() => {
      expect(simulateH2H).toHaveBeenCalledWith(
        expect.objectContaining({ knockout: true }),
      )
    })
  })

  it('populates selects with team list from /teams', async () => {
    renderEnfrentamientoTab()
    await waitFor(() => {
      const homeSelect = screen.getByLabelText(/local/i) as HTMLSelectElement
      const options = Array.from(homeSelect.options).map((o) => o.value)
      expect(options).toContain('Spain')
      expect(options).toContain('Germany')
    })
  })
})
