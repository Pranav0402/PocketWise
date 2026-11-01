import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowDownRight, ArrowLeft, ArrowUpRight, CalendarDays, Check, Clock3, Plus, Search, Users, Wallet, Pencil, Trash2, Moon, Sun } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { FormField, Modal } from '../components/Forms'
import { formatDate, request, today } from '../services/api'
import { useTheme } from '../context/ThemeContext'

const blankFriend = { name: '', nickname: '', phone: '', email: '', notes: '' }
const blankDebt = { friend_id: '', direction: 'borrowed', amount: '', date: today(), due_date: '', description: '' }
const blankRepayment = { amount: '', date: today(), notes: '' }
const STATUS = { unpaid: 'Unpaid', partial: 'Partially paid', fully_paid: 'Fully paid', overdue: 'Overdue' }
const COLORS = ['#10b981', '#fb7185', '#f59e0b', '#8b5cf6']
const money = value => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value) || 0)

function Field({ label, children }) { return <FormField label={label}>{children}</FormField> }
function Metric({ label, value, icon: Icon, tint }) { return <article className="stat-card"><div className={`stat-icon ${tint}`}><Icon size={18}/></div><div className="stat-label">{label}</div><div className="stat-value">{money(value)}</div></article> }
function Notice({ error, success }) { return <>{error && <div className="alert error" role="alert">{error}</div>}{success && <div className="alert success" role="status">{success}</div>}</> }
function Status({ value }) { return <span className={`pill debt-status ${value}`}>{STATUS[value] || value}</span> }

