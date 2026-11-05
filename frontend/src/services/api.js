export const API_BASE = (import.meta.env?.VITE_API_URL || '/api').replace(/\/$/, '')
const TOKEN_KEY = 'pocketwise_token'
export function token() { return sessionStorage.getItem(TOKEN_KEY) || localStorage.getItem(TOKEN_KEY) }
export async function request(path, options = {}) {
  const { timeoutMs, ...fetchOptions } = options
  const controller = new AbortController()
  const timeout = timeoutMs ? setTimeout(() => controller.abort(), timeoutMs) : null
  try {
    const res = await fetch(`${API_BASE}${path}`, { ...fetchOptions, signal: fetchOptions.signal || controller.signal, headers: { 'Content-Type': 'application/json', ...(token() ? { Authorization: `Bearer ${token()}` } : {}), ...fetchOptions.headers } })
    if (res.status === 204) return null
    const body = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(body.detail || 'Something went wrong. Please try again.')
    return body
  } catch (error) {
    if (controller.signal.aborted) throw new Error('This is taking longer than expected. Please try again.')
    if (error instanceof TypeError) throw new Error('Unable to connect to PocketWise. Check your internet connection and try again.')
    throw error
  } finally {
    if (timeout) clearTimeout(timeout)
  }
}
export const money = (n = 0) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n)
export const today = () => new Intl.DateTimeFormat('en-CA', { year: 'numeric', month: '2-digit', day: '2-digit', timeZone: 'Asia/Kolkata' }).format(new Date())
export const formatDate = (value) => value ? new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'Asia/Kolkata' }).format(new Date(`${value.slice(0,10)}T00:00:00+05:30`)) : '—'
