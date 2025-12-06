"""
AIトレードコーチ・分析ページ
"""
import streamlit as st
import pandas as pd
from database import (
    get_all_transactions, 
    get_portfolio_summary
)
from stock_api import get_prices_for_tickers
from analysis_agent import (
    check_api_status, 
    analyze_trade_history, 
    get_trade_advice
)

def show_ai_coach():
    st.header("🤖 AIトレードコーチ")

    # API接続状態を確認
    from analysis_agent import ENV_PATH, get_api_key
    api_key = get_api_key()
    api_ok, api_msg = check_api_status()
    
    # デバッグ: API状態を表示
    with st.expander("🔧 デバッグ情報", expanded=True):
        st.write(f"ENV_PATH: `{ENV_PATH}`")
        st.write(f"ENV exists: `{ENV_PATH.exists()}`")
        st.write(f"API Key found: `{api_key[:10] + '...' if api_key else 'None'}`")
        st.write(f"API OK: `{api_ok}`")
        st.write(f"API Message: `{api_msg}`")

    if not api_ok:
        st.warning("⚠️ AI分析機能を利用するには `.env` ファイルに `GEMINI_API_KEY` を設定してください。")
        with st.expander("🔧 セットアップ方法"):
            st.markdown("""
    ### Gemini API キーの取得方法

    1. [Google AI Studio](https://aistudio.google.com/app/apikey) にアクセス
    2. 「Get API key」をクリック
    3. APIキーを作成・コピー

    ### .envファイルの設定

    プロジェクトフォルダ内の `.env` ファイルに以下を追加:
            """)
            st.code("GEMINI_API_KEY=your_api_key_here", language="bash")
        return

    st.success("✅ Gemini API 接続済み")

    # セッション状態初期化
    if 'ai_analysis_result' not in st.session_state:
        st.session_state.ai_analysis_result = None
    if 'ai_advice_result' not in st.session_state:
        st.session_state.ai_advice_result = None

    analysis_tab, advice_tab = st.tabs(["📊 ポートフォリオ診断", "💬 コーチに相談"])

    with analysis_tab:
        st.markdown("##### あなたの取引履歴とポートフォリオをAIが分析します")
        
        # 分析ボタン
        if st.button("🔍 ポートフォリオを分析", use_container_width=True, type="primary"):
            with st.spinner("🤖 AIが分析中..."):
                # データ準備
                # 1. 取引履歴
                all_transactions = get_all_transactions()
                
                # 2. ポートフォリオ（現在価格付き）
                raw_portfolio = get_portfolio_summary()
                
                # 現在価格を取得してデータをリッチにする
                tickers = [p['ticker'] for p in raw_portfolio]
                if tickers:
                    current_prices = get_prices_for_tickers(tickers)
                else:
                    current_prices = {}

                enriched_portfolio = []
                for p in raw_portfolio:
                    p_copy = p.copy()
                    ticker = p['ticker']
                    # 現在価格を付与
                    p_copy['current_price'] = current_prices.get(ticker)
                    enriched_portfolio.append(p_copy)

                # AI分析実行
                result = analyze_trade_history(all_transactions, enriched_portfolio)
                st.session_state.ai_analysis_result = result
        
        # 分析結果を表示
        if st.session_state.ai_analysis_result:
            st.markdown("### 📊 分析結果")
            st.markdown(st.session_state.ai_analysis_result)
            
            if st.button("🔄 分析をクリア"):
                st.session_state.ai_analysis_result = None
                st.rerun()

    with advice_tab:
        st.markdown("##### トレードに関する疑問や銘柄について相談できます")
        
        col_q1, col_q2 = st.columns([3, 1])
        
        with col_q1:
            user_query = st.text_area(
                "質問・相談内容",
                placeholder="例: 最近損切りが遅れがちです。どうすれば改善できますか？\n例: ポートフォリオの現金比率についてアドバイスをください。",
                height=100
            )
        
        with col_q2:
            st.markdown("<br><br>", unsafe_allow_html=True) # レイアウト調整
            ask_button = st.button("📩 相談する", use_container_width=True)
        
        if ask_button and user_query:
            with st.spinner("🤖 AIが回答を生成中..."):
                # コンテキストとして主要なポートフォリオ情報を渡す（簡易版）
                raw_portfolio = get_portfolio_summary()
                
                # 簡易的な評価額計算（厳密さは求めないが、ある程度の規模感を伝える）
                tickers = [p['ticker'] for p in raw_portfolio]
                prices = get_prices_for_tickers(tickers) if tickers else {}
                
                total_val = 0
                total_pl = 0
                
                for p in raw_portfolio:
                    cp = prices.get(p['ticker'])
                    if cp:
                        val = abs(p['total_quantity']) * cp
                        cost = abs(p['total_quantity']) * p['avg_price']
                        pl = val - cost
                        total_val += val
                        total_pl += pl

                pf_context = f"現在のポートフォリオ評価額: 約{total_val:,.0f}円, 含み損益: 約{total_pl:+,.0f}円"
                
                advice = get_trade_advice(user_query, context=pf_context)
                st.session_state.ai_advice_result = advice
        
        if st.session_state.ai_advice_result:
            st.info("💡 AIからのアドバイス")
            st.markdown(st.session_state.ai_advice_result)
            
            # クリアボタンを追加
            if st.button("🗑️ 会話履歴をクリア"):
                st.session_state.ai_advice_result = None
                st.rerun()

if __name__ == "__main__":
    st.set_page_config(page_title="AIトレードコーチ", page_icon="🤖")
    show_ai_coach()
