# pages/available_boards.py
import streamlit as st
import pandas as pd
from datetime import date
from utils.database import get_connection, run_query
from utils.helpers import safe_split, badge_animated, create_metric_card_3d
from utils.helpers import (
    convert_date_to_period_name,
    get_period_number,
    get_period_from_date,
    safe_split,
    badge_animated,
    create_metric_card_3d
)
# ============================================================
# دوال الفترات (من الكود الأساسي)
# ============================================================

MONTHS_AR = {
    1: "كانون ثاني", 2: "شباط", 3: "اذار", 4: "نيسان",
    5: "ايار", 6: "حزيران", 7: "تموز", 8: "اب",
    9: "ايلول", 10: "تشرين اول", 11: "تشرين ثاني", 12: "كانون اول"
}

def convert_date_to_period_name(date_obj):
    month_name = MONTHS_AR[date_obj.month]
    if date_obj.day <= 15:
        return f"{month_name} 15-1"
    else:
        return f"{month_name} 30-15"

def get_available_boards_from_date(start_date):
    """اللوحات المتاحة ابتداءً من تاريخ محدد"""
    target_period = convert_date_to_period_name(start_date)
    target_year = start_date.year
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # جلب أرقام اللوحات المحجوزة في الفترة المطلوبة
    cursor.execute("""
        SELECT "رقم اللوحة" FROM "حجوزات1" 
        WHERE "فترة الحجز" = %s AND "العام" = %s
    """, (target_period, target_year))
    
    booked_ids = [row[0] for row in cursor.fetchall()]
    
    # جلب جميع الأعمدة
    cursor.execute('SELECT * FROM "اعمدة انارة"')
    all_columns = cursor.fetchall()
    col_names = [desc[0] for desc in cursor.description]
    
    cursor.close()
    conn.close()
    
    all_boards_df = pd.DataFrame(all_columns, columns=col_names)
    available_df = all_boards_df[~all_boards_df['رقم اللوحة'].isin(booked_ids)]
    
    return available_df

def show(start_date=None):
    """عرض صفحة الأعمدة المتاحة"""
    if start_date is None:
        start_date = date.today()
    
    st.title("📍 الأعمدة المتاحة للإيجار")
    st.info("📌 عرض الأعمدة المتاحة من تاريخ محدد")
    
    # فلتر تاريخ البداية
    with st.form(key="filter_form"):
        st.subheader("📅 فلتر تاريخ بداية الإتاحة")
        start_date = st.date_input(
            "عرض الأعمدة المتاحة من تاريخ:",
            value=start_date,
            help="اختر التاريخ الذي تبدأ منه فترة الإتاحة"
        )
        submitted = st.form_submit_button("🔍 تطبيق الفلتر")
    
    if not submitted and 'df_available' not in st.session_state:
        submitted = True
    
    if submitted:
        # جلب البيانات
        df = get_available_boards_from_date(start_date)
        
        st.write(f"📅 التاريخ المختار: {start_date}")
        st.write(f"📊 عدد الأعمدة المتاحة: {len(df)}")
        
        # عرض الجدول
        st.dataframe(
            df[['رقم اللوحة', 'اسم العمود', 'المحافظة', 'الشبكة', 'الحجم', 'العدد']],
            use_container_width=True
        )
        
        # تصدير
        csv_data = df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            "📥 تحميل التقرير (CSV)",
            csv_data,
            f"available_boards_{start_date.strftime('%Y%m%d')}.csv",
            "text/csv",
            use_container_width=True
        )
