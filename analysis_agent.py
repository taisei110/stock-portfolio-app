"""
AIトレードコーチ機能
Google Gemini API を使用した取引分析
"""

import os
from pathlib import Path
from typing import Optional
import google.generativeai as genai

# .envファイルのパス（絶対パスで解決）
ENV_PATH = Path(__file__).resolve().parent / ".env"

def get_api_key() -> str | None:
    """直接.envファイルを読み込んでAPIキーを取得"""
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


def get_gemini_model():
    """Geminiモデルを取得（テキスト生成用）"""
    return genai.GenerativeModel('gemini-2.5-pro')


def get_vision_model():
    """画像認識対応のGeminiモデルを取得"""
    return genai.GenerativeModel('gemini-1.5-pro')


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
        model = get_vision_model()
        response = model.generate_content([prompt, image_data])
        return response.text
    except Exception as e:
        return f"❌ 画像分析中にエラーが発生しました: {str(e)}"


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


def get_trade_advice(query: str, context: str = "") -> str:
    """
    トレードに関するアドバイスを取得
    
    Args:
        query: ユーザーからの質問または対象銘柄
        context: 補足情報（メモや状況など）
        
    Returns:
        AIからのアドバイス
    """
    if not init_gemini():
        return "❌ Gemini API キーが設定されていません。"
    
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
        model = get_gemini_model()
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"❌ エラー: {str(e)}"


def analyze_trade_history(transactions: list[dict], portfolio: list[dict]) -> str:
    """
    取引履歴を分析してアドバイスを生成
    
    Args:
        transactions: 取引履歴リスト
        portfolio: ポートフォリオサマリー
    
    Returns:
        AIからの分析結果
    """
    if not init_gemini():
        return "❌ Gemini API キーが設定されていません。.envファイルにGEMINI_API_KEYを設定してください。"
    
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
        model = get_gemini_model()
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"❌ AI分析中にエラーが発生しました: {str(e)}"


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
