import { useState, useCallback, Suspense, lazy } from 'react'
import './App.css'
import {
  getInitialTheme,
  applyTheme,
  persistTheme,
  toggleTheme,
  type Theme,
} from './lib/theme'

// ---------------------------------------------------------------------------
// Lazy-loaded tab components (code-split per tab)
// ---------------------------------------------------------------------------
const CupTab = lazy(() =>
  import('./components/CupTab').then((m) => ({ default: m.CupTab })),
)
const HoyTab = lazy(() =>
  import('./components/HoyTab').then((m) => ({ default: m.HoyTab })),
)
const MercadoTab = lazy(() =>
  import('./components/MercadoTab').then((m) => ({ default: m.MercadoTab })),
)
const EnfrentamientoTab = lazy(() =>
  import('./components/EnfrentamientoTab').then((m) => ({ default: m.EnfrentamientoTab })),
)
const FuerzaTab = lazy(() =>
  import('./components/FuerzaTab').then((m) => ({ default: m.FuerzaTab })),
)

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
// Tab content fallback
// ---------------------------------------------------------------------------
function TabFallback() {
  return (
    <div aria-busy="true" style={{ padding: '2rem', color: 'var(--dim)', fontSize: '0.875rem' }}>
      Cargando…
    </div>
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

      {/* Tab panels */}
      <main className="tab-content">
        <div
          role="tabpanel"
          id="panel-cup"
          aria-labelledby="tab-cup"
          data-testid="tab-cup"
          hidden={activeTab !== 'cup'}
        >
          <Suspense fallback={<TabFallback />}>
            {activeTab === 'cup' && <CupTab />}
          </Suspense>
        </div>

        <div
          role="tabpanel"
          id="panel-hoy"
          aria-labelledby="tab-hoy"
          data-testid="tab-hoy"
          hidden={activeTab !== 'hoy'}
        >
          <Suspense fallback={<TabFallback />}>
            {activeTab === 'hoy' && <HoyTab />}
          </Suspense>
        </div>

        <div
          role="tabpanel"
          id="panel-mercado"
          aria-labelledby="tab-mercado"
          data-testid="tab-mercado"
          hidden={activeTab !== 'mercado'}
        >
          <Suspense fallback={<TabFallback />}>
            {activeTab === 'mercado' && <MercadoTab />}
          </Suspense>
        </div>

        <div
          role="tabpanel"
          id="panel-enfrentamiento"
          aria-labelledby="tab-enfrentamiento"
          data-testid="tab-enfrentamiento"
          hidden={activeTab !== 'enfrentamiento'}
        >
          <Suspense fallback={<TabFallback />}>
            {activeTab === 'enfrentamiento' && <EnfrentamientoTab />}
          </Suspense>
        </div>

        <div
          role="tabpanel"
          id="panel-fuerza"
          aria-labelledby="tab-fuerza"
          data-testid="tab-fuerza"
          hidden={activeTab !== 'fuerza'}
        >
          <Suspense fallback={<TabFallback />}>
            {activeTab === 'fuerza' && <FuerzaTab />}
          </Suspense>
        </div>
      </main>
    </div>
  )
}
