"""
エントリー分析ページ
インタラクティブチャートでエントリーポイントをマーク、AIが評価
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, date
import pandas as pd

from database import get_portfolio_summary
from stock_api import get_historical_data, normalize_ticker, get_stock_info, get_japanese_company_name
from analysis_agent import get_api_key

# ページ設定
st.set_page_config(page_title="エントリー分析", page_icon="🎯", layout="wide")

st.header("🎯 エントリー分析")
st.markdown("""
チャート上でエントリーポイント（買い/売り）をマークし、AIがそのタイミングを評価します。
""")

# セッション状態の初期化
if 'entry_points' not in st.session_state:
    st.session_state.entry_points = []
if 'selected_ticker_entry' not in st.session_state:
    st.session_state.selected_ticker_entry = None

# 銘柄選択
st.markdown("### 📊 銘柄選択")
col1, col2 = st.columns([2, 1])

with col1:
    ticker_input = st.text_input(
        "銘柄コードを入力",
        value="7203.T",
        placeholder="例: 7203.T（トヨタ）"
    )

with col2:
    period = st.selectbox(
        "期間",
        options=["1mo", "3mo", "6mo", "1y"],
        index=2,
        format_func=lambda x: {"1mo": "1ヶ月", "3mo": "3ヶ月", "6mo": "6ヶ月", "1y": "1年"}[x]
    )

# 銘柄情報取得
if ticker_input:
    normalized_ticker = normalize_ticker(ticker_input)
    company_name = get_japanese_company_name(ticker_input)
    if not company_name:
        company_name = ticker_input
    
    st.info(f"📈 **{normalized_ticker}** - {company_name}")
    
    # 株価データ取得
    with st.spinner("チャートデータを取得中..."):
        hist_data = get_historical_data(normalized_ticker, period=period)
    
    if not hist_data.empty:
        st.markdown("---")
        st.markdown("### 📍 エントリーポイント設定")
        
        # エントリーポイント入力フォーム
        entry_col1, entry_col2, entry_col3, entry_col4 = st.columns([2, 2, 2, 1])
        
        with entry_col1:
            entry_type = st.selectbox(
                "タイプ",
                options=["buy", "sell", "stop_loss", "take_profit"],
                format_func=lambda x: {
                    "buy": "🟢 買いエントリー",
                    "sell": "🔴 売りエントリー",
                    "stop_loss": "🛑 損切りライン",
                    "take_profit": "🎯 利確ライン"
                }[x]
            )
        
        with entry_col2:
            # 日付範囲を取得
            min_date = hist_data['Date'].min() if 'Date' in hist_data.columns else hist_data.index.min()
            max_date = hist_data['Date'].max() if 'Date' in hist_data.columns else hist_data.index.max()
            
            if hasattr(min_date, 'date'):
                min_date = min_date.date()
            if hasattr(max_date, 'date'):
                max_date = max_date.date()
            
            entry_date = st.date_input(
                "日付",
                value=max_date,
                min_value=min_date,
                max_value=max_date
            )
        
        with entry_col3:
            # その日の株価を取得して参考表示
            current_close = hist_data['Close'].iloc[-1] if not hist_data.empty else 0
            entry_price = st.number_input(
                "価格",
                min_value=0.0,
                value=float(current_close),
                step=1.0
            )
        
        with entry_col4:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("➕ 追加", use_container_width=True):
                st.session_state.entry_points.append({
                    'type': entry_type,
                    'date': str(entry_date),
                    'price': entry_price,
                    'ticker': normalized_ticker
                })
                st.rerun()
        
        # 追加済みエントリーポイント表示
        if st.session_state.entry_points:
            st.markdown("#### 追加済みポイント")
            for i, ep in enumerate(st.session_state.entry_points):
                if ep['ticker'] == normalized_ticker:
                    type_label = {
                        "buy": "🟢 買い",
                        "sell": "🔴 売り",
                        "stop_loss": "🛑 損切り",
                        "take_profit": "🎯 利確"
                    }[ep['type']]
                    
                    cols = st.columns([4, 1])
                    with cols[0]:
                        st.write(f"{type_label}: {ep['date']} @ ¥{ep['price']:,.0f}")
                    with cols[1]:
                        if st.button("🗑️", key=f"del_{i}"):
                            st.session_state.entry_points.pop(i)
                            st.rerun()
            
            if st.button("🗑️ 全てクリア", use_container_width=False):
                st.session_state.entry_points = []
                st.rerun()
        
        st.markdown("---")
        
        # チャート描画
        st.markdown("### 📈 チャート")
        
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            subplot_titles=('', '出来高'),
            row_heights=[0.7, 0.3]
        )
        
        # ローソク足
        fig.add_trace(go.Candlestick(
            x=hist_data.index,
            open=hist_data['Open'],
            high=hist_data['High'],
            low=hist_data['Low'],
            close=hist_data['Close'],
            name='株価'
        ), row=1, col=1)
        
        # 移動平均線
        if 'MA5' in hist_data.columns:
            fig.add_trace(go.Scatter(
                x=hist_data.index, y=hist_data['MA5'],
                mode='lines', name='5日MA',
                line=dict(color='red', width=1)
            ), row=1, col=1)
        
        if 'MA25' in hist_data.columns:
            fig.add_trace(go.Scatter(
                x=hist_data.index, y=hist_data['MA25'],
                mode='lines', name='25日MA',
                line=dict(color='orange', width=1.5)
            ), row=1, col=1)
        
        if 'MA75' in hist_data.columns:
            fig.add_trace(go.Scatter(
                x=hist_data.index, y=hist_data['MA75'],
                mode='lines', name='75日MA',
                line=dict(color='blue', width=1.5)
            ), row=1, col=1)
        
        # エントリーポイントをプロット
        for ep in st.session_state.entry_points:
            if ep['ticker'] == normalized_ticker:
                color = {
                    "buy": "green",
                    "sell": "red",
                    "stop_loss": "orange",
                    "take_profit": "purple"
                }[ep['type']]
                
                symbol = {
                    "buy": "triangle-up",
                    "sell": "triangle-down",
                    "stop_loss": "x",
                    "take_profit": "star"
                }[ep['type']]
                
                label = {
                    "buy": "買い",
                    "sell": "売り",
                    "stop_loss": "損切り",
                    "take_profit": "利確"
                }[ep['type']]
                
                # マーカー追加
                fig.add_trace(go.Scatter(
                    x=[ep['date']],
                    y=[ep['price']],
                    mode='markers+text',
                    marker=dict(size=15, color=color, symbol=symbol),
                    text=[label],
                    textposition='top center',
                    name=label,
                    showlegend=False
                ), row=1, col=1)
                
                # 水平線追加
                fig.add_hline(
                    y=ep['price'],
                    line_dash="dash",
                    line_color=color,
                    opacity=0.5,
                    row=1, col=1
                )
        
        # 出来高
        colors = ['red' if row['Open'] > row['Close'] else 'green' for _, row in hist_data.iterrows()]
        fig.add_trace(go.Bar(
            x=hist_data.index,
            y=hist_data['Volume'],
            marker_color=colors,
            name='出来高',
            showlegend=False
        ), row=2, col=1)
        
        fig.update_layout(
            height=600,
            xaxis_rangeslider_visible=False,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        fig.update_yaxes(title_text="株価 (円)", row=1, col=1)
        fig.update_yaxes(title_text="出来高", row=2, col=1)
        
        st.plotly_chart(fig, use_container_width=True)
        
        # AI評価セクション
        st.markdown("---")
        st.markdown("### 🤖 AI評価")
        
        # エントリーポイントがある場合のみ評価可能
        current_entries = [ep for ep in st.session_state.entry_points if ep['ticker'] == normalized_ticker]
        
        if current_entries:
            analysis_context = st.text_area(
                "トレードの根拠・背景（任意）",
                placeholder="例: 25日移動平均線のブレイクでエントリー。直近高値を利確目標に設定。",
                height=80
            )
            
            if st.button("🤖 AIでエントリーを評価", type="primary", use_container_width=True):
                api_key = get_api_key()
                
                if not api_key:
                    st.error("⚠️ Gemini API キーが設定されていません。Secretsにキーを追加してください。")
                else:
                    with st.spinner("AIが分析中..."):
                        try:
                            import google.generativeai as genai
                            genai.configure(api_key=api_key)
                            model = genai.GenerativeModel('gemini-2.5-flash')
                            
                            # チャートデータの要約
                            recent_data = hist_data.tail(10)
                            price_summary = f"""
