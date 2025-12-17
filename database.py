"""
株式投資ポートフォリオ管理アプリ
データベース操作モジュール
SQLite / PostgreSQL (Supabase) 両対応
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Optional
from contextlib import contextmanager

from sqlalchemy import create_engine, text, Column, Integer, String, Float, DateTime, CheckConstraint
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError


# .envファイルのパス
ENV_PATH = Path(__file__).resolve().parent / ".env"

# SQLiteのパス（フォールバック用）
SQLITE_PATH = Path(__file__).parent / "portfolio.db"

# テクニカル状態（旧カテゴリ）
CATEGORIES = ["上昇トレンド", "下降トレンド", "レンジ相場"]

# エントリー戦略
ENTRY_STRATEGIES = ["トレンド順張り", "トレンド逆張り", "レンジ内リバウンド", "ブレイクアウト", "決済", "その他"]

# 口座種別
ACCOUNT_TYPES = ["現物", "信用"]


def get_database_url() -> str:
    """環境変数からDATABASE_URLを取得、なければSQLiteにフォールバック"""
    # .envファイルから直接読み込み
    if ENV_PATH.exists():
        try:
            with open(ENV_PATH, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('#') or '=' not in line:
                        continue
                    key, value = line.split('=', 1)
                    if key.strip() == 'DATABASE_URL':
                        value = value.strip().strip('"').strip("'")
                        if value:
                            return value
        except Exception:
            pass
    
    # 環境変数からも取得を試みる
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url
    
    # フォールバック: SQLite
    return f"sqlite:///{SQLITE_PATH}"


# データベース接続設定
DATABASE_URL = get_database_url()
IS_POSTGRES = DATABASE_URL.startswith("postgresql")

# エンジン作成（接続プーリング設定）
if IS_POSTGRES:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=False
    )
else:
    engine = create_engine(DATABASE_URL, echo=False)

Session = sessionmaker(bind=engine)
Base = declarative_base()


@contextmanager
def get_connection():
    """データベース接続をコンテキストマネージャーとして取得"""
    conn = engine.connect()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_session():
    """セッションをコンテキストマネージャーとして取得"""
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """データベースを初期化し、テーブルを作成"""
    with engine.connect() as conn:
        # PostgreSQL用とSQLite用でわずかに構文が異なる
        if IS_POSTGRES:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    ticker VARCHAR(20) NOT NULL,
                    company_name VARCHAR(100),
                    transaction_type VARCHAR(10) NOT NULL CHECK(transaction_type IN ('buy', 'sell')),
                    account_type VARCHAR(20) DEFAULT '現物',
                    quantity INTEGER NOT NULL CHECK(quantity > 0),
                    price NUMERIC(15, 2) NOT NULL CHECK(price > 0),
                    stop_loss NUMERIC(15, 2),
                    chart_image TEXT,
                    rating INTEGER,
                    transaction_date DATE NOT NULL,
                    transaction_time VARCHAR(10) DEFAULT '09:00',
                    notes TEXT,
                    category VARCHAR(50) DEFAULT 'その他',
                    entry_checklist TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
        else:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    company_name TEXT,
                    transaction_type TEXT NOT NULL CHECK(transaction_type IN ('buy', 'sell')),
                    account_type TEXT DEFAULT '現物',
                    quantity INTEGER NOT NULL CHECK(quantity > 0),
                    price REAL NOT NULL CHECK(price > 0),
                    stop_loss REAL,
                    chart_image TEXT,
                    rating INTEGER,
                    transaction_date TEXT NOT NULL,
                    transaction_time TEXT DEFAULT '09:00',
                    notes TEXT,
                    category TEXT DEFAULT 'その他',
                    entry_checklist TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """))
        conn.commit()
    
    # 既存テーブルに新しいカラムを追加（マイグレーション）
    migrate_add_columns()


