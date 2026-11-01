import test from 'node:test'
import assert from 'node:assert/strict'
import { conversationReducer, WELCOME_MESSAGE } from '../src/utils/assistantConversation.js'

test('assistant conversation appends both roles and clear starts a fresh local conversation', () => {
  let messages=[WELCOME_MESSAGE]
  messages=conversationReducer(messages,{type:'append',message:{id:'u1',role:'user',text:'How much did I spend?'}})
  messages=conversationReducer(messages,{type:'append',message:{id:'a1',role:'assistant',text:'You spent ₹20.00.'}})
  assert.deepEqual(messages.map(x=>x.role),['assistant','user','assistant'])
  assert.deepEqual(conversationReducer(messages,{type:'clear'}),[WELCOME_MESSAGE])
})

test('conversation reducer ignores invalid actions without exposing account data', () => {
  const messages=[WELCOME_MESSAGE]
  assert.equal(conversationReducer(messages,{type:'append',message:{id:'bad',text:'Missing role'}}),messages)
  assert.equal(conversationReducer(messages,{type:'unknown'}),messages)
})
