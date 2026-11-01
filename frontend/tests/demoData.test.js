import test from 'node:test'
import assert from 'node:assert/strict'
import { demoCategories, demoMonthly } from '../src/pages/demoData.js'

test('demo category totals match the demo monthly expense total', () => {
  const june = demoMonthly.find(row => row.month === 'Jun')
  assert.equal(demoCategories.reduce((sum, category) => sum + category.value, 0), june.expenses)
})

test('demo sample numbers are explicit constants and contain no account identifiers', () => {
  for (const row of demoMonthly) {
    assert.equal(typeof row.income, 'number')
    assert.equal(typeof row.expenses, 'number')
    assert.equal('user_id' in row, false)
  }
})
