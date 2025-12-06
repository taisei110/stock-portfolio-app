"""
進化版 株式アプリ (開発中)
ダッシュボード + チャート分析 + 検索・フィルタ機能
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime
from database import (
    init_db,
    add_transaction,
    get_all_transactions,
    get_transaction_by_id,
    update_transaction,
    delete_transaction,
    get_portfolio_summary,
    get_all_categories,
    get_realized_profit_loss,
    get_total_realized_profit_loss,
    CATEGORIES,
    ACCOUNT_TYPES
)
from stock_api import (
    normalize_ticker,
    get_current_price,
    get_prices_for_tickers,
    get_historical_data,
    search_stocks
)

# ページ設定
st.set_page_config(
    page_title="進化版 株式アプリ",
    page_icon="📈",
    layout="wide"
)

# データベース初期化
init_db()

# PWA対応メタタグ
st.markdown("""
<head>
    <link rel="manifest" href="./static/manifest.json">
    <meta name="theme-color" content="#6366f1">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="株式アプリ">
    <link rel="apple-touch-icon" href="https://cdn-icons-png.flaticon.com/512/2534/2534204.png">
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
</head>
""", unsafe_allow_html=True)


# カスタムCSS - ダークモダンテーマ
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* 全体のフォント */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* メインエリア */
    .main {
        padding: 1rem 2rem;
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
    }
    
    /* ヘッダー */
    h1, h2, h3 {
        color: #f1f5f9 !important;
        font-weight: 700;
    }
    
    /* テキスト */
    p, span, label, .stMarkdown {
        color: #cbd5e1;
    }
    
    /* サイドバー */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
    }
    
    [data-testid="stSidebar"] [data-testid="stForm"] {
        background-color: rgba(30, 41, 59, 0.8);
        padding: 1rem;
        border-radius: 12px;
        border: 1px solid #334155;
        backdrop-filter: blur(10px);
    }
    
    /* ボタン */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
        border: none;
        color: white;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
    }
    
    /* メトリクスカード */
    [data-testid="stMetricValue"] {
        color: #f1f5f9 !important;
        font-size: 1.8rem !important;
        font-weight: 700 !important;
    }
    
    [data-testid="stMetricLabel"] {
        color: #94a3b8 !important;
    }
    
    /* セグメントボタン */
    .period-buttons {
        display: flex;
        gap: 8px;
        margin-bottom: 1rem;
    }
    
    /* データフレーム */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
    }
    
    /* 入力フィールド */
    .stTextInput input, .stSelectbox select, .stNumberInput input {
        background-color: #1e293b !important;
        border: 1px solid #334155 !important;
        color: #f1f5f9 !important;
        border-radius: 8px;
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background-color: rgba(30, 41, 59, 0.5) !important;
        border-radius: 8px;
    }
    
    /* 成功・警告メッセージ */
    .stSuccess { background-color: rgba(34, 197, 94, 0.2); border-left: 4px solid #22c55e; }
    .stWarning { background-color: rgba(234, 179, 8, 0.2); border-left: 4px solid #eab308; }
    .stInfo { background-color: rgba(59, 130, 246, 0.2); border-left: 4px solid #3b82f6; }
</style>
""", unsafe_allow_html=True)

# セッション状態の初期化
if 'editing_id' not in st.session_state:
    st.session_state.editing_id = None
if 'delete_id' not in st.session_state:
    st.session_state.delete_id = None
if 'price_cache' not in st.session_state:
    st.session_state.price_cache = {}
if 'search_results' not in st.session_state:
    st.session_state.search_results = []
if 'selected_stock' not in st.session_state:
    st.session_state.selected_stock = None
if 'use_current_time' not in st.session_state:
    st.session_state.use_current_time = False

