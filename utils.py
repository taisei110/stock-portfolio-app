import requests
import re
from typing import Optional, Tuple

def get_image_bytes_from_url(url: str) -> Tuple[Optional[bytes], Optional[str]]:
    """
    URLから画像データを取得する。
    TradingViewのスナップショットURL（/x/）の場合は、OGPタグから画像URLを解析して取得する。
    
    Args:
        url: 画像URLまたはTradingViewスナップショットURL
        
    Returns:
        (image_bytes, error_message): 成功時は (bytes, None)、失敗時は (None, error_str)
    """
    try:
        actual_image_url = url.strip()
        if not actual_image_url:
            return None, "URLが空です"
        
        # TradingViewのスナップショットURL（/x/形式）の場合
        if "tradingview.com/x/" in actual_image_url:
            try:
                # User-Agentを設定しないと拒否される場合があるため設定
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                page_response = requests.get(actual_image_url, headers=headers, timeout=10)
                page_response.raise_for_status()
                
                # og:imageタグを探す
                og_match = re.search(r'<meta property="og:image" content="([^"]+)"', page_response.text)
                if og_match:
                    actual_image_url = og_match.group(1)
                else:
                    return None, "TradingViewページから画像URLを抽出できませんでした。og:imageタグが見つかりません。"
            except Exception as e:
                return None, f"TradingViewページの解析に失敗しました: {str(e)}"
                
        # 画像をダウンロード
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(actual_image_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        content_type = response.headers.get('content-type', '').lower()
        if 'image' not in content_type:
             return None, f"指定されたURLのコンテンツタイプが画像ではありません ({content_type})。"
             
        return response.content, None
        
    except Exception as e:
        return None, f"画像の取得に失敗しました: {str(e)}"
