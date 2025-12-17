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
import json

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

# チェックリスト用定数
MARKETS = ["プライム", "スタンダード", "グロース"]
ENTRY_TIMES = ["前場", "後場", "引け付近"]
HIGHER_TIMEFRAMES = ["日足", "4H"]
EXECUTION_TIMEFRAMES = ["15分", "5分"]
TREND_DIRECTIONS = ["上昇", "下降", "レンジ"]
PHASES = ["初動", "中盤", "終盤", "不明"]
RR_CATEGORIES = ["～1:2", "1:2～1:3", "1:3～1:5", "1:5以上", "1:10以上"]
LOT_TYPES = ["通常（1.0%）", "試験（1.5%）", "攻め（2.0%）"]
DENIAL_CONDITIONS = ["構造ゾーン割れ", "上位足トレンド否定", "想定外のギャップ"]
DENIAL_ACTIONS = ["即損切り", "ルール通り放置", "観察のみ"]
ANXIETY_LEVELS = ["なし", "少し", "強い"]
FINAL_DECISIONS = ["実行してよい", "観察のみ", "見送り"]


def show_transactions():
    """取引記録ページを表示"""
    st.header("📝 取引記録")
    
    # タブで新規登録と一覧を分ける
    tab1, tab2 = st.tabs(["➕ 新規取引登録", "📋 取引一覧"])
    
    with tab1:
        show_transaction_form()
    
    with tab2:
        show_transactions_list()


