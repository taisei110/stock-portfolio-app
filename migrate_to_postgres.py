"""
SQLite -> PostgreSQL (Supabase) データ移行スクリプト

使用方法:
1. .envにDATABASE_URLを設定
2. python migrate_to_postgres.py を実行
"""

import sqlite3
from pathlib import Path
import os

from sqlalchemy import create_engine, text


# パス設定
SQLITE_PATH = Path(__file__).parent / "portfolio.db"
ENV_PATH = Path(__file__).parent / ".env"


def get_postgres_url() -> str | None:
    """環境変数からPostgreSQL URLを取得"""
    if ENV_PATH.exists():
        with open(ENV_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                if key.strip() == 'DATABASE_URL':
                    value = value.strip().strip('"').strip("'")
                    if value and value.startswith('postgresql'):
                        return value
    return os.getenv("DATABASE_URL")


def migrate():
    """SQLiteからPostgreSQLへデータを移行"""
    print("=" * 50)
    print("SQLite -> PostgreSQL Migration")
    print("=" * 50)
    
    # 1. PostgreSQL接続確認
    postgres_url = get_postgres_url()
    if not postgres_url:
        print("[ERROR] DATABASE_URL is not set.")
        print("  Please set DATABASE_URL in .env file.")
        return False
    
    print(f"[OK] PostgreSQL URL: {postgres_url[:50]}...")
    
    # 2. SQLiteデータ確認
    if not SQLITE_PATH.exists():
        print("[ERROR] portfolio.db not found.")
        print("  No data to migrate.")
        return False
    
    # SQLiteからデータ読み込み
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    cursor = sqlite_conn.cursor()
    
    cursor.execute("SELECT * FROM transactions ORDER BY id")
    rows = cursor.fetchall()
    sqlite_conn.close()
    
    print(f"[OK] Loaded {len(rows)} records from SQLite.")
    
    if len(rows) == 0:
        print("[INFO] No data to migrate.")
        return True
    
    # 3. PostgreSQL接続
    try:
        pg_engine = create_engine(postgres_url, pool_pre_ping=True)
        with pg_engine.connect() as conn:
            # テスト接続
            conn.execute(text("SELECT 1"))
        print("[OK] PostgreSQL connection successful")
    except Exception as e:
        print(f"[ERROR] PostgreSQL connection failed: {e}")
        return False
    
    # 4. テーブル作成
    with pg_engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(20) NOT NULL,
                company_name VARCHAR(100),
                transaction_type VARCHAR(10) NOT NULL CHECK(transaction_type IN ('buy', 'sell')),
                account_type VARCHAR(20) DEFAULT 'genbutsu',
                quantity INTEGER NOT NULL CHECK(quantity > 0),
                price NUMERIC(15, 2) NOT NULL CHECK(price > 0),
                transaction_date DATE NOT NULL,
                transaction_time VARCHAR(10) DEFAULT '09:00',
                notes TEXT,
                category VARCHAR(50) DEFAULT 'other',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()
    print("[OK] Table created/verified")
    
    # 5. データ移行
    migrated = 0
    skipped = 0
    errors = 0
    
    with pg_engine.connect() as conn:
        for row in rows:
            try:
                # 既存データチェック（重複防止）
                result = conn.execute(text(
                    "SELECT id FROM transactions WHERE id = :id"
                ), {"id": row['id']})
                
                if result.fetchone():
                    print(f"  [SKIP] ID {row['id']}: Already exists")
                    skipped += 1
                    continue
                
                # データ挿入（IDを保持）
                conn.execute(text("""
                    INSERT INTO transactions 
                    (id, ticker, company_name, transaction_type, account_type, quantity, 
                     price, transaction_date, transaction_time, notes, category, created_at)
                    VALUES 
                    (:id, :ticker, :company_name, :transaction_type, :account_type, :quantity,
                     :price, :transaction_date, :transaction_time, :notes, :category, :created_at)
                """), {
                    "id": row['id'],
                    "ticker": row['ticker'],
                    "company_name": row['company_name'],
                    "transaction_type": row['transaction_type'],
                    "account_type": row['account_type'] or 'genbutsu',
                    "quantity": row['quantity'],
                    "price": row['price'],
                    "transaction_date": row['transaction_date'],
                    "transaction_time": row['transaction_time'] or '09:00',
                    "notes": row['notes'],
                    "category": row['category'] or 'other',
                    "created_at": row['created_at']
                })
                
                migrated += 1
                print(f"  [OK] ID {row['id']}: {row['ticker']} migrated")
                
            except Exception as e:
                errors += 1
                print(f"  [ERROR] ID {row['id']}: {e}")
        
        conn.commit()
    
    # 6. シーケンスリセット（PostgreSQL）
    try:
        with pg_engine.connect() as conn:
            conn.execute(text("""
                SELECT setval('transactions_id_seq', (SELECT COALESCE(MAX(id), 1) FROM transactions), true)
            """))
            conn.commit()
        print("[OK] Sequence reset")
    except Exception as e:
        print(f"[WARN] Sequence reset failed: {e}")
    
    print("=" * 50)
    print(f"Migration complete: {migrated} migrated, {skipped} skipped, {errors} errors")
    print("=" * 50)
    
    # 7. 検証
    with pg_engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM transactions"))
        pg_count = result.fetchone()[0]
    
    print(f"\nVerification:")
    print(f"  SQLite: {len(rows)} records")
    print(f"  PostgreSQL: {pg_count} records")
    
    if pg_count >= len(rows):
        print("\n[SUCCESS] Data migration completed successfully!")
        print("\nNext steps:")
        print("1. Restart the app")
        print("2. Verify PostgreSQL connection")
        return True
    else:
        print("\n[WARN] Record count mismatch. Please verify.")
        return False


if __name__ == "__main__":
    migrate()
