"""
取引記録ページ
取引の登録・編集・削除を管理
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime, time as dt_time
import time
import base64
import requests

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
    
    # 現在時刻ボタン用のセッション状態
    use_current_time_key = f'use_current_time_{edit_id}' if edit_id else 'use_current_time_new'
    if use_current_time_key not in st.session_state:
        st.session_state[use_current_time_key] = False
    
    # ウィジェットキーのサフィックス（編集時と新規作成時で異なるキーを使用）
    key_suffix = f"_edit_{edit_id}" if edit_id else "_new"
    
    # 編集モードの場合、既存データを取得
    default_values = {
        'ticker': '',
        'company_name': '',
        'transaction_date': date.today(),
        'transaction_time': dt_time(9, 0),
        'transaction_type': 'buy',
        'quantity': 100,
        'price': 0.0,
        'stop_loss': None,
        'chart_image': None,
        'notes': '',
        'category': '上昇トレンド',
        'account_type': '現物'
    }
    
    if edit_id:
        existing = get_transaction_by_id(edit_id)
        if existing:
            default_values = {
                'ticker': existing['ticker'],
                'company_name': existing.get('company_name', ''),
                'transaction_date': pd.to_datetime(existing['transaction_date']).date(),
                'transaction_time': datetime.strptime(existing.get('transaction_time', '09:00'), "%H:%M").time() if existing.get('transaction_time') else dt_time(9, 0),
                'transaction_type': existing.get('transaction_type', 'buy'),
                'quantity': existing['quantity'],
                'price': float(existing['price']) if existing['price'] else 0.0,
                'stop_loss': float(existing['stop_loss']) if existing.get('stop_loss') else None,
                'chart_image': existing.get('chart_image'),
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
        default_values['company_name'] = st.session_state[session_key]['name']
    
    st.markdown("---")
    
    # フォームキーを動的に生成（編集時は異なるキーを使用）
    st.subheader("取引情報を入力" if not edit_id else f"取引ID {edit_id} を編集")
    
    # 銘柄コード入力のキーを動的に生成
    ticker_input_key = f"ticker_{edit_id}_{default_values['ticker']}" if edit_id else f"ticker_new_{default_values['ticker']}"
    
    ticker = st.text_input(
        "銘柄コード *",
        value=default_values['ticker'],
        placeholder="例: 7203.T（トヨタ）",
        help="上の検索欄で銘柄を選択すると自動入力されます",
        key=ticker_input_key
    )
    
    company_name = st.text_input(
        "会社名（自動入力）",
        value=default_values['company_name'],
        placeholder="銘柄コードから自動取得されます",
        key=f"company_name{key_suffix}"
    )
    
    transaction_type = st.selectbox(
        "取引種別 *",
        options=["buy", "sell"],
        format_func=lambda x: "🟢 買い" if x == "buy" else "🔴 売り",
        index=0 if default_values['transaction_type'] == 'buy' else 1,
        key=f"transaction_type{key_suffix}"
    )
    
    # テクニカル状態選択
    category = st.selectbox(
        "📊 テクニカル状態",
        options=CATEGORIES,
        index=CATEGORIES.index(default_values['category']) if default_values['category'] in CATEGORIES else 0,
        help="エントリー時の相場状況を選択",
        key=f"category{key_suffix}"
    )
    
    # エントリー戦略選択
    entry_strategy = st.selectbox(
        "🎯 エントリー戦略",
        options=ENTRY_STRATEGIES,
        index=0,
        help="どのような戦略でエントリーしたかを選択",
        key=f"entry_strategy{key_suffix}"
    )
    
    # 口座種別選択（横並びラジオ）
    account_type = st.radio(
        "口座種別",
        options=ACCOUNT_TYPES,
        index=ACCOUNT_TYPES.index(default_values['account_type']) if default_values['account_type'] in ACCOUNT_TYPES else 0,
        horizontal=True,
        key=f"account_type{key_suffix}"
    )
    
    quantity = st.number_input(
        "株数 *", min_value=1,
        value=default_values['quantity'], step=100,
        key=f"quantity{key_suffix}"
    )
    
    price = st.number_input(
        "単価 (円) *", min_value=0.0,
        value=default_values['price'],
        step=0.5, format="%.1f",
        key=f"price{key_suffix}"
    )
    
    # 逆指値（ストップロス）入力
    stop_loss = st.number_input(
        "🛑 逆指値 (円)",
        min_value=0.0,
        value=default_values['stop_loss'] if default_values['stop_loss'] else 0.0,
        step=0.5,
        format="%.1f",
        help="損切りラインを設定（任意）。0の場合は未設定として扱います。",
        key=f"stop_loss{key_suffix}"
    )
    # 0の場合はNoneに変換
    stop_loss = stop_loss if stop_loss > 0 else None
    
    # 現在時刻ボタンが押された場合は現在日時を使用
    if st.session_state[use_current_time_key]:
        default_date = date.today()
        now = datetime.now()
        default_time = dt_time(now.hour, now.minute)
        st.session_state[use_current_time_key] = False
    else:
        default_date = default_values['transaction_date']
        default_time = default_values['transaction_time']
    
    date_col, time_col = st.columns(2)
    with date_col:
        transaction_date = st.date_input("取引日 *", value=default_date, key=f"transaction_date{key_suffix}")
    with time_col:
        transaction_time = st.time_input("取引時刻", value=default_time, key=f"transaction_time{key_suffix}")
    
    # 現在時刻ボタン
    if st.button("⏰ 現在時刻を入力", use_container_width=True, key=f"current_time_btn{key_suffix}"):
        st.session_state[use_current_time_key] = True
        st.rerun()
    
    notes = st.text_area(
        "取引の根拠・メモ",
        value=default_values['notes'],
        placeholder="例: 25日移動平均線ブレイクでエントリー、出来高増加を確認",
        height=80,
        key=f"notes{key_suffix}"
    )
    
    # チャート画像アップロード
    st.markdown("##### 📊 チャート画像（任意）")
    
    # 入力方式の切り替え
    image_input_method = st.radio(
        "入力方式",
        ["📁 ファイルをアップロード", "🔗 URLを貼り付け"],
        horizontal=True,
        label_visibility="collapsed",
        key=f"image_input_method{key_suffix}"
    )
    
    # 画像をBase64にエンコード
    chart_image = None
    
    if image_input_method == "📁 ファイルをアップロード":
        uploaded_file = st.file_uploader(
            "TradingViewなどのスクリーンショットをアップロード",
            type=["png", "jpg", "jpeg"],
            help="エントリー時のチャート画像を保存できます（最大5MB）",
            key=f"chart_file_uploader{key_suffix}"
        )
        
        if uploaded_file is not None:
            # ファイルサイズチェック（5MB制限）
            if uploaded_file.size > 5 * 1024 * 1024:
                st.warning("⚠️ 画像サイズが大きすぎます（最大5MB）")
            else:
                image_bytes = uploaded_file.read()
                chart_image = base64.b64encode(image_bytes).decode('utf-8')
                st.success(f"✅ 画像をアップロードしました（{len(image_bytes) / 1024:.1f} KB）")
                # プレビュー表示
                st.image(image_bytes, caption="アップロードされた画像", use_container_width=True)
    
    else:  # URL入力
        image_url = st.text_input(
            "画像URL",
            placeholder="https://www.tradingview.com/x/xxxxxxxxx/ または画像の直接URL",
            help="TradingViewのスナップショットURLまたは画像の直接URLを入力",
            key=f"chart_image_url{key_suffix}"
        )
        
        if image_url:
            try:
                with st.spinner("画像を取得中..."):
                    actual_image_url = image_url
                    
                    # TradingViewのスナップショットURL（/x/形式）の場合、ページからOGP画像URLを取得
                    if "tradingview.com/x/" in image_url:
                        try:
                            # ページを取得してOGPタグから画像URLを抽出
                            page_response = requests.get(image_url, timeout=10)
                            page_response.raise_for_status()
                            
                            # og:imageタグを探す
                            import re
                            og_match = re.search(r'<meta property="og:image" content="([^"]+)"', page_response.text)
                            if og_match:
                                actual_image_url = og_match.group(1)
                                st.caption(f"📎 取得した画像URL: {actual_image_url[:50]}...")
                            else:
                                st.warning("⚠️ TradingViewページから画像URLを取得できませんでした。画像の直接URLを使用してください。")
                                st.info("💡 TradingViewでチャートを右クリック → 「画像をコピー」→ 画像を貼り付けてURLを取得してください。")
                                actual_image_url = None
                        except Exception as e:
                            st.warning(f"⚠️ TradingViewページの取得に失敗しました: {str(e)}")
                            actual_image_url = None
                    
                    if actual_image_url:
                        # 画像をダウンロード
                        response = requests.get(actual_image_url, timeout=10)
                        response.raise_for_status()
                        
                        # コンテンツタイプを確認
                        content_type = response.headers.get('content-type', '')
                        if 'image' in content_type:
                            image_bytes = response.content
                            if len(image_bytes) > 5 * 1024 * 1024:
                                st.warning("⚠️ 画像サイズが大きすぎます（最大5MB）")
                            else:
                                chart_image = base64.b64encode(image_bytes).decode('utf-8')
                                st.success(f"✅ 画像を取得しました（{len(image_bytes) / 1024:.1f} KB）")
                                # プレビュー表示
                                st.image(image_bytes, caption="取得した画像", use_container_width=True)
                        else:
                            st.warning("⚠️ 画像として認識できませんでした。直接の画像URLを試してください。")
            except requests.exceptions.Timeout:
                st.error("⏱️ タイムアウト: URLから画像を取得できませんでした")
            except requests.exceptions.RequestException as e:
                st.error(f"❌ 画像の取得に失敗しました: {str(e)}")
            except Exception as e:
                st.error(f"❌ エラー: {str(e)}")
    
    # 既存の画像がある場合（新しい画像がアップロードされていない場合）
    if chart_image is None and default_values['chart_image']:
        chart_image = default_values['chart_image']
        st.info("📎 既存のチャート画像があります")
        try:
            st.image(base64.b64decode(chart_image), caption="保存済みのチャート画像", use_container_width=True)
        except Exception:
            pass
    
    # 取得額の計算表示
    total_cost = quantity * price
    st.metric("取得額合計", f"¥{total_cost:,.0f}")
    
    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        submit = st.button(
            "💾 保存" if not edit_id else "✏️ 更新",
            type="primary",
            use_container_width=True,
            key=f"submit_btn{key_suffix}"
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
        
        # 会社名の解決（フォーム入力値を優先）
        target_company_name = company_name if company_name else None
        
        # フォームに会社名がない場合、セッションステートから取得
        if not target_company_name:
            if session_key in st.session_state and st.session_state[session_key]:
                if st.session_state[session_key]['ticker'] == ticker:
                    target_company_name = st.session_state[session_key]['name']
        
        # まだ会社名がない場合はAPIから取得を試みる
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
                    account_type=account_type,
                    stop_loss=stop_loss,
                    chart_image=chart_image
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
                    account_type=account_type,
                    stop_loss=stop_loss,
                    chart_image=chart_image
                )
                
                st.success(f"✅ 取引を登録しました！（ID: {new_id}）")
                
                # 銘柄情報を表示
                with st.spinner("銘柄情報を取得中..."):
                    info = get_stock_info(ticker)
                    if info:
                        st.info(f"📊 {info.get('name', ticker)} を登録しました")
                
                # フォームをクリアするために遅延リラン
                time.sleep(1)
                st.rerun()
            
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
