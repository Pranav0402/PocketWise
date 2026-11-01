import { createContext, useContext, useEffect, useState } from 'react'
import { request, token } from '../services/api'
const AuthContext = createContext(null)
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); const [ready, setReady] = useState(false)
  useEffect(() => {
    const legacy=localStorage.getItem('pocketwise_token')
    if (legacy && !sessionStorage.getItem('pocketwise_token')) sessionStorage.setItem('pocketwise_token', legacy)
    localStorage.removeItem('pocketwise_token')
    if (token()) request('/auth/me').then(setUser).catch(() => sessionStorage.removeItem('pocketwise_token')).finally(() => setReady(true)); else setReady(true)
  }, [])
  async function authenticate(path, data) { const result = await request(path, { method: 'POST', body: JSON.stringify(data) }); sessionStorage.setItem('pocketwise_token', result.access_token); localStorage.removeItem('pocketwise_token'); setUser(result.user); return result.user }
  function logout() { sessionStorage.removeItem('pocketwise_token'); localStorage.removeItem('pocketwise_token'); setUser(null) }
  return <AuthContext.Provider value={{ user, ready, authenticate, logout }}>{children}</AuthContext.Provider>
}
export const useAuth = () => useContext(AuthContext)
