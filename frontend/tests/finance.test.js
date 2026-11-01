import test from 'node:test'
import assert from 'node:assert/strict'
import { budgetStatus, budgetUtilization, netPosition, savingsProgress } from '../src/utils/finance.js'
import { buildTransactionQuery } from '../src/utils/transactionFilters.js'

test('net position uses cents precision', () => {
  assert.equal(netPosition(1200.1, 800.05), 400.05)
})

test('budget utilization handles thresholds and zero budgets', () => {
  assert.equal(budgetUtilization(75, 100), 75)
  assert.equal(budgetUtilization(90, 100), 90)
  assert.equal(budgetUtilization(20, 0), 0)
})

test('budget warning levels use exact paise thresholds', () => {
  assert.equal(budgetStatus(74.99, 100), 'normal')
  assert.equal(budgetStatus(75, 100), 'warning')
  assert.equal(budgetStatus(89.99, 100), 'warning')
  assert.equal(budgetStatus(90, 100), 'critical')
  assert.equal(budgetStatus(100, 100), 'critical')
  assert.equal(budgetStatus(100.01, 100), 'exceeded')
  assert.equal(budgetStatus(1, 0), 'unbudgeted')
})

test('savings progress is capped at the goal target', () => {
  assert.equal(savingsProgress(12000, 50000), 24)
  assert.equal(savingsProgress(60000, 50000), 100)
  assert.equal(savingsProgress(1, 0), 0)
})

test('income transaction query includes search, source, dates and sort order', () => {
  const query = new URLSearchParams(buildTransactionQuery({ search:'home', source:'Scholarship', category:'Food', date_from:'2025-01-01', date_to:'2025-01-31', sort_by:'amount', sort_order:'asc' }, 'income'))
  assert.equal(query.get('search'), 'home')
  assert.equal(query.get('source'), 'Scholarship')
  assert.equal(query.get('category'), null)
  assert.equal(query.get('date_from'), '2025-01-01')
  assert.equal(query.get('sort_by'), 'amount')
})

test('expense transaction query filters by category and omits income source', () => {
  const query = new URLSearchParams(buildTransactionQuery({ search:'bus', source:'Scholarship', category:'Travel', date_from:'', date_to:'', sort_by:'date', sort_order:'desc' }, 'expenses'))
  assert.equal(query.get('category'), 'Travel')
  assert.equal(query.get('source'), null)
  assert.equal(query.get('search'), 'bus')
})
