import { useState, useCallback } from 'react'
import './App.css'
import {
  getInitialTheme,
  applyTheme,
  persistTheme,
  toggleTheme,
  type Theme,
} from './lib/theme'

// ---------------------------------------------------------------------------
// Tab definitions
// ---------------------------------------------------------------------------

const TABS = [
  { id: 'cup', label: 'Copa' },
  { id: 'hoy', label: 'Hoy' },
  { id: 'mercado', label: 'Mercado' },
  { id: 'enfrentamiento', label: 'Enfrentamiento' },
  { id: 'fuerza', label: 'Fuerza' },
] as const

type TabId = (typeof TABS)[number]['id']

const VALID_TABS = new Set<string>(TABS.map((t) => t.id))

function getTabFromURL(): TabId {
  const params = new URLSearchParams(window.location.search)
  const tab = params.get('tab')
  if (tab && VALID_TABS.has(tab)) return tab as TabId
  return 'cup'
}

function setTabInURL(tab: TabId): void {
  const url = new URL(window.location.href)
  url.searchParams.set('tab', tab)
  window.history.pushState({}, '', url)
}

// ---------------------------------------------------------------------------
// ThemeToggle
// ---------------------------------------------------------------------------

interface ThemeToggleProps {
  theme: Theme
  onToggle: () => void
}

function ThemeToggle({ theme, onToggle }: ThemeToggleProps) {
  return (
    <button
      type="button"
      className="theme-toggle-btn"
      onClick={onToggle}
      aria-label={
        theme === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'
      }
    >
      {theme === 'dark' ? '☀' : '🌙'}
    </button>
  )
}

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

export default function App() {
  const [theme, setTheme] = useState<Theme>(() => {
    const initial = getInitialTheme()
    applyTheme(initial)
    return initial
  })

  const [activeTab, setActiveTab] = useState<TabId>(getTabFromURL)

  const handleToggleTheme = useCallback(() => {
    setTheme((prev) => {
      const next = toggleTheme(prev)
      applyTheme(next)
      persistTheme(next)
      return next
    })
  }, [])

  const handleTabChange = useCallback((tab: TabId) => {
    setActiveTab(tab)
    setTabInURL(tab)
  }, [])

  return (
    <div className="app-shell">
      {/* Header */}
      <header className="app-header">
        <span className="app-title">WC2026 &middot; Simulador</span>
        <ThemeToggle theme={theme} onToggle={handleToggleTheme} />
      </header>

      {/* Tab navigation */}
      <nav aria-label="Secciones" className="tab-nav" role="tablist">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            aria-controls={`panel-${tab.id}`}
            id={`tab-${tab.id}`}
            className="tab-btn"
            onClick={() => handleTabChange(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {/* Tab panels — placeholders for W5 */}
      <main className="tab-content">
        {TABS.map((tab) => (
          <div
            key={tab.id}
            role="tabpanel"
            id={`panel-${tab.id}`}
            aria-labelledby={`tab-${tab.id}`}
            data-testid={`tab-${tab.id}`}
            hidden={activeTab !== tab.id}
          >
            {/* W5 will replace this placeholder */}
            <p style={{ color: 'var(--dim)', fontSize: '0.875rem' }}>
              {tab.label} — contenido pendiente (W5)
            </p>
          </div>
        ))}
      </main>
    </div>
  )
}
