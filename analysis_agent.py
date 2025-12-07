"""
AIトレードコーチ機能
Google Gemini API を使用した取引分析
"""

import os
import json
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone, timedelta
import google.generativeai as genai
from dotenv import load_dotenv

# .envファイルのパス（絶対パスで解決）
ENV_PATH = Path(__file__).resolve().parent / ".env"
USAGE_FILE = Path(__file__).resolve().parent / ".gemini_usage.json"

# .envファイルを読み込む（存在する場合）
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)

# 利用可能なモデルとその無料枠設定
AVAILABLE_MODELS = {
    "gemini-2.5-flash": {"name": "⚡ Gemini 2.5 Flash (最新・高速)", "rpd": 1500},
    "gemini-2.5-pro": {"name": "✨ Gemini 2.5 Pro (最新・高性能)", "rpd": 50},
    "gemini-2.0-flash-exp": {"name": " Gemini 2.0 Flash Exp", "rpd": 1500},
}
DEFAULT_MODEL = "gemini-2.5-flash"


def get_pacific_date() -> str:
    """太平洋時間の現在日付を取得（クォータリセット基準）"""
    # 太平洋標準時 (PST) は UTC-8、太平洋夏時間 (PDT) は UTC-7
    # 簡易的に UTC-8 で計算
    pacific_tz = timezone(timedelta(hours=-8))
    return datetime.now(pacific_tz).strftime("%Y-%m-%d")


