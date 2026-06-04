import pandas as pd
import sqlite3
import requests
import json
import joblib
import re

# ==========================================
# 1. ML（LightGBM）によるベース勝率の算出
# ==========================================
def calculate_ml_probabilities(csv_path, course_info, model_path='lgbm_model.pkl'):
    # モデルの読み込み
    try:
        model = joblib.load(model_path)
    except FileNotFoundError:
        print(f"❌ モデルファイル {model_path} が見つかりません。")
        return None

    df = pd.read_csv(csv_path, encoding="utf-8")
    
    # MLに入力するための特徴量データフレームを作成
    ml_df = pd.DataFrame()
    ml_df['枠番'] = pd.to_numeric(df['枠'], errors='coerce')
    ml_df['馬番'] = pd.to_numeric(df['馬番'], errors='coerce')
    ml_df['斤量'] = pd.to_numeric(df['斤量'], errors='coerce')
    
    # "牡4" などを 性別="牡", 年齢=4 に分割
    ml_df['性別'] = df['性別年齢'].astype(str).str[0]
    ml_df['年齢'] = df['性別年齢'].astype(str).str[1:].astype(float)
    
    # コース情報の付与（全頭共通）
    ml_df['surface'] = course_info['surface']
    ml_df['direction'] = course_info['direction']
    ml_df['distance'] = course_info['distance']
    ml_df['weather'] = course_info['weather']
    ml_df['condition'] = course_info['condition']
    
    # カテゴリ変数の型変換
    cat_cols = ['surface', 'direction', 'weather', 'condition', '性別']
    for col in cat_cols:
        ml_df[col] = ml_df[col].astype('category')
        
    # 特徴量の並びを学習時と完全に一致させる
    features = ['枠番', '馬番', '斤量', '年齢', '性別', 'surface', 'direction', 'distance', 'weather', 'condition']
    X = ml_df[features]
    
    # 勝率の予測
    probabilities = model.predict(X)
    
    # 確率をパーセンテージに変換して元のデータフレームに結合
    df['ml_prob'] = (probabilities * 100).round(1)
    
    # 確率の合計が100%になるように正規化（オプショナルですが見栄えが良くなります）
    total_prob = df['ml_prob'].sum()
    if total_prob > 0:
        df['ml_prob_normalized'] = (df['ml_prob'] / total_prob * 100).round(1)
    else:
        df['ml_prob_normalized'] = 0.0
        
    return df

# ==========================================
# 2. プロンプト生成 (RAG + ML + CSV)
# ==========================================
def generate_hybrid_prompt(enriched_df, race_name, course_info, db_path="keiba_data.db"):
    conn = sqlite3.connect(db_path)
    
    prompt = f"# 競馬予想タスク：{race_name}\n\n"
    prompt += "あなたはプロの競馬データアナリストです。機械学習モデルが算出した「ベース勝率」と、血統・騎手などの定性的な情報を総合的に勘案し、最終的な勝率（合計1.0）と、その予想根拠を出力してください。\n\n"
    
    # 💡 簡易的なRAG（傾向抽出）の例
    prompt += "## 📊 コースの過去傾向 (RAG抽出データ)\n"
    prompt += f"- 今回の条件: {course_info['surface']} {course_info['distance']}m ({course_info['condition']})\n"
    # ※ここにフェーズ1で作ったDBから血統傾向などを引っ張るSQL処理を入れるとさらに強力になります
    
    prompt += "\n## 🐎 出走馬データとMLベース予測勝率\n"
    
    for _, row in enriched_df.iterrows():
        h_name = row['馬名']
        prompt += f"### 馬番{row['馬番']}：{h_name} ({row['性別年齢']}, {row['斤量']}kg, {row['騎手']})\n"
        prompt += f"- **血統**: 父 {row['父']} / 母 {row['母']}\n"
        prompt += f"- 🤖 **機械学習ベース勝率**: {row['ml_prob_normalized']}%\n"
        
        # 過去戦績の取得
        history_query = f"SELECT 日付, レース名, 着順 FROM horse_results WHERE horse_name = '{h_name}' ORDER BY 日付 DESC LIMIT 3"
        try:
            history = pd.read_sql(history_query, conn)
            if not history.empty:
                prompt += "- **直近3走**:\n"
                for _, h_row in history.iterrows():
                    prompt += f"  - {h_row['日付']} {h_row['レース名']} -> {h_row['着順']}\n"
        except Exception:
            pass
        prompt += "\n"
        
    prompt += """
## 期待する出力フォーマット (JSON)
思考プロセスを含めず、以下のJSONのみを出力してください（Markdownの ```json は不要です）。
{
  "predictions": [
    {
      "horse_number": 1,
      "horse_name": "馬名",
      "final_winning_probability": 0.15,
      "reasoning": "MLのベース勝率に加えて、父系の血統が今回の馬場状態に合致しているため高く評価。"
    }
  ]
}
"""
    conn.close()
    return prompt

# ==========================================
# 3. Ollama への推論リクエスト
# ==========================================
def predict_with_ollama(prompt, model_name="llama3.3"):
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model_name,
        "prompt": prompt,
        "format": "json",
        "stream": False
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return json.loads(response.json()["response"])
    except Exception as e:
        print(f"❌ Ollama エラー: {e}")
        return None

# ==========================================
# 実行テスト
# ==========================================
if __name__ == "__main__":
    # ユーザーが入力する想定のテストデータ
    target_csv = "target_race.csv" # 事前に作成したテスト用CSV
    race_name = "第69回 有馬記念 (G1)"
    
    # 辞書型で整理されたコース情報
    course_info = {
        'surface': '芝',
        'direction': '右',
        'distance': 2500,
        'weather': '晴',
        'condition': '良'
    }
    
    print("1. 🤖 LightGBMでベース勝率を計算中...")
    enriched_df = calculate_ml_probabilities(target_csv, course_info)
    
    if enriched_df is not None:
        print("\n2. 📝 LLM用の統合プロンプトを生成中...")
        prompt_text = generate_hybrid_prompt(enriched_df, race_name, course_info)
        
        print("3. 🧠 Ollama (LLM) に最終推論をリクエスト中...")
        final_prediction = predict_with_ollama(prompt_text, model_name="llama3.3")
        
        if final_prediction:
            print("\n🎉【最終予測結果】完成したハイブリッドAIの出力:")
            print(json.dumps(final_prediction, indent=2, ensure_ascii=False))