def migrate_add_columns() -> None:
    """既存のtransactionsテーブルに新しいカラムを追加"""
    with engine.connect() as conn:
        try:
            if IS_POSTGRES:
                conn.execute(text("""
                    ALTER TABLE transactions ADD COLUMN IF NOT EXISTS stop_loss NUMERIC(15, 2)
                """))
                conn.execute(text("""
                    ALTER TABLE transactions ADD COLUMN IF NOT EXISTS chart_image TEXT
                """))
                conn.execute(text("""
                    ALTER TABLE transactions ADD COLUMN IF NOT EXISTS rating INTEGER
                """))
                conn.execute(text("""
                    ALTER TABLE transactions ADD COLUMN IF NOT EXISTS entry_checklist TEXT
                """))
            else:
                # SQLiteではIF NOT EXISTSが使えないので、例外をキャッチ
                try:
                    conn.execute(text("""
                        ALTER TABLE transactions ADD COLUMN stop_loss REAL
                    """))
                except Exception:
                    pass
                try:
                    conn.execute(text("""
                        ALTER TABLE transactions ADD COLUMN chart_image TEXT
                    """))
                except Exception:
                    pass
                try:
                    conn.execute(text("""
                        ALTER TABLE transactions ADD COLUMN rating INTEGER
                    """))
                except Exception:
                    pass
                try:
                    conn.execute(text("""
                        ALTER TABLE transactions ADD COLUMN entry_checklist TEXT
                    """))
                except Exception:
                    pass
            conn.commit()
        except Exception:
            pass


def add_transaction(
    ticker: str,
    company_name: Optional[str],
    transaction_type: str,
    quantity: int,
    price: float,
    transaction_date: str,
    notes: Optional[str] = None,
    category: str = "その他",
    transaction_time: str = "09:00",
    account_type: str = "現物",
    stop_loss: Optional[float] = None,
    chart_image: Optional[str] = None,
    rating: Optional[int] = None,
    entry_checklist: Optional[str] = None
) -> int:
    """取引記録を追加"""
    with engine.connect() as conn:
        if IS_POSTGRES:
            result = conn.execute(text("""
                INSERT INTO transactions 
                (ticker, company_name, transaction_type, account_type, quantity, price, stop_loss, chart_image, rating, transaction_date, transaction_time, notes, category, entry_checklist)
                VALUES (:ticker, :company_name, :transaction_type, :account_type, :quantity, :price, :stop_loss, :chart_image, :rating, :transaction_date, :transaction_time, :notes, :category, :entry_checklist)
                RETURNING id
            """), {
                "ticker": ticker, "company_name": company_name, "transaction_type": transaction_type,
                "account_type": account_type, "quantity": quantity, "price": price, "stop_loss": stop_loss,
                "chart_image": chart_image, "rating": rating, "transaction_date": transaction_date, "transaction_time": transaction_time,
                "notes": notes, "category": category, "entry_checklist": entry_checklist
            })
            transaction_id = result.fetchone()[0]
        else:
            result = conn.execute(text("""
                INSERT INTO transactions 
                (ticker, company_name, transaction_type, account_type, quantity, price, stop_loss, chart_image, rating, transaction_date, transaction_time, notes, category, entry_checklist)
                VALUES (:ticker, :company_name, :transaction_type, :account_type, :quantity, :price, :stop_loss, :chart_image, :rating, :transaction_date, :transaction_time, :notes, :category, :entry_checklist)
            """), {
                "ticker": ticker, "company_name": company_name, "transaction_type": transaction_type,
                "account_type": account_type, "quantity": quantity, "price": price, "stop_loss": stop_loss,
                "chart_image": chart_image, "rating": rating, "transaction_date": transaction_date, "transaction_time": transaction_time,
                "notes": notes, "category": category, "entry_checklist": entry_checklist
            })
            transaction_id = result.lastrowid
        
        conn.commit()
        return transaction_id


def get_all_transactions(category_filter: Optional[list[str]] = None) -> list[dict]:
    """全ての取引記録を取得"""
    with engine.connect() as conn:
        if category_filter:
            # プレースホルダーを動的に生成
            placeholders = ", ".join([f":cat{i}" for i in range(len(category_filter))])
            params = {f"cat{i}": cat for i, cat in enumerate(category_filter)}
            result = conn.execute(text(f"""
                SELECT * FROM transactions 
                WHERE category IN ({placeholders})
                ORDER BY transaction_date DESC, transaction_time DESC, created_at DESC
            """), params)
        else:
            result = conn.execute(text("""
                SELECT * FROM transactions 
                ORDER BY transaction_date DESC, transaction_time DESC, created_at DESC
            """))
        
        rows = result.fetchall()
        columns = result.keys()
        return [dict(zip(columns, row)) for row in rows]


