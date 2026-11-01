import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import { AuthProvider } from './context/AuthContext.jsx'
import { ThemeProvider } from './context/ThemeContext.jsx'
import './tailwind.css'
import './styles.css'
import './polish.css'
import './savings.css'
import './reminders.css'
import './reports.css'
import './assistant.css'
import './theme.css'
ReactDOM.createRoot(document.getElementById('root')).render(<React.StrictMode><ThemeProvider><BrowserRouter><AuthProvider><App/></AuthProvider></BrowserRouter></ThemeProvider></React.StrictMode>)

if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}), { once: true })
}
