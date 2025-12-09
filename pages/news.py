"""
関連ニュースページ
保有銘柄のニュースを表示（日本株対応・株探リアルタイム取得）
"""

import streamlit as st
import yfinance as yf
import requests
from datetime import datetime
import re
from bs4 import BeautifulSoup

from database import get_portfolio_summary
from stock_api import normalize_ticker, get_stock_info
from analysis_agent import translate_news_batch


def fetch_kabutan_news(code: str) -> list:
    """
    株探から材料ニュースと決算速報をスクレイピング
    """
    news_items = []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # 株探の銘柄ニュースページを取得
        url = f"https://kabutan.jp/stock/news?code={code}"
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # ニュース一覧を取得
            news_table = soup.find('table', class_='stock_news_table')
            if news_table:
                rows = news_table.find_all('tr')
                for row in rows[:10]:  # 最新10件
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        date_cell = cells[0].get_text(strip=True)
                        title_cell = cells[1]
                        
                        link_tag = title_cell.find('a')
                        if link_tag:
                            title = link_tag.get_text(strip=True)
                            link = link_tag.get('href', '')
                            if link and not link.startswith('http'):
                                link = f"https://kabutan.jp{link}"
                            
                            # カテゴリ判定
                            category = ""
                            if "決算" in title:
                                category = "🔴 決算速報"
                            elif any(kw in title for kw in ["材料", "開示", "発表", "上方", "下方", "増配", "減配"]):
                                category = "🟠 材料ニュース"
                            else:
                                category = "📰 ニュース"
                            
                            news_items.append({
                                'title': f"{category} {title}",
                                'link': link,
                                'publisher': "株探",
                                'timestamp': date_cell,
                                'thumbnail': '',
                                'is_important': "決算" in title or "材料" in title
                            })
        
    except Exception as e:
        print(f"Error fetching Kabutan news for {code}: {e}")
    
    return news_items


def get_yfinance_news(ticker: str, max_items: int = 10) -> list:
    """
    yfinanceからニュースを取得（要約付き）
    """
    try:
        normalized = normalize_ticker(ticker)
        stock = yf.Ticker(normalized)
        news = stock.news
        
        if not news:
            return []
        
        parsed_news = []
        for item in news[:max_items]:
            # Nested content support
            data = item.get('content', item)
            
            title = data.get('title', 'No title')
            
            # Link extraction
            link = ""
            if 'clickThroughUrl' in data and data['clickThroughUrl']:
                link = data['clickThroughUrl'].get('url', '')
            elif 'canonicalUrl' in data and data['canonicalUrl']:
                link = data['canonicalUrl'].get('url', '')
            else:
                link = data.get('link', '')
            
            # Publisher
            publisher = data.get('publisher', '')
            if not publisher and 'provider' in data:
                publisher = data['provider'].get('displayName', '')
                
            # Timestamp
            timestamp = data.get('pubDate') or data.get('providerPublishTime', 0)
            
            # Summary
            summary = data.get('summary', '')
            
            news_item = {
                'title': title,
                'link': link,
                'publisher': publisher,
                'timestamp': timestamp,
                'summary': summary,
                'thumbnail': '',
                'is_important': False
            }
            
            # Thumbnail extraction
            if 'thumbnail' in data and data['thumbnail']:
                thumb = data['thumbnail']
                if 'resolutions' in thumb and thumb['resolutions']:
                    news_item['thumbnail'] = thumb['resolutions'][0].get('url', '')
                elif 'originalUrl' in thumb:
                    news_item['thumbnail'] = thumb.get('originalUrl', '')
            
            parsed_news.append(news_item)
        
        return parsed_news
        
    except Exception as e:
        print(f"Error fetching yfinance news for {ticker}: {e}")
        return []


