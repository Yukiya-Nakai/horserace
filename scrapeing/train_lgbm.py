import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib

def train_model():
    print("データの読み込み中...")
    df = pd.read_csv("train_data.csv")

    # 特徴量（X）とターゲット（y）の分離
    # race_id は学習に使わない（ただの識別子）ので除外
    features = [
        '枠番', '馬番', '斤量', '年齢', '性別', 
        'surface', 'direction', 'distance', 'weather', 'condition'
    ]
    
    X = df[features]
    y = df['target']

    # カテゴリ変数の型変換（Pandasが読み込む際にObject型になるため、Category型に直す）
    cat_cols = ['surface', 'direction', 'weather', 'condition', '性別']
    for col in cat_cols:
        X[col] = X[col].astype('category')

    # 学習データとテストデータに分割（8:2）
    print("データを分割し、学習を開始します...")
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # LightGBM用のデータセット作成
    train_data = lgb.Dataset(X_train, label=y_train)
    test_data = lgb.Dataset(X_test, label=y_test, reference=train_data)

    # パラメータ設定（二値分類：勝つか負けるか）
    params = {
        'objective': 'binary',
        'metric': 'binary_logloss',
        'boosting_type': 'gbdt',
        'learning_rate': 0.1,
        'num_leaves': 31,
        'verbose': -1 # 余計なログを非表示
    }

    # 学習の実行
    model = lgb.train(
        params,
        train_data,
        valid_sets=[train_data, test_data],
        # valid_names=['train', 'eval'], # 最新バージョンでは非推奨
        num_boost_round=100,
        callbacks=[lgb.early_stopping(stopping_rounds=10, verbose=True)]
    )

    # テストデータで予測精度の確認（0.5以上なら「勝ち」と予測）
    y_pred_prob = model.predict(X_test)
    y_pred_binary = (y_pred_prob >= 0.5).astype(int)

    print("\n--- モデルの評価 ---")
    print(classification_report(y_test, y_pred_binary))
    
    # 🎯 ここが重要！学習したモデルをファイルとして保存
    model_path = 'lgbm_model.pkl'
    joblib.dump(model, model_path)
    print(f"\n✅ 学習が完了し、モデルを {model_path} に保存しました！")
    
    # AIがどの特徴量を重視したか（重要度）を表示
    importance = pd.DataFrame({
        'Feature': features,
        'Importance': model.feature_importance(importance_type='gain')
    }).sort_values(by='Importance', ascending=False)
    print("\n【特徴量の重要度（AIは何を見て予測したか？）】")
    print(importance)

if __name__ == "__main__":
    train_model()