def get_transaction_by_id(transaction_id: int) -> Optional[dict]:
    """IDで取引記録を取得"""
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM transactions WHERE id = :id"),
            {"id": transaction_id}
        )
        row = result.fetchone()
        if row:
            columns = result.keys()
            return dict(zip(columns, row))
        return None


def update_transaction(
    transaction_id: int,
    ticker: str,
    company_name: Optional[str],
    transaction_type: str,
    quantity: int,
    price: float,
    transaction_date: str,
    notes: Optional[str] = None,
    category: str = "その他",
    transaction_time: str = "09:00",
    account_type: str = "現物",
    stop_loss: Optional[float] = None,
    chart_image: Optional[str] = None,
    rating: Optional[int] = None,
    entry_checklist: Optional[str] = None
) -> bool:
    """取引記録を更新"""
    with engine.connect() as conn:
        result = conn.execute(text("""
            UPDATE transactions 
            SET ticker = :ticker, company_name = :company_name, transaction_type = :transaction_type,
                account_type = :account_type, quantity = :quantity, price = :price, stop_loss = :stop_loss,
                chart_image = :chart_image, rating = :rating, transaction_date = :transaction_date, transaction_time = :transaction_time,
                notes = :notes, category = :category, entry_checklist = :entry_checklist
            WHERE id = :id
        """), {
            "ticker": ticker, "company_name": company_name, "transaction_type": transaction_type,
            "account_type": account_type, "quantity": quantity, "price": price, "stop_loss": stop_loss,
            "chart_image": chart_image, "rating": rating, "transaction_date": transaction_date, "transaction_time": transaction_time,
            "notes": notes, "category": category, "entry_checklist": entry_checklist, "id": transaction_id
        })
        conn.commit()
        return result.rowcount > 0


def delete_transaction(transaction_id: int) -> bool:
    """取引記録を削除"""
    with engine.connect() as conn:
        result = conn.execute(
            text("DELETE FROM transactions WHERE id = :id"),
            {"id": transaction_id}
        )
        conn.commit()
        return result.rowcount > 0


def get_portfolio_summary(category_filter: Optional[list[str]] = None) -> list[dict]:
    """
    ポートフォリオ（現在の保有ポジション）を取
    時系列シミュレーションにより正確な平均取得単価（移動平均法）を算出する
    """
    with engine.connect() as conn:
        # 全取引取得 (時系列順)
        query = "SELECT * FROM transactions ORDER BY transaction_date ASC, transaction_time ASC, id ASC"
        result = conn.execute(text(query))
        columns = result.keys()
        all_transactions = [dict(zip(columns, row)) for row in result.fetchall()]

    portfolio_state = {} # ticker -> {qty, avg_price, company_name, category}

    for tx in all_transactions:
        t = tx['ticker']
        if t not in portfolio_state:
            portfolio_state[t] = {'qty': 0, 'avg_price': 0, 'company_name': tx['company_name'], 'category': tx['category']}
        
        state = portfolio_state[t]
        current_qty = state['qty']
        avg_price = state['avg_price']
        
        # メタデータの更新（最新の情報を使用）
        if tx['company_name']: state['company_name'] = tx['company_name']
        if tx['category']: state['category'] = tx['category']

        tx_qty = float(tx['quantity'])
        tx_price = float(tx['price'])
        tx_type = tx['transaction_type']
        
        # === 損益計算ロジック（get_realized_profit_lossと共通） ===
        if tx_type == 'buy':
            if current_qty >= 0:
                # 買い増し（または新規）：取得単価を更新（加重平均）
                total_val = (current_qty * avg_price) + (tx_qty * tx_price)
                new_qty = current_qty + tx_qty
                state['qty'] = new_qty
                state['avg_price'] = total_val / new_qty if new_qty != 0 else 0
            else:
                # ショートカバー（買い戻し）
                cover_qty = min(abs(current_qty), tx_qty)
                # 損益確定はここでは計算しないが、ポジション更新を行う
                state['qty'] = current_qty + tx_qty
                
                if state['qty'] > 0: # ドテンロングになった場合
                    # 残りの買い分が新しい取得単価になる
                    state['avg_price'] = tx_price
        
        elif tx_type == 'sell':
            if current_qty > 0:
                 # 利益確定売り（または損切り）
                 state['qty'] = current_qty - tx_qty
                 if state['qty'] < 0: # ドテンショートになった場合
                     state['avg_price'] = tx_price
            else:
                 # 新規空売り（または売り増し）：売り単価を更新
                 short_qty = abs(current_qty)
                 total_val = (short_qty * avg_price) + (tx_qty * tx_price)
                 new_short_qty = short_qty + tx_qty
                 
                 state['qty'] = current_qty - tx_qty # マイナス方向に増加
                 state['avg_price'] = total_val / new_short_qty if new_short_qty != 0 else 0

    # 結果リストの構築
    summary = []
    for ticker, state in portfolio_state.items():
        qty = state['qty']
        if qty == 0:
            continue
            
        # カテゴリフィルタ（最新のカテゴリで判定）
        if category_filter and state['category'] not in category_filter:
            continue
        
        # app.pyが期待するキー形式に合わせる
        summary.append({
            'ticker': ticker,
            'company_name': state['company_name'],
            'category': state['category'],
            'total_quantity': qty, 
            'avg_price': state['avg_price'],
            'position_type': 'long' if qty > 0 else 'short',
            # 以下は互換性のためのダミー値（app.pyでは計算済みのavg_priceを使用するように修正済み）
            'total_buy_amount': 0,
            'total_buy_quantity': 0,
            'total_sell_amount': 0,
            'total_sell_quantity': 0
        })
    
    return summary


