import sqlite3
import pandas as pd
import re

def clean_course_details(db_path="keiba_data.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("🔍 データベースを読み込んでいます...")
    df = pd.read_sql("SELECT * FROM race_info", conn)
    
    new_columns = {
        "surface": "TEXT",
        "direction": "TEXT",
        "distance": "INTEGER",
        "weather": "TEXT",
        "condition": "TEXT"
    }
    
    for col, dtype in new_columns.items():
        try:
            cursor.execute(f"ALTER TABLE race_info ADD COLUMN {col} {dtype}")
        except sqlite3.OperationalError:
            pass # 既にカラムが存在する場合はスキップ（今回はここを通ります）
            
    print("⚙️ 文字列の分割・解析処理を開始します (内外回り対応版)...")
    
    update_data = []
    
    for _, row in df.iterrows():
        race_id = row['race_id']
        details = str(row['course_details'])
        
        surface, direction, distance, weather, condition = None, None, None, None, None
        
        # 💡 修正点：スペース(\s)を許容し、右・左・直・内・外の組み合わせをすべて拾う
        match_track = re.search(r'(芝|ダ|ダート|障|障害)\s*([右左直内外\s]*)\s*(\d+)m', details)
        if match_track:
            surface_raw = match_track.group(1)
            # スペースを除去して「右外」「左内」のように綺麗な文字列にする
            direction_raw = match_track.group(2).replace(' ', '').replace('\u3000', '')
            
            surface = "芝" if "芝" in surface_raw else "ダート" if "ダ" in surface_raw else "障害"
            direction = direction_raw if direction_raw else "不明"
            distance = int(match_track.group(3))
            
        match_weather = re.search(r'天候\s*:\s*([^\s|]+)', details)
        if match_weather:
            weather = match_weather.group(1).strip()
            
        match_cond = re.search(r'(芝|ダート|ダ|障害)\s*:\s*([^\s|]+)', details)
        if match_cond:
            condition = match_cond.group(2).strip()
            
        update_data.append((surface, direction, distance, weather, condition, race_id))
    
    print("💾 データベースを更新しています...")
    cursor.executemany("""
        UPDATE race_info 
        SET surface = ?, direction = ?, distance = ?, weather = ?, condition = ?
        WHERE race_id = ?
    """, update_data)
    
    conn.commit()
    
    # 💡 先ほどエラーになった 201509040408 (芝右 外1800m) が直ったかピンポイントで確認
    check_df = pd.read_sql("SELECT race_id, course_details, surface, direction, distance FROM race_info WHERE race_id = '201509040408'", conn)
    print("\n✅ クレンジング完了！修正確認:")
    print(check_df)
    
    conn.close()

if __name__ == "__main__":
    clean_course_details()