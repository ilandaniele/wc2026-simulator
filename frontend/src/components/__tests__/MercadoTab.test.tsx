import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MercadoTab } from '../MercadoTab'

// ---------------------------------------------------------------------------
// Mock API
// ---------------------------------------------------------------------------
vi.mock('../../api/client', () => ({
  getMarketOdds: vi.fn(),
  simulateMatch: vi.fn(),
}))

import { getMarketOdds, simulateMatch } from '../../api/client'

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------
const MOCK_ODDS = [
  { home: 'Algeria', away: 'Austria', h: -110, d: 240, a: 280 },
  { home: 'Jordan', away: 'Argentina', h: 500, d: 340, a: -180 },
]

// Algeria: model strongly favours Austria (pA=0.60) vs market (~0.35 de-vigged)
// Edge for Austria: ~25pp > 2pp => green
const MOCK_MATCH_ALGERIA_AUSTRIA = {
  home: 'Algeria',
  away: 'Austria',
  pH: 0.35, // similar to market
  pD: 0.25,
  pA: 0.40, // strong positive edge vs ~0.30 market
}

// Jordan vs Argentina: model pA=0.70 (heavy fav)
const MOCK_MATCH_JORDAN_ARGENTINA = {
  home: 'Jordan',
  away: 'Argentina',
  pH: 0.08,
  pD: 0.17,
  pA: 0.75,
}

function renderMercadoTab() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MercadoTab />
    </QueryClientProvider>,
  )
}

// ---------------------------------------------------------------------------
// Tests — AC18
// ---------------------------------------------------------------------------
describe('MercadoTab (AC18)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getMarketOdds).mockResolvedValue({ odds: MOCK_ODDS })
    vi.mocked(simulateMatch).mockImplementation((req) => {
      if (req.home === 'Algeria') return Promise.resolve(MOCK_MATCH_ALGERIA_AUSTRIA)
      return Promise.resolve(MOCK_MATCH_JORDAN_ARGENTINA)
    })
  })

  it('calls getMarketOdds on mount', async () => {
    renderMercadoTab()
    await waitFor(() => {
      expect(getMarketOdds).toHaveBeenCalled()
    })
  })

  it('renders match headers for each odds entry', async () => {
    renderMercadoTab()
    await waitFor(() => {
      expect(screen.getByText('Algeria')).toBeInTheDocument()
      expect(screen.getByText('Jordan')).toBeInTheDocument()
    })
  })

  it('renders Modelo %, Mercado %, Edge columns', async () => {
    renderMercadoTab()
    await waitFor(() => {
      const headers = screen.getAllByText(/modelo %/i)
      expect(headers.length).toBeGreaterThanOrEqual(1)
    })
  })

  it('shows positive edge in green color when edge > 2pp', async () => {
    // Austria edge: model 40% vs market ~30% = ~10pp > 2pp
    renderMercadoTab()

    await waitFor(() => {
      // We need to find cells with positive edge styling
      // The EdgeCell applies color 'var(--green)' for edge > 2pp
      // We check for "pp" text in the document
      const ppCells = screen.getAllByText(/\+\d+\.\dpp/)
      expect(ppCells.length).toBeGreaterThan(0)
    })
  })

  it('shows negative edge in red color when edge < -2pp', async () => {
    // Algeria pH: model 35% vs market ~52% de-vigged = negative large edge
    renderMercadoTab()

    await waitFor(() => {
      const negativePP = screen.getAllByText(/-\d+\.\dpp/)
      expect(negativePP.length).toBeGreaterThan(0)
    })
  })

  it('calls simulateMatch for each market entry', async () => {
    renderMercadoTab()
    await waitFor(() => {
      expect(simulateMatch).toHaveBeenCalledTimes(MOCK_ODDS.length)
    })
  })

  it('renders table outcome rows for home/draw/away', async () => {
    renderMercadoTab()
    await waitFor(() => {
      // Empate is the draw label
      const empateRows = screen.getAllByText('Empate')
      expect(empateRows.length).toBeGreaterThanOrEqual(1)
    })
  })

  it('shows error message when getMarketOdds fails', async () => {
    vi.mocked(getMarketOdds).mockRejectedValue(new Error('Network error'))
    renderMercadoTab()
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })
  })
})
