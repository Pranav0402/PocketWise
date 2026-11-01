import { useCallback, useEffect, useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, ComposedChart, Line, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { AlertTriangle, ArrowDownRight, ArrowUpRight, CalendarDays, Check, Copy, Pencil, Plus, Search, Target, Trash2, Wallet, X, History, Moon, Sun } from 'lucide-react'
import { FormField, Modal } from '../components/Forms'
import { request, today } from '../services/api'
import { useTheme } from '../context/ThemeContext'

const CATEGORIES = ['Rent','Electricity','Food','Groceries','Travel','Clothes','Shopping','Education','Entertainment','Subscriptions','Healthcare','Other']
const TONES = { normal: 'normal', warning: 'warning', critical: 'critical', exceeded: 'exceeded', unbudgeted: 'unbudgeted' }
const STATUS = { normal: 'On track', warning: 'Watch', critical: 'Almost at limit', exceeded: 'Over budget', unbudgeted: 'Unbudgeted' }
const PALETTE = ['#10b981','#f59e0b','#fb7185','#8b5cf6','#38bdf8','#a3e635','#f97316','#14b8a6']
const monthNow = today().slice(0,7)
const yearNow = Number(monthNow.slice(0,4))
const exactMoney = value => new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',minimumFractionDigits:2,maximumFractionDigits:2}).format(Number(value)||0)

function Metric({ title, value, foot, icon: Icon, tone }) { return <article className="stat-card"><div className={`stat-icon ${tone}`}><Icon size={18}/></div><div className="stat-label">{title}</div><div className="stat-value">{typeof value === 'number' ? exactMoney(value) : value}</div><div className="stat-foot">{foot}</div></article> }
function Notice({ error, success, dismiss }) { return <>{error && <div className="alert error" role="alert"><AlertTriangle size={15}/>{error}<button onClick={dismiss} aria-label="Dismiss error"><X size={14}/></button></div>}{success && <div className="alert success" role="status"><Check size={15}/>{success}</div>}</> }
function Progress({ item }) {
  const pct = Math.max(0, Number(item.utilization || 0))
  const width = Math.min(100,pct)
  return <div className={`budget-card ${TONES[item.status] || 'normal'}`}><div className="budget-card-top"><div><span className="budget-category-dot"/><h3>{item.category}</h3></div><span className={`budget-badge ${item.status}`}>{STATUS[item.status] || 'On track'}</span></div><div className="budget-values"><span>Spent <b>{exactMoney(item.spent)}</b></span>{item.budgeted ? <span>Limit <b>{exactMoney(item.amount)}</b></span> : <span>No limit set</span>}</div>{item.budgeted ? <><div className="budget-track"><i style={{width:`${width}%`}}/></div><div className="budget-progress-meta"><span>{item.remaining >= 0 ? `${exactMoney(item.remaining)} remaining` : `${exactMoney(Math.abs(item.remaining))} over limit`}</span><b>{pct.toFixed(0)}%</b></div></> : <p className="unbudgeted-note">Spending here is not covered by a category budget.</p>}{item.alert && <div className={`budget-alert-copy ${item.status}`}><AlertTriangle size={13}/>{item.alert}</div>}</div>
}

export default function BudgetManagement() {
  const { dark, toggleTheme } = useTheme()
  const [month,setMonth] = useState(monthNow), [historyYear,setHistoryYear] = useState(String(yearNow)), [summary,setSummary] = useState(null), [history,setHistory] = useState([]), [budgets,setBudgets] = useState([])
  const [query,setQuery] = useState(''), [filterStatus,setFilterStatus] = useState(''), [loading,setLoading] = useState(true), [busy,setBusy] = useState(false)
  const [error,setError] = useState(''), [success,setSuccess] = useState(''), [dialog,setDialog] = useState(false), [editing,setEditing] = useState(null)

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const [s,b,h] = await Promise.all([request(`/budgets/summary?month=${month}`),request(`/budgets?month=${month}`),request(`/budgets/history?year=${historyYear}`)])
      setSummary(s); setBudgets(b); setHistory(h)
    } catch(e) { setError(e.message) } finally { setLoading(false) }
  },[month,historyYear])
  useEffect(()=>{load()},[load])

  const filtered = useMemo(()=> (summary?.categories || []).filter(x => (!query.trim() || x.category.toLowerCase().includes(query.toLowerCase())) && (!filterStatus || x.status===filterStatus)),[summary,query,filterStatus])
  const chartData = (summary?.categories || []).filter(x=>x.budgeted).map(x=>({category:x.category,Planned:x.amount,Actual:x.spent}))
  const utilizationData = (summary?.categories || []).filter(x=>x.budgeted).map(x=>({name:x.category,spent:x.spent,utilization:x.utilization||0,status:x.status}))

  function toast(message){setSuccess(message);window.setTimeout(()=>setSuccess(''),3500)}
  async function saveBudget(e){
    e.preventDefault();setBusy(true);setError('')
    const form=new FormData(e.currentTarget), body={category:form.get('category'),amount:String(form.get('amount')),month:form.get('month'),year:Number(String(form.get('month')).slice(0,4)),description:String(form.get('description')||'').trim()}
    try{await request(editing?`/budgets/${editing.id}`:'/budgets',{method:editing?'PUT':'POST',body:JSON.stringify(body)});setDialog(false);setEditing(null);toast(editing?'Budget updated.':'Monthly budget created.');await load()}
    catch(err){setError(err.message)}finally{setBusy(false)}
  }
  async function deleteBudget(row){if(!window.confirm(`Delete the ${row.category} budget for ${row.month}?`))return;try{await request(`/budgets/${row.id}`,{method:'DELETE'});toast('Budget deleted.');await load()}catch(e){setError(e.message)}}
  async function copyPrevious(){
    const [y,m]=month.split('-').map(Number), previous=new Date(y,m-2,1), prevMonth=`${previous.getFullYear()}-${String(previous.getMonth()+1).padStart(2,'0')}`
    setBusy(true);setError('')
    try{
      const [source,target]=await Promise.all([request(`/budgets?month=${prevMonth}`),request(`/budgets?month=${month}`)])
      const existing=new Set(target.map(x=>x.category)), toCopy=source.filter(x=>!existing.has(x.category))
      if(!toCopy.length){toast(source.length?'All previous month categories already exist.':'No budgets found to copy from the previous month.');return}
      const outcomes=await Promise.allSettled(toCopy.map(x=>request('/budgets',{method:'POST',body:JSON.stringify({category:x.category,amount:x.amount,month,year:Number(month.slice(0,4)),description:x.description||''})})))
      const made=outcomes.filter(x=>x.status==='fulfilled').length, failed=outcomes.length-made
      if(failed)setError(`${made} budget${made===1?'':'s'} copied; ${failed} could not be copied. ${outcomes.find(x=>x.status==='rejected')?.reason?.message||''}`)
      else toast(`${made} budget${made===1?'':'s'} copied from ${prevMonth}.`)
      await load()
    }catch(e){setError(e.message)}finally{setBusy(false)}
  }

  return <div className={`budget-management ${dark?'theme-dark':''}`}>
    <header className="page-header"><div><div className="eyebrow">PLAN AHEAD</div><h1>Budget your month</h1><p>Set category limits and see how your actual spending compares.</p></div><div className="budget-header-actions"><button className="button secondary theme-toggle" aria-label={`Switch to ${dark?'light':'dark'} mode`} onClick={toggleTheme}>{dark?<Sun size={16}/>:<Moon size={16}/>}</button><label className="month-picker"><CalendarDays size={15}/><input type="month" value={month} onChange={e=>setMonth(e.target.value)}/></label><button className="button secondary" onClick={copyPrevious} disabled={busy}><Copy size={15}/> Copy previous month</button><button className="button primary" onClick={()=>{setEditing(null);setDialog(true)}}><Plus size={16}/> Add budget</button></div></header>
    <Notice error={error} success={success} dismiss={()=>setError('')}/>
    {loading&&!summary ? <div className="loading-inline"><span className="loader"/>Loading your budgetsâ€¦</div> : <>
      <div className="stat-grid budget-summary-stats"><Metric title="Monthly budget" value={summary?.total_budget||0} foot="Total category limits" icon={Target} tone="green"/><Metric title="Total spent" value={summary?.total_spent||0} foot="Actual expenses this month" icon={ArrowUpRight} tone="rose"/><Metric title="Remaining" value={summary?.remaining||0} foot="Budget total minus actual spend" icon={Wallet} tone="blue"/><Metric title="Overall utilization" value={summary?.utilization==null?'No budgets':`${summary.utilization.toFixed(0)}%`} foot="Only spending in budgeted categories" icon={History} tone="violet"/><Metric title="Categories within limit" value={summary?.within_budget_count||0} foot="Budgeted categories at or below limit" icon={Check} tone="green"/><Metric title="Over budget" value={summary?.exceeded_count||0} foot="Categories above 100%" icon={AlertTriangle} tone="amber"/></div>
      {summary?.alerts?.length>0&&<section className="budget-alert-strip" aria-label="Budget alerts">{summary.alerts.map(a=><div key={`${a.category}-${a.status}`} className={`budget-alert ${a.status}`}><AlertTriangle size={15}/><span>{a.message}</span></div>)}</section>}
      <div className="dashboard-grid budget-charts"><section className="panel chart-panel"><div className="panel-heading"><div><h2>Planned vs actual</h2><p>Category budget compared with real expenses</p></div></div>{chartData.length?<div className="chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={chartData} margin={{top:8,right:12,left:0,bottom:4}}><CartesianGrid strokeDasharray="3 5" vertical={false}/><XAxis dataKey="category" tickLine={false} axisLine={false} tick={{fontSize:9}}/><YAxis tickLine={false} axisLine={false} tickFormatter={v=>v>=1000?`₹${v/1000}k`:`₹${v}`} width={45}/><Tooltip formatter={v=>exactMoney(v)}/><Bar dataKey="Planned" fill="#a7e6ce" radius={[5,5,0,0]}/><Bar dataKey="Actual" fill="#10b981" radius={[5,5,0,0]}/></ComposedChart></ResponsiveContainer></div>:<Empty text="Add category limits to compare planned and actual spending."/>}</section><section className="panel chart-panel"><div className="panel-heading"><div><h2>Budget utilization</h2><p>Share of each category limit spent</p></div></div>{utilizationData.length?<div className="chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={utilizationData} margin={{top:8,right:14,left:0,bottom:4}}><CartesianGrid strokeDasharray="3 5" vertical={false}/><XAxis dataKey="name" tickLine={false} axisLine={false} tick={{fontSize:9}}/><YAxis tickLine={false} axisLine={false} tickFormatter={v=>`${v}%`} width={40}/><Tooltip formatter={(v,_,props)=>[`${Number(v).toFixed(1)}% · ${exactMoney(props.payload.spent)}`,'Utilized']}/><Bar dataKey="utilization" radius={[5,5,0,0]}>{utilizationData.map(x=><Cell key={x.name} fill={x.status==='exceeded'?'#e96e78':x.status==='critical'?'#f08c50':x.status==='warning'?'#f1b443':'#10b981'}/>)}</Bar></BarChart></ResponsiveContainer></div>:<Empty text="Add category limits to see budget utilization."/>}</section></div>
      <section className="panel data-panel budget-categories-panel"><div className="panel-heading"><div><h2>Category budgets</h2><p>{new Date(`${month}-01T00:00:00`).toLocaleDateString('en-IN',{month:'long',year:'numeric'})} Â· actual expenses only</p></div><div className="budget-filters"><label className="budget-search"><Search size={15}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search categories" aria-label="Search budget categories"/></label><select aria-label="Filter budget status" value={filterStatus} onChange={e=>setFilterStatus(e.target.value)}><option value="">All statuses</option><option value="normal">On track</option><option value="warning">Warning</option><option value="critical">Critical</option><option value="exceeded">Exceeded</option><option value="unbudgeted">Unbudgeted</option></select></div></div>{filtered.length?<div className="budget-cards-grid">{filtered.map(item=>{const row=budgets.find(b=>b.category===item.category);return <article key={item.category}><Progress item={item}/>{row&&<div className="budget-card-actions"><span>{row.description||'Monthly category plan'}</span><div><button className="icon-button" title={`Edit ${row.category} budget`} onClick={()=>{setEditing(row);setDialog(true)}}><Pencil size={14}/></button><button className="icon-button danger-text" title={`Delete ${row.category} budget`} onClick={()=>deleteBudget(row)}><Trash2 size={14}/></button></div></div>}</article>})}</div>:<Empty text={query||filterStatus?'No categories match your search or status.':'No budgets or spending recorded for this month.'}/>}</section>
      <section className="panel data-panel budget-history-panel"><div className="panel-heading"><div><h2>Monthly history</h2><p>Planned and actual totals for months with budgets.</p></div><label className="history-year"><CalendarDays size={14}/><select value={historyYear} onChange={e=>setHistoryYear(e.target.value)}>{Array.from({length:7},(_,i)=>String(yearNow-i)).map(y=><option key={y}>{y}</option>)}</select></label></div>{history.length?<div className="table-scroll"><table><thead><tr><th>MONTH</th><th>PLANNED</th><th>ACTUAL SPEND</th><th>REMAINING</th><th>UTILIZATION</th><th>OVER LIMIT</th></tr></thead><tbody>{history.map(h=><tr key={h.month} className="history-row" onClick={()=>setMonth(h.month)}><td><b>{new Date(`${h.month}-01T00:00:00`).toLocaleDateString('en-IN',{month:'long',year:'numeric'})}</b></td><td>{exactMoney(h.total_budget)}</td><td>{exactMoney(h.total_spent)}</td><td className={h.remaining<0?'negative':''}>{exactMoney(h.remaining)}</td><td>{h.utilization==null?'â€”':`${h.utilization.toFixed(0)}%`}</td><td>{h.exceeded_count}</td></tr>)}</tbody></table></div>:<Empty text={`No historical budgets found for ${historyYear}.`}/>}</section>
      {summary?.unbudgeted_categories?.length>0&&<section className="panel unbudgeted-panel"><div className="panel-heading"><div><h2>Spending without a budget</h2><p>These expenses are included in total actual spending but have no category limit.</p></div></div><div className="unbudgeted-list">{summary.unbudgeted_categories.map(x=><div key={x.category}><span>{x.category}</span><b>{exactMoney(x.spent)}</b><span className="budget-badge unbudgeted">No limit</span></div>)}</div></section>}
    </>}
    {dialog&&<Modal title={editing?'Edit category budget':'Create monthly budget'} onClose={()=>{setDialog(false);setEditing(null)}}><form className="modal-form" onSubmit={saveBudget}><FormField label="Category"><select name="category" required defaultValue={editing?.category||''}><option value="" disabled>Select category</option>{CATEGORIES.filter(c=>editing?.category===c||!budgets.some(b=>b.category===c)).map(c=><option key={c}>{c}</option>)}</select></FormField><FormField label="Budget amount (â‚¹)"><input name="amount" type="number" min="0.01" step="0.01" required defaultValue={editing?.amount??''}/></FormField><FormField label="Month"><input name="month" type="month" required defaultValue={editing?.month||month}/></FormField><FormField label="Description (optional)"><input name="description" maxLength="300" placeholder="e.g. Monthly food allowance" defaultValue={editing?.description||''}/></FormField><div className="form-actions"><button type="button" className="button secondary" onClick={()=>{setDialog(false);setEditing(null)}}>Cancel</button><button className="button primary" disabled={busy}>{busy?'Savingâ€¦':editing?'Save changes':'Create budget'}</button></div></form></Modal>}
  </div>
}

function Empty({text}){return <div className="empty-state"><div className="empty-icon"><Wallet size={20}/></div><p>{text}</p></div>}
