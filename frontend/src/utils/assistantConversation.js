export const WELCOME_MESSAGE = Object.freeze({
  role: 'assistant',
  text: 'Hi! I can help you understand your saved finances, budgets, savings, bills, and friend balances. Ask me a question or try one of the prompts.',
  id: 'welcome',
})

export function conversationReducer(messages, action) {
  if (action.type === 'clear') return [WELCOME_MESSAGE]
  if (action.type === 'append' && action.message?.role && action.message?.text) return [...messages, action.message]
  return messages
}
