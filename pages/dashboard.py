"""
ダッシュボードページ
ポートフォリオの概要、KPI、グラフを表示
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from database import get_portfolio_summary, get_all_transactions
from stock_api import get_prices_for_tickers


def show_dashboard():
    """ダッシュボードを表示"""
    st.header("📊 ダッシュボード")
    
    # ポートフォリオサマリーを取得（リストとして返される）
    portfolio_list = get_portfolio_summary()
    
    if not portfolio_list:
        st.info("📝 まだ取引が登録されていません。サイドバーの「取引記録」から取引を追加してください。")
        return
    
    # DataFrameに変換
    portfolio = pd.DataFrame(portfolio_list)
    
    # Decimal型をfloatに変換（PostgreSQL対応）
    for col in ['avg_price', 'total_quantity', 'total_buy_amount', 'total_sell_amount']:
        if col in portfolio.columns:
            portfolio[col] = portfolio[col].apply(lambda x: float(x) if x is not None else 0.0)
    
    # 現在の株価を取得
    with st.spinner("株価データを取得中..."):
        tickers = portfolio['ticker'].tolist()
        current_prices = get_prices_for_tickers(tickers)
    
    # 取得額を計算（avg_price * total_quantity）
    portfolio['total_cost'] = portfolio['avg_price'] * portfolio['total_quantity'].abs()
    
    # ポートフォリオに現在価格と評価額を追加
    portfolio['current_price'] = portfolio['ticker'].map(
        lambda t: float(current_prices.get(t)) if current_prices.get(t) else 0.0
    )
    portfolio['current_value'] = portfolio['total_quantity'].abs() * portfolio['current_price']
    portfolio['profit_loss'] = portfolio['current_value'] - portfolio['total_cost']
    portfolio['profit_loss_pct'] = portfolio.apply(
        lambda row: ((row['profit_loss'] / row['total_cost'] * 100) if row['total_cost'] > 0 else 0), axis=1
    ).round(2)
    portfolio['daily_change'] = 0  # 簡易化のため0
    portfolio['daily_change_pct'] = 0
    
    # 会社名の修正（Noneまたは不正な場合はAPIから取得）
    def get_display_name(row):
        name = row.get('company_name')
        ticker = row.get('ticker', '')
        
        # 既に有効な日本語名がある場合はそのまま使用
        if name and str(name) != 'None' and not str(name).replace('.', '').isdigit():
            return name
        
        # APIから日本語会社名を取得
        try:
            from stock_api import get_stock_info
            info = get_stock_info(ticker)
            if info and info.get('name'):
                return info['name']
        except:
            pass
        
        return ticker
    
    portfolio['name'] = portfolio.apply(get_display_name, axis=1)
    
    # KPI表示
    show_kpi(portfolio)
    
    st.markdown("---")
    
    # グラフセクション
    col1, col2 = st.columns(2)
    
    with col1:
        show_portfolio_pie_chart(portfolio)
    
    with col2:
        show_profit_loss_bar_chart(portfolio)
    
    st.markdown("---")
    
    # ポートフォリオ詳細テーブル
    show_portfolio_table(portfolio)


def show_kpi(portfolio: pd.DataFrame):
    """KPIメトリクスを表示"""
    total_cost = portfolio['total_cost'].sum()
    total_value = portfolio['current_value'].sum()
    total_profit = total_value - total_cost
    total_profit_pct = (total_profit / total_cost * 100) if total_cost > 0 else 0
    
    # 前日比の計算
    daily_change = (portfolio['daily_change'] * portfolio['total_quantity']).sum()
    daily_change_pct = (daily_change / total_value * 100) if total_value > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "💰 評価額合計",
            f"¥{total_value:,.0f}",
            f"¥{total_profit:+,.0f} ({total_profit_pct:+.2f}%)"
        )
    
    with col2:
        st.metric(
            "📈 トータル損益",
            f"¥{total_profit:,.0f}",
            f"{total_profit_pct:+.2f}%",
            delta_color="normal"
        )
    
    with col3:
        st.metric(
            "📅 前日比",
            f"¥{daily_change:,.0f}",
            f"{daily_change_pct:+.2f}%",
            delta_color="normal"
        )
    
    with col4:
        st.metric(
            "🏦 取得額合計",
            f"¥{total_cost:,.0f}",
            f"{len(portfolio)}銘柄保有"
        )


def show_portfolio_pie_chart(portfolio: pd.DataFrame):
    """ポートフォリオ構成比率の円グラフ"""
    st.subheader("📊 ポートフォリオ構成")
    
    if portfolio['current_value'].sum() == 0:
        st.warning("株価データを取得できませんでした")
        return
    
    fig = px.pie(
        portfolio,
        values='current_value',
        names='name',
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    
    fig.update_traces(
        textposition='inside',
        textinfo='percent+label',
        hovertemplate='%{label}<br>¥%{value:,.0f}<br>%{percent}'
    )
    
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2),
        margin=dict(t=20, b=20, l=20, r=20),
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)


def show_profit_loss_bar_chart(portfolio: pd.DataFrame):
    """銘柄別損益の棒グラフ"""
    st.subheader("📈 銘柄別 損益")
    
    # 損益でソート
    sorted_portfolio = portfolio.sort_values('profit_loss', ascending=True)
    
    colors = ['#ef4444' if x < 0 else '#22c55e' for x in sorted_portfolio['profit_loss']]
    
    fig = go.Figure(go.Bar(
        x=sorted_portfolio['profit_loss'],
        y=sorted_portfolio['name'],
        orientation='h',
        marker_color=colors,
        text=[f"¥{x:,.0f}" for x in sorted_portfolio['profit_loss']],
        textposition='outside',
        hovertemplate='%{y}<br>損益: ¥%{x:,.0f}<extra></extra>'
    ))
    
    fig.update_layout(
        xaxis_title="損益（円）",
        yaxis_title="",
        margin=dict(t=20, b=40, l=20, r=80),
        height=400,
        showlegend=False
    )
    
    fig.add_vline(x=0, line_dash="dash", line_color="gray")
    
    st.plotly_chart(fig, use_container_width=True)


def show_portfolio_table(portfolio: pd.DataFrame):
    """ポートフォリオ詳細テーブル"""
    st.subheader("📋 ポートフォリオ詳細")
    
    # 表示用にフォーマット
    display_df = portfolio[['name', 'ticker', 'total_quantity', 'avg_price', 
                            'current_price', 'total_cost', 'current_value', 
                            'profit_loss', 'profit_loss_pct']].copy()
    
    display_df.columns = ['銘柄名', 'コード', '保有株数', '平均取得単価', 
                          '現在株価', '取得額', '評価額', '損益', '損益率(%)']
    
    # 数値フォーマット
    st.dataframe(
        display_df.style.format({
            '保有株数': '{:,.0f}',
            '平均取得単価': '¥{:,.2f}',
            '現在株価': '¥{:,.2f}',
            '取得額': '¥{:,.0f}',
            '評価額': '¥{:,.0f}',
            '損益': '¥{:+,.0f}',
            '損益率(%)': '{:+.2f}%'
        }).applymap(
            lambda x: 'color: #22c55e' if isinstance(x, (int, float)) and x > 0 
                      else ('color: #ef4444' if isinstance(x, (int, float)) and x < 0 else ''),
            subset=['損益', '損益率(%)']
        ),
        use_container_width=True,
        hide_index=True
    )


# ページエントリーポイント
st.set_page_config(page_title="ダッシュボード", page_icon="📊", layout="wide")
show_dashboard()
