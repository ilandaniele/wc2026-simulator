import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import App from './App'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

function renderApp() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={qc}>
      <App />
    </QueryClientProvider>,
  )
}

describe('App shell', () => {
  beforeEach(() => {
    // Reset URL to base before each test
    window.history.pushState({}, '', '/')
    localStorage.clear()
    document.documentElement.className = ''
  })

  it('renders tab bar with 5 tabs', () => {
    renderApp()
    const tabs = screen.getAllByRole('tab')
    expect(tabs).toHaveLength(5)
    expect(tabs[0]).toHaveTextContent('Copa')
    expect(tabs[1]).toHaveTextContent('Hoy')
    expect(tabs[2]).toHaveTextContent('Mercado')
    expect(tabs[3]).toHaveTextContent('Enfrentamiento')
    expect(tabs[4]).toHaveTextContent('Fuerza')
  })

  it('renders header with app title', () => {
    renderApp()
    expect(screen.getByText(/WC2026/i)).toBeInTheDocument()
  })

  it('cup tab is active by default', () => {
    renderApp()
    const cupTab = screen.getByRole('tab', { name: 'Copa' })
    expect(cupTab).toHaveAttribute('aria-selected', 'true')
  })

  it('clicking a tab updates URL query param', () => {
    renderApp()
    const hoyTab = screen.getByRole('tab', { name: 'Hoy' })
    fireEvent.click(hoyTab)
    expect(window.location.search).toContain('tab=hoy')
  })

  it('clicking Fuerza tab sets tab=fuerza in URL', () => {
    renderApp()
    const fuerzaTab = screen.getByRole('tab', { name: 'Fuerza' })
    fireEvent.click(fuerzaTab)
    expect(window.location.search).toContain('tab=fuerza')
  })

  it('each tab panel has data-testid matching tab-{id}', () => {
    renderApp()
    expect(screen.getByTestId('tab-cup')).toBeInTheDocument()
    expect(screen.getByTestId('tab-hoy')).toBeInTheDocument()
    expect(screen.getByTestId('tab-mercado')).toBeInTheDocument()
    expect(screen.getByTestId('tab-enfrentamiento')).toBeInTheDocument()
    expect(screen.getByTestId('tab-fuerza')).toBeInTheDocument()
  })
})

describe('Dark mode toggle (AC22)', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/')
    localStorage.clear()
    document.documentElement.className = ''
  })

  it('theme toggle button is rendered', () => {
    renderApp()
    const btn = screen.getByRole('button', { name: /modo oscuro|modo claro/i })
    expect(btn).toBeInTheDocument()
  })

  it('clicking moon toggle sets localStorage["wc2026.theme"] == "dark"', () => {
    renderApp()
    // Start in light mode (no stored theme, no dark class)
    const toggleBtn = screen.getByRole('button', { name: /Cambiar a modo oscuro/i })
    fireEvent.click(toggleBtn)
    expect(localStorage.getItem('wc2026.theme')).toBe('dark')
  })

  it('clicking toggle adds .dark class to <html>', () => {
    renderApp()
    const toggleBtn = screen.getByRole('button', { name: /Cambiar a modo oscuro/i })
    fireEvent.click(toggleBtn)
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })

  it('clicking toggle twice restores light mode and removes .dark class', () => {
    renderApp()
    const toggleBtn = screen.getByRole('button', { name: /Cambiar a modo oscuro/i })
    fireEvent.click(toggleBtn) // → dark
    const lightBtn = screen.getByRole('button', { name: /Cambiar a modo claro/i })
    fireEvent.click(lightBtn) // → light
    expect(localStorage.getItem('wc2026.theme')).toBe('light')
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('reads dark mode from localStorage on mount and applies .dark class', () => {
    // Simulate a prior session that saved dark mode
    localStorage.setItem('wc2026.theme', 'dark')
    document.documentElement.classList.add('dark') // FOUC guard sets this
    renderApp()
    // The app should read dark from storage and keep the class
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })

  it('toggle button label changes after switching to dark mode', () => {
    renderApp()
    const moonBtn = screen.getByRole('button', { name: /Cambiar a modo oscuro/i })
    fireEvent.click(moonBtn)
    // Now in dark mode, button should say "Cambiar a modo claro"
    expect(
      screen.getByRole('button', { name: /Cambiar a modo claro/i }),
    ).toBeInTheDocument()
  })
})

describe('Theme persistence — simulating reload (AC22)', () => {
  it('after clicking dark toggle, stored theme persists across re-render', () => {
    const { unmount } = renderApp()
    const toggleBtn = screen.getByRole('button', { name: /Cambiar a modo oscuro/i })
    fireEvent.click(toggleBtn)
    expect(localStorage.getItem('wc2026.theme')).toBe('dark')
    unmount()

    // Simulate reload: document class is set by FOUC guard based on localStorage
    document.documentElement.classList.add('dark')

    // Re-render — App should read localStorage and start in dark mode
    renderApp()
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(localStorage.getItem('wc2026.theme')).toBe('dark')
  })
})

describe('Tab URL integration', () => {
  it('reads active tab from URL on mount', () => {
    window.history.pushState({}, '', '/?tab=mercado')
    renderApp()
    const mercadoTab = screen.getByRole('tab', { name: 'Mercado' })
    expect(mercadoTab).toHaveAttribute('aria-selected', 'true')
  })

  it('falls back to cup tab for unknown tab param', () => {
    window.history.pushState({}, '', '/?tab=unknown')
    renderApp()
    const cupTab = screen.getByRole('tab', { name: 'Copa' })
    expect(cupTab).toHaveAttribute('aria-selected', 'true')
  })
})

// Suppress console.error noise from React in tests
beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => {})
})