def get_jp_stock_news(ticker: str, max_items: int = 10) -> list:
    """
    日本株のニュースを取得
    株探からリアルタイムスクレイピング + 各サイトへのリンク
    """
    code = re.sub(r'[^0-9]', '', ticker.split('.')[0])
    
    if not code:
        return []
    
    news_items = []
    
    try:
        # 株探から実際のニュースを取得
        kabutan_news = fetch_kabutan_news(code)
        if kabutan_news:
            news_items.extend(kabutan_news)
            
        # yfinanceからもニュースを取得（要約付き・最新情報）
        yf_news = get_yfinance_news(ticker, max_items)
        if yf_news:
            # 重複を排除しつつ追加（タイトルで簡易判定）
            existing_titles = {item['title'] for item in news_items}
            for item in yf_news:
                if item['title'] not in existing_titles:
                    news_items.append(item)
        
        # 重要なニュースがなければリンクも追加
        if len(news_items) < 3:
            # Yahoo!ファイナンス日本
            yahoo_jp_url = f"https://finance.yahoo.co.jp/quote/{code}.T/news"
            news_items.append({
                'title': f"📰 {code} の最新ニュースを見る（Yahoo!ファイナンス）",
                'link': yahoo_jp_url,
                'publisher': "Yahoo!ファイナンス",
                'timestamp': datetime.now().strftime("%Y-%m-%d"),
                'thumbnail': '',
                'is_important': False
            })
            
            # みんかぶ
            minkabu_url = f"https://minkabu.jp/stock/{code}/news"
            news_items.append({
                'title': f"💬 {code} の株価ニュース（みんかぶ）",
                'link': minkabu_url,
                'publisher': "みんかぶ",
                'timestamp': datetime.now().strftime("%Y-%m-%d"),
                'thumbnail': '',
                'is_important': False
            })
        
        return news_items[:max_items]
        
    except Exception as e:
        print(f"Error fetching JP news for {ticker}: {e}")
        return []


def get_stock_news(ticker: str, max_items: int = 10) -> list:
    """銘柄のニュースを取得（日本株・米国株対応）"""
    
    is_jp_stock = ticker.endswith('.T') or ticker.replace('.T', '').isdigit()
    
    if is_jp_stock:
        return get_jp_stock_news(ticker, max_items)
    
    # 米国株などはyfinanceから取得
    return get_yfinance_news(ticker, max_items)


def format_timestamp(timestamp) -> str:
    """タイムスタンプを日時文字列に変換"""
    try:
        if isinstance(timestamp, int) and timestamp > 0:
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime("%Y-%m-%d %H:%M")
        elif isinstance(timestamp, str):
            # ISOフォーマット対応
            if 'T' in timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    return dt.strftime("%Y-%m-%d %H:%M")
                except:
                    pass
            return timestamp
        return ""
    except:
        return ""


def get_company_name_for_ticker(ticker: str, portfolio: list) -> str:
    """銘柄コードから会社名を取得"""
    for p in portfolio:
        if p['ticker'] == ticker:
            name = p.get('company_name')
            if name and name != 'None' and str(name).strip():
                return name
    
    try:
        info = get_stock_info(ticker)
        if info and info.get('name'):
            return info['name']
    except:
        pass
    
    return ticker


