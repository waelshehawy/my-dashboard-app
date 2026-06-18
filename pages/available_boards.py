# pages/available_boards.py
import streamlit as st
import pandas as pd
from datetime import date
from utils.database import get_connection, run_query
from utils.helpers import safe_split, badge_animated, create_metric_card_3d
import psycopg2

def show(start_date=None):

    
    # ✅ اختبار الاتصال أولاً
    try:
        test_df = run_query("SELECT 1 as test")
        st.success("✅ الاتصال بقاعدة البيانات ناجح!")
    except Exception as e:
        st.error(f"❌ فشل الاتصال: {e}")
        st.stop()
    
    if start_date is None:
        start_date = date.today()

def get_connection_direct():
    return psycopg2.connect(
        host="aws-1-eu-north-1.pooler.supabase.com",
        port="6543",
        database="postgres",
        user="postgres.ncuofpvbaglwbdqnpman",
        password="W@elPreview2026",
        sslmode="require",
        connect_timeout=30
    )
def get_period_from_date(date_obj):
    """تحويل التاريخ إلى رقم الفترة (1-24) باستخدام أسماء الفترات من جدول الفترة"""
    day = date_obj.day
    month = date_obj.month
    
    month_names = {
        1: 'كانون الثاني', 2: 'شباط', 3: 'آذار', 4: 'نيسان',
        5: 'أيار', 6: 'حزيران', 7: 'تموز', 8: 'آب',
        9: 'أيلول', 10: 'تشرين الأول', 11: 'تشرين الثاني', 12: 'كانون الأول'
    }
    
    month_name = month_names[month]
    
    if day <= 15:
        period_name = f"{month_name} 15-1"
    else:
        # تحديد آخر يوم في الشهر
        if month == 2:  # شباط
            last_day = 28
        elif month in [4, 6, 9, 11]:  # نيسان, حزيران, أيلول, تشرين الثاني
            last_day = 30
        else:
            last_day = 31
        period_name = f"{month_name} {last_day}-15"
    
    # قراءة أسماء الفترات من قاعدة البيانات
    periods_df = run_query('SELECT no, namee FROM "الفترة" ORDER BY no')
    period_map = {row['namee']: row['no'] for _, row in periods_df.iterrows()}
    
    return period_map.get(period_name, 99)

