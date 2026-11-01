export function buildReportQuery({ period, startDate = '', endDate = '', transactionType = '', category = '', paymentMethod = '' }) {
  const params = new URLSearchParams({ period })
  if (period === 'custom' && startDate && endDate) {
    params.set('start_date', startDate)
    params.set('end_date', endDate)
  }
  if (transactionType) params.set('transaction_type', transactionType)
  if (category) params.set('category', category)
  if (paymentMethod) params.set('payment_method', paymentMethod)
  return params.toString()
}

export function monthlyLabel(value) {
  return new Date(`${value}-02T00:00:00`).toLocaleDateString('en-IN', { month: 'short', year: '2-digit' })
}
