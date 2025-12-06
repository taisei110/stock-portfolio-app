# 📈 株式ポートフォリオ管理アプリ

AIトレードコーチ搭載の株式投資ポートフォリオ管理アプリ

## ✨ 機能

- 📊 **ダッシュボード** - 保有銘柄の評価額・損益をリアルタイム表示
- 📝 **取引記録** - 買い/売りの記録管理（CRUD）
- 📈 **チャート分析** - ローソク足チャート・移動平均線
- 🤖 **AIトレードコーチ** - Gemini AIによるトレード分析・添削
- 📷 **チャート画像診断** - チャート画像をAIが分析・採点
- 📊 **パフォーマンス分析** - 勝率・月次/年次リターン
- 📰 **関連ニュース** - 株探からリアルタイムでニュース取得
- ☁️ **クラウド同期** - Supabase PostgreSQLでマルチデバイス対応
- 📱 **PWA対応** - スマホにインストール可能

## 🚀 セットアップ

### 1. クローン
```bash
git clone https://github.com/YOUR_USERNAME/stock-portfolio-app.git
cd stock-portfolio-app
```

### 2. 仮想環境作成
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Mac/Linux
```

### 3. 依存関係インストール
```bash
pip install -r requirements.txt
```

### 4. 環境変数設定
`.env.example`をコピーして`.env`を作成:
```bash
copy .env.example .env
```
`.env`を編集してAPIキーを設定:
```env
GEMINI_API_KEY=your_gemini_api_key
DATABASE_URL=your_supabase_url
```

### 5. アプリ起動
```bash
streamlit run app.py
```

## 📁 プロジェクト構成

```
stock_portfolio_app/
├── app.py              # メインアプリ
├── database.py         # データベース操作
├── stock_api.py        # 株価API
├── analysis_agent.py   # AI分析モジュール
├── pages/              # Streamlitページ
│   ├── dashboard.py
│   ├── transactions.py
│   ├── analysis.py
│   ├── ai_coach.py
│   ├── chart_diagnosis.py
│   ├── performance.py
│   └── news.py
├── requirements.txt
├── .env.example
└── .gitignore
```

## 🔑 必要なAPIキー

| API | 用途 | 取得先 |
|-----|------|--------|
| Gemini API | AIトレードコーチ | [Google AI Studio](https://aistudio.google.com/) |
| Supabase | クラウドDB | [Supabase](https://supabase.com/) |

## 📱 Streamlit Cloudへのデプロイ

1. GitHubにプッシュ
2. [Streamlit Cloud](https://streamlit.io/cloud)でアカウント作成
3. リポジトリを接続
4. Secretsに環境変数を設定

## ⚠️ 注意事項

- `.env`ファイルは絶対にGitHubにアップロードしないでください
- 本番環境ではStreamlit CloudのSecretsを使用してください

## 📄 ライセンス

MIT License
