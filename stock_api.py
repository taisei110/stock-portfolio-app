"""
株価取得モジュール
yfinance を使用して現在の株価を取得
銘柄検索機能付き（東証全銘柄対応）
"""

import yfinance as yf
from typing import Optional
import re
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import requests
import io


# 日本株リストのキャッシュファイル
STOCK_LIST_CACHE = Path(__file__).parent / "jp_stocks.csv"
CACHE_MAX_AGE_DAYS = 30  # キャッシュの有効期限（日）

# JPX 東証上場銘柄一覧のURL（Excelファイル）
JPX_STOCK_LIST_URL = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"


# 主要な日本株の簡易リスト（フォールバック用）
JP_STOCKS_FALLBACK = [
    ("7203.T", "トヨタ自動車"),
    ("9984.T", "ソフトバンクグループ"),
    ("6758.T", "ソニーグループ"),
    ("9432.T", "日本電信電話"),
    ("8306.T", "三菱UFJフィナンシャル・グループ"),
    ("6861.T", "キーエンス"),
    ("9433.T", "KDDI"),
    ("6098.T", "リクルートホールディングス"),
    ("4063.T", "信越化学工業"),
    ("8035.T", "東京エレクトロン"),
    ("7974.T", "任天堂"),
    ("4661.T", "オリエンタルランド"),
    ("6501.T", "日立製作所"),
    ("7267.T", "本田技研工業"),
    ("8058.T", "三菱商事"),
    ("9983.T", "ファーストリテイリング"),
    ("6902.T", "デンソー"),
    ("4519.T", "中外製薬"),
    ("6594.T", "日本電産"),
    ("3382.T", "セブン&アイ・ホールディングス"),
    ("8766.T", "東京海上ホールディングス"),
    ("4568.T", "第一三共"),
    ("6981.T", "村田製作所"),
    ("2914.T", "日本たばこ産業"),
    ("7751.T", "キヤノン"),
    ("8031.T", "三井物産"),
    ("9434.T", "ソフトバンク"),
    ("6367.T", "ダイキン工業"),
    ("4503.T", "アステラス製薬"),
    ("8001.T", "伊藤忠商事"),
]


def download_jpx_stock_list() -> list[tuple[str, str]]:
    """
    JPXから東証上場銘柄一覧をダウンロード
    
    Returns:
        [(ticker, name), ...] 形式のリスト
    """
    try:
        # JPXからExcelファイルをダウンロード
        response = requests.get(JPX_STOCK_LIST_URL, timeout=30)
        response.raise_for_status()
        
        # Excelファイルを読み込み
        df = pd.read_excel(io.BytesIO(response.content))
        
        stocks = []
        for _, row in df.iterrows():
            # 銘柄コードと銘柄名を取得
            code = str(row.get('コード', row.get('銘柄コード', '')))
            name = str(row.get('銘柄名', ''))
            
            if code and name and code.isdigit():
                # 東証の銘柄コードに.Tサフィックスを追加
                ticker = f"{code}.T"
                stocks.append((ticker, name))
        
        return stocks
    except Exception as e:
        print(f"JPXからのダウンロードに失敗: {e}")
        return []


def is_cache_valid() -> bool:
    """キャッシュが有効かどうかを確認"""
    if not STOCK_LIST_CACHE.exists():
        return False
    
    # キャッシュファイルの更新日時を確認
    cache_mtime = datetime.fromtimestamp(STOCK_LIST_CACHE.stat().st_mtime)
    cache_age = datetime.now() - cache_mtime
    
    return cache_age < timedelta(days=CACHE_MAX_AGE_DAYS)


def get_jp_stock_list() -> list[tuple[str, str]]:
    """
    日本株リストを取得
    1. 有効なキャッシュがあれば使用
    2. なければJPXからダウンロード試行
    3. それでもダメならフォールバックリストを使用
    """
    # キャッシュが有効な場合はそれを使用
    if is_cache_valid():
        try:
            df = pd.read_csv(STOCK_LIST_CACHE)
            return [(row['ticker'], row['name']) for _, row in df.iterrows()]
        except Exception:
            pass
    
    # JPXからダウンロードを試行
    stocks = download_jpx_stock_list()
    if stocks:
        # キャッシュに保存
        save_stock_list_cache(stocks)
        return stocks
    
    # フォールバック: 既存のキャッシュファイルがあれば使用
    if STOCK_LIST_CACHE.exists():
        try:
            df = pd.read_csv(STOCK_LIST_CACHE)
            return [(row['ticker'], row['name']) for _, row in df.iterrows()]
        except Exception:
            pass
    
    return JP_STOCKS_FALLBACK


