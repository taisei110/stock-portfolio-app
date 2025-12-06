"""
パフォーマンス分析ページ
月次/年次リターン、勝率計算を表示
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from decimal import Decimal

from database import get_realized_profit_loss, get_all_transactions


def show_performance():
    """パフォーマンス分析ページを表示"""
    st.header("📊 パフォーマンス分析")
    
    # 確定損益データを取得
    realized_pl = get_realized_profit_loss()
    
    if not realized_pl:
        st.info("📭 まだ売却取引がありません。売却を記録すると、パフォーマンス分析が表示されます。")
        return
    
    # データフレームに変換
    df = pd.DataFrame(realized_pl)
    
    # 数値型に変換（Decimal対応）
    for col in ['price', 'quantity', 'avg_buy_price', 'realized_pl', 'realized_pl_pct']:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: float(x) if isinstance(x, Decimal) else x)
    
    # 日付をパース
    df['transaction_date'] = pd.to_datetime(df['transaction_date'])
    df['year'] = df['transaction_date'].dt.year
    df['month'] = df['transaction_date'].dt.to_period('M')
    df['year_month'] = df['transaction_date'].dt.strftime('%Y-%m')
    
    # 勝ち負けの判定
    df['is_win'] = df['realized_pl'] > 0
    
    # ========== KPIセクション ==========
    st.markdown("---")
    st.subheader("📈 トレードサマリー")
    
    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
    
    # 総トレード数
    total_trades = len(df)
    
    # 勝ちトレード数
    winning_trades = df['is_win'].sum()
    
    # 勝率
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    # 総確定損益
    total_pl = df['realized_pl'].sum()
    
    with kpi_col1:
        st.metric(
            "🎯 勝率",
            f"{win_rate:.1f}%",
            f"{winning_trades}勝 / {total_trades - winning_trades}敗"
        )
    
    with kpi_col2:
        st.metric(
            "💰 総確定損益",
            f"¥{total_pl:+,.0f}",
            delta_color="normal"
        )
    
    with kpi_col3:
        # 平均利益（勝ちトレードのみ）
        avg_win = df[df['is_win']]['realized_pl'].mean() if winning_trades > 0 else 0
        st.metric(
            "📈 平均利益",
            f"¥{avg_win:,.0f}" if avg_win else "-"
        )
    
    with kpi_col4:
        # 平均損失（負けトレードのみ）
        losing_trades = len(df[~df['is_win']])
        avg_loss = df[~df['is_win']]['realized_pl'].mean() if losing_trades > 0 else 0
        st.metric(
            "📉 平均損失",
            f"¥{avg_loss:,.0f}" if avg_loss else "-"
        )
    
    # リスクリワード比
    st.markdown("---")
    rr_col1, rr_col2, rr_col3 = st.columns(3)
    
    with rr_col1:
        # リスクリワード比
        risk_reward = abs(avg_win / avg_loss) if avg_loss != 0 else 0
        st.metric(
            "⚖️ リスクリワード比",
            f"{risk_reward:.2f}" if risk_reward else "-",
            help="平均利益 ÷ 平均損失"
        )
    
    with rr_col2:
        # 最大利益
        max_win = df['realized_pl'].max()
        st.metric(
            "🏆 最大利益",
            f"¥{max_win:+,.0f}"
        )
    
    with rr_col3:
        # 最大損失
        max_loss = df['realized_pl'].min()
        st.metric(
            "💔 最大損失",
            f"¥{max_loss:+,.0f}"
        )
    
    # ========== 月次リターン ==========
    st.markdown("---")
    st.subheader("📅 月次パフォーマンス")
    
    # 月別集計
    monthly = df.groupby('year_month').agg({
        'realized_pl': 'sum',
        'is_win': ['sum', 'count']
    }).reset_index()
    monthly.columns = ['month', 'total_pl', 'wins', 'total']
    monthly['win_rate'] = (monthly['wins'] / monthly['total'] * 100).round(1)
    
    # 月次リターン棒グラフ
    colors = ['#22c55e' if pl >= 0 else '#ef4444' for pl in monthly['total_pl']]
    
    fig_monthly = go.Figure()
    fig_monthly.add_trace(go.Bar(
        x=monthly['month'],
        y=monthly['total_pl'],
        marker_color=colors,
        text=[f"¥{pl:+,.0f}" for pl in monthly['total_pl']],
        textposition='outside',
        hovertemplate='%{x}<br>損益: ¥%{y:,.0f}<extra></extra>'
    ))
    
    fig_monthly.update_layout(
        title="月次確定損益",
        xaxis_title="月",
        yaxis_title="確定損益（円）",
        height=350,
        margin=dict(t=50, b=50),
        showlegend=False
    )
    fig_monthly.add_hline(y=0, line_dash="dash", line_color="gray")
    
    st.plotly_chart(fig_monthly, use_container_width=True)
    
    # 月次テーブル
    monthly_display = monthly.copy()
    monthly_display['total_pl'] = monthly_display['total_pl'].apply(lambda x: f"¥{x:+,.0f}")
    monthly_display['win_rate'] = monthly_display['win_rate'].apply(lambda x: f"{x:.1f}%")
    monthly_display.columns = ['月', '確定損益', '勝ち', '取引数', '勝率']
    st.dataframe(monthly_display, use_container_width=True, hide_index=True)
    
    # ========== 年次リターン ==========
    st.markdown("---")
    st.subheader("📆 年次パフォーマンス")
    
    # 年別集計
    yearly = df.groupby('year').agg({
        'realized_pl': 'sum',
        'is_win': ['sum', 'count']
    }).reset_index()
    yearly.columns = ['year', 'total_pl', 'wins', 'total']
    yearly['win_rate'] = (yearly['wins'] / yearly['total'] * 100).round(1)
    
    # 年次リターン棒グラフ
    colors_yearly = ['#22c55e' if pl >= 0 else '#ef4444' for pl in yearly['total_pl']]
    
    fig_yearly = go.Figure()
    fig_yearly.add_trace(go.Bar(
        x=yearly['year'].astype(str),
        y=yearly['total_pl'],
        marker_color=colors_yearly,
        text=[f"¥{pl:+,.0f}" for pl in yearly['total_pl']],
        textposition='outside'
    ))
    
    fig_yearly.update_layout(
        title="年次確定損益",
        xaxis_title="年",
        yaxis_title="確定損益（円）",
        height=300,
        margin=dict(t=50, b=50),
        showlegend=False
    )
    fig_yearly.add_hline(y=0, line_dash="dash", line_color="gray")
    
    st.plotly_chart(fig_yearly, use_container_width=True)
    
    # ========== 銘柄別パフォーマンス ==========
    st.markdown("---")
    st.subheader("🏢 銘柄別パフォーマンス")
    
    # 銘柄別集計
    by_ticker = df.groupby('ticker').agg({
        'realized_pl': 'sum',
        'is_win': ['sum', 'count']
    }).reset_index()
    by_ticker.columns = ['ticker', 'total_pl', 'wins', 'total']
    by_ticker['win_rate'] = (by_ticker['wins'] / by_ticker['total'] * 100).round(1)
    by_ticker = by_ticker.sort_values('total_pl', ascending=True)
    
    # 銘柄別損益棒グラフ
    colors_ticker = ['#22c55e' if pl >= 0 else '#ef4444' for pl in by_ticker['total_pl']]
    
    fig_ticker = go.Figure()
    fig_ticker.add_trace(go.Bar(
        y=by_ticker['ticker'],
        x=by_ticker['total_pl'],
        orientation='h',
        marker_color=colors_ticker,
        text=[f"¥{pl:+,.0f}" for pl in by_ticker['total_pl']],
        textposition='outside'
    ))
    
    fig_ticker.update_layout(
        title="銘柄別確定損益",
        xaxis_title="確定損益（円）",
        yaxis_title="",
        height=max(250, len(by_ticker) * 40),
        margin=dict(t=50, b=50, l=100),
        showlegend=False
    )
    fig_ticker.add_vline(x=0, line_dash="dash", line_color="gray")
    
    st.plotly_chart(fig_ticker, use_container_width=True)


# ページエントリーポイント
st.set_page_config(page_title="パフォーマンス分析", page_icon="📊", layout="wide")
show_performance()
