import '@testing-library/jest-dom'

// jsdom does not implement window.matchMedia — mock it
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
})

// Reset localStorage before each test to avoid state leakage
beforeEach(() => {
  localStorage.clear()
})

// Reset document.documentElement classes before each test
beforeEach(() => {
  document.documentElement.className = ''
})