def save_stock_list_cache(stocks: list[tuple[str, str]]) -> None:
    """銘柄リストをキャッシュに保存"""
    df = pd.DataFrame(stocks, columns=['ticker', 'name'])
    df.to_csv(STOCK_LIST_CACHE, index=False)


def search_stocks(query: str, limit: int = 10) -> list[dict]:
    """
    銘柄名または銘柄コードで部分一致検索
    
    Args:
        query: 検索クエリ（銘柄名の一部または銘柄コード）
        limit: 最大結果数
    
    Returns:
        [{'ticker': '7203.T', 'name': 'トヨタ自動車'}, ...]
    """
    if not query or len(query) < 1:
        return []
    
    query = query.lower()
    stock_list = get_jp_stock_list()
    
    results = []
    for ticker, name in stock_list:
        # 銘柄コードまたは銘柄名で部分一致
        if query in ticker.lower() or query in name.lower():
            results.append({'ticker': ticker, 'name': name})
            if len(results) >= limit:
                break
    
    return results



def normalize_ticker(ticker: str) -> str:
    """
    銘柄コードを正規化
    日本株4桁の場合は末尾に.Tを自動補完
    
    Args:
        ticker: 銘柄コード (例: "7203" or "7203.T" or "AAPL")
    
    Returns:
        正規化された銘柄コード
    """
    ticker = ticker.strip().upper()
    
    # すでにサフィックスがある場合はそのまま
    if '.' in ticker:
        return ticker
    
    # 4桁の数字のみ → 日本株として.Tを付与
    if re.match(r'^\d{4}$', ticker):
        return f"{ticker}.T"
    
    return ticker


def get_current_price(ticker: str) -> Optional[float]:
    """
    指定銘柄の現在株価を取得
    
    Args:
        ticker: 銘柄コード
    
    Returns:
        現在株価、取得失敗時はNone
    """
    try:
        normalized = normalize_ticker(ticker)
        stock = yf.Ticker(normalized)
        
        # 現在価格を取得（複数の方法を試行）
        info = stock.info
        
        # regularMarketPrice が最も信頼性が高い
        if 'regularMarketPrice' in info and info['regularMarketPrice']:
            return float(info['regularMarketPrice'])
        
        # currentPrice をフォールバック
        if 'currentPrice' in info and info['currentPrice']:
            return float(info['currentPrice'])
        
        # 最終手段: 直近の終値
        hist = stock.history(period="1d")
        if not hist.empty:
            return float(hist['Close'].iloc[-1])
        
        return None
        
    except Exception as e:
        print(f"Error fetching price for {ticker}: {e}")
        return None


def get_prices_for_tickers(tickers: list[str]) -> dict[str, Optional[float]]:
    """
    複数銘柄の株価を一括取得
    
    Args:
        tickers: 銘柄コードのリスト
    
    Returns:
        銘柄コード → 株価の辞書
    """
    prices = {}
    
    for ticker in tickers:
        normalized = normalize_ticker(ticker)
        prices[ticker] = get_current_price(normalized)
    
    return prices


def get_japanese_company_name(code: str) -> str:
    """
    Yahoo!ファイナンス日本から日本語会社名を取得
    """
    import requests
    from bs4 import BeautifulSoup
    import re
    
    # 銘柄コードから数字のみ抽出
    code_num = re.sub(r'[^0-9]', '', code.split('.')[0])
    if not code_num:
        return ""
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        url = f"https://finance.yahoo.co.jp/quote/{code_num}.T"
        response = requests.get(url, headers=headers, timeout=5)
        response.encoding = 'utf-8'
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 会社名を取得（タイトルから）
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text()
                # "トヨタ自動車【7203】" のような形式から会社名を抽出
                match = re.match(r'^(.+?)【\d+】', title)
                if match:
                    return match.group(1).strip()
            
            # 代替: h1タグから取得
            h1_tag = soup.find('h1')
            if h1_tag:
                name = h1_tag.get_text().strip()
                # 銘柄コードを除去
                name = re.sub(r'【\d+】', '', name).strip()
                if name:
                    return name
        
    except Exception as e:
        print(f"Error fetching Japanese name for {code}: {e}")
    
    return ""


