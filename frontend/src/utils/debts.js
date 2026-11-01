export function amountToPaise(value) {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return 0
  return Math.round((amount + Number.EPSILON) * 100)
}

export function debtStatus({ amount = 0, repaid = 0, due_date: dueDate = null }, today) {
  const remaining = amountToPaise(amount) - amountToPaise(repaid)
  if (remaining <= 0) return 'fully_paid'
  if (dueDate && dueDate < today) return 'overdue'
  return repaid > 0 ? 'partial' : 'unpaid'
}

export function debtCashFlowPaise(debts, repayments) {
  const byId = new Map(debts.map(debt => [debt.id, debt]))
  const principalFlow = debts.reduce((sum, debt) => sum + (debt.direction === 'borrowed' ? 1 : -1) * amountToPaise(debt.amount), 0)
  const repaymentFlow = repayments.reduce((sum, repayment) => {
    const debt = byId.get(repayment.debt_id)
    if (!debt) return sum
    return sum + (debt.direction === 'lent' ? 1 : -1) * amountToPaise(repayment.amount)
  }, 0)
  return principalFlow + repaymentFlow
}