直近10日の終値: {recent_data['Close'].tolist()}
直近高値: ¥{hist_data['High'].max():,.0f}
直近安値: ¥{hist_data['Low'].min():,.0f}
5日MA最新値: ¥{hist_data['MA5'].iloc[-1]:,.0f}
25日MA最新値: ¥{hist_data['MA25'].iloc[-1]:,.0f}
"""
                            
                            # エントリーポイント情報
                            entries_text = "\n".join([
                                f"- {ep['type']}: {ep['date']} @ ¥{ep['price']:,.0f}"
                                for ep in current_entries
                            ])
                            
                            prompt = f"""
あなたは経験豊富なトレードコーチです。以下のエントリープランを評価してください。

## 銘柄情報
銘柄: {normalized_ticker} ({company_name})

## 株価データ
{price_summary}

## ユーザーのエントリープラン
{entries_text}

## ユーザーのコメント
{analysis_context if analysis_context else "なし"}

## 評価項目（各項目100点満点）
1. **エントリータイミング**: トレンド、移動平均線、出来高を考慮
2. **リスク管理**: 損切り位置の妥当性
3. **リワード**: 利確目標の設定
4. **全体評価**: 総合スコア

## 出力フォーマット
以下の形式で評価してください：

### 📊 総合スコア: XX点 / 100点

### 📈 エントリータイミング評価
- スコア: XX点
- 評価理由: ...

### 🛑 リスク管理評価
- スコア: XX点
- 評価理由: ...

### 🎯 リワード評価
- スコア: XX点
- 評価理由: ...

### 💡 改善アドバイス
- ...

### ✅ 良い点
- ...
"""
                            
                            response = model.generate_content(prompt)
                            
                            st.markdown("---")
                            st.markdown(response.text)
                            
                        except Exception as e:
                            st.error(f"AI評価中にエラーが発生しました: {e}")
        else:
            st.info("📍 上のフォームでエントリーポイントを追加してください。買い/売り、損切り、利確ラインを設定できます。")
    else:
        st.warning("株価データを取得できませんでした。銘柄コードを確認してください。")