export default function FriendsDebts() {
  const { dark, toggleTheme } = useTheme()
  const { friendId, debtId } = useParams()
  const navigate = useNavigate()
  const [friends, setFriends] = useState([]), [debts, setDebts] = useState([]), [summary, setSummary] = useState(null)
  const [friend, setFriend] = useState(null), [detailDebt, setDetailDebt] = useState(null)
  const [busy, setBusy] = useState(false), [loading, setLoading] = useState(true)
  const [error, setError] = useState(''), [success, setSuccess] = useState('')
  const [query, setQuery] = useState(''), [month, setMonth] = useState(''), [year, setYear] = useState(''), [friendFilter, setFriendFilter] = useState(''), [direction, setDirection] = useState(''), [status, setStatus] = useState('')
  const [dialog, setDialog] = useState(null), [editing, setEditing] = useState(null), [repayments, setRepayments] = useState([])

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const filters = new URLSearchParams()
      if (month) filters.set('month', month); else if (year) filters.set('year', year)
      if (friendFilter) filters.set('friend_id', friendFilter)
      if (direction) filters.set('direction', direction)
      if (status) filters.set('status', status)
      const suffix = filters.size ? `?${filters}` : ''
      const [f, d, s] = await Promise.all([request(`/friends${query.trim() ? `?search=${encodeURIComponent(query.trim())}` : ''}`), request('/debts'), request(`/debts/summary${suffix}`)])
      setFriends(f); setDebts(d); setSummary(s)
    } catch (e) { setError(e.message) } finally { setLoading(false) }
  }, [query, month, year, friendFilter, direction, status])
  useEffect(() => { load() }, [load])
  useEffect(() => {
    if (!friendId) { setFriend(null); return }
    let active = true
    setLoading(true); request(`/friends/${friendId}`).then(x => { if (active) { setFriend(x); setError('') } }).catch(e => { if (active) setError(e.message) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [friendId])
  useEffect(() => {
    if (!debtId) { setDetailDebt(null); if (dialog === 'detail') setDialog(null); return }
    let active = true
    setLoading(true); request(`/debts/${debtId}`).then(x => { if (active) { setDetailDebt(x); setRepayments(x.repayments || []); setDialog('detail'); setError('') } }).catch(e => { if (active) setError(e.message) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [debtId])

  const selectedDebts = useMemo(() => debts.filter(d => (!friendId || d.friend_id === Number(friendId)) && (!friendFilter || d.friend_id === Number(friendFilter)) && (!month || d.date?.slice(0, 7) === month) && (!year || d.date?.slice(0, 4) === year) && (!direction || d.direction === direction) && (!status || d.status === status) && (!query.trim() || `${d.friend_name} ${d.description}`.toLowerCase().includes(query.toLowerCase()))), [debts, friendId, friendFilter, month, year, direction, status, query])
  const paidRows = summary?.recent_repayments || []
  function flash(message) { setSuccess(message); window.setTimeout(() => setSuccess(''), 3500) }
  async function submitFriend(e) {
    e.preventDefault(); setBusy(true); setError('')
    const f = new FormData(e.currentTarget), body = Object.fromEntries(['name','nickname','phone','email','notes'].map(k => [k, String(f.get(k) || '').trim() || null]))
    body.notes ||= ''
    try { await request(editing ? `/friends/${editing.id}` : '/friends', { method: editing ? 'PUT' : 'POST', body: JSON.stringify(body) }); setDialog(null); setEditing(null); flash(editing ? 'Friend details updated.' : 'Friend added.'); await load(); if (friendId) setFriend(await request(`/friends/${friendId}`)) }
    catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  async function submitDebt(e) {
    e.preventDefault(); setBusy(true); setError('')
    const f = new FormData(e.currentTarget), body = { friend_id: Number(f.get('friend_id')), direction: f.get('direction'), amount: String(f.get('amount')), date: f.get('date'), due_date: f.get('due_date') || null, description: String(f.get('description') || '').trim() }
    try { await request(editing ? `/debts/${editing.id}` : '/debts', { method: editing ? 'PUT' : 'POST', body: JSON.stringify(body) }); setDialog(null); setEditing(null); flash(editing ? 'Record updated.' : 'Borrowing/lending record saved.'); await load(); if (friendId) setFriend(await request(`/friends/${friendId}`)) }
    catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  async function submitRepayment(e) {
    e.preventDefault(); if (!detailDebt) return; setBusy(true); setError('')
    const f = new FormData(e.currentTarget), amount = String(f.get('amount'))
    try {
      await request(`/debts/${detailDebt.id}/repayments`, { method: 'POST', body: JSON.stringify({ amount, date: f.get('date'), notes: f.get('notes') || '', request_id: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}` }) })
      flash(detailDebt.direction === 'borrowed' ? 'Repayment recorded.' : 'Returned amount recorded.')
      setDialog(null); await load(); const d = await request(`/debts/${detailDebt.id}`); setDetailDebt(d); setRepayments(d.repayments || []); if (friendId) setFriend(await request(`/friends/${friendId}`))
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  function openDebt(d) { setError(''); navigate(`/debts/records/${d.id}`) }
  async function removeFriend(f) { if (!window.confirm(`Delete ${f.name}? Friends with financial records cannot be deleted.`)) return; try { await request(`/friends/${f.id}`, { method: 'DELETE' }); flash('Friend deleted.'); if (friendId) navigate('/debts'); await load() } catch (e) { setError(e.message) } }
  async function removeDebt(d) { if (!window.confirm('Delete this record?')) return; try { await request(`/debts/${d.id}`, { method: 'DELETE' }); flash('Record deleted.'); await load(); if (friendId) setFriend(await request(`/friends/${friendId}`)) } catch (e) { setError(e.message) } }

  const borrowedChart = [{ name: 'Borrowed', amount: summary?.total_borrowed || 0 }, { name: 'Lent', amount: summary?.total_lent || 0 }]
  const statusChart = Object.entries(summary?.statuses || {}).map(([name, value]) => ({ name: STATUS[name], value })).filter(x => x.value)

  return <div className={`friends-debts-view ${dark ? 'theme-dark' : ''}`}>
    <header className="page-header"><div><div className="eyebrow">FRIENDS & FAIRNESS</div><h1>{friend ? friend.name : 'Friends & debts'}</h1><p>{friend ? 'A clear view of the money you share with this friend.' : 'Track borrowing, lending and repayments in one place.'}</p></div><div className="debt-header-actions"><button className="button secondary theme-toggle" aria-label={`Switch to ${dark ? 'light' : 'dark'} mode`} onClick={toggleTheme}>{dark?<Sun size={16}/>:<Moon size={16}/>}</button>{friend ? <button className="button secondary" onClick={() => navigate('/debts')}><ArrowLeft size={16}/> All friends</button> : <><button className="button secondary" onClick={() => { setEditing(null); setDialog('friend') }}><Plus size={16}/> Add friend</button><button className="button primary" onClick={() => { setEditing(null); setDialog('debt') }}><Plus size={16}/> Add record</button></>}</div></header>
    <Notice error={error} success={success}/>
    {loading && !friends.length && !friend ? <div className="loading-screen"><span className="loader"/>Loading friends and records</div> : friend ? <>
      <div className="friend-profile panel"><div className="friend-avatar">{friend.name?.slice(0,1).toUpperCase()}</div><div className="friend-profile-info"><span className="eyebrow">FRIEND PROFILE</span><h2>{friend.nickname ? `${friend.nickname} · ${friend.name}` : friend.name}</h2><div className="friend-contact">{friend.email && <span>{friend.email}</span>}{friend.phone && <span>{friend.phone}</span>}</div>{friend.notes && <p>{friend.notes}</p>}</div><div className="friend-actions"><button className="button secondary" onClick={() => { setEditing(friend); setDialog('friend') }}><Pencil size={15}/> Edit</button><button className="button primary" onClick={() => { setEditing(null); setDialog('debt') }}><Plus size={15}/> Borrow / lend</button></div></div>
      <div className="stat-grid debt-stats"><Metric label="Borrowed from them" value={friend.totals?.borrowed} icon={ArrowDownRight} tint="rose"/><Metric label="Lent to them" value={friend.totals?.lent} icon={ArrowUpRight} tint="green"/><Metric label="You still owe" value={friend.totals?.outstanding_borrowed} icon={Wallet} tint="amber"/><Metric label="They still owe" value={friend.totals?.outstanding_lent} icon={Clock3} tint="violet"/></div>
      <section className="panel data-panel"><div className="panel-heading"><div><h2>Borrowing & lending history</h2><p>Repayments remain attached to their original record.</p></div></div><DebtTable rows={friend.debts || []} openDebt={openDebt} editDebt={d => { setEditing(d); setDialog('debt') }} removeDebt={removeDebt}/></section>
      <section className="panel repayment-panel"><div className="panel-heading"><div><h2>Repayment activity</h2><p>Every payment recorded with a date.</p></div></div>{friend.repayment_history?.length ? <RepaymentList rows={friend.repayment_history}/> : <Empty text="No repayment activity yet."/>}</section>
    </> : <>
      <div className="stat-grid debt-stats six"><Metric label="Total borrowed" value={summary?.total_borrowed} icon={ArrowDownRight} tint="rose"/><Metric label="Total lent" value={summary?.total_lent} icon={ArrowUpRight} tint="green"/><Metric label="Outstanding debt" value={summary?.outstanding_debt} icon={Wallet} tint="amber"/><Metric label="Outstanding receivables" value={summary?.outstanding_receivables} icon={Users} tint="blue"/><Metric label="Repayments made" value={summary?.total_repayments_made} icon={Check} tint="violet"/><Metric label="Repayments received" value={summary?.total_repayments_received} icon={Check} tint="green"/></div>
      <div className="dashboard-grid debt-chart-grid"><section className="panel chart-panel"><div className="panel-heading"><div><h2>Borrowed vs lent</h2><p>Original amounts across your records</p></div></div><div className="chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={borrowedChart}><CartesianGrid strokeDasharray="3 5" vertical={false}/><XAxis dataKey="name"/><YAxis tickFormatter={v => v >= 1000 ? `₹${v / 1000}k` : `₹${v}`}/><Tooltip formatter={v => money(v)}/><Bar dataKey="amount" radius={[6,6,0,0]}>{borrowedChart.map((x,i)=><Cell key={x.name} fill={i ? '#10b981' : '#fb7185'}/>)}</Bar></BarChart></ResponsiveContainer></div></section><section className="panel chart-panel"><div className="panel-heading"><div><h2>Payment status</h2><p>Open and settled records</p></div></div>{statusChart.length ? <div className="chart"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={statusChart} dataKey="value" nameKey="name" innerRadius={48} outerRadius={78}>{statusChart.map((x,i)=><Cell key={x.name} fill={COLORS[i%COLORS.length]}/>)}</Pie><Tooltip/></PieChart></ResponsiveContainer></div> : <Empty text="Status chart will appear when you add a record."/>}</section></div>
      <div className="dashboard-grid debt-lower-grid"><section className="panel data-panel"><div className="panel-heading"><div><h2>Friend profiles</h2><p>People connected to your records</p></div><button className="button small secondary" onClick={() => { setEditing(null); setDialog('friend') }}><Plus size={14}/> Add friend</button></div><div className="debt-search"><Search size={16}/><input aria-label="Search friends and records" placeholder="Search friends or descriptions" value={query} onChange={e=>setQuery(e.target.value)}/></div>{friends.length ? <div className="friend-list">{friends.map(f=><article className="friend-row" key={f.id}><Link to={`/debts/friends/${f.id}`} className="friend-row-main"><span className="friend-avatar small-avatar">{f.name.slice(0,1).toUpperCase()}</span><span><b>{f.nickname || f.name}</b><small>{f.nickname ? f.name : f.email || f.phone || 'Friend profile'}</small></span></Link><span className="friend-balances"><small>You owe {money(f.totals?.outstanding_borrowed)}</small><small>Owes you {money(f.totals?.outstanding_lent)}</small></span><button className="icon-button" title="Edit friend" onClick={()=>{setEditing(f);setDialog('friend')}}><Pencil size={15}/></button><button className="icon-button danger-text" title="Delete friend" onClick={()=>removeFriend(f)}><Trash2 size={15}/></button></article>)}</div> : <Empty text={query ? 'No matching friends.' : 'Add a friend to start tracking shared money.'}/>}</section>
      <section className="panel repayment-panel"><div className="panel-heading"><div><h2>Recent repayments</h2><p>Latest recorded money movement</p></div></div>{paidRows.length ? <RepaymentList rows={paidRows.slice(0,6)}/> : <Empty text="Your repayments will appear here."/>}<div className="deadline-block"><h3><CalendarDays size={16}/> Upcoming deadlines</h3>{summary?.upcoming_deadlines?.length ? summary.upcoming_deadlines.slice(0,4).map(d=><button className="deadline-row" key={d.id} onClick={()=>openDebt(d)}><span><b>{d.friend_name}</b><small>{formatDate(d.due_date)} · {d.direction}</small></span><b>{money(d.remaining)}</b></button>) : <p className="muted-copy">No upcoming deadlines.</p>}</div>{summary?.overdue_items?.length > 0 && <div className="deadline-block overdue-block"><h3>Overdue payments</h3>{summary.overdue_items.slice(0,4).map(d=><button className="deadline-row" key={d.id} onClick={()=>openDebt(d)}><span><b>{d.friend_name}</b><small>Due {formatDate(d.due_date)}</small></span><b>{money(d.remaining)}</b></button>)}</div>}</section></div>
      <section className="panel data-panel"><div className="panel-heading"><div><h2>All records</h2><p>Filter your borrow and lend history.</p></div><div className="debt-filters"><label><CalendarDays size={14}/><input aria-label="Filter month" type="month" value={month} onChange={e=>{setMonth(e.target.value);if(e.target.value)setYear('')}}/></label><select aria-label="Filter year" value={year} onChange={e=>{setYear(e.target.value);if(e.target.value)setMonth('')}}><option value="">All years</option>{Array.from({length:7},(_,i)=>String(new Date().getFullYear()-i)).map(y=><option key={y}>{y}</option>)}</select><select aria-label="Filter friend" value={friendFilter} onChange={e=>setFriendFilter(e.target.value)}><option value="">All friends</option>{friends.map(f=><option key={f.id} value={f.id}>{f.name}</option>)}</select><select aria-label="Filter direction" value={direction} onChange={e=>setDirection(e.target.value)}><option value="">All directions</option><option value="borrowed">Borrowed</option><option value="lent">Lent</option></select><select aria-label="Filter status" value={status} onChange={e=>setStatus(e.target.value)}><option value="">All statuses</option>{Object.entries(STATUS).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></div></div><DebtTable rows={selectedDebts} openDebt={openDebt} editDebt={d=>{setEditing(d);setDialog('debt')}} removeDebt={removeDebt}/></section>
    </>}

    {dialog === 'friend' && <Modal title={editing ? 'Edit friend' : 'Add a friend'} onClose={()=>{setDialog(null);setEditing(null)}}><form className="modal-form" onSubmit={submitFriend}><Field label="Full name"><input name="name" required maxLength="120" defaultValue={editing?.name || ''} placeholder="e.g. Rahul Mehta"/></Field><Field label="Nickname (optional)"><input name="nickname" maxLength="80" defaultValue={editing?.nickname || ''}/></Field><div className="form-grid"><Field label="Phone (optional)"><input name="phone" type="tel" defaultValue={editing?.phone || ''}/></Field><Field label="Email (optional)"><input name="email" type="email" defaultValue={editing?.email || ''}/></Field></div><Field label="Notes"><textarea name="notes" rows="3" defaultValue={editing?.notes || ''}/></Field><div className="form-actions"><button type="button" className="button secondary" onClick={()=>setDialog(null)}>Cancel</button><button className="button primary" disabled={busy}>{busy?'Saving…':editing?'Save changes':'Add friend'}</button></div></form></Modal>}
    {dialog === 'debt' && <Modal title={editing ? 'Edit financial record' : 'Add borrowing or lending'} onClose={()=>{setDialog(null);setEditing(null)}}><form className="modal-form" onSubmit={submitDebt}><Field label="Friend"><select name="friend_id" required defaultValue={editing?.friend_id || friendId || ''}><option value="" disabled>Select a friend</option>{friends.map(f=><option key={f.id} value={f.id}>{f.name}</option>)}</select></Field><Field label="Direction"><select name="direction" defaultValue={editing?.direction || 'borrowed'}><option value="borrowed">I borrowed money</option><option value="lent">I lent money</option></select></Field><Field label="Amount (₹)"><input type="number" name="amount" min="0.01" step="0.01" required defaultValue={editing?.amount ?? ''}/></Field><div className="form-grid"><Field label="Transaction date"><input type="date" name="date" required defaultValue={editing?.date || today()}/></Field><Field label="Due date (optional)"><input type="date" name="due_date" defaultValue={editing?.due_date || ''}/></Field></div><Field label="Description"><input name="description" maxLength="300" placeholder="e.g. Hostel expenses" defaultValue={editing?.description || ''}/></Field><div className="form-actions"><button type="button" className="button secondary" onClick={()=>setDialog(null)}>Cancel</button><button className="button primary" disabled={busy}>{busy?'Saving…':editing?'Save changes':'Save record'}</button></div></form></Modal>}
    {dialog === 'detail' && detailDebt && <Modal title="Record details" onClose={()=>navigate('/debts')}><div className="debt-detail"><div className="debt-detail-top"><span className={`pill ${detailDebt.direction}`}>{detailDebt.direction === 'borrowed' ? 'Borrowed' : 'Lent'}</span><Status value={detailDebt.status}/></div><h3>{detailDebt.friend_name}</h3><p>{detailDebt.description || 'No description'} · {formatDate(detailDebt.date)}</p><div className="detail-amounts"><span>Original<b>{money(detailDebt.amount)}</b></span><span>Paid / received<b>{money(detailDebt.repaid)}</b></span><span>Remaining<b>{money(detailDebt.remaining)}</b></span></div>{detailDebt.due_date && <p className="muted-copy">Due {formatDate(detailDebt.due_date)}</p>}<div className="panel-heading compact-heading"><div><h2>Repayment history</h2><p>{repayments.length} payment{repayments.length===1?'':'s'}</p></div></div>{repayments.length ? <RepaymentList rows={repayments}/> : <Empty text="No repayments recorded."/>}{detailDebt.remaining > 0 && <button className="button primary full repayment-action" onClick={()=>setDialog('repayment')}>{detailDebt.direction === 'borrowed' ? 'Record repayment' : 'Record amount received'}</button>}</div></Modal>}
    {dialog === 'repayment' && detailDebt && <Modal title={detailDebt.direction === 'borrowed' ? 'Record a repayment' : 'Record money received'} onClose={()=>setDialog('detail')}><p className="muted-copy">Outstanding balance: <b>{money(detailDebt.remaining)}</b></p><form className="modal-form" onSubmit={submitRepayment}><Field label="Amount (₹)"><input type="number" name="amount" min="0.01" max={detailDebt.remaining} step="0.01" required autoFocus/></Field><Field label="Date"><input type="date" name="date" defaultValue={today()} required/></Field><Field label="Notes"><input name="notes" maxLength="300" placeholder="Optional note"/></Field><div className="form-actions"><button type="button" className="button secondary" onClick={()=>setDialog('detail')}>Cancel</button><button className="button primary" disabled={busy}>{busy?'Saving…':'Save repayment'}</button></div></form></Modal>}
  </div>
}

function Empty({ text }) { return <div className="empty-state"><div className="empty-icon"><Wallet size={20}/></div><p>{text}</p></div> }
function DebtTable({ rows, openDebt, editDebt, removeDebt }) {
  if (!rows?.length) return <Empty text="No records match your filters."/>
  return <div className="table-scroll"><table><thead><tr><th>FRIEND & DATE</th><th>DIRECTION</th><th>STATUS</th><th>ORIGINAL</th><th>REMAINING</th><th>ACTIONS</th></tr></thead><tbody>{rows.map(d=><tr key={d.id}><td><button className="table-link" onClick={()=>openDebt(d)}><b>{d.friend_name}</b><small className="table-sub">{formatDate(d.date)}{d.due_date ? ` · due ${formatDate(d.due_date)}` : ''}</small></button></td><td><span className={`pill ${d.direction}`}>{d.direction}</span><small className="table-sub">{d.description || '—'}</small></td><td><Status value={d.status}/></td><td>{money(d.amount)}<small className="table-sub">{money(d.repaid)} paid</small></td><td><b>{money(d.remaining)}</b></td><td><div className="row-actions">{d.remaining > 0 && <button className="button small secondary" onClick={()=>openDebt(d)}>Details / repay</button>}{!d.repayment_count && <button className="icon-button" title="Edit record" onClick={()=>editDebt(d)}><Pencil size={14}/></button>}<button className="icon-button danger-text" title="Delete record" onClick={()=>removeDebt(d)}><Trash2 size={14}/></button></div></td></tr>)}</tbody></table></div>
}
function RepaymentList({ rows }) { return <div className="repayment-list">{rows.map((r,i)=><div className="repayment-row" key={r.id || `${r.debt_id}-${i}`}><span className="repayment-icon"><Check size={15}/></span><span className="repayment-description"><b>{r.friend_name || r.direction || 'Repayment'}</b><small>{formatDate(r.date)}{r.note ? ` · ${r.note}` : r.notes ? ` · ${r.notes}` : ''}</small></span><b className={r.direction === 'borrowed' ? 'negative' : 'positive'}>{r.direction === 'borrowed' ? '−' : '+'}{money(r.amount)}</b></div>)}</div> }
