# utils/database.py
import psycopg2
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

def get_connection():
    """اتصال مباشر بـ Supabase"""
    return psycopg2.connect(
        host="aws-1-eu-north-1.pooler.supabase.com",
        port="6543",
        database="postgres",
        user="postgres.ncuofpvbaglwbdqnpman",
        password="WaelPreview2026",
        sslmode="require",
        connect_timeout=30
    )

def get_engine():
    """محرك SQLAlchemy للاتصال بـ Supabase"""
    url_obj = URL.create(
        drivername="postgresql+psycopg2",
        username="postgres.ncuofpvbaglwbdqnpman",
        password="WaelPreview2026",
        host="aws-1-eu-north-1.pooler.supabase.com",
        port="6543",
        database="postgres",
    )
    return create_engine(url_obj, connect_args={'sslmode': 'require'})

def run_query(query, params=None):
    """تنفيذ استعلام والعودة كـ DataFrame"""
    conn = get_connection()
    try:
        df = pd.read_sql_query(query, conn, params=params)
        return df
    finally:
        conn.close()
