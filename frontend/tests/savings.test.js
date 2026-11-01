import test from 'node:test'
import assert from 'node:assert/strict'
import { emergencyRange, savingsCashFlow, savingsProgress, savingsRemaining } from '../src/utils/savings.js'

test('savings planner caps progress and calculates remaining without floating point drift',()=>{
 assert.equal(savingsProgress(24.1,100),24)
 assert.equal(savingsProgress(120,100),100)
 assert.equal(savingsRemaining(0.1,1),0.9)
})

test('savings cash flow treats deposits and withdrawals as separate cash movements in paise',()=>{
 assert.equal(savingsCashFlow([{transaction_type:'contribution',amount:10.1},{transaction_type:'withdrawal',amount:3.05}]),-705)
})

test('emergency fund guide derives a three to six month range from recorded monthly expenses',()=>{
 assert.deepEqual(emergencyRange(1200.5),{low:3601.5,high:7203})
})
