import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpRight, ArrowDownRight, Wallet, PiggyBank, Receipt, CalendarDays, AlertCircle } from 'lucide-react'
import { AreaChart, Area, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid, PieChart, Pie, Cell } from 'recharts'
import { money, request, today } from '../services/api'
import { budgetUtilization, budgetStatus } from '../utils/finance'

const monthNow = today().slice(0,7)
function PageHeader({eyebrow,title,subtitle,action}) { return <div className="page-header"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{subtitle}</p></div>{action}</div> }
function StatCard({title,value,icon:Icon,tone="green",foot}) { return <article className="stat-card"><div className={`stat-icon ${tone}`}><Icon size={19}/></div><div className="stat-label">{title}</div><div className="stat-value">{money(value)}</div><div className="stat-foot">{foot}</div></article> }
function Empty({text}){return <div className="empty-state"><div className="empty-icon"><Wallet size={20}/></div><p>{text}</p></div>}
function RequestStatus({loading,error,hasData,label,staleMessage,onRetry}) {
  if (loading) return <div className="alert" role="status" aria-live="polite"><span className="loader"/><span>{hasData?`Refreshing ${label}…`:`Loading ${label}…`}{staleMessage&&<><br/><small>{staleMessage}</small></>}</span></div>
  if (error) return <div className="alert error" role="alert"><AlertCircle size={16}/><span>{error}{staleMessage&&<><br/><small>{staleMessage}</small></>}</span><button className="text-link" type="button" onClick={onRetry}>Retry {label}</button></div>
  return null
}

