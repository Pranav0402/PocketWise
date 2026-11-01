import { createContext, useContext, useEffect, useMemo, useState } from 'react'

const ThemeContext = createContext(null)
const STORAGE_KEY = 'pocketwise_theme'

function loadTheme() {
  try { return localStorage.getItem(STORAGE_KEY) === 'dark' ? 'dark' : 'light' }
  catch { return 'light' }
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(loadTheme)
  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, theme) } catch { /* Storage can be disabled. */ }
  }, [theme])
  const value = useMemo(() => ({ theme, dark: theme === 'dark', toggleTheme: () => setTheme(value => value === 'dark' ? 'light' : 'dark') }), [theme])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (!context) throw new Error('useTheme must be used within ThemeProvider')
  return context
}
