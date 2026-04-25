import streamlit as st
import sqlite3
import pandas as pd

def get_connection():
    # تأكد أن اسم الملف هنا يطابق تماماً الاسم المرفوع على GitHub
    return sqlite3.connect('billboards_data.db')

st.title("🔍 فحص اتطابق الجداول")

# 1. جلب الأسماء الحقيقية للجداول من السيرفر
try:
    conn = get_connection()
    real_tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", conn)['name'].tolist()
    st.write("الجداول الموجودة فعلياً في الملف المرفوع:", real_tables)
    
    # 2. البحث عن الجدولين حتى لو اختلف الاسم (مثلاً وجود مسافات)
    table_poles = next((t for t in real_tables if "اعمدة" in t), None)
    table_booking = next((t for t in real_tables if "الحجوزات" in t), None)

    if table_poles and table_booking:
        query = f"""
        SELECT 
            T1.[اسم العمود], T1.[المحافظة], T1.[الحجم],
            T2.[اسم الزبون], T2.[تاريخ الحجز إلى]
        FROM [{table_poles}] T1
        LEFT JOIN [{table_booking}] T2 ON T1.[رقم اللوحة] = T2.[رقم اللوحة]
        """
        df = pd.read_sql(query, conn)
        st.success(f"تم الربط بنجاح بين جدول {table_poles} و {table_booking}")
        st.dataframe(df)
    else:
        st.error("لم نجد الجداول المطلوبة. يرجى التأكد من رفع ملف billboards_data.db الصحيح.")
except Exception as e:
    st.error(f"خطأ تقني: {e}")