function Dashboard(){
  const [month,setMonth]=useState(monthNow)
  const selectedYear=month.slice(0,4)
  const [data,setData]=useState(null)
  const [analytics,setAnalytics]=useState(null)
  const [dataMonth,setDataMonth]=useState(null)
  const [analyticsYear,setAnalyticsYear]=useState(null)
  const [summaryLoading,setSummaryLoading]=useState(true)
  const [analyticsLoading,setAnalyticsLoading]=useState(true)
  const [summaryError,setSummaryError]=useState('')
  const [analyticsError,setAnalyticsError]=useState('')
  const summaryRequestId=useRef(0),analyticsRequestId=useRef(0)
  const summaryController=useRef(null),analyticsController=useRef(null)

  const loadSummary=useCallback(async targetMonth=>{
    const requestId=++summaryRequestId.current
    summaryController.current?.abort()
    const controller=new AbortController()
    summaryController.current=controller
    setSummaryLoading(true)
    setSummaryError('')
    try{
      const result=await request(`/dashboard/summary?month=${targetMonth}`,{signal:controller.signal})
      if(requestId===summaryRequestId.current){setData(result);setDataMonth(targetMonth)}
    }catch(error){
      if(requestId===summaryRequestId.current&&!controller.signal.aborted)setSummaryError(error.message||'Could not load the dashboard summary.')
    }finally{
      if(requestId===summaryRequestId.current){
        setSummaryLoading(false)
        summaryController.current=null
      }
    }
  },[])

  const loadAnalytics=useCallback(async targetYear=>{
    const requestId=++analyticsRequestId.current
    analyticsController.current?.abort()
    const controller=new AbortController()
    analyticsController.current=controller
    setAnalyticsLoading(true)
    setAnalyticsError('')
    try{
      const result=await request(`/dashboard/analytics?year=${targetYear}`,{signal:controller.signal})
      if(requestId===analyticsRequestId.current){setAnalytics(result);setAnalyticsYear(targetYear)}
    }catch(error){
      if(requestId===analyticsRequestId.current&&!controller.signal.aborted)setAnalyticsError(error.message||'Could not load dashboard analytics.')
    }finally{
      if(requestId===analyticsRequestId.current){
        setAnalyticsLoading(false)
        analyticsController.current=null
      }
    }
  },[])

  useEffect(()=>{
    loadSummary(month)
    return ()=>{
      summaryRequestId.current++
      summaryController.current?.abort()
    }
  },[month,loadSummary])

  useEffect(()=>{
    loadAnalytics(selectedYear)
    return ()=>{
      analyticsRequestId.current++
      analyticsController.current?.abort()
    }
  },[selectedYear,loadAnalytics])

  const palette=['#10b981','#64748b','#f59e0b','#8b5cf6','#38bdf8','#fb7185','#a3e635']
  const monthlyAnalytics=analytics?.monthly||[]
  const categories=data?.categories||{}
  const summaryStaleMessage=dataMonth&&dataMonth!==month?`Showing the last successful summary for ${new Date(`${dataMonth}-02T12:00:00`).toLocaleString('en',{month:'long',year:'numeric'})}.`:''
  const analyticsStaleMessage=analyticsYear&&analyticsYear!==selectedYear?`Showing the last successful analytics for ${analyticsYear}.`:''

  return <>
    <PageHeader eyebrow="YOUR FINANCIAL OVERVIEW" title="Good to see you" subtitle="A clear view of your money, so you can make it go further." action={<label className="month-picker"><CalendarDays size={16}/><input type="month" value={month} onChange={e=>setMonth(e.target.value)}/></label>}/>
    <div aria-busy={summaryLoading||Boolean(summaryStaleMessage)}>
      <RequestStatus loading={summaryLoading||Boolean(summaryStaleMessage)} error={summaryError} hasData={Boolean(data)} label="summary" staleMessage={summaryStaleMessage} onRetry={()=>loadSummary(month)}/>
      {data&&<>
        <div className="stat-grid"><StatCard title="Total income" value={data.income} icon={ArrowDownRight} tone="green" foot="For selected month"/><StatCard title="Total expenses" value={data.expenses} icon={ArrowUpRight} tone="rose" foot="For selected month"/><StatCard title="Available this month" value={data.net} icon={Wallet} tone="blue" foot="Income minus expenses"/><StatCard title="Reserved savings" value={data.reserved_savings} icon={PiggyBank} tone="violet" foot="Across your savings goals"/></div>
        <div className="stat-grid secondary-stats"><div className="mini-stat"><span><span className="dot amber"/>Pending bills</span><b>{money(data.pending_bills)}</b></div><div className="mini-stat"><span><span className="dot rose-dot"/>You owe friends</span><b>{money(data.owed_to_friends)}</b></div><div className="mini-stat"><span><span className="dot green-dot"/>Friends owe you</span><b>{money(data.owed_by_friends)}</b></div><Link className="mini-stat cash-flow-link" to="/debts"><span><span className="dot blue-dot"/>Cash flow incl. debts & savings</span><b>{money(data.available_cash_change)}</b></Link></div>
      </>}
    </div>

    <div className="dashboard-grid">
      <section className="panel chart-panel">
        <div className="panel-heading"><div><h2>Income & spending</h2><p>Your monthly money flow</p></div><span className="legend"><i className="legend-income"/> Income <i className="legend-expenses"/> Expenses</span></div>
        <div aria-busy={analyticsLoading||Boolean(analyticsStaleMessage)}><RequestStatus loading={analyticsLoading||Boolean(analyticsStaleMessage)} error={analyticsError} hasData={Boolean(analytics)} label="analytics" staleMessage={analyticsStaleMessage} onRetry={()=>loadAnalytics(selectedYear)}/></div>
        {monthlyAnalytics.length?<div className="chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={monthlyAnalytics.map(x=>({...x,name:new Date(x.month+'-02').toLocaleString('en',{month:'short'})}))}><defs><linearGradient id="incFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#10b981" stopOpacity={.18}/><stop offset="95%" stopColor="#10b981" stopOpacity={0}/></linearGradient><linearGradient id="expFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#fb7185" stopOpacity={.15}/><stop offset="95%" stopColor="#fb7185" stopOpacity={0}/></linearGradient></defs><CartesianGrid strokeDasharray="3 5" vertical={false} stroke="#edf0f4"/><XAxis dataKey="name" tickLine={false} axisLine={false} tick={{fontSize:11,fill:'#98a2b3'}}/><YAxis tickLine={false} axisLine={false} tick={{fontSize:10,fill:'#98a2b3'}} tickFormatter={v=>v>=1000?`₹${v/1000}k`:`₹${v}`} width={52}/><Tooltip formatter={v=>money(v)} contentStyle={{border:'1px solid #edf0f4',borderRadius:12,fontSize:12}}/><Area type="monotone" dataKey="income" name="Income" stroke="#10b981" strokeWidth={2.5} fill="url(#incFill)"/><Area type="monotone" dataKey="expenses" name="Expenses" stroke="#fb7185" strokeWidth={2.5} fill="url(#expFill)"/></AreaChart></ResponsiveContainer></div>:analytics&&!analyticsLoading&&<Empty text="Your monthly chart will appear when analytics data is available."/>}
      </section>
      <section className="panel category-panel">
        <div className="panel-heading"><div><h2>Spending by category</h2><p>Where this month went</p></div></div>
        {data&&Object.keys(categories).length?<><div className="donut-wrap"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={Object.entries(categories).map(([name,value])=>({name,value}))} dataKey="value" innerRadius={58} outerRadius={78} paddingAngle={3} stroke="none">{Object.keys(categories).map((_,i)=><Cell key={i} fill={palette[i%palette.length]}/>)}</Pie><Tooltip formatter={v=>money(v)}/></PieChart></ResponsiveContainer><div className="donut-center"><b>{money(data.expenses)}</b><small>Total spent</small></div></div><div className="category-legend">{Object.entries(categories).slice(0,5).map(([name,value],i)=><div key={name}><span><i style={{background:palette[i%palette.length]}}/>{name}</span><b>{money(value)}</b></div>)}</div></>:data?<Empty text="Your category breakdown will appear after your first expense."/>:<Empty text={summaryLoading?"Loading summary data…":"Summary unavailable. Retry the summary above."}/>}
      </section>
    </div>

    <div className="dashboard-grid bottom-grid">
      <section className="panel">
        <div className="panel-heading"><div><h2>Recent transactions</h2><p>Your latest activity</p></div><Link className="text-link" to="/expenses">View all <ArrowUpRight size={14}/></Link></div>
        {data?(data.recent_transactions.length?<div className="transaction-list">{data.recent_transactions.map(t=><div className="transaction-row" key={`${t.type}-${t.id}`}><div className="transaction-icon"><Receipt size={17}/></div><div className="transaction-info"><b>{t.description||t.category}</b><small>{t.category} · {t.date}</small></div><b className={t.type==='income'?'positive':'negative'}>{t.type==='income'?'+':'-'}{money(t.amount)}</b></div>)}</div>:<Empty text="Your transactions will show up here when you add them."/>):<Empty text={summaryLoading?"Loading summary data…":"Summary unavailable. Retry the summary above."}/>}
      </section>
      <section className="panel">
        <div className="panel-heading"><div><h2>Monthly budgets</h2><p>Keep the month on track</p></div><Link className="text-link" to="/budgets">Manage <ArrowUpRight size={14}/></Link></div>
        {data?(data.budgets.length?data.budgets.map(b=>{const p=Math.min(100,budgetUtilization(b.spent,b.amount)),state=budgetStatus(b.spent,b.amount);return <div className="budget-progress" key={b.category}><div><b>{b.category}</b><span>{money(b.spent)} / {money(b.amount)}</span></div><div className="progress"><i className={state==='exceeded'?'exceeded':state==='critical'?'critical':state==='warning'?'warning':''} style={{width:`${p}%`}}/></div><small>{p>=90?'Budget nearly used':p>=75?'Approaching limit':`${Math.round(p)}% used`}</small></div>}):<Empty text="Set a category budget to keep an eye on spending."/>):<Empty text={summaryLoading?"Loading summary data…":"Summary unavailable. Retry the summary above."}/>}
      </section>
    </div>
  </>
}
export default Dashboard
