export function buildTransactionQuery(filters, kind) {
  const params = new URLSearchParams()
  for (const key of ['search', 'date_from', 'date_to', 'sort_by', 'sort_order']) {
    if (filters[key]) params.set(key, filters[key])
  }
  if (kind === 'income' && filters.source) params.set('source', filters.source)
  if (kind === 'expenses' && filters.category) params.set('category', filters.category)
  return params.toString()
}
