"""
市況・経済ニュースまとめページ
Geminiを活用して、毎朝・毎夕にマーケットニュースを要約して表示
"""

import streamlit as st
import json
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from stock_api import get_yfinance_news
from analysis_agent import analyze_market_outlook
import yfinance as yf

# JSTタイムゾーン定義
JST = timezone(timedelta(hours=9), 'JST')

# キャッシュファイルのパス（プロジェクトルート）
CACHE_FILE = Path(__file__).parent.parent / "market_outlook_cache.json"

def get_market_news() -> list:
    """市場の主要指数のニュースを取得"""
    # 日経平均、ダウ平均、ドル円、S&P500
    tickers = ["^N225", "^DJI", "JPY=X", "^GSPC"]
    all_news = []
    
    # プログレスバー
    progress_bar = st.progress(0, text="ニュース収集中...")
    
    for i, ticker in enumerate(tickers):
        progress_bar.progress((i + 1) / len(tickers), text=f"{ticker} のニュースを取得中...")
        news = get_yfinance_news(ticker, max_items=15) # 多めに取得
        all_news.extend(news)
        
    progress_bar.empty()
    
    # 重複削除（タイトルで判定）
    seen = set()
    unique_news = []
    for item in all_news:
        if item['title'] not in seen:
            seen.add(item['title'])
            unique_news.append(item)
            
    # 新しい順にソート（タイムスタンプがあれば）
    try:
        unique_news.sort(key=lambda x: x.get('timestamp', 0) if isinstance(x.get('timestamp'), (int, float)) else 0, reverse=True)
    except:
        pass
        
    return unique_news

def load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_cache(data: dict):
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def should_update(last_update_str: str) -> bool:
    """前回の更新から定時（8時・20時）をまたいでいるか判定"""
    if not last_update_str:
        return True
    
    now = datetime.now(JST)
    
    try:
        # ISO形式だがタイムゾーンがない場合を考慮
        last_update = datetime.fromisoformat(last_update_str)
        if last_update.tzinfo is None:
             # キャッシュに保存時にtzinfoなしかもしれないのでJSTとみなす
             last_update = last_update.replace(tzinfo=JST)
    except:
        return True
        
    # 今日の8時と20時
    today_morning = now.replace(hour=8, minute=0, second=0, microsecond=0)
    today_evening = now.replace(hour=20, minute=0, second=0, microsecond=0)
    
    # 昨日の20時
    yesterday_evening = today_evening - timedelta(days=1)
    
    # チェックポイント（更新基準時刻）を決定
    if now < today_morning:
        # 現在が朝8時前なら、基準は「昨日の20時」
        target = yesterday_evening
    elif now < today_evening:
        # 現在が8時〜20時の間なら、基準は「今日の8時」
        target = today_morning
    else:
        # 現在が20時以降なら、基準は「今日の20時」
        target = today_evening
        
    # 「最後の更新」が「基準時刻」より前なら、情報が古いので更新が必要
    return last_update < target

def update_report():
    """レポート更新処理"""
    with st.spinner("AIがマーケットニュースを分析中...（数分かかる場合があります）"):
        news_items = get_market_news()
        if not news_items:
            st.error("ニュースを取得できませんでした。")
            return None
        
        report = analyze_market_outlook(news_items)
        
        # キャッシュ更新
        now = datetime.now(JST)
        cache = {
            "timestamp": now.isoformat(),
            "content": report
        }
        save_cache(cache)
        return cache

def show_outlook():
    st.title("🌍 市況・経済ニュースまとめ")
    st.caption("AIが主要マーケットニュースを分析し、毎朝8時と夜20時にレポートを配信します。")
    
    cache = load_cache()
    last_updated = cache.get("timestamp", "")
    content = cache.get("content", "")
    
    needs_update = should_update(last_updated)
    
    # 強制更新（セッション状態を使用）
    if 'force_update' not in st.session_state:
        st.session_state.force_update = False
        
    # 更新が必要、または強制更新フラグがある場合
    if needs_update or st.session_state.force_update or not content:
        if st.session_state.force_update or needs_update:
            new_cache = update_report()
            if new_cache:
                content = new_cache["content"]
                last_updated = new_cache["timestamp"]
                st.session_state.force_update = False # フラグクリア
                st.rerun() # リロードして表示更新
    
    # レポート表示エリア
    if content:
        # Last updated display
        try:
            dt = datetime.fromisoformat(last_updated)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=JST)
            st.info(f"最終更新: {dt.strftime('%Y/%m/%d %H:%M')}")
        except:
            pass
            
        st.markdown(content)
        
    else:
        st.info("レポートを準備中です...")
        if st.button("レポートを作成"):
             st.session_state.force_update = True
             st.rerun()

    # 手動更新ボタン（下部）
    st.markdown("---")
    if st.button("🔄 手動で最新情報に更新"):
        st.session_state.force_update = True
        st.rerun()

# ページ設定
st.set_page_config(page_title="市況ニュース", page_icon="📈", layout="wide")
show_outlook()
