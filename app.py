import streamlit as st
import sqlite3
import pandas as pd

# إعداد الصفحة
st.set_page_config(page_title="نظام لوحات الإنارة", layout="wide")

def get_connection():
    return sqlite3.connect('billboards_data.db')

st.title("📊 نظام إدارة إعلانات أعمدة الإنارة")

# القائمة الجانبية
menu = ["🏠 عرض الإشغال العام", "📅 تسجيل حجز جديد", "💰 تقرير الرسوم"]
choice = st.sidebar.selectbox("القائمة الرئيسية", menu)

if choice == "🏠 عرض الإشغال العام":
    st.subheader("📋 حالة اللوحات الحالية")
    
    # الاستعلام المعتمد بالأسماء الدقيقة
    query = """
    SELECT 
        T1.[اسم العمود], 
        T1.[المحافظة] AS [محافظة اللوحة], 
        T1.[الحجم],
        T2.[اسم الزبون], 
        T2.[تاريخ الحجز الى]
    FROM [اعمدة انارة] T1
    LEFT JOIN [الحجوزات] T2 ON T1.[رقم اللوحة] = T2.[رقم اللوحة]
    """
    
    try:
        df = pd.read_sql(query, get_connection())
        # إضافة محرك بحث
        search = st.text_input("🔍 ابحث عن لوحة، محافظة، أو زبون...")
        if search:
            df = df[df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]
        
        st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"خطأ في العرض: {e}")

elif choice == "📅 تسجيل حجز جديد":
    st.subheader("📝 إضافة عقد حجز")
    with st.form("booking_form"):
        # جلب اللوحات المتاحة
        conn = get_connection()
        poles = pd.read_sql("SELECT [رقم اللوحة], [اسم العمود] FROM [اعمدة انارة]", conn)
        
        col1, col2 = st.columns(2)
        with col1:
            selected_pole = st.selectbox("اختر اللوحة", poles['اسم العمود'])
            p_id = int(poles[poles['اسم العمود'] == selected_pole]['رقم اللوحة'].values[0])
            customer = st.text_input("اسم الزبون")
            month = st.selectbox("الشهر", [str(i) for i in range(1, 13)])
        with col2:
            date_from = st.date_input("تاريخ الحجز من")
            date_to = st.date_input("تاريخ الحجز الى")
            fees = st.number_input("رسوم مؤسسة", min_value=0)
            
        if st.form_submit_button("حفظ الحجز"):
            # تنفيذ عملية الإدخال
            insert_query = """
            INSERT INTO [الحجوزات] ([رقم اللوحة], [اسم الزبون], [الشهر], [تاريخ الحجز من], [تاريخ الحجز الى], [رسوم مؤسسة])
            VALUES (?, ?, ?, ?, ?, ?)
            """
            cursor = conn.cursor()
            cursor.execute(insert_query, (p_id, customer, month, str(date_from), str(date_to), fees))
            conn.commit()
            st.success(f"تم تسجيل حجز {customer} على اللوحة {selected_pole} بنجاح!")

elif choice == "💰 تقرير الرسوم":
    st.subheader("📊 ملخص مالي")
    df_finance = pd.read_sql("SELECT [اسم الزبون], [رسوم مؤسسة], [عمولات مندوبين] FROM [الحجوزات]", get_connection())
    st.metric("إجمالي رسوم المؤسسة", f"{df_finance['رسوم مؤسسة'].sum():,.0f} ل.س")
    st.bar_chart(df_finance.groupby('اسم الزبون')['رسوم مؤسسة'].sum())