# ========== サイドバー: 取引追加フォーム ==========
with st.sidebar:
    st.title("📈 株式アプリ")
    st.markdown("---")
    
    editing = st.session_state.editing_id is not None
    form_title = "✏️ 取引を編集" if editing else "📝 新規取引"
    st.subheader(form_title)
    
    existing = get_transaction_by_id(st.session_state.editing_id) if editing else None
    
    # 銘柄検索セクション
    st.markdown("##### 🔍 銘柄検索")
    search_query = st.text_input(
        "銘柄名で検索",
        placeholder="例: トヨタ、ソニー",
        key="stock_search"
    )
    
    if search_query:
        results = search_stocks(search_query)
        if results:
            options = [f"{r['ticker']} - {r['name']}" for r in results]
            selected = st.selectbox("検索結果", options=["選択してください"] + options)
            if selected != "選択してください":
                st.session_state.selected_stock = results[options.index(selected)]
        else:
            st.caption("該当する銘柄がありません")
    
    # 銘柄コードから会社名を自動取得
    st.markdown("##### 📝 銘柄コード直接入力")
    ticker_input = st.text_input(
        "銘柄コードを入力して自動補完",
        placeholder="例: 7203.T",
        key="ticker_autocomplete"
    )
    
    if ticker_input and st.button("🔍 銘柄情報を取得", key="fetch_info"):
        with st.spinner("銘柄情報を取得中..."):
            from stock_api import get_stock_info
            info = get_stock_info(ticker_input)
            if info and info.get('name'):
                st.session_state.selected_stock = {
                    'ticker': info['ticker'],
                    'name': info['name']
                }
                st.success(f"✅ {info['ticker']} - {info['name']}")
                st.rerun()
            else:
                st.warning("銘柄情報を取得できませんでした。銘柄コードを確認してください。")
    
    # 選択された銘柄を表示
    if st.session_state.selected_stock:
        st.success(f"選択: {st.session_state.selected_stock['ticker']} - {st.session_state.selected_stock['name']}")
    
    st.markdown("---")
    
    with st.form("transaction_form", clear_on_submit=True):
        # 銘柄コード（検索結果があれば自動入力）
        default_ticker = ""
        default_company = ""
        if st.session_state.selected_stock:
            default_ticker = st.session_state.selected_stock['ticker']
            default_company = st.session_state.selected_stock['name']
        elif existing:
            default_ticker = existing['ticker']
            default_company = existing['company_name'] or ""
        
        ticker = st.text_input(
            "銘柄コード *",
            value=default_ticker,
            placeholder="例: 7203.T",
            help="上の入力欄で銘柄情報取得ボタンを押すと自動補完されます"
        )
        
        company_name = st.text_input(
            "会社名（自動入力）",
            value=default_company,
            placeholder="銘柄コードから自動取得されます"
        )
        
        transaction_type = st.selectbox(
            "取引種別 *",
            options=["buy", "sell"],
            format_func=lambda x: "🟢 買い" if x == "buy" else "🔴 売り",
            index=0 if not existing else (0 if existing['transaction_type'] == 'buy' else 1)
        )
        
        # カテゴリ選択
        category = st.selectbox(
            "カテゴリ",
            options=CATEGORIES,
            index=CATEGORIES.index(existing.get('category', 'その他')) if existing and existing.get('category') in CATEGORIES else CATEGORIES.index('その他')
        )
        
        # 口座種別選択
        account_type = st.radio(
            "口座種別",
            options=ACCOUNT_TYPES,
            index=ACCOUNT_TYPES.index(existing.get('account_type', '現物')) if existing and existing.get('account_type') in ACCOUNT_TYPES else 0,
            horizontal=True
        )
        
        quantity = st.number_input(
            "株数 *", min_value=1,
            value=existing['quantity'] if existing else 100, step=1
        )
        
        price = st.number_input(
            "単価 (円) *", min_value=0.0,
            value=float(existing['price']) if existing else 0.0,
            step=0.5, format="%.1f"
        )
        
        # 現在時刻ボタンが押された場合は現在日時を使用
        if st.session_state.use_current_time:
            default_date = date.today()
            from datetime import time as dt_time
            now = datetime.now()
            default_time = dt_time(now.hour, now.minute)
            st.session_state.use_current_time = False
        elif existing:
            try:
                default_date = datetime.strptime(existing['transaction_date'], "%Y-%m-%d").date()
            except:
                default_date = date.today()
            try:
                default_time = datetime.strptime(existing.get('transaction_time', '09:00'), "%H:%M").time()
            except:
                from datetime import time as dt_time
                default_time = dt_time(9, 0)
        else:
            default_date = date.today()
            from datetime import time as dt_time
            default_time = dt_time(9, 0)
        
        date_col, time_col = st.columns(2)
        with date_col:
            transaction_date = st.date_input("取引日 *", value=default_date)
        with time_col:
            transaction_time = st.time_input("取引時刻", value=default_time)
        
        # 現在時刻ボタン（フォーム外）
        if st.form_submit_button("⏰ 現在時刻を入力", use_container_width=True):
            st.session_state.use_current_time = True
            st.rerun()
        
        notes = st.text_area(
            "取引の根拠・メモ",
            value=existing['notes'] if existing and existing['notes'] else "",
            placeholder="例: 決算発表前のエントリー、移動平均線ブレイクでエントリー、目標価格到達で利確など",
            height=80
        )
        
        col1, col2 = st.columns(2)
        with col1:
            submit_label = "更新" if editing else "登録"
            submitted = st.form_submit_button(submit_label, use_container_width=True, type="primary")
        with col2:
            cancelled = st.form_submit_button("キャンセル", use_container_width=True) if editing else False
        
        if submitted:
            if not ticker or price <= 0:
                st.error("銘柄コードと単価は必須です")
            else:
                normalized_ticker = normalize_ticker(ticker)
                time_str = transaction_time.strftime("%H:%M")
                
                # 会社名が空の場合、yfinanceから自動取得
                final_company_name = company_name
                if not final_company_name:
                    try:
                        from stock_api import get_stock_info
                        info = get_stock_info(normalized_ticker)
                        if info and info.get('name'):
                            final_company_name = info['name']
                    except:
                        pass
                
                if editing:
                    update_transaction(
                        st.session_state.editing_id,
                        normalized_ticker, final_company_name, transaction_type,
                        quantity, price, str(transaction_date), notes, category, time_str, account_type
                    )
                    st.success("✅ 更新しました")
                    st.session_state.editing_id = None
                else:
                    add_transaction(
                        normalized_ticker, final_company_name, transaction_type,
                        quantity, price, str(transaction_date), notes, category, time_str, account_type
                    )
                    st.success(f"✅ {final_company_name or normalized_ticker} を登録しました")
                st.session_state.price_cache = {}
                st.session_state.selected_stock = None
                st.session_state.use_current_time = False
                st.rerun()
        
        if cancelled:
            st.session_state.editing_id = None
            st.session_state.selected_stock = None
            st.rerun()
    
    st.markdown("---")
    
    if st.button("🔄 株価を更新", use_container_width=True):
        st.session_state.price_cache = {}
        st.rerun()

