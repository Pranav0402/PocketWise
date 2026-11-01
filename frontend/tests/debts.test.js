import test from 'node:test'
import assert from 'node:assert/strict'
import { amountToPaise, debtCashFlowPaise, debtStatus } from '../src/utils/debts.js'

test('debt status handles partial, settled and overdue balances', () => {
  assert.equal(debtStatus({ amount: 2000, repaid: 500, due_date: '2026-12-01' }, '2026-11-01'), 'partial')
  assert.equal(debtStatus({ amount: 2000, repaid: 2000, due_date: '2026-01-01' }, '2026-11-01'), 'fully_paid')
  assert.equal(debtStatus({ amount: 2000, repaid: 0, due_date: '2026-10-31' }, '2026-11-01'), 'overdue')
  assert.equal(debtStatus({ amount: 2000, repaid: 0, due_date: null }, '2026-11-01'), 'unpaid')
})

test('cash flow keeps borrowed and lent principal and repayments separate in integer paise', () => {
  assert.equal(amountToPaise('10.10'), 1010)
  const debts = [{ id: 1, direction: 'borrowed', amount: 10.10 }, { id: 2, direction: 'lent', amount: 5 }]
  const repayments = [{ debt_id: 1, amount: 1.01 }, { debt_id: 2, amount: 2 }]
  assert.equal(debtCashFlowPaise(debts, repayments), 609)
})
