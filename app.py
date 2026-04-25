import streamlit as st
import sqlite3
import pandas as pd

def get_connection():
    return sqlite3.connect('billboards_data.db')

st.set_page_config(page_title="نظام لوحات الإنارة", layout="wide")

st.sidebar.title("القائمة الرئيسية")
choice = st.sidebar.radio("انتقل إلى:", ["🏠 الرئيسية", "📅 إدارة الحجوزات", "⚙️ الإعدادات"])

if choice == "🏠 الرئيسية":
    st.title("📊 حالة إشغال أعمدة الإنارة")
    
    # الاستعلام المحدث بناءً على الأسماء الحقيقية للجداول
    query = """
    SELECT 
        T1.[اسم العمود], 
        T1.[المحافظة], 
        T1.[الحجم],
        T2.[اسم الزبون], 
        T2.[تاريخ الحجز إلى]
    FROM [اعمدة انارة] T1
    LEFT JOIN [الحجوزات] T2 ON T1.[رقم اللوحة] = T2.[رقم اللوحة]
    """
    try:
        df = pd.read_sql(query, get_connection())
        st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"حدث خطأ في جلب البيانات: {e}")

elif choice == "📅 إدارة الحجوزات":
    st.title("📝 تسجيل حجز جديد")
    with st.form("booking_form"):
        # جلب قائمة اللوحات من الجدول الصحيح
        poles = pd.read_sql("SELECT [رقم اللوحة], [اسم العمود] FROM [اعمدة انارة]", get_connection())
        selected_pole = st.selectbox("اختر العمود", poles['اسم العمود'])
        
        customer = st.text_input("اسم الزبون")
        date_from = st.date_input("من تاريخ")
        date_to = st.date_input("إلى تاريخ")
        
        if st.form_submit_button("تثبيت الحجز"):
            st.success(f"تم تسجيل حجز {customer} بنجاح.")

elif choice == "⚙️ الإعدادات":
    st.title("⚙️ الجداول المتوفرة في النظام")
    # عرض كافة الجداول للتأكد
    tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", get_connection())
    st.write(tables)
