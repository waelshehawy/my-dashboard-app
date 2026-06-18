# utils/database.py
import psycopg2
import pandas as pd

# ✅ اتصال واحد على مستوى الملف
conn = psycopg2.connect(
    host="aws-1-eu-north-1.pooler.supabase.com",
    port="6543",
    database="postgres",
    user="postgres.ncuofpvbaglwbdqnpman",
    password="W@elPreview2026",
    sslmode="require",
    connect_timeout=30
)

def get_connection():
    """إرجاع الاتصال المفتوح (للتسجيل الدخول والاستعلامات)"""
    return conn

def run_query(query, params=None, fetch=True):
    """تنفيذ استعلام على Supabase"""
    cursor = conn.cursor()
    try:
        cursor.execute(query, params or ())
        if fetch and query.strip().upper().startswith('SELECT'):
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            return pd.DataFrame(rows, columns=columns)
        else:
            conn.commit()
            return cursor.rowcount
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