def get_realized_profit_loss(ticker: Optional[str] = None) -> list[dict]:
    """
    確定損益を計算
    移動平均法を用いて、時系列順に取得単価を計算し、
    決済取引（Longの売り、Shortの買い戻し）発生時の損益を算出する
    """
    with engine.connect() as conn:
        # 全取引を時系列順に取得（古い順）
        query = "SELECT * FROM transactions"
        params = {}
        if ticker:
            query += " WHERE ticker = :ticker"
            params["ticker"] = ticker
        
        query += " ORDER BY transaction_date ASC, transaction_time ASC, id ASC"
        
        result = conn.execute(text(query), params)
        columns = result.keys()
        all_transactions = [dict(zip(columns, row)) for row in result.fetchall()]
        
    realized_pl_list = []
    
    # ポートフォリオの状態 {ticker: {'qty': 0, 'avg_price': 0}}
    portfolio_state = {}
    
    for tx in all_transactions:
        t = tx['ticker']
        if t not in portfolio_state:
            portfolio_state[t] = {'qty': 0, 'avg_price': 0}
            
        state = portfolio_state[t]
        current_qty = state['qty']
        avg_price = state['avg_price']
        
        tx_qty = tx['quantity']
        tx_price = float(tx['price'])
        tx_type = tx['transaction_type']
        
        # 数値型をfloatに統一
        if hasattr(tx_qty, 'real'): tx_qty = float(tx_qty)
        if hasattr(current_qty, 'real'): current_qty = float(current_qty)
        if hasattr(avg_price, 'real'): avg_price = float(avg_price)
        
        # 損益計算用の一時変数
        pl = 0.0
        pct = 0.0
        is_closing = False
        closing_cost = avg_price # 決済時の基準コスト
        
        if tx_type == 'buy':
            if current_qty >= 0:
                # 買い増し（または新規）：取得単価を更新（加重平均）
                total_val = (current_qty * avg_price) + (tx_qty * tx_price)
                new_qty = current_qty + tx_qty
                state['qty'] = new_qty
                state['avg_price'] = total_val / new_qty if new_qty != 0 else 0
            else:
                # ショートカバー（買い戻し）：損益確定
                # 決済数量（保有ショート数と今回の買い数の小さい方）
                cover_qty = min(abs(current_qty), tx_qty)
                
                if cover_qty > 0:
                    is_closing = True
                    # ショートの利益 = (売り単価 - 買い戻し単価) * 数量
                    pl = (avg_price - tx_price) * cover_qty
                    # 騰落率（下落でプラス） = (売り単価 - 買い単価) / 売り単価
                    pct = ((avg_price - tx_price) / avg_price) * 100 if avg_price != 0 else 0
                    closing_cost = avg_price
                
                # 残りのショートポジションまたはドテンロングの計算
                remaining_buy = tx_qty - cover_qty
                state['qty'] = current_qty + tx_qty # 単純加算 (-10 + 15 = 5)
                
                if state['qty'] > 0: # ドテンロングになった場合
                    # 残りの買い分が新しい取得単価になる
                    state['avg_price'] = tx_price
                    
        elif tx_type == 'sell':
            if current_qty > 0:
                # 利益確定売り（または損切り）：損益確定
                sell_qty = min(current_qty, tx_qty)
                
                if sell_qty > 0:
                    is_closing = True
                    # ロングの利益 = (売り単価 - 取得単価) * 数量
                    pl = (tx_price - avg_price) * sell_qty
                    pct = ((tx_price / avg_price) - 1) * 100 if avg_price != 0 else 0
                    closing_cost = avg_price
                
                # 残りのポジションまたはドテンショート
                state['qty'] = current_qty - tx_qty
                if state['qty'] < 0: # ドテンショートになった場合
                    state['avg_price'] = tx_price
                    
            else:
                # 新規空売り（または売り増し）：売り単価を更新
                # abs(current_qty) * avg + tx_qty * price
                short_qty = abs(current_qty)
                total_val = (short_qty * avg_price) + (tx_qty * tx_price)
                new_short_qty = short_qty + tx_qty
                
                state['qty'] = current_qty - tx_qty # マイナス方向に増加
                state['avg_price'] = total_val / new_short_qty if new_short_qty != 0 else 0

        # 決済取引のみリストに追加
        if is_closing:
            # 元の辞書をコピーして結果を追加
            closed_tx = tx.copy()
            closed_tx['realized_pl'] = pl
            closed_tx['realized_pl_pct'] = pct
            closed_tx['avg_buy_price'] = closing_cost # 参考用（取得単価/売り単価）
            realized_pl_list.append(closed_tx)

    # 日付の新しい順にソートして返す
    realized_pl_list.sort(key=lambda x: (x['transaction_date'], x.get('transaction_time', '00:00')), reverse=True)
    
    return realized_pl_list