@st.cache_data(ttl=300)
def load_available_boards_data(target_period_num, target_year):
    """جلب بيانات الأعمدة المتاحة مع تصنيفها"""
    conn = get_connection()
    
    query = f"""
    WITH booking_periods AS (
        SELECT 
            CAST("رقم اللوحة" AS TEXT) as "رقم اللوحة",
            "فترة الحجز",
            "العام",
            CASE
                WHEN "فترة الحجز" = 'كانون ثاني 15-1' THEN 1
                WHEN "فترة الحجز" = 'كانون ثاني 30-15' THEN 2
                WHEN "فترة الحجز" = 'شباط 15-1' THEN 3
                WHEN "فترة الحجز" = 'شباط 30-15' THEN 4
                WHEN "فترة الحجز" = 'اذار 15-1' THEN 5
                WHEN "فترة الحجز" = 'اذار 30-15' THEN 6
                WHEN "فترة الحجز" = 'نيسان 15-1' THEN 7
                WHEN "فترة الحجز" = 'نيسان 30-15' THEN 8
                WHEN "فترة الحجز" = 'ايار15-1' THEN 9
                WHEN "فترة الحجز" = 'أيار 30-15' THEN 10
                WHEN "فترة الحجز" = 'حزيران 15-1' THEN 11
                WHEN "فترة الحجز" = 'حزيران 30-15' THEN 12
                WHEN "فترة الحجز" = 'تموز 15-1' THEN 13
                WHEN "فترة الحجز" = 'تموز 30-15' THEN 14
                WHEN "فترة الحجز" = 'اب 15-1' THEN 15
                WHEN "فترة الحجز" = 'اب 30-15' THEN 16
                WHEN "فترة الحجز" = 'أيلول 15-1' THEN 17
                WHEN "فترة الحجز" = 'ايلول30-15' THEN 18
                WHEN "فترة الحجز" = 'تشرين اول 15-1' THEN 19
                WHEN "فترة الحجز" = 'تشرين اول30-15' THEN 20
                WHEN "فترة الحجز" = 'تشرين ثاني 15-1' THEN 21
                WHEN "فترة الحجز" = 'تشرين ثاني 30-15' THEN 22
                WHEN "فترة الحجز" = 'كانون اول 15-1' THEN 23
                WHEN "فترة الحجز" = 'كانون اول 30-15' THEN 24
            END as period_num
        FROM "حجوزات1"
        WHERE "العام" >= {target_year}
    ),
    board_aggregated AS (
        SELECT 
            "رقم اللوحة",
            MAX(CASE WHEN "العام" = {target_year} AND "period_num" = {target_period_num} THEN 1 ELSE 0 END) as has_current,
            MAX(CASE WHEN ("العام" > {target_year}) OR ("العام" = {target_year} AND "period_num" > {target_period_num}) THEN 1 ELSE 0 END) as has_future,
            MIN(CASE WHEN ("العام" > {target_year}) OR ("العام" = {target_year} AND "period_num" > {target_period_num}) THEN period_num ELSE NULL END) as min_future_period,
            MAX(CASE WHEN "period_num" <= {target_period_num} THEN period_num ELSE NULL END) as max_current_period
        FROM booking_periods
        GROUP BY "رقم اللوحة"
    )
    SELECT 
        a."رقم اللوحة",
        a."اسم العمود",
        a."المحافظة",
        a."الشبكة",
        a."الحجم",
        a."العدد",
        CASE 
            WHEN b.has_current = 1 AND b.has_future = 1 THEN '🔴 محجوز بالكامل'
            WHEN b.has_current = 1 AND b.has_future = 0 THEN '🟠 محجوز مؤقتاً'
            WHEN b.has_current = 0 AND b.has_future = 1 THEN '🟡 متاح مؤقتاً'
            ELSE '🟢 متاح فوراً'
        END as status,
        b.min_future_period as next_booking_period,
        b.max_current_period as end_booking_period
    FROM "اعمدة انارة" a
    LEFT JOIN board_aggregated b ON CAST(a."رقم اللوحة" AS TEXT) = b."رقم اللوحة"
    ORDER BY a."المحافظة", a."رقم اللوحة"
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def show(start_date=None):
    """عرض صفحة الأعمدة المتاحة"""
    if start_date is None:
        start_date = date.today()
    
    st.title("📍 الأعمدة المتاحة للإيجار")
    st.info("📌 عرض الأعمدة حسب حالة الإتاحة مع عدد اللوحات الفعلية")
    
    # فلتر تاريخ البداية (بدون إعادة تحميل تلقائي)
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
        # حساب الفترة المستهدفة
        target_period_num = get_period_from_date(start_date)
        target_year = start_date.year
        
        st.write(f"📅 التاريخ المختار: {start_date}")
        st.write(f"📅 رقم الفترة: {target_period_num}")
        
        # جلب البيانات
        df = load_available_boards_data(target_period_num, target_year)
        
        # حساب الإحصائيات
        available_now_sites = len(df[df['status'] == '🟢 متاح فوراً'])
        available_now_boards = df[df['status'] == '🟢 متاح فوراً']['العدد'].sum()
        
        available_temp_sites = len(df[df['status'] == '🟡 متاح مؤقتاً'])
        available_temp_boards = df[df['status'] == '🟡 متاح مؤقتاً']['العدد'].sum()
        
        booked_temp_sites = len(df[df['status'] == '🟠 محجوز مؤقتاً'])
        booked_temp_boards = df[df['status'] == '🟠 محجوز مؤقتاً']['العدد'].sum()
        
        booked_full_sites = len(df[df['status'] == '🔴 محجوز بالكامل'])
        booked_full_boards = df[df['status'] == '🔴 محجوز بالكامل']['العدد'].sum()
        
        # عرض الإحصائيات
        st.subheader("📊 إحصائيات عامة")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 🟢 متاح فوراً")
            st.markdown(f"📍 **المواقع:** {available_now_sites}")
            st.markdown(f"📌 **اللوحات:** {int(available_now_boards):,}")
        
        with col2:
            st.markdown("#### 🟡 متاح مؤقتاً")
            st.markdown(f"📍 **المواقع:** {available_temp_sites}")
            st.markdown(f"📌 **اللوحات:** {int(available_temp_boards):,}")
        
        col3, col4 = st.columns(2)
        with col3:
            st.markdown("#### 🟠 محجوز مؤقتاً")
            st.markdown(f"📍 **المواقع:** {booked_temp_sites}")
            st.markdown(f"📌 **اللوحات:** {int(booked_temp_boards):,}")
        
        with col4:
            st.markdown("#### 🔴 محجوز بالكامل")
            st.markdown(f"📍 **المواقع:** {booked_full_sites}")
            st.markdown(f"📌 **اللوحات:** {int(booked_full_boards):,}")
        
        st.divider()
        
        # عرض حسب المحافظة
        for city in df['المحافظة'].unique():
            city_data = df[df['المحافظة'] == city]
            
            with st.expander(f"🏙️ {city} - {len(city_data)} موقع", expanded=False):
                
                display_df = city_data.copy()
                
                def period_to_text(period_num):
                    if pd.isna(period_num):
                        return ""
                    period_map = {11: "يبدأ 1/6", 12: "يبدأ 16/6", 13: "يبدأ 1/7", 14: "يبدأ 16/7"}
                    return period_map.get(period_num, f"فترة {period_num}")
                
                display_df['تاريخ البدء'] = display_df['next_booking_period'].apply(period_to_text)
                display_df['تاريخ الانتهاء'] = display_df['end_booking_period'].apply(period_to_text)
                
                st.dataframe(
                    display_df[['رقم اللوحة', 'اسم العمود', 'الشبكة', 'الحجم', 'العدد', 'status', 'تاريخ البدء', 'تاريخ الانتهاء']],
                    use_container_width=False,
                    height=300
                )
        
        # تصدير
        csv_data = df[['رقم اللوحة', 'اسم العمود', 'المحافظة', 'الشبكة', 'الحجم', 'العدد', 'status', 'next_booking_period', 'end_booking_period']].to_csv(
            index=False, encoding='utf-8-sig'
        )
        st.download_button(
            "📥 تحميل التقرير (CSV)",
            csv_data,
            f"available_boards_{start_date.strftime('%Y%m%d')}.csv",
            "text/csv",
            use_container_width=True
        )
