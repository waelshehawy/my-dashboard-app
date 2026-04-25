import streamlit as st
import sqlite3
import pandas as pd

st.set_page_config(page_title="نظام لوحات الإنارة", layout="wide")

def get_connection():
    return sqlite3.connect('billboards_data.db')

st.title("📊 نظام إدارة إعلانات أعمدة الإنارة")

menu = ["🏠 عرض الإشغال (حجوزات1)", "➕ إضافة حجز جديد"]
choice = st.sidebar.selectbox("القائمة", menu)

if choice == "🏠 عرض الإشغال (حجوزات1)":
    st.subheader("📋 تفاصيل الحجوزات واللوحات")
    query = """
    SELECT 
        T1.[اسم العمود], T1.[المحافظة], T1.[الحجم],
        T2.[اسم الزبون], T2.[فترة الحجز], T2.[العام], T2.[رسوم مؤسسة]
    FROM [اعمدة انارة] T1
    LEFT JOIN [حجوزات1] T2 ON T1.[رقم اللوحة] = T2.[رقم اللوحة]
    """
    try:
        df = pd.read_sql(query, get_connection())
        search = st.text_input("🔍 ابحث عن زبون أو محافظة...")
        if search:
            df = df[df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]
        st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"خطأ في عرض البيانات: {e}")

elif choice == "➕ إضافة حجز جديد":
    st.subheader("📝 نموذج إدخال حجز جديد")
    
    # جلب البيانات خارج الـ Form لتجنب الأخطاء
    poles_df = pd.read_sql("SELECT [رقم اللوحة], [اسم العمود] FROM [اعمدة انارة]", get_connection())
    
    # بداية النموذج
    with st.form(key="my_new_form"):
        selected_pole = st.selectbox("اختر العمود", poles_df['اسم العمود'].tolist())
        customer = st.text_input("اسم الزبون")
        period = st.text_input("فترة الحجز")
        year = st.text_input("العام", value="2024")
        fees = st.number_input("رسوم مؤسسة", min_value=0)
        
        # الزر يجب أن يكون بداخل الـ with حصراً
        submit_button = st.form_submit_button(label="حفظ الحجز الآن")

    # معالجة البيانات بعد الضغط على الزر (خارج الـ form)
    if submit_button:
        try:
            # طريقة آمنة لجلب رقم اللوحة
            p_id_row = poles_df[poles_df['اسم العمود'] == selected_pole]['رقم اللوحة'].values
            if len(p_id_row) > 0:
                p_id = int(p_id_row[0])
                
                conn = get_connection()
                sql = "INSERT INTO [حجوزات1] ([رقم اللوحة], [اسم الزبون], [فترة الحجز], [العام], [رسوم مؤسسة]) VALUES (?, ?, ?, ?, ?)"
                conn.execute(sql, (p_id, customer, period, year, fees))
                conn.commit()
                st.success(f"✅ تم بنجاح تسجيل حجز {customer}")
            else:
                st.error("تعذر العثور على رقم اللوحة المحددة")
        except Exception as e:
            st.error(f"حدث خطأ أثناء الحفظ: {e}")
