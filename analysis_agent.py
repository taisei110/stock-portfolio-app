"""
AI分析エージェント
Google Gemini APIを活用した分析機能
- チャート画像診断
- 市況ニュース分析
- ニュース翻訳・要約
"""

import os
import io
from pathlib import Path
from typing import Optional

# .envファイルから環境変数を読み込む
ENV_PATH = Path(__file__).resolve().parent / ".env"


def _load_api_key() -> Optional[str]:
    """GEMINI_API_KEYを.envファイルまたは環境変数から取得"""
    # .envファイルから直接読み込み
    if ENV_PATH.exists():
        try:
            with open(ENV_PATH, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('#') or '=' not in line:
                        continue
                    key, value = line.split('=', 1)
                    if key.strip() == 'GEMINI_API_KEY':
                        value = value.strip().strip('"').strip("'")
                        if value:
                            return value
        except Exception:
            pass

    # 環境変数からも取得を試みる
    return os.getenv("GEMINI_API_KEY")


def _get_model():
    """Geminiモデルを取得"""
    import google.generativeai as genai

    api_key = _load_api_key()
    if not api_key:
        raise ValueError("GEMINI_API_KEY が設定されていません。.envファイルを確認してください。")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')
    return model


def check_api_status() -> tuple[bool, str]:
    """
    Gemini APIの接続状態を確認
    Returns: (接続OK, メッセージ)
    """
    try:
        api_key = _load_api_key()
        if not api_key:
            return False, "GEMINI_API_KEY が設定されていません"

        model = _get_model()
        # 簡単なテストリクエスト
        response = model.generate_content("Hello")
        if response and response.text:
            return True, "Gemini API 接続OK"
        return False, "APIレスポンスが空です"
    except Exception as e:
        error_str = str(e)
        if "429" in error_str or "Quota exceeded" in error_str:
            return False, "⚠️ Gemini APIの利用制限（無料枠）に達しました。時間をおいて再試行してください。"
        return False, f"API接続エラー: {error_str}"


def analyze_market_outlook(news_items: list) -> str:
    """
    市場ニュースを分析し、マーケットアウトルックレポートを生成
    Args:
        news_items: ニュース記事のリスト（dict: title, link, publisher, etc.）
    Returns:
        マークダウン形式のレポート文字列
    """
    try:
        model = _get_model()

        # ニュースを整理してプロンプト用テキストに変換
        news_text = ""
        for i, item in enumerate(news_items[:30], 1):  # 最大30件
            title = item.get('title', '')
            publisher = item.get('publisher', '')
            news_text += f"{i}. [{publisher}] {title}\n"

        prompt = f"""あなたは経験豊富な金融アナリストです。以下の最新マーケットニュースを分析し、
日本語で簡潔な市況レポートを作成してください。

## 分析対象ニュース
{news_text}

## レポート要件
以下の構成でMarkdown形式のレポートを作成してください：

### 📊 マーケット概況
- 全体的な市場の動向を3-5行で要約

### 🇯🇵 日本市場
- 日経平均・TOPIXなどの動向
- 注目材料・イベント

### 🇺🇸 米国市場
- NYダウ・S&P500・NASDAQの動向
- 注目材料・イベント

### 💱 為替・商品
- ドル円の動向
- 原油・金など商品市況

### ⚠️ 注目ポイント・リスク
- 今後注意すべきイベントやリスク要因

### 🎯 投資戦略メモ
- 現在の相場環境に基づく短期的な投資戦略のヒント

簡潔かつ分かりやすく、個人投資家目線で作成してください。
"""

        response = model.generate_content(prompt)

        if response and response.text:
            return response.text
        return "レポートの生成に失敗しました。"

    except Exception as e:
        error_str = str(e)
        if "429" in error_str or "Quota exceeded" in error_str:
            return (
                "⚠️ **Gemini APIの利用制限（無料枠）に達しました。**\n\n"
                "現在ご利用のAPIキーはリクエスト上限に到達しています。\n"
                "しばらく時間をおいてから再実行するか、[Google AI Studio](https://aistudio.google.com/)でプランをご確認ください。\n\n"
                f"<details><summary>詳細なエラーメッセージ</summary>\n\n```text\n{error_str}\n```\n</details>"
            )
        return f"⚠️ レポート生成エラー: {error_str}"


def diagnose_chart_image(image, user_memo: str = "") -> str:
    """
    チャート画像をAIで診断・分析
    Args:
        image: PIL.Image オブジェクト
        user_memo: ユーザーの分析メモ（任意）
    Returns:
        マークダウン形式の診断結果
    """
    try:
        model = _get_model()

        # PIL ImageをBytesに変換
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)

        prompt = f"""あなたは経験豊富なテクニカルアナリストです。
このチャート画像を詳細に分析し、以下の形式で診断結果を返してください。

{f"## ユーザーの分析メモ" + chr(10) + user_memo + chr(10) if user_memo else ""}

## 診断結果の形式（Markdown）

### 📊 チャート概要
- 銘柄・時間足の推定
- 現在のトレンド方向（上昇/下降/レンジ）
- トレンドの強さ（強い/普通/弱い）

### 📈 テクニカル分析
- **移動平均線**: 配列（パーフェクトオーダー等）とトレンド判定
- **サポート・レジスタンス**: 主要なサポートラインとレジスタンスライン
- **チャートパターン**: 確認できるパターン（ダブルトップ、三角保ち合い等）
- **出来高**: 出来高の傾向（増加/減少/通常）

### 🎯 エントリー判断
- **推奨方向**: ロング/ショート/様子見
- **エントリーポイント**: 具体的な価格水準
- **損切りライン**: 推奨される損切り水準
- **利確目標**: 推奨される利確水準
- **リスクリワード比**: 推定値

### ⭐ 総合評価
- **スコア**: /100点
- **コメント**: 総合的な所見

{f"### 📝 ユーザー分析の採点" + chr(10) + "- ユーザーの分析メモの良い点と改善点を具体的にフィードバック" if user_memo else ""}

具体的な数値やレベルを記載し、実践的なアドバイスを心がけてください。
"""

        # 画像とテキストを一緒に送信
        import google.generativeai as genai

        response = model.generate_content([prompt, image])

        if response and response.text:
            return response.text
        return "診断結果の生成に失敗しました。"

    except Exception as e:
        error_str = str(e)
        if "429" in error_str or "Quota exceeded" in error_str:
            return (
                "⚠️ **Gemini APIの利用制限（無料枠）に達しました。**\n\n"
                "現在ご利用のAPIキーはリクエスト上限に到達しています。\n"
                "しばらく時間をおいてから再実行するか、[Google AI Studio](https://aistudio.google.com/)でプランをご確認ください。\n\n"
                f"<details><summary>詳細なエラーメッセージ</summary>\n\n```text\n{error_str}\n```\n</details>"
            )
        return f"⚠️ 診断エラー: {error_str}"


