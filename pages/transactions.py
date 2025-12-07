"""
取引記録ページ
取引の登録・編集・削除を管理
"""

import streamlit as st
import pandas as pd
from datetime import date

from database import (
    add_transaction, 
    update_transaction, 
    delete_transaction, 
    get_all_transactions,
    get_transaction_by_id,
    CATEGORIES,
    ENTRY_STRATEGIES,
    ACCOUNT_TYPES
)
from stock_api import get_stock_info


def show_transactions():
    """取引記録ページを表示"""
    st.header("📝 取引記録")
    
    # タブで新規登録と一覧を分ける
    tab1, tab2 = st.tabs(["➕ 新規取引登録", "📋 取引一覧"])
    
    with tab1:
        show_transaction_form()
    
    with tab2:
        show_transactions_list()


def show_transaction_form(edit_id: int = None):
    """取引登録/編集フォームを表示"""
    
    from stock_api import search_stocks, get_stock_info
    
    # セッション状態で選択された銘柄を管理
    session_key = f'selected_stock_{edit_id}' if edit_id else 'selected_stock_new'
    if session_key not in st.session_state:
        st.session_state[session_key] = None
    
    # 編集モードの場合、既存データを取得
    default_values = {
        'ticker': '',
        'transaction_date': date.today(),
        'transaction_type': 'buy',
        'quantity': 100,
        'price': 0.0,
        'notes': '',
        'category': '上昇トレンド',
        'account_type': '現物'
    }
    
    if edit_id:
        existing = get_transaction_by_id(edit_id)
        if existing:
            default_values = {
                'ticker': existing['ticker'],
                'transaction_date': pd.to_datetime(existing['transaction_date']).date(),
                'transaction_type': existing.get('transaction_type', 'buy'),
                'quantity': existing['quantity'],
                'price': float(existing['price']) if existing['price'] else 0.0,
                'notes': existing.get('notes', ''),
                'category': existing.get('category', 'その他'),
                'account_type': existing.get('account_type', '現物')
            }
    
    # ========== 銘柄検索セクション（フォーム外） ==========
    st.markdown("#### 🔍 銘柄検索")
    
    search_col1, search_col2 = st.columns([3, 1])
    
    with search_col1:
        search_query = st.text_input(
            "銘柄名または銘柄コードで検索",
            placeholder="例: トヨタ、ソニー、7203",
            key=f"stock_search_{edit_id}" if edit_id else "stock_search_new",
            help="銘柄名の一部または銘柄コードを入力すると候補が表示されます"
        )
    
    # 検索結果を表示
    if search_query and len(search_query) >= 1:
        results = search_stocks(search_query, limit=10)
        if results:
            options = ["選択してください"] + [f"{r['ticker']} - {r['name']}" for r in results]
            selected_option = st.selectbox(
                "📋 検索結果から選択",
                options=options,
                key=f"search_results_{edit_id}" if edit_id else "search_results_new"
            )
            
            if selected_option != "選択してください":
                idx = options.index(selected_option) - 1
                selected_stock = results[idx]
                st.session_state[session_key] = selected_stock
                st.success(f"✅ 選択: {selected_stock['ticker']} - {selected_stock['name']}")
        else:
            st.caption("該当する銘柄がありません。銘柄コードを直接入力してください。")
    
    # 選択された銘柄から値を取得
    if st.session_state[session_key]:
        default_values['ticker'] = st.session_state[session_key]['ticker']
    
    st.markdown("---")
    
    # フォームキーを動的に生成（編集時は異なるキーを使用）
    st.subheader("取引情報を入力" if not edit_id else f"取引ID {edit_id} を編集")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 銘柄コード入力のキーを動的に生成して、値の更新を確実に反映させる
        ticker_input_key = f"ticker_{edit_id}_{default_values['ticker']}" if edit_id else f"ticker_new_{default_values['ticker']}"
        
        ticker = st.text_input(
            "銘柄コード *",
            value=default_values['ticker'],
            placeholder="例: 7203.T（トヨタ）",
            help="上の検索欄で銘柄を選択すると自動入力されます",
            key=ticker_input_key
        )
        
        transaction_date = st.date_input(
            "取引日 *",
            value=default_values['transaction_date'],
            max_value=date.today()
        )
        
        transaction_type = st.selectbox(
            "売買種別 *",
            options=['buy', 'sell'],
            index=0 if default_values['transaction_type'] == 'buy' else 1,
            format_func=lambda x: '買い' if x == 'buy' else '売り'
        )
        
        quantity = st.number_input(
            "株数 *",
            min_value=1,
            value=default_values['quantity'],
            step=100
        )
    
    with col2:
        price = st.number_input(
            "単価（円） *",
            min_value=0.0,
            value=default_values['price'],
            step=0.01,
            format="%.2f"
        )
        
        account_type = st.selectbox(
            "口座種別",
            options=ACCOUNT_TYPES,
            index=ACCOUNT_TYPES.index(default_values['account_type']) if default_values['account_type'] in ACCOUNT_TYPES else 0
        )
        
        category = st.selectbox(
            "📊 テクニカル状態",
            options=CATEGORIES,
            index=CATEGORIES.index(default_values['category']) if default_values['category'] in CATEGORIES else 0,
            help="エントリー時の相場状況"
        )
        
        entry_strategy = st.selectbox(
            "🎯 エントリー戦略",
            options=ENTRY_STRATEGIES,
            index=0,
            help="どのような戦略でエントリーしたか"
        )
        
        notes = st.text_area(
            "メモ",
            value=default_values['notes'],
            placeholder="取引の根拠やメモ"
        )
        
        # 取得額の計算表示
        total_cost = quantity * price
        st.metric("取得額合計", f"¥{total_cost:,.0f}")
    
    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        submit = st.button(
            "💾 保存" if not edit_id else "✏️ 更新",
            type="primary",
            use_container_width=True
        )
    
    if submit:
        # バリデーション
        if not ticker:
            st.error("銘柄コードを入力してください")
            return
        
        if price <= 0:
            st.error("単価は0より大きい値を入力してください")
            return
        
        # エントリー戦略をメモに含める
        final_notes = f"【戦略: {entry_strategy}】{notes}" if notes else f"【戦略: {entry_strategy}】"
        
        # 会社名の解決
        target_company_name = None
        
        # 1. 検索結果から選択されている場合（銘柄コードが一致することを確認）
        if session_key in st.session_state and st.session_state[session_key]:
            if st.session_state[session_key]['ticker'] == ticker:
                target_company_name = st.session_state[session_key]['name']
        
        # 2. まだ会社名がない場合はAPIから取得を試みる
        if not target_company_name:
            with st.spinner("会社名を取得中..."):
                try:
                    info = get_stock_info(ticker)
                    if info:
                        target_company_name = info.get('name')
                except Exception:
                    pass
        
        # 取引を保存
        try:
            if edit_id:
                success = update_transaction(
                    transaction_id=edit_id,
                    ticker=ticker,
                    company_name=target_company_name,
                    transaction_type=transaction_type,
                    quantity=quantity,
                    price=price,
                    transaction_date=str(transaction_date),
                    notes=final_notes,
                    category=category,
                    account_type=account_type
                )
                if success:
                    st.success(f"✅ 取引ID {edit_id} を更新しました！")
                    st.rerun()
            else:
                new_id = add_transaction(
                    ticker=ticker,
                    company_name=target_company_name,
                    transaction_type=transaction_type,
                    quantity=quantity,
                    price=price,
                    transaction_date=str(transaction_date),
                    notes=final_notes,
                    category=category,
                    account_type=account_type
                )
                        ticker=ticker,
                        company_name=target_company_name,
                        transaction_type=transaction_type,
                        quantity=quantity,
                        price=price,
                        transaction_date=str(transaction_date),
                        notes=final_notes,
                        category=category,
                        account_type=account_type
                    )
                    st.success(f"✅ 取引を登録しました！（ID: {new_id}）")
                    
                    # 銘柄情報を表示
                    with st.spinner("銘柄情報を取得中..."):
                        info = get_stock_info(ticker)
                        if info:
                            st.info(f"📊 {info.get('name', ticker)} を登録しました")
                    
            except Exception as e:
                st.error(f"❌ エラーが発生しました: {e}")