def get_total_realized_profit_loss() -> float:
    """全銘柄の確定損益合計"""
    realized = get_realized_profit_loss()
    return sum(r['realized_pl'] for r in realized)


def get_all_categories() -> list[str]:
    """使用されている全カテゴリを取得"""
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT DISTINCT category FROM transactions WHERE category IS NOT NULL"
        ))
        
        categories = [row[0] for row in result.fetchall() if row[0]]
        for cat in CATEGORIES:
            if cat not in categories:
                categories.append(cat)
        
        return sorted(categories)


def get_unique_tickers() -> list[str]:
    """登録されている全ての銘柄コード（ユニーク）を取得"""
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT DISTINCT ticker FROM transactions ORDER BY ticker"
        ))
        return [row[0] for row in result.fetchall()]


def get_all_transactions(category_filter: Optional[list[str]] = None) -> list[dict]:
    """全ての取引記録を日付の降順で取得"""
    with engine.connect() as conn:
        query_str = "SELECT * FROM transactions"
        params = {}
        
        if category_filter:
            placeholders = ", ".join([f":cat{i}" for i in range(len(category_filter))])
            params = {f"cat{i}": cat for i, cat in enumerate(category_filter)}
            query_str += f" WHERE category IN ({placeholders})"
        
        query_str += " ORDER BY transaction_date DESC, id DESC"
        
        result = conn.execute(text(query_str), params)
        columns = result.keys()
        return [dict(zip(columns, row)) for row in result.fetchall()]


def get_db_info() -> dict:
    """現在のデータベース接続情報を取得（デバッグ用）"""
    return {
        "database_url": DATABASE_URL[:50] + "..." if len(DATABASE_URL) > 50 else DATABASE_URL,
        "is_postgres": IS_POSTGRES,
        "type": "PostgreSQL (Supabase)" if IS_POSTGRES else "SQLite (Local)"
    }
