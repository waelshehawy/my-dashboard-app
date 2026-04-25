import streamlit as st
import sqlite3
import pandas as pd

st.set_page_config(page_title="نظام لوحات الإنارة", layout="wide")

def get_connection():
    return sqlite3.connect('billboards_data.db')

st.title("📊 نظام إدارة إعلانات أعمدة الإنارة")

# القائمة الجانبية
menu = ["🏠 عرض الإشغال العام", "📅 تسجيل حجز جديد"]
choice = st.sidebar.selectbox("القائمة الرئيسية", menu)

if choice == "🏠 عرض الإشغال العام":
    st.subheader("📋 حالة اللوحات الحالية (من جدول حجوزات1)")
    
    # الاستعلام المحدث لاستخدام جدول "حجوزات1"
    query = """
    SELECT 
        T1.[اسم العمود], 
        T1.[المحافظة], 
        T1.[الحجم],
        T2.[اسم الزبون], 
        T2.[تاريخ الحجز الى]
    FROM [اعمدة انارة] T1
    LEFT JOIN [حجوزات1] T2 ON T1.[رقم اللوحة] = T2.[رقم اللوحة]
    """
    
    try:
        df = pd.read_sql(query, get_connection())
        # فلتر لعرض المحجوز فقط أو الكل
        show_all = st.checkbox("عرض جميع الأعمدة (بما فيها المتاحة)", value=True)
        if not show_all:
            df = df[df['اسم الزبون'].notna()]
            
        st.dataframe(df, use_container_width=True)
        st.info(f"عدد السجلات المعروضة: {len(df)}")
    except Exception as e:
        st.error(f"خطأ في جلب البيانات: {e}")

elif choice == "📅 تسجيل حجز جديد":
    st.subheader("📝 إضافة عقد حجز جديد")
    with st.form("new_booking"):
        # جلب قائمة الأعمدة
        poles = pd.read_sql("SELECT [رقم اللوحة], [اسم العمود] FROM [اعمدة انارة]", get_connection())
        pole_name = st.selectbox("اختر العمود", poles['اسم العمود'])
        p_id = int(poles[poles['اسم العمود'] == pole_name]['رقم اللوحة'].values[0])
        
        customer = st.text_input("اسم الزبون")
        date_to = st.text_input("تاريخ الحجز الى (مثال: 2024-12-31)")
        
        if st.form_submit_button("حفظ الحجز في حجوزات1"):
            conn = get_connection()
            conn.execute("INSERT INTO [حجوزات1] ([رقم اللوحة], [اسم الزبون], [تاريخ الحجز الى]) VALUES (?, ?, ?)", 
                         (p_id, customer, date_to))
            conn.commit()
            st.success("تم الحفظ بنجاح!")
