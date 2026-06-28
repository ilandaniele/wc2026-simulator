import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { HoyTab } from '../HoyTab'

// ---------------------------------------------------------------------------
// Mock API
// ---------------------------------------------------------------------------
vi.mock('../../api/client', () => ({
  simulateMatch: vi.fn(),
  simulateModal: vi.fn(),
}))

import { simulateMatch, simulateModal } from '../../api/client'

// ---------------------------------------------------------------------------
// Mock data helpers
// ---------------------------------------------------------------------------
function makeMatchResponse(home: string, away: string, pH = 0.45, pD = 0.28, pA = 0.27) {
  return { home, away, pH, pD, pA }
}

function makeModalResponse(home: string, away: string) {
  return {
    home,
    away,
    scorelines: [
      { h: 1, a: 0, prob: 0.14 },
      { h: 2, a: 1, prob: 0.10 },
      { h: 0, a: 0, prob: 0.09 },
    ],
  }
}

function renderHoyTab() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <HoyTab />
    </QueryClientProvider>,
  )
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe('HoyTab — multi-day schedule', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(simulateMatch).mockImplementation((req) =>
      Promise.resolve(makeMatchResponse(req.home, req.away)),
    )
    vi.mocked(simulateModal).mockImplementation((req) =>
      Promise.resolve(makeModalResponse(req.home, req.away)),
    )
  })

  it('renders date section headers for multiple days', () => {
    renderHoyTab()
    // Multiple match-day headings should be present
    expect(screen.getByText(/jornada final/i)).toBeInTheDocument()
  })

  it('Algeria vs Austria shows as a result (score 3 – 3)', () => {
    renderHoyTab()
    // Result cards show the score inline
    expect(screen.getByText(/3 – 3/)).toBeInTheDocument()
  })

  it('Jordan vs Argentina result is shown (0 – 2)', () => {
    renderHoyTab()
    expect(screen.getByText(/0 – 2/)).toBeInTheDocument()
  })

  it('Canada vs South Africa result is shown (1 – 0)', () => {
    renderHoyTab()
    expect(screen.getByText(/1 – 0/)).toBeInTheDocument()
  })

  it('renders prediction card for Brazil vs Japan (upcoming)', async () => {
    renderHoyTab()
    await waitFor(() => {
      expect(screen.getByTestId('match-card-Brazil-Japan')).toBeInTheDocument()
    })
  })

  it('renders prediction card for France vs Sweden (upcoming)', async () => {
    renderHoyTab()
    await waitFor(() => {
      expect(screen.getByTestId('match-card-France-Sweden')).toBeInTheDocument()
    })
  })

  it('prediction cards show top scoreline from modal', async () => {
    renderHoyTab()
    await waitFor(() => {
      const scorelines = screen.getAllByText(/1–0/)
      expect(scorelines.length).toBeGreaterThanOrEqual(1)
    })
  })

  it('simulateMatch is called for upcoming matches', async () => {
    renderHoyTab()
    await waitFor(() => {
      // There are upcoming matches that need predictions
      expect(simulateMatch).toHaveBeenCalled()
    })
  })

  it('simulateModal is called for upcoming matches', async () => {
    renderHoyTab()
    await waitFor(() => {
      expect(simulateModal).toHaveBeenCalled()
    })
  })

  it('probabilities round to 100 for a Brazil-Japan card (45+28+27=100)', async () => {
    renderHoyTab()
    await waitFor(() => {
      expect(screen.getByTestId('match-card-Brazil-Japan')).toBeInTheDocument()
    })
    const card = screen.getByTestId('match-card-Brazil-Japan')
    expect(card.textContent).toMatch(/45%/)
    expect(card.textContent).toMatch(/28%/)
    expect(card.textContent).toMatch(/27%/)
  })
})
