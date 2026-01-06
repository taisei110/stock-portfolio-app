# 📈 Stock Portfolio Manager

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase-336791?style=for-the-badge&logo=postgresql&logoColor=white)](https://supabase.com)
[![Plotly](https://img.shields.io/badge/Plotly-5.18+-3F4F75?style=for-the-badge&logo=plotly&logoColor=white)](https://plotly.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

🔗 **[Live Demo](https://stock-portfolio-app-taisei.streamlit.app/)**

日本株式対応のポートフォリオ管理アプリ。リアルタイムの株価取得、AI診断機能、独自のテクニカル分析判断ツールを搭載。

---

## 🎯 開発背景

個人投資家として株式投資を行う中で、以下の課題を感じました：

- 複数銘柄の保有状況を一元管理したい
- トレードの根拠や反省を記録に残したい
- チャート分析をAIにサポートしてほしい

これらの課題を解決するため、**自分専用のポートフォリオ管理ツール**として開発しました。

---

## ✨ 機能一覧

### 📊 ダッシュボード
- 保有銘柄の**リアルタイム評価額**を表示
- ポートフォリオ構成のパイチャート
- 銘柄別の損益状況をビジュアル化

### 📝 取引記録管理 (CRUD)
- 買い/売り取引の登録・編集・削除
- 逆指値（ストップロス）の記録
- 取引根拠・反省のメモ機能
- トレードチェックリスト機能

### 📈 チャート分析
- **ローソク足チャート**（日足/週足/月足）
- 移動平均線（5, 25, 75日）の表示
- 出来高グラフ

### 🤖 AI チャート診断
- チャート画像を**Google Gemini AI**が分析
- エントリーポイントの評価・採点
- 改善点のフィードバック

### 📊 パフォーマンス分析
- 勝率・平均利益率の算出
- 月次/年次リターンの可視化
- 銘柄別損益ランキング

### 📰 関連ニュース
- 株探から最新ニュースを自動取得
- 保有銘柄のニュースを一覧表示

### ☁️ クラウド同期
- **Supabase PostgreSQL**によるデータ永続化
- マルチデバイス対応（PC/スマホ）
- PWA対応でホーム画面にインストール可能

---

## 🛠️ 技術スタック

| カテゴリ | 技術 |
|---------|------|
| **フロントエンド** | Streamlit, Plotly, CSS3 |
| **バックエンド** | Python 3.9+ |
| **データベース** | SQLite (ローカル), PostgreSQL (本番) |
| **外部API** | yfinance (株価), Google Gemini AI |
| **インフラ** | Streamlit Cloud, Supabase |
| **その他** | BeautifulSoup4 (スクレイピング), Pillow |

---

## 🚀 クイックスタート

### 1. リポジトリをクローン
```bash
git clone https://github.com/taisei110/stock-portfolio-app.git
cd stock-portfolio-app
```

### 2. 仮想環境を作成
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate
```

### 3. 依存関係をインストール
```bash
pip install -r requirements.txt
```

### 4. 環境変数を設定
```bash
cp .env.example .env
```

`.env` ファイルを編集:
```env
GEMINI_API_KEY=your_gemini_api_key
DATABASE_URL=your_supabase_url  # オプション
```

### 5. アプリを起動
```bash
streamlit run app.py
```

ブラウザで http://localhost:8501 を開きます。

---

## 📁 プロジェクト構成

```
stock_portfolio_app/
├── app.py                 # メインアプリケーション
├── database.py            # データベース操作 (SQLite/PostgreSQL)
├── stock_api.py           # 株価API連携
├── utils.py               # ユーティリティ関数
├── pages/                 # Streamlitマルチページ
│   ├── dashboard.py       # ダッシュボード
│   ├── transactions.py    # 取引記録一覧
│   ├── performance.py     # パフォーマンス分析
│   ├── chart_diagnosis.py # AIチャート診断
│   ├── news.py            # 関連ニュース
│   └── market_outlook.py  # マーケット概況
├── static/                # 静的ファイル (PWA用)
├── jp_stocks.csv          # 日本株銘柄マスタ
├── requirements.txt       # 依存パッケージ
├── .env.example           # 環境変数テンプレート
└── .gitignore
```

---

## 🔑 必要なAPIキー

| API | 用途 | 取得先 |
|-----|------|--------|
| **Gemini API** | AIチャート診断 | [Google AI Studio](https://aistudio.google.com/) |
| **Supabase** | クラウドDB（オプション） | [Supabase](https://supabase.com/) |

---

## 📱 デプロイ

### Streamlit Cloud
1. GitHubにリポジトリをプッシュ
2. [Streamlit Cloud](https://streamlit.io/cloud)でアカウント作成
3. リポジトリを接続してデプロイ
4. Secrets設定に環境変数を追加

---

## 📝 今後の開発予定

- [ ] テスト自動化 (pytest)
- [ ] CI/CD パイプライン構築
- [ ] 銘柄スクリーニング機能
- [ ] アラート通知機能

--

---

## 📄 ライセンス

MIT License - 詳細は [LICENSE](LICENSE) を参照

---

## 👤 開発者

**taisei110**

[![GitHub](https://img.shields.io/badge/GitHub-taisei110-181717?style=flat-square&logo=github)](https://github.com/taisei110)
