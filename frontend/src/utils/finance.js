export function netPosition(income, expenses) {
  return Math.round((income - expenses) * 100) / 100
}

export function budgetUtilization(spent, budget) {
  if (!budget || budget <= 0) return 0
  return Math.round((spent / budget) * 10000) / 100
}

export function budgetStatus(spent, budget) {
  if (!budget || budget <= 0) return 'unbudgeted'
  const spentPaise = Math.round((Number(spent) + Number.EPSILON) * 100)
  const budgetPaise = Math.round((Number(budget) + Number.EPSILON) * 100)
  if (spentPaise > budgetPaise) return 'exceeded'
  if (spentPaise * 10 >= budgetPaise * 9) return 'critical'
  if (spentPaise * 4 >= budgetPaise * 3) return 'warning'
  return 'normal'
}

export function savingsProgress(saved, target) {
  if (!target || target <= 0) return 0
  return Math.min(100, Math.round((saved / target) * 10000) / 100)
}
