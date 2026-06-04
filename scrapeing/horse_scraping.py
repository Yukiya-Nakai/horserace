import time
import random
import requests
from bs4 import BeautifulSoup
import pandas as pd
import sqlite3
import urllib.parse

# ==========================================
# 1. データベース設定
# ==========================================
def setup_horse_tables(conn):
    cursor = conn.cursor()
    
    # 【新規】競走馬の基本情報（血統）テーブル
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS horse_info (
        horse_name TEXT PRIMARY KEY,
        sire TEXT,        -- 父
        dam TEXT,         -- 母
        sire_sire TEXT,   -- 父の父
        dam_sire TEXT     -- 母の父 (BMS)
    )
    ''')
    
    # 競走馬の過去成績テーブル
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS horse_results (
        horse_name TEXT,
        日付 TEXT,
        開催 TEXT,
        レース名 TEXT,
        着順 TEXT,
        騎手 TEXT,
        斤量 TEXT,
        距離 TEXT,
        馬場 TEXT,
        タイム TEXT,
        通過 TEXT,
        上り TEXT,
        馬体重 TEXT,
        勝ち馬 TEXT,
        FOREIGN KEY (horse_name) REFERENCES horse_info(horse_name)
    )
    ''')
    conn.commit()

# ==========================================
# 2. 馬名からURLを検索
# ==========================================
def get_horse_url(horse_name):
    try:
        encoded_name = urllib.parse.quote(horse_name.encode('euc-jp'))
        search_url = f"https://db.netkeiba.com/?pid=horse_list&word={encoded_name}&match=1"
        
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(search_url, headers=headers, timeout=10)
        res.encoding = 'EUC-JP'
        
        soup = BeautifulSoup(res.text, 'html.parser')
        table = soup.find("table")
        if table:
            links = table.find_all("a", href=True)
            for link in links:
                if "/horse/" in link['href']:
                    return f"https://db.netkeiba.com{link['href']}"
    except Exception as e:
        print(f"⚠️ {horse_name} のID検索エラー: {e}")
    return None

# ==========================================
# 3. 血統と戦績のスクレイピング
# ==========================================
def scrape_horse_data(horse_name, horse_url, conn):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(horse_url, headers=headers, timeout=10)
        res.encoding = 'EUC-JP'
        html = res.text
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # ------------------------------
        # ① 血統情報の取得 (BeautifulSoup)
        # ------------------------------
        sire, dam, sire_sire, dam_sire = "", "", "", ""
        
        blood_table = soup.find("table", class_="blood_table")
        if blood_table:
            # 父と母は rowspan="4" のセルに入っている
            parents = blood_table.find_all("td", rowspan="4")
            if len(parents) >= 2:
                sire = parents[0].text.strip().replace('\n', '')
                dam = parents[1].text.strip().replace('\n', '')
                
            # 祖父母は rowspan="2" のセルに入っている (0:父の父, 1:父の母, 2:母の父, 3:母の母)
            grandparents = blood_table.find_all("td", rowspan="2")
            if len(grandparents) >= 3:
                sire_sire = grandparents[0].text.strip().replace('\n', '')
                dam_sire = grandparents[2].text.strip().replace('\n', '') # 競馬予想で超重要なBMS

        # 血統データを保存
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO horse_info (horse_name, sire, dam, sire_sire, dam_sire)
            VALUES (?, ?, ?, ?, ?)
        ''', (horse_name, sire, dam, sire_sire, dam_sire))
        
        # ------------------------------
        # ② 過去戦績の取得 (Pandas)
        # ------------------------------
        clean_html = html.replace('<br>', '').replace('<br />', '').replace('\n', '')
        dfs = pd.read_html(clean_html)
        
        history_df = None
        for df in dfs:
            if '日付' in df.columns and 'レース名' in df.columns:
                history_df = df
                break
                
        if history_df is not None:
            target_columns = ['日付', '開催', 'レース名', '着順', '騎手', '斤量', '距離', '馬場', 'タイム', '通過', '上り', '馬体重', '勝ち馬(2着馬)']
            available_columns = [col for col in target_columns if col in history_df.columns]
            
            final_df = history_df[available_columns].copy()
            final_df = final_df.rename(columns={'勝ち馬(2着馬)': '勝ち馬'})
            final_df['horse_name'] = horse_name
            
            final_df.to_sql('horse_results', conn, if_exists='append', index=False)
            
            conn.commit()
            print(f"✅ {horse_name}: 血統と戦績({len(final_df)}戦)を保存しました")
        else:
            conn.commit()
            print(f"⚠️ {horse_name}: 血統は保存しましたが、戦績テーブルがありません")

    except Exception as e:
        print(f"❌ {horse_name} のデータ取得失敗: {e}")

# ==========================================
# 4. メイン実行ループ
# ==========================================
if __name__ == "__main__":
    conn = sqlite3.connect('keiba_data.db')
    setup_horse_tables(conn)
    
    # 既に取得済みの馬リストを取得 (レジューム用)
    cursor = conn.cursor()
    cursor.execute("SELECT horse_name FROM horse_info")
    already_fetched = set([row[0] for row in cursor.fetchall()])
    
    # レースDBに存在する全ての馬名を取得
    horses_df = pd.read_sql("SELECT DISTINCT 馬名 FROM race_results WHERE 馬名 IS NOT NULL", conn)
    all_horse_names = horses_df['馬名'].tolist()
    
    # 未取得の馬だけを対象にする
    target_horses = [name for name in all_horse_names if name not in already_fetched]
    
    print(f"🚀 全{len(all_horse_names)}頭のうち、未取得の {len(target_horses)} 頭のデータ収集を開始します...")
    
    for idx, name in enumerate(target_horses):
        print(f"[{idx+1}/{len(target_horses)}] {name} を処理中...")
        
        horse_url = get_horse_url(name)
        if horse_url:
            scrape_horse_data(name, horse_url, conn)
        else:
            print(f"⚠️ {name} のURLが見つかりませんでした")
            
        time.sleep(random.uniform(2.0, 4.0))

    conn.close()
    print("🎉 競走馬データの収集が完了しました！")
