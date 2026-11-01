export function savingsProgress(balance,target){return target>0?Math.min(100,Math.max(0,Math.round((Number(balance)||0)*100/Number(target)))):0}
export function savingsRemaining(balance,target){return Math.max(0,Math.round(((Number(target)||0)-(Number(balance)||0))*100)/100)}
export function savingsCashFlow(transactions){return (transactions||[]).reduce((sum,x)=>sum+(x.transaction_type==='withdrawal'?1:-1)*Math.round((Number(x.amount)||0)*100),0)}
export function emergencyRange(monthlyExpenses){const average=Math.max(0,Number(monthlyExpenses)||0);return {low:Math.round(average*3*100)/100,high:Math.round(average*6*100)/100}}
