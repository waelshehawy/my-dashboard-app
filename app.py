import streamlit as st
import sqlite3
import pandas as pd

def get_connection():
    return sqlite3.connect('billboards_data.db')

st.title("📊 نظام إدارة إعلانات الإنارة")

try:
    conn = get_connection()
    
    # 1. عرض معاينة سريعة لجدول الحجوزات لنعرف أسماء الأعمدة بدقة
    st.sidebar.subheader("فحص الأعمدة")
    cols_hjezz = pd.read_sql("SELECT * FROM [حجوزات1] LIMIT 1", conn).columns.tolist()
    st.sidebar.write("أعمدة جدول الحجوزات الحالية:", cols_hjezz)

    # 2. الاستعلام (سنستخدم الأسماء التي زودتني بها سابقاً ونضعها بين أقواس مربعة)
    # ملاحظة: إذا فشل 'تاريخ الحجز إلى'، سنعرض فقط اسم الزبون واللوحة حالياً
    query = """
    SELECT 
        T1.[اسم العمود], 
        T1.[المحافظة], 
        T2.[اسم الزبون],
        T1.[الحجم]
    FROM [اعمدة انارة] T1
    LEFT JOIN [حجوزات1] T2 ON T1.[رقم اللوحة] = T2.[رقم اللوحة]
    """
    
    df = pd.read_sql(query, conn)
    st.success("تم جلب البيانات بنجاح!")
    st.dataframe(df, use_container_width=True)

except Exception as e:
    st.error(f"خطأ في جلب البيانات: {e}")
    st.info("تأكد من تطابق أسماء الأعمدة بين الكود وقاعدة البيانات.")