def render_entry_checklist(key_suffix: str = "", existing_checklist: dict = None) -> dict:
    """
    エントリーチェックリストUIを描画し、入力データを返す
    8つのセクションで構成される包括的なチェックリスト
    """
    if existing_checklist is None:
        existing_checklist = {}
    
    checklist_data = {}
    
    st.markdown("---")
    st.subheader("📋 エントリーチェックリスト")
    st.caption("エントリー前に以下のチェック項目を確認してください")
    
    # ① 基本情報
    with st.expander("① 基本情報【選択式】", expanded=True):
        basic = existing_checklist.get("basic", {})
        
        col1, col2 = st.columns(2)
        with col1:
            market = st.selectbox(
                "市場",
                options=["未選択"] + MARKETS,
                index=MARKETS.index(basic.get("market", "")) + 1 if basic.get("market") in MARKETS else 0,
                key=f"market{key_suffix}"
            )
            entry_time = st.selectbox(
                "想定エントリー時間帯",
                options=["未選択"] + ENTRY_TIMES,
                index=ENTRY_TIMES.index(basic.get("entry_time", "")) + 1 if basic.get("entry_time") in ENTRY_TIMES else 0,
                key=f"entry_time{key_suffix}"
            )
        with col2:
            higher_tf = st.selectbox(
                "上位足",
                options=["未選択"] + HIGHER_TIMEFRAMES,
                index=HIGHER_TIMEFRAMES.index(basic.get("higher_timeframe", "")) + 1 if basic.get("higher_timeframe") in HIGHER_TIMEFRAMES else 0,
                key=f"higher_tf{key_suffix}"
            )
            exec_tf = st.selectbox(
                "実行足",
                options=["未選択"] + EXECUTION_TIMEFRAMES,
                index=EXECUTION_TIMEFRAMES.index(basic.get("execution_timeframe", "")) + 1 if basic.get("execution_timeframe") in EXECUTION_TIMEFRAMES else 0,
                key=f"exec_tf{key_suffix}"
            )
        
        checklist_data["basic"] = {
            "market": market if market != "未選択" else None,
            "entry_time": entry_time if entry_time != "未選択" else None,
            "higher_timeframe": higher_tf if higher_tf != "未選択" else None,
            "execution_timeframe": exec_tf if exec_tf != "未選択" else None
        }
    
    # ② 上位足環境認識（MTF）
    with st.expander("② 上位足環境認識（MTF）【チェック式】", expanded=True):
        mtf = existing_checklist.get("mtf_analysis", {})
        
        col1, col2 = st.columns(2)
        with col1:
            trend_dir = st.selectbox(
                "上位足トレンド方向",
                options=["未選択"] + TREND_DIRECTIONS,
                index=TREND_DIRECTIONS.index(mtf.get("trend_direction", "")) + 1 if mtf.get("trend_direction") in TREND_DIRECTIONS else 0,
                key=f"trend_dir{key_suffix}"
            )
            phase = st.selectbox(
                "現在の局面",
                options=["未選択"] + PHASES,
                index=PHASES.index(mtf.get("phase", "")) + 1 if mtf.get("phase") in PHASES else 0,
                key=f"phase{key_suffix}"
            )
        with col2:
            is_with_trend = st.radio(
                "上位足順張りか",
                options=["Yes（逆張り要素なし）", "No"],
                index=0 if mtf.get("is_with_trend", True) else 1,
                key=f"is_with_trend{key_suffix}"
            )
        
        # 逆張りの場合は警告
        if is_with_trend == "No":
            st.error("⚠️ 上位足逆張りの場合、このエントリーは見送りを推奨します")
        
        checklist_data["mtf_analysis"] = {
            "trend_direction": trend_dir if trend_dir != "未選択" else None,
            "phase": phase if phase != "未選択" else None,
            "is_with_trend": is_with_trend == "Yes（逆張り要素なし）"
        }
    
    # ③ 構造的優位チェック
    with st.expander("③ 構造的優位チェック【核心・チェック式】", expanded=True):
        structure = existing_checklist.get("structure_check", {})
        
        st.caption("該当するものにチェック ✔")
        
        trend_cont = st.checkbox(
            "上位足トレンド継続構造（高安更新・MA傾斜など）",
            value=structure.get("trend_continuation", False),
            key=f"trend_cont{key_suffix}"
        )
        support_resist = st.checkbox(
            "明確な支持帯／抵抗帯（ロルリバ含む）",
            value=structure.get("support_resistance", False),
            key=f"support_resist{key_suffix}"
        )
        channel_contact = st.checkbox(
            "チャネル／トレンドライン接触",
            value=structure.get("channel_contact", False),
            key=f"channel_contact{key_suffix}"
        )
        similar_pattern = st.checkbox(
            "複数回出現している同型値動き",
            value=structure.get("similar_pattern", False),
            key=f"similar_pattern{key_suffix}"
        )
        reversal_signal = st.checkbox(
            "下位足での調整完了＋反転シグナル",
            value=structure.get("reversal_signal", False),
            key=f"reversal_signal{key_suffix}"
        )
        
        structure_count = sum([trend_cont, support_resist, channel_contact, similar_pattern, reversal_signal])
        st.metric("👉 構造カウント数", f"{structure_count}個")
        
        checklist_data["structure_check"] = {
            "trend_continuation": trend_cont,
            "support_resistance": support_resist,
            "channel_contact": channel_contact,
            "similar_pattern": similar_pattern,
            "reversal_signal": reversal_signal,
            "count": structure_count
        }
    
    # ④ RR判定
    with st.expander("④ RR判定【数値のみ】", expanded=True):
        rr = existing_checklist.get("rr_assessment", {})
        
        col1, col2, col3 = st.columns(3)
        with col1:
            entry_price = st.number_input(
                "想定エントリー価格",
                min_value=0.0,
                value=float(rr.get("entry_price", 0.0)),
                step=1.0,
                key=f"rr_entry{key_suffix}"
            )
        with col2:
            sl_price = st.number_input(
                "損切り価格",
                min_value=0.0,
                value=float(rr.get("stop_loss_price", 0.0)),
                step=1.0,
                key=f"rr_sl{key_suffix}"
            )
        with col3:
            tp_price = st.number_input(
                "利確目標価格",
                min_value=0.0,
                value=float(rr.get("take_profit_price", 0.0)),
                step=1.0,
                key=f"rr_tp{key_suffix}"
            )
        
        # RR比率を自動計算
        rr_ratio = 0.0
        rr_category = "未計算"
        if entry_price > 0 and sl_price > 0 and tp_price > 0:
            risk = abs(entry_price - sl_price)
            reward = abs(tp_price - entry_price)
            if risk > 0:
                rr_ratio = reward / risk
                if rr_ratio >= 10:
                    rr_category = "1:10以上"
                elif rr_ratio >= 5:
                    rr_category = "1:5以上"
                elif rr_ratio >= 3:
                    rr_category = "1:3～1:5"
                elif rr_ratio >= 2:
                    rr_category = "1:2～1:3"
                else:
                    rr_category = "～1:2"
        
        st.metric("👉 想定RR", f"1:{rr_ratio:.1f}" if rr_ratio > 0 else "未計算", delta=rr_category if rr_category != "未計算" else None)
        
        checklist_data["rr_assessment"] = {
            "entry_price": entry_price,
            "stop_loss_price": sl_price,
            "take_profit_price": tp_price,
            "rr_ratio": rr_ratio,
            "rr_category": rr_category
        }
    
    # ⑤ ロット自動判定
    with st.expander("⑤ ロット自動判定【選択＋自動ロジック】", expanded=True):
        lot = existing_checklist.get("lot_determination", {})
        structure_count = checklist_data["structure_check"]["count"]
        rr_ratio = checklist_data["rr_assessment"]["rr_ratio"]
        
        st.markdown("##### 通常ロット")
        normal_lot_ok = st.checkbox(
            "ルール適合 → Yes",
            value=lot.get("normal_lot_ok", True),
            key=f"normal_lot{key_suffix}"
        )
        
        st.markdown("##### 試験ロット判定")
        trial_crit1 = structure_count >= 2 and rr_ratio >= 3
        trial_crit2 = structure_count >= 3 and rr_ratio >= 2
        trial_met = trial_crit1 or trial_crit2
        
        col1, col2 = st.columns(2)
        with col1:
            st.checkbox("構造 ≥2 ＆ RR ≥1:3", value=trial_crit1, disabled=True, key=f"trial1{key_suffix}")
            st.checkbox("構造 ≥3 ＆ RR ≥1:2", value=trial_crit2, disabled=True, key=f"trial2{key_suffix}")
        with col2:
            st.info(f"→ {'✅ 該当あり' if trial_met else '❌ 該当なし'}")
        
        st.markdown("##### 攻めロット判定")
        aggr_crit1 = structure_count >= 3 and rr_ratio >= 5
        aggr_crit2 = st.checkbox(
            "A（市場・セクター）or C（事前検証）あり",
            value=lot.get("market_sector_verified", False),
            key=f"aggr_ac{key_suffix}"
        )
        aggr_crit3 = rr_ratio >= 10
        aggr_met = (aggr_crit1 and aggr_crit2) or aggr_crit3
        
        col1, col2 = st.columns(2)
        with col1:
            st.checkbox("構造 ≥3 ＆ RR ≥1:5", value=aggr_crit1, disabled=True, key=f"aggr1{key_suffix}")
            st.checkbox("RR ≥1:10（例外適用）", value=aggr_crit3, disabled=True, key=f"aggr3{key_suffix}")
        with col2:
            st.info(f"→ {'✅ 該当あり' if aggr_met else '❌ 該当なし'}")
        
        # 最終ロット判定
        if aggr_met:
            final_lot = "攻め（2.0%）"
        elif trial_met:
            final_lot = "試験（1.5%）"
        else:
            final_lot = "通常（1.0%）"
        
        st.success(f"👉 最終ロット: **{final_lot}**")
        
        checklist_data["lot_determination"] = {
            "normal_lot_ok": normal_lot_ok,
            "trial_criteria_met": trial_met,
            "aggressive_criteria_met": aggr_met,
            "market_sector_verified": aggr_crit2,
            "final_lot": final_lot
        }
    
    # ⑥ 否定シナリオ
    with st.expander("⑥ 否定シナリオ【最低限・選択式】", expanded=True):
        denial = existing_checklist.get("denial_scenario", {})
        
        st.markdown("##### 否定される条件（該当するもの）")
        denial_conds = []
        for cond in DENIAL_CONDITIONS:
            if st.checkbox(cond, value=cond in denial.get("denial_conditions", []), key=f"denial_{cond}{key_suffix}"):
                denial_conds.append(cond)
        
        other_cond = st.text_input(
            "その他（1行のみ）",
            value=denial.get("other_condition", ""),
            max_chars=100,
            key=f"denial_other{key_suffix}"
        )
        
        st.markdown("##### 否定時の行動")
        denial_action = st.selectbox(
            "行動",
            options=DENIAL_ACTIONS,
            index=DENIAL_ACTIONS.index(denial.get("action_on_denial", "即損切り")) if denial.get("action_on_denial") in DENIAL_ACTIONS else 0,
            key=f"denial_action{key_suffix}"
        )
        
        checklist_data["denial_scenario"] = {
            "denial_conditions": denial_conds,
            "other_condition": other_cond,
            "action_on_denial": denial_action
        }
    
    # ⑦ 感情・行動チェック
    with st.expander("⑦ 感情・行動チェック【チェック式】", expanded=True):
        emotion = existing_checklist.get("emotion_check", {})
        
        col1, col2 = st.columns(2)
        with col1:
            anxiety = st.selectbox(
                "焦り",
                options=ANXIETY_LEVELS,
                index=ANXIETY_LEVELS.index(emotion.get("anxiety_level", "なし")) if emotion.get("anxiety_level") in ANXIETY_LEVELS else 0,
                key=f"anxiety{key_suffix}"
            )
            revenge = st.radio(
                "取り返したい感情",
                options=["なし", "あり"],
                index=1 if emotion.get("revenge_trading", False) else 0,
                horizontal=True,
                key=f"revenge{key_suffix}"
            )
        with col2:
            ok_to_skip = st.radio(
                "見送っても後悔しない",
                options=["Yes", "No"],
                index=0 if emotion.get("ok_to_skip", True) else 1,
                horizontal=True,
                key=f"ok_skip{key_suffix}"
            )
            loss_rule_ok = st.radio(
                "連敗・停止ルール抵触していない",
                options=["Yes", "No"],
                index=0 if emotion.get("consecutive_loss_rule_ok", True) else 1,
                horizontal=True,
                key=f"loss_rule{key_suffix}"
            )
        
        # 警告表示
        if anxiety == "強い":
            st.warning("⚠️ 焦りが強い状態でのトレードは注意")
        if revenge == "あり":
            st.warning("⚠️ 取り返したい感情がある状態は危険です")
        if loss_rule_ok == "No":
            st.error("🚫 連敗・停止ルールに抵触している場合はトレードを控えてください")
        
        checklist_data["emotion_check"] = {
            "anxiety_level": anxiety,
            "revenge_trading": revenge == "あり",
            "ok_to_skip": ok_to_skip == "Yes",
            "consecutive_loss_rule_ok": loss_rule_ok == "Yes"
        }
    
    # ⑧ 実行判断
    with st.expander("⑧ 実行判断【最終】", expanded=True):
        final = existing_checklist.get("final_decision", "実行してよい")
        
        final_decision = st.radio(
            "このトレードは",
            options=FINAL_DECISIONS,
            index=FINAL_DECISIONS.index(final) if final in FINAL_DECISIONS else 0,
            key=f"final_decision{key_suffix}"
        )
        
        if final_decision == "実行してよい":
            st.success("✅ エントリー条件を満たしています")
        elif final_decision == "観察のみ":
            st.info("👀 観察モードで経過を見守りましょう")
        else:
            st.warning("🛑 この機会は見送りましょう")
        
        checklist_data["final_decision"] = final_decision
    
    return checklist_data


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
                'account_type': existing.get('account_type', '現物'),
                'entry_checklist': json.loads(existing['entry_checklist']) if existing.get('entry_checklist') else None
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
    
    # エントリーチェックリストを表示
    existing_checklist = default_values.get('entry_checklist') if 'entry_checklist' in default_values else None
    checklist_data = render_entry_checklist(key_suffix, existing_checklist)
    
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
            # チェックリストをJSON文字列に変換
            entry_checklist_json = json.dumps(checklist_data, ensure_ascii=False) if checklist_data else None
            
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
                    chart_image=chart_image,
                    entry_checklist=entry_checklist_json
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
                    chart_image=chart_image,
                    entry_checklist=entry_checklist_json
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
                ticker_code = str(row['ticker']).replace('.T', '')
                company_name_display = row.get('company_name', '') or ''
                display_name = f"{ticker_code} {company_name_display}" if company_name_display else ticker_code
                st.markdown(f"**{display_name}** {tx_type}")
                st.caption(f"ID: {row['id']}")
            
            with col2:
                st.markdown(f"📅 {row['transaction_date']}")
                # チェックリストの判断を表示
                if row.get('entry_checklist'):
                    try:
                        checklist = json.loads(row['entry_checklist']) if isinstance(row['entry_checklist'], str) else row['entry_checklist']
                        final = checklist.get('final_decision', '')
                        if final == "実行してよい":
                            st.caption("✅ 実行")
                        elif final == "観察のみ":
                            st.caption("👀 観察")
                        elif final == "見送り":
                            st.caption("🛑 見送")
                    except:
                        pass
            
            with col3:
                st.markdown(f"📈 {row['quantity']:,}株")
                # チェックリストの構造・RRを表示
                if row.get('entry_checklist'):
                    try:
                        checklist = json.loads(row['entry_checklist']) if isinstance(row['entry_checklist'], str) else row['entry_checklist']
                        structure = checklist.get('structure_check', {})
                        rr = checklist.get('rr_assessment', {})
                        count = structure.get('count', 0)
                        rr_cat = rr.get('rr_category', '')
                        if count > 0 or rr_cat:
                            st.caption(f"構造{count} {rr_cat}")
                    except:
                        pass
            
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
