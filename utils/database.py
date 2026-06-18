# utils/database.py
import psycopg2
import pandas as pd

def get_connection():
    """اتصال مباشر بـ Supabase PostgreSQL"""
    return psycopg2.connect(
        host="aws-1-eu-north-1.pooler.supabase.com",
        port="6543",
        database="postgres",
        user="postgres.ncuofpvbaglwbdqnpman",
        password="W@elPreview2026",
        sslmode="require",
        connect_timeout=30
    )

def run_query(query, params=None):
    """تنفيذ استعلام والعودة كـ DataFrame"""
    conn = get_connection()
    try:
        df = pd.read_sql_query(query, conn, params=params)
        return df
    finally:
        conn.close()