def translate_news_batch(news_items: list) -> list:
    """
    英語ニュースのタイトルを日本語に翻訳（バッチ処理）
    Args:
        news_items: 翻訳対象のニュースリスト
    Returns:
        翻訳済みのニュースリスト（元のdictにtitleを上書き）
    """
    if not news_items:
        return news_items

    try:
        model = _get_model()

        # タイトルを抽出
        titles = [item.get('title', '') for item in news_items]
        titles_text = "\n".join([f"{i+1}. {t}" for i, t in enumerate(titles)])

        prompt = f"""以下の英語ニュースタイトルを日本語に翻訳してください。
番号付きで、翻訳結果のみを返してください（説明不要）。
元の絵文字（🔴🟠📰など）がある場合はそのまま維持してください。

{titles_text}
"""

        response = model.generate_content(prompt)

        if response and response.text:
            # レスポンスをパース
            translated_lines = response.text.strip().split('\n')
            translated_titles = []
            for line in translated_lines:
                # "1. 翻訳結果" 形式をパース
                line = line.strip()
                if line and line[0].isdigit():
                    # 番号部分を削除
                    parts = line.split('.', 1)
                    if len(parts) > 1:
                        translated_titles.append(parts[1].strip())
                    else:
                        translated_titles.append(line)
                elif line:
                    translated_titles.append(line)

            # 翻訳結果を元のリストに反映
            result = []
            for i, item in enumerate(news_items):
                new_item = item.copy()
                if i < len(translated_titles):
                    # 元のタイトルを保存し、翻訳をtitleに設定
                    new_item['original_title'] = item.get('title', '')
                    new_item['title'] = translated_titles[i]
                result.append(new_item)

            return result

    except Exception as e:
        print(f"翻訳エラー: {e}")

    # 失敗時は元のリストを返す
    return news_items


def summarize_news_batch(news_items: list) -> list:
    """
    ニュースの要約を生成（バッチ処理）
    Args:
        news_items: 要約対象のニュースリスト
    Returns:
        要約付きのニュースリスト（元のdictにsummaryを追加）
    """
    if not news_items:
        return news_items

    try:
        model = _get_model()

        # タイトルを抽出
        titles = [item.get('title', '') for item in news_items]
        titles_text = "\n".join([f"{i+1}. {t}" for i, t in enumerate(titles)])

        prompt = f"""以下のニュースタイトルから、それぞれ1行（30文字以内）で要約・解説を日本語で作成してください。
番号付きで、要約のみを返してください（説明不要）。
投資家目線で重要なポイントを簡潔にまとめてください。

{titles_text}
"""

        response = model.generate_content(prompt)

        if response and response.text:
            # レスポンスをパース
            summary_lines = response.text.strip().split('\n')
            summaries = []
            for line in summary_lines:
                line = line.strip()
                if line and line[0].isdigit():
                    parts = line.split('.', 1)
                    if len(parts) > 1:
                        summaries.append(parts[1].strip())
                    else:
                        summaries.append(line)
                elif line:
                    summaries.append(line)

            # 要約を元のリストに反映
            result = []
            for i, item in enumerate(news_items):
                new_item = item.copy()
                if i < len(summaries):
                    new_item['summary'] = summaries[i]
                result.append(new_item)

            return result

    except Exception as e:
        print(f"要約生成エラー: {e}")

    # 失敗時は元のリストを返す
    return news_items
