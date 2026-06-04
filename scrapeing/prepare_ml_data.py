import sqlite3
import pandas as pd
import numpy as np

def create_training_data(db_path="keiba_data.db", output_csv="train_data.csv"):
    conn = sqlite3.connect(db_path)
    
    print("🔍 データベースから過去のレース結果を抽出しています...")
    # race_results と 先ほど綺麗にした race_info を結合して取得
    query = """
    SELECT
        r.race_id, r.馬番, r.枠番, r.性齢, r.斤量, r.着順,
        i.surface, i.direction, i.distance, i.weather, i.condition
    FROM race_results r
    JOIN race_info i ON r.race_id = i.race_id
    """
    df = pd.read_sql(query, conn)
    conn.close()

    print("⚙️ 特徴量（AIの入力データ）を生成しています...")

    # 1. 目的変数（正解ラベル）の作成
    # 着順には「取消」「除外」や「1(降)」などの文字が混ざるため、数字だけを抽出
    df['着順_num'] = df['着順'].astype(str).str.extract(r'(\d+)').astype(float)
    df = df.dropna(subset=['着順_num']) # 着順が取れない行（出走取消など）は削除
    
    # 今回は「1着になる確率（勝率）」を予測するため、1着なら1、それ以外は0とする
    df['target'] = (df['着順_num'] == 1).astype(int)

    # 2. テキストデータの分解（例: "牡4" -> 性別="牡", 年齢=4）
    df['性別'] = df['性齢'].astype(str).str[0]
    df['年齢'] = df['性齢'].astype(str).str[1:].astype(float)

    # 3. 数値型のキャスト（文字列を計算可能な数字に変換）
    for col in ['枠番', '馬番', '斤量', 'distance']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # 4. LightGBM向けのカテゴリ変数化
    # 決定木モデルは、これをカテゴリとして指定するだけで勝手に特徴を学習してくれます
    cat_cols = ['surface', 'direction', 'weather', 'condition', '性別']
    for col in cat_cols:
        df[col] = df[col].astype('category')

    # AIに学習させる特徴量カラムのリスト
    features = [
        '枠番', '馬番', '斤量', '年齢', '性別', 
        'surface', 'direction', 'distance', 'weather', 'condition'
    ]
    
    # 必要な列だけを抽出し、欠損値がある行を一旦綺麗に削除
    output_df = df[['race_id', 'target'] + features].copy()
    output_df = output_df.dropna()
    
    print("💾 学習用データをCSVとして保存しています...")
    output_df.to_csv(output_csv, index=False)
    
    print(f"✅ 学習データ ({output_csv}) の作成完了！")
    print(f"📊 抽出された有効なデータ件数: {len(output_df)}件")
    print("\nデータのプレビュー:")
    print(output_df.head())

if __name__ == "__main__":
    create_training_data()