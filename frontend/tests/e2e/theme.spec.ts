import { test, expect } from '@playwright/test'

test.describe('Theme toggle (AC22)', () => {
  test.beforeEach(async ({ page }) => {
    // Clear localStorage before each test to start in light mode
    await page.goto('/')
    await page.evaluate(() => localStorage.clear())
    await page.reload()
  })

  test('moon toggle click sets localStorage["wc2026.theme"] == "dark"', async ({
    page,
  }) => {
    await page.goto('/')

    // Find and click the moon/dark-mode toggle
    const toggleBtn = page.getByRole('button', { name: /Cambiar a modo oscuro/i })
    await expect(toggleBtn).toBeVisible()
    await toggleBtn.click()

    // Verify localStorage
    const storedTheme = await page.evaluate(() =>
      localStorage.getItem('wc2026.theme'),
    )
    expect(storedTheme).toBe('dark')
  })

  test('after clicking toggle, .dark class is on <html>', async ({ page }) => {
    await page.goto('/')
    const toggleBtn = page.getByRole('button', { name: /Cambiar a modo oscuro/i })
    await toggleBtn.click()

    const hasDark = await page.evaluate(() =>
      document.documentElement.classList.contains('dark'),
    )
    expect(hasDark).toBe(true)
  })

  test('reload after dark mode persists theme (AC22 — core assertion)', async ({
    page,
  }) => {
    // Step 1: Navigate and enable dark mode
    await page.goto('/')
    const toggleBtn = page.getByRole('button', { name: /Cambiar a modo oscuro/i })
    await toggleBtn.click()

    // Verify dark is stored
    const stored = await page.evaluate(() => localStorage.getItem('wc2026.theme'))
    expect(stored).toBe('dark')

    // Step 2: Reload and verify dark mode is still applied
    await page.reload()

    const hasDark = await page.evaluate(() =>
      document.documentElement.classList.contains('dark'),
    )
    expect(hasDark).toBe(true)

    // Verify localStorage still says dark
    const storedAfterReload = await page.evaluate(() =>
      localStorage.getItem('wc2026.theme'),
    )
    expect(storedAfterReload).toBe('dark')
  })

  test('toggle from dark back to light removes .dark class', async ({ page }) => {
    await page.goto('/')
    // Enable dark
    const moonBtn = page.getByRole('button', { name: /Cambiar a modo oscuro/i })
    await moonBtn.click()

    // Click sun button to go back to light
    const sunBtn = page.getByRole('button', { name: /Cambiar a modo claro/i })
    await sunBtn.click()

    const hasDark = await page.evaluate(() =>
      document.documentElement.classList.contains('dark'),
    )
    expect(hasDark).toBe(false)

    const stored = await page.evaluate(() => localStorage.getItem('wc2026.theme'))
    expect(stored).toBe('light')
  })
})

test.describe('Tab navigation', () => {
  test('renders 5 tabs', async ({ page }) => {
    await page.goto('/')
    const tabs = page.getByRole('tab')
    await expect(tabs).toHaveCount(5)
  })

  test('Cup tab is selected by default', async ({ page }) => {
    await page.goto('/')
    const cupTab = page.getByRole('tab', { name: 'Copa' })
    await expect(cupTab).toHaveAttribute('aria-selected', 'true')
  })

  test('clicking Hoy tab updates URL to ?tab=hoy', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('tab', { name: 'Hoy' }).click()
    await expect(page).toHaveURL(/\?tab=hoy/)
  })
})
