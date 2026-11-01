// Fictional data used only by the explicitly labeled UI demo.
// It is never sent to the API or stored as a user's financial record.
export const demoTransactions = [
  { id: 1, name: 'Hostel rent', category: 'Rent', date: '2025-06-02', amount: 6200, method: 'Bank transfer', type: 'Expense' },
  { id: 2, name: 'Monthly allowance', category: 'Allowance', date: '2025-06-01', amount: 12000, method: 'Bank transfer', type: 'Income' },
  { id: 3, name: 'Groceries at More', category: 'Food', date: '2025-05-30', amount: 840, method: 'UPI', type: 'Expense' },
  { id: 4, name: 'Metro card top-up', category: 'Travel', date: '2025-05-29', amount: 500, method: 'UPI', type: 'Expense' },
  { id: 5, name: 'Freelance design', category: 'Side income', date: '2025-05-28', amount: 2500, method: 'Bank transfer', type: 'Income' },
  { id: 6, name: 'Dinner with friends', category: 'Food', date: '2025-05-27', amount: 460, method: 'UPI', type: 'Expense' },
  { id: 7, name: 'Course materials', category: 'Education', date: '2025-06-01', amount: 250, method: 'UPI', type: 'Expense' },
]

export const demoBills = [
  { id: 1, name: 'Hostel rent', date: '2025-06-05', amount: 6200, category: 'Housing', icon: 'home' },
  { id: 2, name: 'Mobile recharge', date: '2025-06-08', amount: 399, category: 'Utilities', icon: 'phone' },
  { id: 3, name: 'Music subscription', date: '2025-06-12', amount: 119, category: 'Subscription', icon: 'music' },
]

export const demoMonthly = [
  { month: 'Jan', income: 14500, expenses: 10900 }, { month: 'Feb', income: 12500, expenses: 9800 },
  { month: 'Mar', income: 15800, expenses: 11700 }, { month: 'Apr', income: 12500, expenses: 10500 },
  { month: 'May', income: 14500, expenses: 11200 }, { month: 'Jun', income: 12000, expenses: 8250 },
]

export const demoCategories = [
  { name: 'Rent', value: 6200, color: '#16a47b' }, { name: 'Food', value: 1100, color: '#f2aa51' },
  { name: 'Travel', value: 500, color: '#6b87d9' }, { name: 'Education', value: 250, color: '#9b82d3' },
  { name: 'Other', value: 200, color: '#d5e3df' },
]