def get_usage_data() -> dict:
    """使用回数データを読み込む"""
    if not USAGE_FILE.exists():
        return {"date": get_pacific_date(), "usage": {}}
    
    try:
        with open(USAGE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 日付が変わっていたらリセット
        if data.get("date") != get_pacific_date():
            return {"date": get_pacific_date(), "usage": {}}
        
        return data
    except Exception:
        return {"date": get_pacific_date(), "usage": {}}


def save_usage_data(data: dict):
    """使用回数データを保存"""
    try:
        with open(USAGE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def increment_usage(model_id: str):
    """使用回数を+1"""
    data = get_usage_data()
    current = data["usage"].get(model_id, 0)
    data["usage"][model_id] = current + 1
    save_usage_data(data)


def get_remaining_quota(model_id: str) -> int:
    """残り使用回数を取得"""
    if model_id not in AVAILABLE_MODELS:
        return 0
    
    max_rpd = AVAILABLE_MODELS[model_id]["rpd"]
    data = get_usage_data()
    used = data["usage"].get(model_id, 0)
    return max(0, max_rpd - used)


def get_usage_count(model_id: str) -> int:
    """本日の使用回数を取得"""
    data = get_usage_data()
    return data["usage"].get(model_id, 0)


def get_api_key() -> str | None:
    """APIキーを取得（Streamlit Secrets優先、なければ.envファイル）"""
    # 1. まずStreamlit Secretsをチェック（Streamlit Cloud用）
    try:
        import streamlit as st
        # st.secretsが存在し、GEMINI_API_KEYが含まれているか確認
        if hasattr(st, 'secrets'):
            try:
                api_key = st.secrets.get("GEMINI_API_KEY")
                if api_key:
                    return api_key
            except Exception:
                # secrets.tomlの形式が異なる場合を試す
                try:
                    if "GEMINI_API_KEY" in st.secrets:
                        return st.secrets["GEMINI_API_KEY"]
                except Exception:
                    pass
    except ImportError:
        pass
    
    # 2. 環境変数をチェック
    env_key = os.environ.get('GEMINI_API_KEY')
    if env_key:
        return env_key
    
    # 3. .envファイルを直接読み込む（ローカル開発用）
    try:
        if not ENV_PATH.exists():
            return None
        
        with open(ENV_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                if key.strip() == 'GEMINI_API_KEY':
                    # 引用符を削除
                    value = value.strip().strip('"').strip("'")
                    return value if value else None
        return None
    except Exception:
        return None

def init_gemini() -> bool:
    """Gemini APIを初期化"""
    api_key = get_api_key()
    if not api_key:
        return False
    
    try:
        genai.configure(api_key=api_key)
        return True
    except Exception:
        return False


def get_gemini_model(model_id: str = None):
    """Geminiモデルを取得（テキスト生成用）"""
    if model_id is None:
        model_id = DEFAULT_MODEL
    return genai.GenerativeModel(model_id)


def get_vision_model(model_id: str = None):
    """画像認識対応のGeminiモデルを取得"""
    if model_id is None:
        model_id = "gemini-2.5-pro"
    return genai.GenerativeModel(model_id)


def handle_gemini_error(e: Exception, model_id: str) -> str:
    """Gemini APIのエラーをハンドリングしてメッセージを返す"""
    error_msg = str(e)
    if "429" in error_msg or "ResourceExhausted" in error_msg or "Quota exceeded" in error_msg:
        model_name = AVAILABLE_MODELS.get(model_id, {}).get('name', model_id)
        return (f"⚠️ **{model_name} の使用制限（クォータ）を超過しました。**\n\n"
                f"サイドバーから **「Gemini 2.5 Flash」** などの軽量モデルに切り替えるか、"
                f"しばらく待ってから再試行してください。\n"
                f"（エラー: 429 Quota Exceeded）")
    return f"❌ AI分析中にエラーが発生しました: {error_msg}"


def diagnose_chart_image(image_data, user_memo: str) -> str:
    """
    チャート画像を分析し、ユーザーのメモを採点・添削する
    
    Args:
        image_data: PIL.Image または bytes形式の画像データ
        user_memo: ユーザーが書いた分析メモ
        
    Returns:
        AIによる採点と添削コメント
    """
    if not init_gemini():
        return "❌ Gemini API キーが設定されていません。.envファイルにGEMINI_API_KEYを設定してください。"
    
    prompt = f"""あなたはプロのテクニカルアナリストです。
以下の手順でチャート画像を分析し、ユーザーの分析メモを評価してください。

## あなたのタスク
1. 画像のチャートパターン、トレンド、インジケーターを読み取る
2. ユーザーの分析メモが正しいか評価する
3. 100点満点で採点し、改善点を具体的に指摘する

## ユーザーの分析メモ
{user_memo if user_memo else "（メモなし）"}

## 回答形式
以下のフォーマットで回答してください：

### 📊 チャート分析
（画像から読み取れるチャートパターン、トレンド、テクニカル指標の状況を簡潔に記載）

### 📝 メモの評価
（ユーザーのメモに対する評価・コメント）

### 🎯 採点: XX点/100点
（採点理由を簡潔に）

### 💡 改善点・アドバイス
（具体的な改善点や追加すべき視点をリスト形式で）
"""
    
    try:
        model_id = "gemini-2.5-pro"  # 画像認識には2.5-proを使用
        model = get_vision_model(model_id)
        response = model.generate_content([prompt, image_data])
        increment_usage(model_id)  # 使用回数をカウント
        return response.text
    except Exception as e:
        return handle_gemini_error(e, model_id)


def summarize_portfolio(portfolio_data: list[dict]) -> str:
    """
    ポートフォリオデータを要約テキストに変換
    
    Args:
        portfolio_data: ポートフォリオのリスト
        
    Returns:
        テキスト形式のポートフォリオサマリー
    """
    if not portfolio_data:
        return "保有銘柄がありません"
        
    summary = []
    for p in portfolio_data:
        ticker = p.get('ticker')
        pos_type = "ロング" if p.get('position_type', 'long') == 'long' else "ショート"
        qty = abs(p.get('total_quantity', 0))
        avg_price = p.get('avg_price', 0)
        current_price = p.get('current_price') # app.py側で計算されている場合がある
        
        line = f"- {ticker}: {pos_type} {qty}株, 建単価: {avg_price:,.0f}円"
        if current_price:
            line += f", 現在値: {current_price:,.0f}円"
            
        summary.append(line)
        
    return "\n".join(summary)


def get_trade_advice(query: str, context: str = "", model_id: str = None) -> str:
    """
    トレードに関するアドバイスを取得
    
    Args:
        query: ユーザーからの質問または対象銘柄
        context: 補足情報（メモや状況など）
        model_id: 使用するGeminiモデルのID
        
    Returns:
        AIからのアドバイス
    """
    if not init_gemini():
        return "❌ Gemini API キーが設定されていません。"
    
    if model_id is None:
        model_id = DEFAULT_MODEL
    
    prompt = f"""あなたは経験豊富なトレードコーチです。
ユーザーからの以下の質問やトピックについて、アドバイスを提供してください。

## 質問・トピック
{query}

## 補足情報
{context if context else "なし"}

注意: 投資助言ではなく、教育目的の一般的なアドバイス、またはコーチングとしての視点を提供してください。
具体的かつ簡潔に（400文字以内）回答してください。
"""
    
    try:
        model = get_gemini_model(model_id)
        response = model.generate_content(prompt)
        increment_usage(model_id)  # 使用回数をカウント
        return response.text
    except Exception as e:
        return handle_gemini_error(e, model_id)


def analyze_trade_history(transactions: list[dict], portfolio: list[dict], model_id: str = None) -> str:
    """
    取引履歴を分析してアドバイスを生成
    
    Args:
        transactions: 取引履歴リスト
        portfolio: ポートフォリオサマリー
        model_id: 使用するGeminiモデルのID
    
    Returns:
        AIからの分析結果
    """
    if not init_gemini():
        return "❌ Gemini API キーが設定されていません。.envファイルにGEMINI_API_KEYを設定してください。"
    
    if model_id is None:
        model_id = DEFAULT_MODEL
    
    # 取引データをテキストに変換
    tx_summary = []
    # 直近30件に増やす
    for tx in transactions[:30]:
        tx_type = "買い" if tx.get('transaction_type') == 'buy' else "売り"
        account = tx.get('account_type', '現物')
        date_str = tx.get('transaction_date')
        ticker = tx.get('ticker')
        qty = tx.get('quantity')
        price = tx.get('price')
        
        tx_summary.append(
            f"- {date_str}: {ticker} {tx_type}({account}) {qty}株 @{price:,.0f}円"
        )
    
    # ポートフォリオサマリー生成
    portfolio_text = summarize_portfolio(portfolio)
    
    prompt = f"""あなたは経験豊富なトレードコーチです。以下の取引履歴とポートフォリオを分析し、
日本語で率直かつ建設的なフィードバックを提供してください。

## 直近の取引履歴 (新しい順)
{chr(10).join(tx_summary) if tx_summary else "取引履歴がありません"}

## 現在のポートフォリオ
{portfolio_text}

## 分析してほしいポイント
1. 売買のタイミングと傾向（順張り・逆張り、損切り早さなど）
2. ポートフォリオのリスク分散状況
3. 良い点と改善すべき点の具体的なコーチング
4. 今後のトレード戦略への提案

トレーダーの成長につながるよう、客観的データに基づいたアドバイスを簡潔に（600文字程度）まとめてください。
"""
    
    try:
        model = get_gemini_model(model_id)
        response = model.generate_content(prompt)
        increment_usage(model_id)  # 使用回数をカウント
        return response.text
    except Exception as e:
        return handle_gemini_error(e, model_id)


def check_api_status() -> tuple[bool, str]:
    """API接続状態を確認"""
    api_key = get_api_key()
    if not api_key:
        return False, "GEMINI_API_KEY が .env に設定されていません"
    
    try:
        init_gemini()
        model = get_gemini_model()
        # 最小限のトークンでテスト
        response = model.generate_content("Hi")
        return True, "✅ Gemini API 接続成功"
    except Exception as e:
        return False, f"❌ 接続エラー: {str(e)}"
