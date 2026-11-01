import { useCallback, useEffect, useState } from 'react'
import { ArrowDownToLine, ArrowDownUp, ArrowUpDown, CalendarDays, CheckCircle2, CircleAlert, LoaderCircle, Pencil, Plus, Search, Trash2, X } from 'lucide-react'
import { FormField, Modal } from '../Forms'
import { formatDate, money, request, today } from '../../services/api'
import { buildTransactionQuery } from '../../utils/transactionFilters'

const incomeSources = ['Monthly allowance from home', 'Scholarship', 'Part-time income', 'Freelancing', 'Gifts', 'Other income']
const expenseCategories = ['Rent', 'Electricity', 'Food', 'Groceries', 'Travel', 'Clothes', 'Shopping', 'Education', 'Entertainment', 'Subscriptions', 'Healthcare', 'Other']
const paymentMethods = ['Cash', 'UPI', 'Card', 'Bank transfer', 'Other']

export function AmountInput({ value, onChange, name = 'amount', required = true }) {
  return <div className="amount-control"><span aria-hidden="true">₹</span><input aria-label="Amount in Indian rupees" name={name} type="number" min="0.01" max="100000000" step="0.01" inputMode="decimal" value={value} onChange={onChange} placeholder="0.00" required={required}/></div>
}

export function CategorySelector({ kind, value, onChange }) {
  const options = kind === 'income' ? incomeSources : expenseCategories
  return <select name={kind === 'income' ? 'source' : 'category'} value={value} onChange={onChange} required>
    <option value="">Choose {kind === 'income' ? 'income source' : 'category'}</option>
    {options.map(option => <option value={option} key={option}>{option}</option>)}
  </select>
}

export function DateSelector({ name = 'date', value, onChange, label = 'Date' }) {
  return <FormField label={label}><div className="date-control"><CalendarDays size={15}/><input name={name} type="date" value={value} onChange={onChange} required/></div></FormField>
}

export function TransactionFilters({ kind, filters, setFilters }) {
  const categoryOptions = kind === 'income' ? incomeSources : expenseCategories
  const update = (key, value) => setFilters(current => ({ ...current, [key]: value }))
  return <section className="transaction-filters" aria-label="Transaction filters">
    <label className="transaction-search"><Search size={16}/><input aria-label="Search transactions" value={filters.search} onChange={e => update('search', e.target.value)} placeholder={`Search ${kind}…`}/></label>
    <select aria-label={kind === 'income' ? 'Filter by source' : 'Filter by category'} value={kind === 'income' ? filters.source : filters.category} onChange={e => update(kind === 'income' ? 'source' : 'category', e.target.value)}>
      <option value="">All {kind === 'income' ? 'sources' : 'categories'}</option>{categoryOptions.map(option => <option key={option}>{option}</option>)}
    </select>
    <label className="filter-date"><span>From</span><input aria-label="Start date" type="date" value={filters.date_from} onChange={e => update('date_from', e.target.value)}/></label>
    <label className="filter-date"><span>To</span><input aria-label="End date" type="date" value={filters.date_to} onChange={e => update('date_to', e.target.value)}/></label>
    <label className="sort-control"><ArrowDownUp size={14}/><select aria-label="Sort transactions" value={`${filters.sort_by}:${filters.sort_order}`} onChange={e => {const [sort_by, sort_order] = e.target.value.split(':');setFilters(current => ({...current,sort_by,sort_order}))}}><option value="date:desc">Newest first</option><option value="date:asc">Oldest first</option><option value="amount:desc">Amount: high to low</option><option value="amount:asc">Amount: low to high</option></select></label>
  </section>
}

export function TransactionTable({ kind, rows, loading, onEdit, onDelete }) {
  const title = kind === 'income' ? 'Source' : 'Description'
  const detail = kind === 'income' ? 'Description' : 'Category'
  if (loading) return <div className="transaction-state"><LoaderCircle className="spin" size={20}/>Loading your {kind}…</div>
  if (!rows.length) return <div className="transaction-empty"><span><ArrowDownToLine size={20}/></span><b>No {kind} records yet</b><p>Add your first {kind === 'income' ? 'allowance or other income' : 'expense'} to start building your history.</p></div>
  return <div className="transaction-table-scroll"><table className="transaction-table"><thead><tr><th>{title}</th><th>{detail}</th><th>Date</th><th>Payment</th><th className="numeric">Amount</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>{rows.map(row => <tr key={row.id}>
    <td><b>{kind === 'income' ? row.source : row.description || row.category}</b>{kind === 'income' && <small>{row.description || 'Income'}</small>}</td>
    <td>{kind === 'income' ? row.description || '—' : <span className="category-badge">{row.category}</span>}</td><td>{formatDate(row.date)}</td><td>{kind === 'income' ? '—' : row.payment_method}</td>
    <td className={`numeric transaction-amount ${kind === 'income' ? 'income-amount' : ''}`}>{kind === 'income' ? '+' : '−'}{money(row.amount)}</td>
    <td><div className="transaction-actions"><button type="button" onClick={() => onEdit(row)} aria-label={`Edit ${kind} record`} title="Edit"><Pencil size={15}/></button><button type="button" onClick={() => onDelete(row)} aria-label={`Delete ${kind} record`} title="Delete" className="delete-action"><Trash2 size={15}/></button></div></td>
  </tr>)}</tbody></table></div>
}

