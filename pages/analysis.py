"""
チャート分析ページ
株価チャート（ローソク足）とテクニカル指標を表示
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from database import get_unique_tickers
from stock_api import get_historical_data, get_stock_info, calculate_technical_indicators


def show_analysis():
    """チャート分析ページを表示"""
    st.header("📈 チャート分析")
    
    # 登録済み銘柄を取得
    registered_tickers = get_unique_tickers()
    
    # 銘柄選択
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        # 手動入力または登録済みから選択
        ticker_option = st.radio(
            "銘柄を選択",
            ["登録済み銘柄から選択", "銘柄コードを入力"],
            horizontal=True
        )
        
        if ticker_option == "登録済み銘柄から選択":
            if not registered_tickers:
                st.info("登録済みの銘柄がありません。「取引記録」から追加してください。")
                return
            
            ticker = st.selectbox(
                "銘柄を選択",
                options=registered_tickers,
                format_func=lambda x: f"{x}"
            )
        else:
            ticker = st.text_input(
                "銘柄コードを入力",
                placeholder="例: 7203.T（トヨタ）"
            )
    
    with col2:
        period = st.selectbox(
            "期間",
            options=["1mo", "3mo", "6mo", "1y", "2y", "5y"],
            index=3,
            format_func=lambda x: {
                "1mo": "1ヶ月",
                "3mo": "3ヶ月",
                "6mo": "6ヶ月",
                "1y": "1年",
                "2y": "2年",
                "5y": "5年"
            }[x]
        )
    
    with col3:
        indicators = st.multiselect(
            "テクニカル指標",
            options=["SMA5", "SMA25", "SMA75", "ボリンジャーバンド"],
            default=["SMA25"]
        )
    
    if not ticker:
        st.info("👆 銘柄を選択または入力してください")
        return
    
    # 株価データを取得
    with st.spinner(f"{ticker} のデータを取得中..."):
        df = get_historical_data(ticker, period)
        stock_info = get_stock_info(ticker)
    
    if df.empty:
        st.error(f"❌ {ticker} のデータを取得できませんでした。銘柄コードを確認してください。")
        return
    
    # テクニカル指標を計算
    df = calculate_technical_indicators(df)
    
    # 銘柄情報を表示
    show_stock_info(stock_info, df)
    
    st.markdown("---")
    
    # ローソク足チャート
    show_candlestick_chart(df, ticker, stock_info.get('name', ticker), indicators)
    
    # 出来高チャート
    show_volume_chart(df)


def show_stock_info(info: dict, df: pd.DataFrame):
    """銘柄情報をKPIとして表示"""
    if df.empty:
        return
    
    latest_price = df['Close'].iloc[-1]
    prev_price = df['Close'].iloc[-2] if len(df) > 1 else latest_price
    price_change = latest_price - prev_price
    price_change_pct = (price_change / prev_price * 100) if prev_price else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            f"📊 {info.get('name', 'N/A')}",
            f"¥{latest_price:,.2f}",
            f"¥{price_change:+,.2f} ({price_change_pct:+.2f}%)"
        )
    
    with col2:
        high_52w = info.get('fifty_two_week_high')
        if high_52w:
            st.metric("52週高値", f"¥{high_52w:,.2f}")
        else:
            st.metric("期間高値", f"¥{df['High'].max():,.2f}")
    
    with col3:
        low_52w = info.get('fifty_two_week_low')
        if low_52w:
            st.metric("52週安値", f"¥{low_52w:,.2f}")
        else:
            st.metric("期間安値", f"¥{df['Low'].min():,.2f}")
    
    with col4:
        avg_volume = df['Volume'].mean()
        st.metric("平均出来高", f"{avg_volume:,.0f}")


def show_candlestick_chart(df: pd.DataFrame, ticker: str, name: str, indicators: list):
    """ローソク足チャートを表示"""
    st.subheader(f"📉 {name} ({ticker}) チャート")
    
    fig = go.Figure()
    
    # ローソク足
    fig.add_trace(go.Candlestick(
        x=df['Date'],
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        name='株価',
        increasing_line_color='#22c55e',
        decreasing_line_color='#ef4444'
    ))
    
    # 移動平均線
    colors = {
        'SMA5': '#fbbf24',
        'SMA25': '#3b82f6',
        'SMA75': '#8b5cf6'
    }
    
    for indicator in indicators:
        if indicator in ['SMA5', 'SMA25', 'SMA75'] and indicator in df.columns:
            fig.add_trace(go.Scatter(
                x=df['Date'],
                y=df[indicator],
                mode='lines',
                name=indicator,
                line=dict(color=colors.get(indicator, '#888'), width=1.5)
            ))
    
    # ボリンジャーバンド
    if 'ボリンジャーバンド' in indicators and 'BB_upper' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['Date'],
            y=df['BB_upper'],
            mode='lines',
            name='BB上限',
            line=dict(color='rgba(156, 163, 175, 0.5)', width=1)
        ))
        fig.add_trace(go.Scatter(
            x=df['Date'],
            y=df['BB_lower'],
            mode='lines',
            name='BB下限',
            line=dict(color='rgba(156, 163, 175, 0.5)', width=1),
            fill='tonexty',
            fillcolor='rgba(156, 163, 175, 0.1)'
        ))
    
    fig.update_layout(
        title=None,
        yaxis_title='株価（円）',
        xaxis_title='日付',
        xaxis_rangeslider_visible=False,
        height=500,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(t=30, b=30)
    )
    
    st.plotly_chart(fig, use_container_width=True)


def show_volume_chart(df: pd.DataFrame):
    """出来高チャートを表示"""
    st.subheader("📊 出来高")
    
    # 株価の上昇/下落で色分け
    colors = ['#22c55e' if df['Close'].iloc[i] >= df['Open'].iloc[i] 
              else '#ef4444' for i in range(len(df))]
    
    fig = go.Figure(go.Bar(
        x=df['Date'],
        y=df['Volume'],
        marker_color=colors,
        name='出来高'
    ))
    
    fig.update_layout(
        yaxis_title='出来高',
        xaxis_title='日付',
        height=200,
        margin=dict(t=10, b=30),
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True)


# ページエントリーポイント
st.set_page_config(page_title="チャート分析", page_icon="📈", layout="wide")
show_analysis()
