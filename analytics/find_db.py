"""
Database finder - helps locate the MCP database
"""
import os
import sqlite3
from datetime import datetime

def find_databases():
    """Find all SQLite databases in the project and nearby directories."""
    import glob
    
    patterns = [
        "**/*.db",
        "**/memory.db",
        "**/*.sqlite",
        "**/*.sqlite3"
    ]
    
    databases = []
    for pattern in patterns:
        for db_file in glob.glob(pattern, recursive=True):
            try:
                stat = os.stat(db_file)
                databases.append({
                    'path': db_file,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            except:
                pass
    
    return databases

def check_database(db_path):
    """Check what's in a database."""
    if not os.path.exists(db_path):
        return {'error': 'File not found'}
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]
        
        # Get counts
        counts = {}
        for table in tables:
            if table != 'sqlite_sequence':
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    counts[table] = cursor.fetchone()[0]
                except:
                    counts[table] = 'ERROR'
        
        conn.close()
        
        return {
            'path': db_path,
            'tables': tables,
            'counts': counts,
            'size': os.path.getsize(db_path)
        }
    except Exception as e:
        return {'error': str(e)}

def main():
    print("=" * 60)
    print("  Database Finder")
    print("=" * 60)
    
    # Find databases
    print("\nSearching for databases...")
    dbs = find_databases()
    
    if not dbs:
        print("No databases found!")
        return
    
    print(f"\nFound {len(dbs)} databases:\n")
    for db in dbs:
        print(f"  {db['path']}")
        print(f"    Size: {db['size']} bytes, Modified: {db['modified']}")
    
    # Check each database
    print("\n" + "=" * 60)
    print("  Database Contents")
    print("=" * 60)
    
    for db in dbs:
        result = check_database(db['path'])
        if 'error' in result:
            print(f"\n{db['path']}: ERROR - {result['error']}")
        else:
            print(f"\n{result['path']}")
            print(f"  Tables: {result['tables']}")
            print(f"  Counts:")
            for table, count in result['counts'].items():
                print(f"    {table}: {count}")

if __name__ == "__main__":
    main()