def get_stock_info(ticker: str) -> dict:
    """
    銘柄の詳細情報を取得
    日本株の場合は日本語会社名を優先
    
    Args:
        ticker: 銘柄コード
    
    Returns:
        銘柄情報の辞書
    """
    try:
        normalized = normalize_ticker(ticker)
        stock = yf.Ticker(normalized)
        info = stock.info
        
        # 日本株かどうか判定
        is_jp_stock = ticker.endswith('.T') or ticker.replace('.T', '').replace('.', '').isdigit()
        
        # 日本株の場合は日本語会社名を取得
        company_name = ""
        if is_jp_stock:
            company_name = get_japanese_company_name(ticker)
        
        # 日本語名が取得できなかった場合はyfinanceから取得
        if not company_name:
            company_name = info.get('longName') or info.get('shortName', '')
        
        return {
            'ticker': normalized,
            'name': company_name,
            'current_price': info.get('regularMarketPrice') or info.get('currentPrice'),
            'previous_close': info.get('previousClose'),
            'currency': info.get('currency', 'JPY'),
            'market_cap': info.get('marketCap'),
            'fifty_two_week_high': info.get('fiftyTwoWeekHigh'),
            'fifty_two_week_low': info.get('fiftyTwoWeekLow'),
        }
    except Exception as e:
        print(f"Error fetching info for {ticker}: {e}")
        return {'ticker': ticker, 'error': str(e)}


def get_historical_data(ticker: str, period: str = "1y") -> "pd.DataFrame":
    """
    過去の株価データを取得（ローソク足チャート用）
    
    Args:
        ticker: 銘柄コード
        period: 取得期間 (例: "1y", "6mo", "3mo", "1mo")
    
    Returns:
        株価データのDataFrame (columns: Date, Open, High, Low, Close, Volume, MA5, MA25, MA75)
    """
    import pandas as pd
    
    try:
        normalized = normalize_ticker(ticker)
        stock = yf.Ticker(normalized)
        hist = stock.history(period=period)
        
        if hist.empty:
            return pd.DataFrame()
        
        # 移動平均線を追加
        hist['MA5'] = hist['Close'].rolling(window=5).mean()
        hist['MA25'] = hist['Close'].rolling(window=25).mean()
        hist['MA75'] = hist['Close'].rolling(window=75).mean()
        
        # インデックス(日付)をカラムに変換
        hist = hist.reset_index()
        hist.rename(columns={'index': 'Date'}, inplace=True)
        if 'Date' not in hist.columns and 'Datetime' in hist.columns:
            hist.rename(columns={'Datetime': 'Date'}, inplace=True)
        
        return hist
        
    except Exception as e:
        print(f"Error fetching historical data for {ticker}: {e}")
        import pandas as pd
        return pd.DataFrame()


def calculate_technical_indicators(df: "pd.DataFrame") -> "pd.DataFrame":
    """
    テクニカル指標を計算
    
    Args:
        df: 株価データのDataFrame (columns: Open, High, Low, Close, Volume)
    
    Returns:
        テクニカル指標を追加したDataFrame
    """
    if df.empty:
        return df
    
    # 移動平均線
    df['SMA5'] = df['Close'].rolling(window=5).mean()
    df['SMA25'] = df['Close'].rolling(window=25).mean()
    df['SMA75'] = df['Close'].rolling(window=75).mean()
    
    # ボリンジャーバンド（25日移動平均ベース）
    df['BB_middle'] = df['SMA25']
    df['BB_std'] = df['Close'].rolling(window=25).std()
    df['BB_upper'] = df['BB_middle'] + (df['BB_std'] * 2)
    df['BB_lower'] = df['BB_middle'] - (df['BB_std'] * 2)
    
    return df


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

