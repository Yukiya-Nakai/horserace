import time
import random
import requests
from bs4 import BeautifulSoup
import pandas as pd

def scrape_race_data(race_id):
    url = f"https://db.netkeiba.com/race/{race_id}/"
    
    # サーバーから弾かれないようUser-Agentを偽装（一般的なブラウザからのアクセスに見せかける）
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() # エラーがあれば例外を発生させる
        
        # netkeiba特有の文字コード対策
        response.encoding = 'EUC-JP'
        html = response.text
        
        soup = BeautifulSoup(html, 'html.parser')

        # --------------------------------------------------
        # 1. レース基本情報の取得 (レース名、コース、馬場など)
        # --------------------------------------------------
        race_info = {}
        
        # レース名
        title_tag = soup.find("div", class_="data_intro")
        if title_tag and title_tag.find("h1"):
            race_info['race_name'] = title_tag.find("h1").text.strip()
        
        # コース・馬場状態などの詳細テキスト（例: "芝右2500m / 天候 : 曇 / 芝 : 良 / 発走 : 15:25"）
        diary_snap = soup.find("diary_snap_cut")
        if diary_snap and diary_snap.find("span"):
            course_texts = diary_snap.find("span").text.replace("\xa0", "").split("/")
            race_info['course_details'] = [t.strip() for t in course_texts]

        # --------------------------------------------------
        # 2. 出走馬・レース結果テーブルの取得 (pandasを使用)
        # --------------------------------------------------
        # HTML内のすべての<table>タグをDataFrameとして読み込む
        dfs = pd.read_html(html)
        
        if len(dfs) > 0:
            results_df = dfs[0]
            
            # 不要な列（「タイム指数」「通過」「上り」など、今回の要件にないもの）を落とすなど
            # 必要な列だけを抽出（実際のサイトの列名に合わせて調整します）
            # 今回はLLMに渡すための必須項目（着順, 枠番, 馬番, 馬名, 性齢, 斤量, 騎手）に絞ります
            target_columns = ['着順', '枠番', '馬番', '馬名', '性齢', '斤量', '騎手', '単勝', '人気']
            
            # 存在する列のみ残す
            available_columns = [col for col in target_columns if col in results_df.columns]
            results_df = results_df[available_columns]
            
            # レースIDをキーとして持たせておく（後でDBで結合するため）
            results_df['race_id'] = race_id
            
        else:
            results_df = pd.DataFrame()

        print(f"✅ レースID: {race_id} の取得完了")
        
        return race_info, results_df

    except Exception as e:
        print(f"❌ レースID: {race_id} の取得に失敗しました: {e}")
        return None, None

# ==========================================
# 実行部分
# ==========================================
if __name__ == "__main__":
    # テストとして2つのレースをスクレイピング
    # 201906050811 (2019年有馬記念), 202306050811 (2023年有馬記念)
    target_race_ids = ["201906050811", "202306050811"]
    
    all_results = []
    
    for race_id in target_race_ids:
        info, df = scrape_race_data(race_id)
        
        if info and df is not None:
            print("【レース情報】", info)
            # DataFrameをリストに格納
            all_results.append(df)
            
        # 🚨【最重要】連続アクセスの場合は必ず2〜5秒のランダムな待機時間を入れる
        sleep_time = random.uniform(2, 5)
        time.sleep(sleep_time)

    # 取得したすべての表を縦に結合して1つのCSVに出力
    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)
        final_df.to_csv("horse_racing_results.csv", index=False, encoding="utf-8-sig")
        print("\n🎉 データの取得とCSV保存が完了しました (horse_racing_results.csv)")
        
        # 取得したデータの先頭を表示
        print(final_df.head())
