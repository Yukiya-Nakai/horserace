import sqlite3
import pandas as pd

conn = sqlite3.connect('keiba_data.db')

# Check tables
tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table';", conn)
print("Tables:", tables['name'].tolist())

# Check race_info
if 'race_info' in tables['name'].values:
    info_df = pd.read_sql("SELECT * FROM race_info LIMIT 40000;", conn)
    print("\nrace_info sample:")
    print(info_df)
    print("Total race_info rows:", pd.read_sql("SELECT COUNT(*) FROM race_info;", conn).iloc[0,0])
    
# Check race_results
if 'race_results' in tables['name'].values:
    results_df = pd.read_sql("SELECT * FROM race_results LIMIT 5;", conn)
    print("\nrace_results sample:")
    print(results_df)
    print("Total race_results rows:", pd.read_sql("SELECT COUNT(*) FROM race_results;", conn).iloc[0,0])
    
conn.close()
