import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { Wallet, LayoutDashboard, ArrowDownLeft, Receipt, Users, Target, PiggyBank, Bell, ChartNoAxesCombined, Sparkles, Settings, LogOut, Menu, PanelLeftClose, PanelLeftOpen, Moon, Sun } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
const links = [
  { to: '/', label: 'Overview', icon: LayoutDashboard }, { to: '/income', label: 'Income', icon: ArrowDownLeft }, { to: '/expenses', label: 'Expenses', icon: Receipt },
  { to: '/debts', label: 'Friends & debts', icon: Users }, { to: '/budgets', label: 'Budgets', icon: Target }, { to: '/savings', label: 'Savings goals', icon: PiggyBank },
  { to: '/reminders', label: 'Reminders', icon: Bell }, { to: '/reports', label: 'Reports', icon: ChartNoAxesCombined }, { to: '/assistant', label: 'AI Finance Assistant', icon: Sparkles }, { to: '/settings', label: 'Settings', icon: Settings },
]
export function Layout({ children }) {
  const { user, logout } = useAuth(); const { dark, toggleTheme } = useTheme(); const [collapsed, setCollapsed] = useState(false); const [mobile, setMobile] = useState(false); const navigate = useNavigate()
  function signOut() { logout(); navigate('/login') }
  return <div className={`app-shell ${dark ? 'theme-dark' : 'theme-light'}`}>
    <aside className={`sidebar ${collapsed ? 'collapsed' : ''} ${mobile ? 'mobile-open' : ''}`}>
      <div className="brand"><span className="brand-icon"><Wallet size={20}/></span>{!collapsed && <span><b>PocketWise</b><small>Spend Smart. Save More.</small></span>}<button className="collapse" onClick={() => setCollapsed(!collapsed)} aria-label="Collapse sidebar">{collapsed ? <PanelLeftOpen size={17}/> : <PanelLeftClose size={17}/>}</button></div>
      <div className="nav-label">MENU</div><nav>{links.map(({to,label,icon:Icon}) => <NavLink key={to} to={to} end={to==='/'} onClick={() => setMobile(false)} title={collapsed ? label : ''}><Icon size={18}/><span>{label}</span></NavLink>)}</nav>
      <div className="sidebar-bottom"><div className="user-avatar">{user?.name?.[0]?.toUpperCase()}</div>{!collapsed && <div className="user-details"><b>{user?.name}</b><small>{user?.email}</small></div>}<button className="icon-button" onClick={signOut} aria-label="Log out" title="Log out"><LogOut size={17}/></button></div>
    </aside>
    {mobile && <button className="scrim" onClick={()=>setMobile(false)} aria-label="Close navigation"/>}
    <main className="main-area"><header className="topbar"><button className="icon-button mobile-menu" onClick={()=>setMobile(true)} aria-label="Open navigation"><Menu/></button><div className="breadcrumb">Workspace <span>/</span> <b>PocketWise</b></div><div className="topbar-right"><button className="icon-button theme-mode-toggle" onClick={toggleTheme} aria-label={`Switch to ${dark ? 'light' : 'dark'} mode`} title={`Switch to ${dark ? 'light' : 'dark'} mode`}>{dark ? <Sun size={17}/> : <Moon size={17}/>}</button><span className="secure"><span/> Your finances, in your hands</span><div className="user-avatar small">{user?.name?.[0]?.toUpperCase()}</div></div></header><div className="page-content">{children || <Outlet/>}</div></main>
  </div>
}
