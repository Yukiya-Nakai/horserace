import time
import random
import requests
from bs4 import BeautifulSoup
import pandas as pd
import sqlite3
import traceback

# ==========================================
# 1. データベースの初期設定
# ==========================================
def setup_database(db_name="keiba_data.db"):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    # レース基本情報テーブル
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS race_info (
        race_id TEXT PRIMARY KEY,
        race_name TEXT,
        course_details TEXT
    )
    ''')
    
    # レース結果（出走馬）テーブル
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS race_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        race_id TEXT,
        着順 TEXT,
        枠番 TEXT,
        馬番 TEXT,
        馬名 TEXT,
        性齢 TEXT,
        斤量 TEXT,
        騎手 TEXT,
        単勝 TEXT,
        人気 TEXT,
        FOREIGN KEY (race_id) REFERENCES race_info(race_id)
    )
    ''')
    conn.commit()
    return conn

# ==========================================
# 2. スクレイピング関数 (前回ベース・DB保存追加)
# ==========================================
def scrape_and_save_race(race_id, conn):
    url = f"https://db.netkeiba.com/race/{race_id}/"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        # 存在しないURL（開催されていない日など）の場合はスキップ
        if response.status_code != 200:
            return False 
            
        response.encoding = 'EUC-JP'
        soup = BeautifulSoup(response.text, 'html.parser')

        # タイトルが取得できなければエラー（レースが存在しないページ）
        title_tag = soup.find("div", class_="data_intro")
        if not title_tag:
            return False

        # --- レース情報の取得 ---
        race_name = title_tag.find("h1").text.strip() if title_tag.find("h1") else "Unknown"
        course_details = ""
        diary_snap = soup.find("diary_snap_cut")
        if diary_snap and diary_snap.find("span"):
            course_texts = diary_snap.find("span").text.replace("\xa0", "").split("/")
            course_details = " | ".join([t.strip() for t in course_texts])

        # --- DBに保存 (race_info) ---
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO race_info (race_id, race_name, course_details)
            VALUES (?, ?, ?)
        ''', (race_id, race_name, course_details))

        # --- 結果テーブルの取得 ---
        
        clean_html = response.text.replace('<br>', '').replace('<br />', '').replace('\n', '')
        dfs = pd.read_html(clean_html)
        if len(dfs) > 0:
            results_df = dfs[0]
            target_columns = ['着順', '枠番', '馬番', '馬名', '性齢', '斤量', '騎手', '単勝', '人気']
            available_columns = [col for col in target_columns if col in results_df.columns]
            results_df = results_df[available_columns]
            results_df['race_id'] = race_id
            
            # DataFrameからDBに一括保存
            results_df.to_sql('race_results', conn, if_exists='append', index=False)

        conn.commit()
        print(f"✅ 取得成功: {race_id} ({race_name})")
        return True

    except Exception as e:
        print(f"⚠️ {race_id} 取得スキップ (データ無し等)")
        return False

# ==========================================
# 3. ID自動生成と実行ループ
# ==========================================
def collect_year_data(year):
    conn = setup_database()
    place_codes = [str(i).zfill(2) for i in range(1, 11)] # 01〜10
    
    print(f"🚀 {year}年のデータ収集を開始します...")
    
    for place in place_codes:
        # 開催回数 (通常1〜6回)
        for kai in range(1, 7):
            # 開催日数 (通常1〜12日)
            for day in range(1, 13):
                empty_race_count = 0
                
                # レース番号 (1〜12R)
                for race_num in range(1, 13):
                    race_id = f"{year}{place}{str(kai).zfill(2)}{str(day).zfill(2)}{str(race_num).zfill(2)}"
                    
                    if int(race_id) < 201509040410:
                        continue
                    
                    # スクレイピング実行
                    success = scrape_and_save_race(race_id, conn)
                    
                    if not success:
                        empty_race_count += 1
                        # 1Rが存在しない場合は、その日自体が開催されていないと判断して次の日へ
                        if race_num == 1 or 2:
                            break
                    
                    # 必須：サーバーへの優しさ（ランダムスリープ）
                    time.sleep(random.uniform(0.1, 2.0))
                
                # その日のレースが全く無かったら、その開催回は終了したとみなして次へ
                if empty_race_count >= 12:
                    break

    conn.close()
    print("🎉 全データの収集が完了しました！")

# 実行
if __name__ == "__main__":
    # まずはテストとして特定の競馬場・短い期間に絞ることを推奨しますが、
    # 以下の関数で指定した年を丸ごと収集できます。
    # ※1年分回すのに数時間かかります。途中で止めても再開可能です。
    for year in range(2015, 2027):
        collect_year_data(year)