# ========== メイン画面 ==========
st.title("📈 進化版 株式アプリ (開発中)")

# フィルタセクション
st.markdown("### 🔍 フィルタ")
filter_col1, filter_col2 = st.columns([2, 4])

with filter_col1:
    available_categories = get_all_categories()
    selected_categories = st.multiselect(
        "カテゴリで絞り込み",
        options=available_categories,
        default=[],
        placeholder="すべて表示"
    )

category_filter = selected_categories if selected_categories else None

# ポートフォリオデータ取得
portfolio = get_portfolio_summary(category_filter)

if not portfolio:
    if category_filter:
        st.info(f"📭 選択したカテゴリ（{', '.join(category_filter)}）の取引記録がありません。")
    else:
        st.info("📭 取引記録がありません。サイドバーから取引を追加してください。")
else:
    # 現在株価を取得
    tickers = [p['ticker'] for p in portfolio]
    
    if not st.session_state.price_cache:
        with st.spinner("株価を取得中..."):
            st.session_state.price_cache = get_prices_for_tickers(tickers)
    
    prices = st.session_state.price_cache
    
    # ポートフォリオ計算
    portfolio_data = []
    total_valuation = 0
    total_cost = 0
    
    for p in portfolio:
        ticker = p['ticker']
        quantity = p['total_quantity']
        # PostgreSQL Decimal型をfloatに変換
        avg_price = float(p['avg_price']) if p['avg_price'] else 0.0
        current_price = prices.get(ticker)
        if current_price:
            current_price = float(current_price)
        position_type = p.get('position_type', 'long')
        
        # ショートの場合はコスト計算が異なる
        abs_quantity = abs(quantity)
        cost = abs_quantity * avg_price
        total_cost += cost
        
        if current_price:
            if position_type == 'long':
                # ロング: (現在値 - 建単価) × 株数
                valuation = abs_quantity * current_price
                profit_loss = (current_price - avg_price) * abs_quantity
            else:
                # ショート: (建単価 - 現在値) × 株数
                valuation = abs_quantity * current_price  # 評価額（絶対値）
                profit_loss = (avg_price - current_price) * abs_quantity
            
            total_valuation += valuation
            profit_loss_pct = (profit_loss / cost * 100) if cost > 0 else 0
        else:
            valuation = 0
            profit_loss = 0
            profit_loss_pct = 0
        
        # 会社名の修正（Noneまたは数字のみの場合はAPIから取得）
        company_name = p.get('company_name') or ''
        if not company_name or str(company_name) == 'None' or str(company_name).replace('.', '').isdigit():
            try:
                from stock_api import get_stock_info
                info = get_stock_info(ticker)
                if info and info.get('name'):
                    company_name = info['name']
            except:
                pass
        if not company_name:
            company_name = ticker
        
        portfolio_data.append({
            'ticker': ticker,
            'company_name': company_name,
            'category': p.get('category', 'その他'),
            'quantity': quantity,
            'position_type': position_type,
            'avg_price': avg_price,
            'current_price': current_price,
            'valuation': valuation,
            'profit_loss': profit_loss,
            'profit_loss_pct': profit_loss_pct
        })
    
    total_pl = total_valuation - total_cost if total_valuation > 0 else 0
    total_pl_pct = (total_pl / total_cost * 100) if total_cost > 0 else 0
    
    # 確定損益を取得
    total_realized_pl = get_total_realized_profit_loss()
    
    # ========== KPI ダッシュボード ==========
    st.markdown("---")
    st.markdown("## 📊 ダッシュボード")
    
    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
    
    with kpi_col1:
        st.metric(
            label="💰 評価額",
            value=f"¥{total_valuation:,.0f}" if total_valuation > 0 else "-"
        )
    
    with kpi_col2:
        st.metric(
            label="📈 含み損益",
            value=f"¥{total_pl:+,.0f}" if total_valuation > 0 else "-",
            delta=f"{total_pl_pct:+.2f}%" if total_valuation > 0 else None
        )
    
    with kpi_col3:
        st.metric(
            label="✅ 確定損益",
            value=f"¥{total_realized_pl:+,.0f}",
            delta="売却済み" if total_realized_pl != 0 else None
        )
    
    with kpi_col4:
        st.metric(
            label="💵 取得総額",
            value=f"¥{total_cost:,.0f}"
        )
    
    st.markdown("---")
    
    # ========== チャートセクション ==========
    chart_col1, chart_col2 = st.columns([1, 2])
    
    with chart_col1:
        st.markdown("### 🥧 保有比率")
        
        pie_data = [p for p in portfolio_data if p['valuation'] > 0]
        
        if pie_data:
            fig_pie = px.pie(
                pie_data,
                values='valuation',
                names='ticker',
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            fig_pie.update_layout(
                showlegend=False,
                margin=dict(t=20, b=20, l=20, r=20),
                height=300
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("評価額データがありません")
    
    with chart_col2:
        st.markdown("### 📉 株価チャート")
        
        ticker_options = [p['ticker'] for p in portfolio_data]
        selected_ticker = st.selectbox(
            "銘柄を選択",
            options=ticker_options,
            index=0 if ticker_options else None
        )
        
        # 表示期間選択
        period_options = {
            "1ヶ月": "1mo",
            "3ヶ月": "3mo",
            "6ヶ月": "6mo",
            "1年": "1y",
            "2年": "2y",
            "5年": "5y"
        }
        
        period_cols = st.columns(6)
        selected_period = "1y"  # デフォルト
        
        for i, (label, period_val) in enumerate(period_options.items()):
            with period_cols[i]:
                if st.button(label, key=f"period_{period_val}", use_container_width=True):
                    st.session_state.chart_period = period_val
        
        # セッションから期間を取得
        if 'chart_period' not in st.session_state:
            st.session_state.chart_period = "1y"
        selected_period = st.session_state.chart_period
        
        if selected_ticker:
            with st.spinner(f"{selected_ticker} のデータを取得中..."):
                hist_data = get_historical_data(selected_ticker, period=selected_period)
            
            if not hist_data.empty:
                fig_candle = go.Figure()
                
                fig_candle.add_trace(go.Candlestick(
                    x=hist_data.index,
                    open=hist_data['Open'],
                    high=hist_data['High'],
                    low=hist_data['Low'],
                    close=hist_data['Close'],
                    name='株価'
                ))
                
                fig_candle.add_trace(go.Scatter(
                    x=hist_data.index, y=hist_data['MA5'],
                    mode='lines', name='5日MA',
                    line=dict(color='red', width=1)
                ))
                
                fig_candle.add_trace(go.Scatter(
                    x=hist_data.index, y=hist_data['MA25'],
                    mode='lines', name='25日MA',
                    line=dict(color='orange', width=1.5)
                ))
                
                fig_candle.add_trace(go.Scatter(
                    x=hist_data.index, y=hist_data['MA75'],
                    mode='lines', name='75日MA',
                    line=dict(color='blue', width=1.5)
                ))
                
                # 期間ラベル
                period_labels = {"1mo": "1ヶ月", "3mo": "3ヶ月", "6mo": "6ヶ月", "1y": "1年", "2y": "2年", "5y": "5年"}
                
                fig_candle.update_layout(
                    title=f"{selected_ticker} - 過去{period_labels.get(selected_period, '1年')}",
                    xaxis_title="日付",
                    yaxis_title="株価 (円)",
                    xaxis_rangeslider_visible=False,
                    height=400,
                    margin=dict(t=40, b=40, l=40, r=40),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                
                st.plotly_chart(fig_candle, use_container_width=True)
            else:
                st.warning("株価データを取得できませんでした")
    
    st.markdown("---")
    
    # ========== ポートフォリオ一覧 ==========
    st.markdown("### 📋 ポートフォリオ詳細")
    
    def format_quantity(p):
        """株数の表示フォーマット（ロング/ショート）"""
        if p['position_type'] == 'short':
            return f"ショート {abs(p['quantity']):,}株"
        else:
            return f"ロング {p['quantity']:,}株"
    
    df_display = pd.DataFrame([{
        '銘柄コード': p['ticker'],
        '会社名': p['company_name'],
        'カテゴリ': p['category'],
        '保有数': format_quantity(p),
        '建単価': f"¥{p['avg_price']:,.1f}",
        '現在値': f"¥{p['current_price']:,.1f}" if p['current_price'] else "取得失敗",
        '評価額': f"¥{p['valuation']:,.0f}" if p['valuation'] else "-",
        '含み損益': f"¥{p['profit_loss']:+,.0f} ({p['profit_loss_pct']:+.1f}%)" if p['current_price'] else "-"
    } for p in portfolio_data])
    
    st.dataframe(df_display, use_container_width=True, hide_index=True)

# 全取引履歴（折りたたみ）
st.markdown("---")
with st.expander("📜 全取引履歴", expanded=False):
    transactions = get_all_transactions(category_filter)
    
    if transactions:
        df_tx = pd.DataFrame(transactions)
        display_cols = ['ticker', 'company_name', 'transaction_type', 'quantity', 'price', 'transaction_date', 'category']
        df_tx_display = df_tx[[c for c in display_cols if c in df_tx.columns]].copy()
        df_tx_display.columns = ['銘柄コード', '会社名', '種別', '株数', '単価', '取引日', 'カテゴリ'][:len(df_tx_display.columns)]
        df_tx_display['種別'] = df_tx_display['種別'].map({'buy': '🟢 買い', 'sell': '🔴 売り'})
        df_tx_display['単価'] = df_tx_display['単価'].apply(lambda x: f"¥{x:,.1f}")
        
        st.dataframe(df_tx_display, use_container_width=True, hide_index=True)
        
        st.markdown("#### 🔧 取引の編集・削除")
        col1, col2 = st.columns(2)
        
        with col1:
            tx_options = {f"{tx['ticker']} - {tx['transaction_date']} ({tx['id']})": tx['id'] for tx in transactions}
            selected_edit = st.selectbox("編集する取引を選択", options=[""] + list(tx_options.keys()), key="edit_select")
            if st.button("✏️ 編集", disabled=not selected_edit):
                st.session_state.editing_id = tx_options[selected_edit]
                st.rerun()
        
        with col2:
            selected_delete = st.selectbox("削除する取引を選択", options=[""] + list(tx_options.keys()), key="delete_select")
            if st.button("🗑️ 削除", disabled=not selected_delete, type="secondary"):
                st.session_state.delete_id = tx_options[selected_delete]
        
        if st.session_state.delete_id:
            tx_to_delete = get_transaction_by_id(st.session_state.delete_id)
            if tx_to_delete:
                st.warning(f"⚠️ 本当に削除しますか？ **{tx_to_delete['ticker']}** ({tx_to_delete['transaction_date']})")
                col_yes, col_no, _ = st.columns([1, 1, 4])
                if col_yes.button("削除する", type="primary"):
                    delete_transaction(st.session_state.delete_id)
                    st.session_state.delete_id = None
                    st.session_state.price_cache = {}
                    st.rerun()
                if col_no.button("キャンセル"):
                    st.session_state.delete_id = None
                    st.rerun()

# ========== フッター ==========
st.markdown("---")
st.caption("📊 進化版 株式アプリ | Powered by Streamlit, yfinance & Plotly | 🤖 AIトレードコーチ搭載")