function TransactionForm({ kind, value, onSubmit, onClose, busy, error }) {
  const [amount, setAmount] = useState(value?.amount == null ? '' : String(value.amount))
  const [source, setSource] = useState(kind === 'income' ? value?.source || '' : value?.category || '')
  const [date, setDate] = useState(value?.date || today())
  const [method, setMethod] = useState(value?.payment_method || 'UPI')
  return <form className="transaction-form" onSubmit={e => {e.preventDefault();const data = new FormData(e.currentTarget);onSubmit({amount: data.get('amount'), date, description: data.get('description').trim(), notes: data.get('notes').trim(), ...(kind === 'income' ? {source} : {category:source,payment_method:method})})}}>
    <FormField label="Amount (INR)"><AmountInput value={amount} onChange={e => setAmount(e.target.value)}/></FormField>
    <FormField label={kind === 'income' ? 'Income source' : 'Expense category'}><CategorySelector kind={kind} value={source} onChange={e => setSource(e.target.value)}/></FormField>
    <DateSelector value={date} onChange={e => setDate(e.target.value)}/>
    {kind === 'expenses' && <FormField label="Payment method"><select value={method} onChange={e => setMethod(e.target.value)} required>{paymentMethods.map(item => <option key={item}>{item}</option>)}</select></FormField>}
    <FormField label="Description"><input name="description" maxLength="500" defaultValue={value?.description || ''} placeholder={kind === 'income' ? 'e.g. June allowance' : 'e.g. Groceries for the week'}/></FormField>
    <FormField label="Notes (optional)"><textarea name="notes" maxLength="2000" defaultValue={value?.notes || ''} rows="2" placeholder="Add a note for your own reference"/></FormField>
    {error&&<div className="transaction-notice error" role="alert"><CircleAlert size={15}/>{error}</div>}
    <div className="transaction-form-actions"><button type="button" className="button secondary" onClick={onClose}>Cancel</button><button className="button primary" disabled={busy}>{busy?'Saving…':value?'Save changes':`Add ${kind}`}</button></div>
  </form>
}

export function AddTransactionModal({ kind, onClose, onSave, busy, error }) {
  return <Modal title={`Add ${kind}`} onClose={onClose}><TransactionForm kind={kind} onSubmit={onSave} onClose={onClose} busy={busy} error={error}/></Modal>
}
export function EditTransactionModal({ kind, transaction, onClose, onSave, busy, error }) {
  return <Modal title={`Edit ${kind}`} onClose={onClose}><TransactionForm key={transaction.id} kind={kind} value={transaction} onSubmit={onSave} onClose={onClose} busy={busy} error={error}/></Modal>
}

const freshFilters = () => ({search:'',source:'',category:'',date_from:'',date_to:'',sort_by:'date',sort_order:'desc'})
export default function TransactionManagement({ kind }) {
  const isIncome = kind === 'income', endpoint = `/${kind}`, noun = isIncome ? 'Income' : 'Expenses'
  const [rows,setRows]=useState([]),[loading,setLoading]=useState(true),[error,setError]=useState(''),[success,setSuccess]=useState(''),[filters,setFilters]=useState(freshFilters),[editor,setEditor]=useState(null),[saving,setSaving]=useState(false)
  const query = buildTransactionQuery(filters, kind)
  const load = useCallback(async () => {setLoading(true);setError('');try{setRows(await request(`${endpoint}?${query}`))}catch(e){setError(e.message)}finally{setLoading(false)}},[endpoint,query])
  useEffect(()=>{load()},[load])
  async function save(payload){setSaving(true);setError('');try{await request(editor?.id?`${endpoint}/${editor.id}`:endpoint,{method:editor?.id?'PUT':'POST',body:JSON.stringify(payload)});setEditor(null);setSuccess(`${noun} ${editor?.id?'updated':'added'} successfully.`);await load();setTimeout(()=>setSuccess(''),3500)}catch(e){setError(e.message)}finally{setSaving(false)}}
  async function remove(row){if(!window.confirm(`Delete this ${isIncome?'income':'expense'} record? This cannot be undone.`))return;setError('');try{await request(`${endpoint}/${row.id}`,{method:'DELETE'});setSuccess(`${noun} record deleted.`);await load();setTimeout(()=>setSuccess(''),3500)}catch(e){setError(e.message)}}
  return <>
    <div className="page-header"><div><div className="eyebrow">{isIncome?'MONEY IN':'MONEY OUT'}</div><h1>{isIncome?'Income':'Expenses'}</h1><p>{isIncome?'Keep a clear history of allowances and other income.':'Track everyday spending and see where your money goes.'}</p></div><button className="button primary" onClick={()=>setEditor({create:true})}><Plus size={16}/> Add {isIncome?'income':'expense'}</button></div>
    {success&&<div className="transaction-notice success"><CheckCircle2 size={16}/>{success}<button aria-label="Dismiss message" onClick={()=>setSuccess('')}><X size={15}/></button></div>}
    {error&&<div className="transaction-notice error"><CircleAlert size={16}/>{error}<button aria-label="Dismiss error" onClick={()=>setError('')}><X size={15}/></button></div>}
    <section className="transaction-panel"><TransactionFilters kind={kind} filters={filters} setFilters={setFilters}/><TransactionTable kind={kind} rows={rows} loading={loading} onEdit={setEditor} onDelete={remove}/><div className="transaction-count">Showing {rows.length} {rows.length===1?'record':'records'} <span>·</span> {isIncome?'Your income history':'Your expense history'}</div></section>
    {editor?.create&&<AddTransactionModal kind={isIncome?'income':'expense'} onClose={()=>setEditor(null)} onSave={save} busy={saving} error={error}/>}
    {editor?.id&&<EditTransactionModal kind={isIncome?'income':'expense'} transaction={editor} onClose={()=>setEditor(null)} onSave={save} busy={saving} error={error}/>}
  </>
}
