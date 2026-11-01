import test from 'node:test'
import assert from 'node:assert/strict'
import { buildReportQuery, monthlyLabel } from '../src/utils/reports.js'
import { demoMonthly } from '../src/pages/demoData.js'

test('custom report query applies dates and selected filters', () => {
  const params = new URLSearchParams(buildReportQuery({ period:'custom', startDate:'2025-06-01', endDate:'2025-06-30', transactionType:'expense', category:'Food', paymentMethod:'UPI' }))
  assert.equal(params.get('period'),'custom')
  assert.equal(params.get('start_date'),'2025-06-01')
  assert.equal(params.get('end_date'),'2025-06-30')
  assert.equal(params.get('transaction_type'),'expense')
  assert.equal(params.get('category'),'Food')
  assert.equal(params.get('payment_method'),'UPI')
})

test('custom report does not request until dates exist', () => {
  const params = new URLSearchParams(buildReportQuery({ period:'custom', startDate:'', endDate:'' }))
  assert.equal(params.get('start_date'), null)
  assert.equal(params.get('end_date'), null)
})

test('report month labels are derived from period keys and demo remains static data', () => {
  assert.match(monthlyLabel('2025-06'), /Jun/)
  assert.equal(Array.isArray(demoMonthly), true)
  assert.equal(demoMonthly.length > 0, true)
})
