import test from 'node:test'
import assert from 'node:assert/strict'
import { filterReminderRows } from '../src/utils/reminders.js'

const rows=[
 {id:1,title:'Campus rent',category:'Rent',status:'overdue',due_date:'2026-11-01'},
 {id:2,title:'Internet',category:'Internet',status:'upcoming',due_date:'2026-12-01'},
 {id:3,title:'Water bill',category:'Water',status:'paid',due_date:'2026-11-11'},
]

test('reminder filtering scopes month and combines search/category/status',()=>{
 assert.deepEqual(filterReminderRows(rows,{month:'2026-11',query:'campus',category:'Rent',status:'overdue'}).map(x=>x.id),[1])
 assert.deepEqual(filterReminderRows(rows,{month:'2026-11',status:'upcoming'}),[])
})

test('year reminder filtering spans months but remains within the selected year',()=>{
 assert.deepEqual(filterReminderRows(rows,{year:'2026',period:'year'}).map(x=>x.id),[1,2,3])
 assert.deepEqual(filterReminderRows(rows,{year:'2025',period:'year'}),[])
})
