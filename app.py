import streamlit as st
import sqlite3
import pandas as pd

st.set_page_config(page_title="نظام لوحات الإنارة - النسخة النهائية", layout="wide")

def get_connection():
    return sqlite3.connect('billboards_data.db')

st.title("📊 نظام إدارة إعلانات أعمدة الإنارة")

menu = ["🏠 عرض الإشغال (حجوزات1)", "➕ إضافة حجز جديد"]
choice = st.sidebar.selectbox("القائمة", menu)

if choice == "🏠 عرض الإشغال (حجوزات1)":
    st.subheader("📋 تفاصيل الحجوزات واللوحات")
    
    # الاستعلام المحدث بناءً على فحص الأعمدة الأخير
    query = """
    SELECT 
        T1.[اسم العمود], 
        T1.[المحافظة], 
        T1.[الحجم],
        T2.[اسم الزبون], 
        T2.[فترة الحجز],
        T2.[العام],
        T2.[رسوم مؤسسة]
    FROM [اعمدة انارة] T1
    LEFT JOIN [حجوزات1] T2 ON T1.[رقم اللوحة] = T2.[رقم اللوحة]
    """
    
    try:
        conn = get_connection()
        df = pd.read_sql(query, conn)
        
        # محرك بحث ذكي
        search = st.text_input("🔍 ابحث عن زبون، محافظة، أو اسم لوحة...")
        if search:
            df = df[df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]
        
        st.dataframe(df, use_container_width=True)
        
        # ملخص سريع
        st.write(f"🔹 إجمالي السجلات: {len(df)}")
        
    except Exception as e:
        st.error(f"خطأ في عرض البيانات: {e}")

elif choice == "➕ إضافة حجز جديد":
    st.subheader("📝 نموذج إدخال حجز جديد لجدول حجوزات1")
    with st.form("add_form"):
        poles = pd.read_sql("SELECT [رقم اللوحة], [اسم العمود] FROM [اعمدة انارة]", get_connection())
        selected_pole = st.selectbox("اختر العمود", poles['اسم العمود'])
        p_id = int(poles[poles['اسم العمود'] == selected_pole]['رقم اللوحة'].values)
        
        customer = st.text_input("اسم الزبون")
        period = st.text_input("فترة الحجز (مثال: شهر نيسان)")
        year = st.text_input("العام", value="2024")
        fees = st.number_input("رسوم مؤسسة", min_value=0)
        
        if st.form_submit_button("حفظ الحجز"):
            conn = get_connection()
            sql = "INSERT INTO [حجوزات1] ([رقم اللوحة], [اسم الزبون], [فترة الحجز], [العام], [رسوم مؤسسة]) VALUES (?, ?, ?, ?, ?)"
            conn.execute(sql, (p_id, customer, period, year, fees))
            conn.commit()
            st.success("✅ تم الحفظ بنجاح في قاعدة البيانات!")
