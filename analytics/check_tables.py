import sqlite3

conn = sqlite3.connect('memory_store_v2/memory.db')
cursor = conn.cursor()

# List tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print('Tables:', cursor.fetchall())

# Check each table
for table in ['sessions', 'tasks', 'checkpoints', 'long_term_memory', 'short_term_memory']:
    try:
        cursor.execute(f'SELECT COUNT(*) FROM {table}')
        count = cursor.fetchone()[0]
        print(f'{table}: {count} rows')
    except Exception as e:
        print(f'{table}: ERROR - {e}')

conn.close()
