#!/usr/bin/env python3

import sqlite3
from datetime import datetime
import uuid

def add_june_transactions():
    """Add test transactions for June 2025 to demonstrate budget progress"""
    
    conn = sqlite3.connect('personalcfo.db')
    cursor = conn.cursor()

    # User ID for dierios93@gmail.com
    user_id = '374d3d13-0e4c-4f6a-954e-04ee6af17251'

    # Get a card ID for this user
    cursor.execute('SELECT id FROM cards WHERE user_id = ? LIMIT 1', (user_id,))
    card_result = cursor.fetchone()
    
    if not card_result:
        print('No cards found for user')
        return False

    card_id = card_result[0]
    print(f'Using card ID: {card_id}')

    # Clear any existing June 2025 transactions to avoid duplicates
    cursor.execute('''
        DELETE FROM transactions 
        WHERE card_id IN (SELECT id FROM cards WHERE user_id = ?) 
        AND transaction_date >= '2025-06-01' 
        AND transaction_date <= '2025-06-30'
    ''', (user_id,))
    
    deleted_count = cursor.rowcount
    print(f'Deleted {deleted_count} existing June 2025 transactions')

    # Test transactions for June 2025
    # Budget: Alimentación = 1500 PEN, Educación = 10 PEN
    test_transactions = [
        # Alimentación category - Add 1600 PEN total (106.7% over 1500 budget)
        ('2025-06-01', 'Alimentación', 'Supermercado Metro', 350.00, 'Weekly groceries'),
        ('2025-06-05', 'Alimentación', 'Restaurant Central', 180.00, 'Family dinner'),
        ('2025-06-10', 'Alimentación', 'Tottus', 420.00, 'Monthly shopping'),
        ('2025-06-15', 'Alimentación', 'Cafeteria', 45.00, 'Lunch at work'),
        ('2025-06-20', 'Alimentación', 'Plaza Vea', 285.00, 'Groceries'),
        ('2025-06-25', 'Alimentación', 'KFC', 38.50, 'Fast food'),
        ('2025-06-28', 'Alimentación', 'Mercado', 125.00, 'Fresh produce'),
        ('2025-06-30', 'Alimentación', 'Starbucks', 156.50, 'Coffee meeting'),
        
        # Educación category - Add 40 PEN total (400% over 10 budget)
        ('2025-06-08', 'Educación', 'Libreria Crisol', 25.00, 'Programming books'),
        ('2025-06-15', 'Educación', 'Coursera', 15.00, 'Online course subscription'),
    ]

    print(f'Adding {len(test_transactions)} test transactions for June 2025...')

    for tx_date, category, merchant, amount, description in test_transactions:
        tx_id = str(uuid.uuid4())
        cursor.execute('''
            INSERT INTO transactions 
            (id, card_id, merchant, amount, transaction_date, category, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            tx_id, card_id, merchant, amount, tx_date, category, description,
            datetime.now(), datetime.now()
        ))

    conn.commit()
    print('All transactions added and committed')

    # Verify the transactions
    print('\nVerifying June 2025 transactions:')
    cursor.execute('''
        SELECT t.category, SUM(t.amount) as total_amount, COUNT(*) as count
        FROM transactions t 
        JOIN cards c ON t.card_id = c.id 
        WHERE c.user_id = ? 
        AND t.transaction_date >= '2025-06-01' 
        AND t.transaction_date <= '2025-06-30'
        GROUP BY t.category
        ORDER BY total_amount DESC
    ''', (user_id,))

    transactions = cursor.fetchall()
    total_spent = 0
    
    for tx in transactions:
        print(f'   {tx[0]}: {tx[1]} PEN ({tx[2]} transactions)')
        total_spent += float(tx[1])
    
    print(f'\nTotal spent in June 2025: {total_spent} PEN')

    # Check against budgets
    print('\nBudget vs Spending comparison:')
    cursor.execute('SELECT category, limit_amount FROM budgets WHERE user_id = ?', (user_id,))
    budgets = cursor.fetchall()
    
    spending_dict = {tx[0]: tx[1] for tx in transactions}
    
    for budget_category, budget_amount in budgets:
        spent = spending_dict.get(budget_category, 0)
        percentage = (spent / float(budget_amount)) * 100 if budget_amount > 0 else 0
        status = "OVER BUDGET" if percentage > 100 else "WITHIN BUDGET"
        print(f'   {budget_category}: {spent}/{budget_amount} PEN ({percentage:.1f}%) - {status}')

    conn.close()
    return True

if __name__ == '__main__':
    try:
        success = add_june_transactions()
        if success:
            print('\n✅ Successfully added June 2025 test transactions!')
            print('The budget progress component should now show actual spending values.')
        else:
            print('❌ Failed to add transactions')
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()
