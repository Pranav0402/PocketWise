export function filterReminderRows(rows,{month,year,period='month',query='',category='',status=''}){
 const term=String(query||'').trim().toLowerCase()
 return (rows||[]).filter(row=>(period==='year'?String(row.due_date||'').startsWith(String(year)):String(row.due_date||'').startsWith(String(month)))&&(!term||`${row.title||''} ${row.category||''} ${row.description||''}`.toLowerCase().includes(term))&&(!category||row.category===category)&&(!status||row.status===status))
}