def show_transactions_list():
    """取引一覧を表示"""
    
    transactions_list = get_all_transactions()
    
    if not transactions_list:
        st.info("取引データがありません。「新規取引登録」タブから取引を追加してください。")
        return
    
    transactions = pd.DataFrame(transactions_list)
    
    # 検索・フィルター
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        search_ticker = st.text_input("🔍 銘柄コードで検索", placeholder="例: 7203.T")
    
    with col2:
        date_range = st.date_input(
            "📅 期間で絞り込み",
            value=[],
            help="開始日と終了日を選択"
        )
    
    # フィルター適用
    filtered_df = transactions.copy()
    
    if search_ticker:
        filtered_df = filtered_df[
            filtered_df['ticker'].str.contains(search_ticker.upper(), na=False)
        ]
    
    if len(date_range) == 2:
        start_date, end_date = date_range
        filtered_df = filtered_df[
            (pd.to_datetime(filtered_df['transaction_date']).dt.date >= start_date) &
            (pd.to_datetime(filtered_df['transaction_date']).dt.date <= end_date)
        ]
    
    st.markdown(f"**{len(filtered_df)}件の取引**")
    
    # 取引一覧テーブル
    for idx, row in filtered_df.iterrows():
        with st.container():
            col1, col2, col3, col4, col5, col6 = st.columns([1.5, 1.5, 1, 1.5, 1, 1])
            
            with col1:
                tx_type = "🟢 買い" if row.get('transaction_type') == 'buy' else "🔴 売り"
                st.markdown(f"**{row['ticker']}** {tx_type}")
                st.caption(f"ID: {row['id']}")
            
            with col2:
                st.markdown(f"📅 {row['transaction_date']}")
            
            with col3:
                st.markdown(f"📈 {row['quantity']:,}株")
            
            with col4:
                total = row['quantity'] * row['price']
                st.markdown(f"¥{row['price']:,.2f}")
                st.caption(f"合計: ¥{total:,.0f}")
            
            with col5:
                if st.button("✏️", key=f"edit_{row['id']}", help="編集"):
                    st.session_state['edit_transaction_id'] = row['id']
                    st.rerun()
            
            with col6:
                if st.button("🗑️", key=f"delete_{row['id']}", help="削除"):
                    st.session_state['delete_transaction_id'] = row['id']
            
            st.markdown("---")
    
    # 削除確認ダイアログ
    if 'delete_transaction_id' in st.session_state:
        delete_id = st.session_state['delete_transaction_id']
        st.warning(f"⚠️ 取引ID {delete_id} を削除しますか？")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("はい、削除する", type="primary"):
                if delete_transaction(delete_id):
                    st.success("削除しました")
                    del st.session_state['delete_transaction_id']
                    st.rerun()
        with col2:
            if st.button("キャンセル"):
                del st.session_state['delete_transaction_id']
                st.rerun()
    
    # 編集モード
    if 'edit_transaction_id' in st.session_state:
        edit_id = st.session_state['edit_transaction_id']
        st.markdown("### ✏️ 取引を編集")
        show_transaction_form(edit_id=edit_id)
        
        if st.button("❌ 編集をキャンセル"):
            del st.session_state['edit_transaction_id']
            st.rerun()


# ページエントリーポイント
st.set_page_config(page_title="取引記録", page_icon="📝", layout="wide")
show_transactions()
