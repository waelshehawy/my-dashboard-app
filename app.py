import streamlit as st
import sqlite3
import pandas as pd

st.title("🧪 كود فحص هيكلية قاعدة البيانات")

def get_connection():
    return sqlite3.connect('billboards_data.db')

try:
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. جلب أسماء جميع الجداول
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    
    st.write("### 📋 الجداول المكتشفة وأعمدتها:")
    
    for table in tables:
        with st.expander(f"📁 جدول: {table}"):
            # 2. جلب أسماء الأعمدة لكل جدول
            cursor.execute(f"PRAGMA table_info([{table}])")
            columns = [f"{col[1]} ({col[2]})" for col in cursor.fetchall()]
            st.write("**الأعمدة:**")
            st.write(columns)
            
            # 3. عرض عينة من أول سطر للتأكد من شكل البيانات
            try:
                sample = pd.read_sql(f"SELECT * FROM [{table}] LIMIT 1", conn)
                st.write("**عينة بيانات (أول سطر):**")
                st.dataframe(sample)
            except:
                st.write("⚠️ الجدول فارغ حالياً")

except Exception as e:
    st.error(f"❌ فشل الاتصال بالقاعدة: {e}")
