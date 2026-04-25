import streamlit as st
import sqlite3
import pandas as pd

def get_connection():
    return sqlite3.connect('billboards_data.db')

st.set_page_config(page_title="نظام الإعلانات المتكامل", layout="wide")

st.title("🏛️ إدارة حجوزات اللوحات الإعلانية")

menu = ["🏠 عرض الإشغال العام", "➕ تسجيل حجز جديد"]
choice = st.sidebar.selectbox("القائمة", menu)

if choice == "🏠 عرض الإشغال العام":
    query = """
    SELECT T1.[اسم العمود], T1.[المحافظة], T1.[الحجم],
           T2.[اسم الزبون], T2.[فترة الحجز], T2.[العام]
    FROM [اعمدة انارة] T1
    LEFT JOIN [حجوزات1] T2 ON T1.[رقم اللوحة] = T2.[رقم اللوحة]
    """
    df = pd.read_sql(query, get_connection())
    st.dataframe(df, use_container_width=True)

elif choice == "➕ تسجيل حجز جديد":
    st.subheader("📝 إضافة حجز جديد من القوائم الثابتة")
    
    conn = get_connection()
    # 1. جلب البيانات للقوائم المنسدلة
    poles_df = pd.read_sql("SELECT [رقم اللوحة], [اسم العمود] FROM [اعمدة انارة]", conn)
    periods_df = pd.read_sql("SELECT [namee] FROM [الفترة]", conn)
    cities_df = pd.read_sql("SELECT [المحافظة] FROM [المحافظات]", conn)
    
    with st.form(key="advanced_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            selected_pole = st.selectbox("اختر اللوحة/العمود", poles_df['اسم العمود'].tolist())
            customer = st.text_input("اسم الزبون")
            # اختيار الفترة من الجدول الثابت
            period = st.selectbox("فترة الحجز (من جدول الفترة)", periods_df['namee'].tolist())
        
        with col2:
            # اختيار المحافظة من الجدول الثابت
            city = st.selectbox("المحافظة", cities_df['المحافظة'].tolist())
            year = st.text_input("العام", value="2024")
            fees = st.number_input("رسوم مؤسسة", min_value=0)

        submit_button = st.form_submit_button(label="حفظ البيانات بالربط الكامل")

    if submit_button:
        try:
            p_id = int(poles_df[poles_df['اسم العمود'] == selected_pole]['رقم اللوحة'].values[0])
            
            sql = """
            INSERT INTO [حجوزات1] ([رقم اللوحة], [اسم الزبون], [فترة الحجز], [المحافظة], [العام], [رسوم مؤسسة]) 
            VALUES (?, ?, ?, ?, ?, ?)
            """
            conn.execute(sql, (p_id, customer, period, city, year, fees))
            conn.commit()
            st.success(f"✅ تم الحجز للزبون {customer} في محافظة {city} بنجاح!")
        except Exception as e:
            st.error(f"حدث خطأ: {e}")