def show_news():
    """関連ニュースページを表示"""
    st.header("📰 関連ニュース")
    
    st.markdown("""
    保有銘柄に関連するニュースをリアルタイムで表示します。
    - 🔴 **決算速報** - 決算関連ニュースを即時反映
    - 🟠 **材料ニュース** - 適時開示・材料を即時反映
    """)
    
    # 自動更新設定
    auto_refresh = st.checkbox("🔄 60秒ごとに自動更新", value=False)
    if auto_refresh:
        st.markdown("""
        <meta http-equiv="refresh" content="60">
        """, unsafe_allow_html=True)
        st.info("60秒後に自動更新されます")
    
    # ポートフォリオデータを取得
    portfolio = get_portfolio_summary()
    
    if not portfolio:
        st.info("📭 保有銘柄がありません。取引を登録するとニュースが表示されます。")
        return
    
    # 銘柄選択
    tickers = [p['ticker'] for p in portfolio]
    ticker_names = {t: get_company_name_for_ticker(t, portfolio) for t in tickers}
    
    st.markdown("---")
    
    # 表示モード選択
    view_mode = st.radio(
        "表示モード",
        options=["すべての銘柄", "銘柄を選択"],
        horizontal=True
    )
    
    if view_mode == "銘柄を選択":
        selected_ticker = st.selectbox(
            "銘柄を選択",
            options=tickers,
            format_func=lambda t: f"{t} - {ticker_names.get(t, t)}"
        )
        tickers_to_show = [selected_ticker]
    else:
        tickers_to_show = tickers
    
    st.markdown("---")
    
    # ニュースを取得して表示
    for ticker in tickers_to_show:
        company_name = ticker_names.get(ticker, ticker)
        
        st.subheader(f"📊 {ticker} - {company_name}")
        
        with st.spinner(f"{ticker} のニュースを取得中..."):
            news_items = get_stock_news(ticker, max_items=10)
        
        if news_items:
            # 重要なニュースを先に表示
            important_news = [n for n in news_items if n.get('is_important')]
            normal_news = [n for n in news_items if not n.get('is_important')]
            
            sorted_news = important_news + normal_news
            
            # --- 翻訳処理 ---
            # 英語（非日本語）記事を抽出して翻訳
            indices_to_translate = []
            items_to_translate = []
            
            for i, item in enumerate(sorted_news):
                # タイトルにひらがな・カタカナ・漢字が含まれていない場合は翻訳対象
                if not re.search(r'[ぁ-んァ-ン一-龥]', item['title']):
                    indices_to_translate.append(i)
                    items_to_translate.append(item)
            
            if items_to_translate:
                # 翻訳実行（スピナー表示）
                with st.spinner(f"🌍 {len(items_to_translate)}件の英語ニュースを日本語に翻訳中... (Powered by Gemini)"):
                    translated = translate_news_batch(items_to_translate)
                    # 結果を元のリストに反映
                    for idx, trans_item in zip(indices_to_translate, translated):
                        sorted_news[idx] = trans_item
            # ----------------
            
            for item in sorted_news:
                title = item.get('title', 'No title')
                link = item.get('link', '')
                publisher = item.get('publisher', '')
                raw_timestamp = item.get('timestamp', '')
                timestamp = format_timestamp(raw_timestamp)
                is_important = item.get('is_important', False)
                summary = item.get('summary', '')
                
                # 重要なニュースはハイライト
                if is_important:
                    st.markdown(f"""
                    <div style="background-color: rgba(255, 165, 0, 0.1); padding: 10px; border-radius: 5px; border-left: 3px solid orange; margin: 5px 0;">
                        <strong><a href="{link}" target="_blank" style="color: #f0f0f0;">{title}</a></strong><br>
                        <small style="color: #888;">📰 {publisher} | 🕐 {timestamp}</small>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    col1, col2 = st.columns([1, 10])
                    
                    with col1:
                        if 'Yahoo' in publisher:
                            st.markdown("🟣")
                        elif '株探' in publisher:
                            st.markdown("🔵")
                        elif 'みんかぶ' in publisher:
                            st.markdown("🟢")
                        else:
                            st.markdown("📄")
                    
                    with col2:
                        if link:
                            st.markdown(f"**[{title}]({link})**")
                        else:
                            st.markdown(f"**{title}**")
                            
                        if summary:
                            st.caption(summary)
                            
                        st.caption(f"📰 {publisher} | 🕐 {timestamp}")
                
                st.markdown("")
            
            st.markdown("---")
        else:
            st.info(f"{ticker} のニュースは見つかりませんでした。")
    
    # 更新ボタン
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 ニュースを更新", use_container_width=True):
            st.rerun()
    with col2:
        st.caption(f"最終更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    st.caption("※ 株探からリアルタイムで材料ニュース・決算速報を取得しています。")


# ページエントリーポイント
st.set_page_config(page_title="関連ニュース", page_icon="📰", layout="wide")
show_news()
