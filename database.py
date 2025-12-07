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
ENTRY_STRATEGIES = ["トレンド順張り", "トレンド逆張り", "レンジ内リバウンド", "ブレイクアウト", "その他"]

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
                    transaction_date DATE NOT NULL,
                    transaction_time VARCHAR(10) DEFAULT '09:00',
                    notes TEXT,
                    category VARCHAR(50) DEFAULT 'その他',
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
                    transaction_date TEXT NOT NULL,
                    transaction_time TEXT DEFAULT '09:00',
                    notes TEXT,
                    category TEXT DEFAULT 'その他',
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
    chart_image: Optional[str] = None
) -> int:
    """取引記録を追加"""
    with engine.connect() as conn:
        if IS_POSTGRES:
            result = conn.execute(text("""
                INSERT INTO transactions 
                (ticker, company_name, transaction_type, account_type, quantity, price, stop_loss, chart_image, transaction_date, transaction_time, notes, category)
                VALUES (:ticker, :company_name, :transaction_type, :account_type, :quantity, :price, :stop_loss, :chart_image, :transaction_date, :transaction_time, :notes, :category)
                RETURNING id
            """), {
                "ticker": ticker, "company_name": company_name, "transaction_type": transaction_type,
                "account_type": account_type, "quantity": quantity, "price": price, "stop_loss": stop_loss,
                "chart_image": chart_image, "transaction_date": transaction_date, "transaction_time": transaction_time,
                "notes": notes, "category": category
            })
            transaction_id = result.fetchone()[0]
        else:
            result = conn.execute(text("""
                INSERT INTO transactions 
                (ticker, company_name, transaction_type, account_type, quantity, price, stop_loss, chart_image, transaction_date, transaction_time, notes, category)
                VALUES (:ticker, :company_name, :transaction_type, :account_type, :quantity, :price, :stop_loss, :chart_image, :transaction_date, :transaction_time, :notes, :category)
            """), {
                "ticker": ticker, "company_name": company_name, "transaction_type": transaction_type,
                "account_type": account_type, "quantity": quantity, "price": price, "stop_loss": stop_loss,
                "chart_image": chart_image, "transaction_date": transaction_date, "transaction_time": transaction_time,
                "notes": notes, "category": category
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
    chart_image: Optional[str] = None
) -> bool:
    """取引記録を更新"""
    with engine.connect() as conn:
        result = conn.execute(text("""
            UPDATE transactions 
            SET ticker = :ticker, company_name = :company_name, transaction_type = :transaction_type,
                account_type = :account_type, quantity = :quantity, price = :price, stop_loss = :stop_loss,
                chart_image = :chart_image, transaction_date = :transaction_date, transaction_time = :transaction_time,
                notes = :notes, category = :category
            WHERE id = :id
        """), {
            "ticker": ticker, "company_name": company_name, "transaction_type": transaction_type,
            "account_type": account_type, "quantity": quantity, "price": price, "stop_loss": stop_loss,
            "chart_image": chart_image, "transaction_date": transaction_date, "transaction_time": transaction_time,
            "notes": notes, "category": category, "id": transaction_id
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
    銘柄ごとのポートフォリオサマリーを取得
    ロング（買い超過）とショート（売り超過）の両方に対応
    """
    with engine.connect() as conn:
        base_query = """
            SELECT 
                ticker,
                company_name,
                category,
                SUM(CASE WHEN transaction_type = 'buy' THEN quantity ELSE -quantity END) as total_quantity,
                SUM(CASE WHEN transaction_type = 'buy' THEN quantity * price ELSE 0 END) as total_buy_amount,
                SUM(CASE WHEN transaction_type = 'buy' THEN quantity ELSE 0 END) as total_buy_quantity,
                SUM(CASE WHEN transaction_type = 'sell' THEN quantity * price ELSE 0 END) as total_sell_amount,
                SUM(CASE WHEN transaction_type = 'sell' THEN quantity ELSE 0 END) as total_sell_quantity
            FROM transactions
        """
        
        if category_filter:
            placeholders = ", ".join([f":cat{i}" for i in range(len(category_filter))])
            params = {f"cat{i}": cat for i, cat in enumerate(category_filter)}
            query = base_query + f" WHERE category IN ({placeholders}) GROUP BY ticker, company_name, category HAVING SUM(CASE WHEN transaction_type = 'buy' THEN quantity ELSE -quantity END) != 0"
            result = conn.execute(text(query), params)
        else:
            query = base_query + " GROUP BY ticker, company_name, category HAVING SUM(CASE WHEN transaction_type = 'buy' THEN quantity ELSE -quantity END) != 0"
            result = conn.execute(text(query))
        
        rows = result.fetchall()
        columns = result.keys()
        
        portfolio = []
        for row in rows:
            row_dict = dict(zip(columns, row))
            total_qty = row_dict['total_quantity']
            
            # ポジションタイプを判定
            if total_qty > 0:
                row_dict['position_type'] = 'long'
                if row_dict['total_buy_quantity'] > 0:
                    row_dict['avg_price'] = row_dict['total_buy_amount'] / row_dict['total_buy_quantity']
                else:
                    row_dict['avg_price'] = 0
            else:
                row_dict['position_type'] = 'short'
                if row_dict['total_sell_quantity'] > 0:
                    row_dict['avg_price'] = row_dict['total_sell_amount'] / row_dict['total_sell_quantity']
                else:
                    row_dict['avg_price'] = 0
            
            portfolio.append(row_dict)
        
        return portfolio


def get_realized_profit_loss(ticker: Optional[str] = None) -> list[dict]:
    """
    確定損益を計算（売り取引から計算）
    売り時の (売値 - 平均取得単価) × 株数
    """
    with engine.connect() as conn:
        # 各銘柄の平均取得単価を計算
        result = conn.execute(text("""
            SELECT 
                ticker,
                SUM(quantity * price) / SUM(quantity) as avg_buy_price
            FROM transactions
            WHERE transaction_type = 'buy'
            GROUP BY ticker
        """))
        
        avg_prices = {row[0]: row[1] for row in result.fetchall()}
        
        # 売り取引を取得
        if ticker:
            result = conn.execute(text("""
                SELECT * FROM transactions
                WHERE transaction_type = 'sell' AND ticker = :ticker
                ORDER BY transaction_date DESC
            """), {"ticker": ticker})
        else:
            result = conn.execute(text("""
                SELECT * FROM transactions
                WHERE transaction_type = 'sell'
                ORDER BY transaction_date DESC
            """))
        
        rows = result.fetchall()
        columns = result.keys()
        
        realized_pl = []
        for row in rows:
            sell_dict = dict(zip(columns, row))
            avg_buy = avg_prices.get(sell_dict['ticker'], 0)
            sell_dict['avg_buy_price'] = avg_buy
            sell_dict['realized_pl'] = (sell_dict['price'] - avg_buy) * sell_dict['quantity']
            sell_dict['realized_pl_pct'] = ((sell_dict['price'] / avg_buy) - 1) * 100 if avg_buy > 0 else 0
            realized_pl.append(sell_dict)
        
        return realized_pl


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


def get_all_transactions() -> list[dict]:
    """全ての取引記録を日付の降順で取得"""
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT * FROM transactions ORDER BY transaction_date DESC, id DESC"
        ))
        columns = result.keys()
        return [dict(zip(columns, row)) for row in result.fetchall()]


def get_db_info() -> dict:
    """現在のデータベース接続情報を取得（デバッグ用）"""
    return {
        "database_url": DATABASE_URL[:50] + "..." if len(DATABASE_URL) > 50 else DATABASE_URL,
        "is_postgres": IS_POSTGRES,
        "type": "PostgreSQL (Supabase)" if IS_POSTGRES else "SQLite (Local)"
    }
