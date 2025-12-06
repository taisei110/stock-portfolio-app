"""
チャート画像診断ページ
TradingViewなどのチャートスクリーンショットをAIが分析・採点
"""

import streamlit as st
from PIL import Image

from analysis_agent import diagnose_chart_image, check_api_status


def show_chart_diagnosis():
    """チャート画像診断ページを表示"""
    st.header("📷 チャート画像診断")
    
    st.markdown("""
    TradingViewなどのチャートスクリーンショットをアップロードすると、
    AIがテクニカル分析を行い、あなたの分析メモを採点・添削します。
    """)
    
    # API接続状態を確認
    api_ok, api_msg = check_api_status()
    
    if not api_ok:
        st.warning("⚠️ AI分析機能を利用するには `.env` ファイルに `GEMINI_API_KEY` を設定してください。")
        return
    
    st.success("✅ Gemini API 接続済み")
    
    st.markdown("---")
    
    # 画像アップローダー
    uploaded_file = st.file_uploader(
        "📤 チャート画像をアップロード",
        type=["png", "jpg", "jpeg"],
        help="TradingViewやMT4/MT5などのチャートスクリーンショットをアップロードしてください"
    )
    
    # プレビュー表示
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption="アップロードされた画像", use_container_width=True)
    
    st.markdown("---")
    
    # 分析メモ入力欄
    user_memo = st.text_area(
        "📝 あなたの分析メモ（エントリー根拠など）",
        placeholder="""例:
・日足で上昇トレンド継続中
・25日移動平均線がサポートとして機能
・RSIは60付近で過熱感なし
・前回高値ブレイクでエントリー予定
・損切りは直近安値の下""",
        height=200,
        help="チャートを見て考えた分析やエントリー根拠を記入してください"
    )
    
    st.markdown("---")
    
    # 診断ボタン
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        diagnose_button = st.button(
            "🔍 AIに診断してもらう",
            type="primary",
            use_container_width=True,
            disabled=(uploaded_file is None)
        )
    
    if uploaded_file is None:
        st.info("👆 まずチャート画像をアップロードしてください")
    
    # 診断実行
    if diagnose_button and uploaded_file is not None:
        with st.spinner("🤖 AIがチャートを分析中... しばらくお待ちください"):
            # 画像を再度読み込み
            image = Image.open(uploaded_file)
            
            # 診断実行
            result = diagnose_chart_image(image, user_memo)
        
        # 結果表示
        st.markdown("## 📊 診断結果")
        st.markdown(result)
        
        # 結果をセッションに保存（履歴用）
        if 'diagnosis_history' not in st.session_state:
            st.session_state.diagnosis_history = []
        
        st.session_state.diagnosis_history.append({
            'memo': user_memo,
            'result': result
        })


# ページエントリーポイント
st.set_page_config(page_title="チャート画像診断", page_icon="📷", layout="wide")
show_chart_diagnosis()
