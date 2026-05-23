# app.py - نسخة الإنترنت فقط مع Supabase
import streamlit as st
import pandas as pd
import os
import io
import folium
import json
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from datetime import datetime, timedelta, date
import plotly.graph_objects as go
import plotly.express as px
import psycopg2
from psycopg2.extras import RealDictCursor

# ============================================================
# إعدادات Supabase (من متغيرات البيئة)
# ============================================================

def get_connection():
    """اتصال مباشر بـ Supabase PostgreSQL"""
    return psycopg2.connect(
        host=os.environ.get("SUPABASE_HOST", "aws-1-eu-north-1.pooler.supabase.com"),
        port=os.environ.get("SUPABASE_PORT", "6543"),
        database=os.environ.get("SUPABASE_DB", "postgres"),
        user=os.environ.get("SUPABASE_USER", "postgres.ncuofpvbaglwbdqnpman"),
        password=os.environ.get("SUPABASE_PASSWORD", "WaelPreview2026"),
        sslmode="require",
        connect_timeout=30
    )

# ============================================================
# التحسينات البصرية
# ============================================================

ADVANCED_CSS = """
<style>
    @keyframes gradientShift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    
    .stApp {
        background: linear-gradient(-45deg, #ee7752, #e73c7e, #23a6d5, #23d5ab);
        background-size: 400% 400%;
        animation: gradientShift 15s ease infinite;
    }
    
    [data-testid="stSidebar"] {
        background: rgba(26, 26, 46, 0.95) !important;
        backdrop-filter: blur(12px) !important;
        border-right: 1px solid rgba(255,255,255,0.2) !important;
    }
    
    [data-testid="stSidebar"] * {
        color: white !important;
    }
    
    .neumorphic-card {
        background: linear-gradient(145deg, #e6e9f0, #ffffff);
        border-radius: 28px;
        box-shadow: 12px 12px 24px rgba(0,0,0,0.1), -12px -12px 24px rgba(255,255,255,0.7);
        padding: 20px;
        margin: 15px 0;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    .neumorphic-card:hover {
        transform: translateY(-8px);
    }
    
    .stat-card-3d {
        background: linear-gradient(135deg, #667eea, #764ba2);
        border-radius: 20px;
        padding: 20px;
        text-align: center;
        color: white;
        transition: transform 0.3s ease;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    }
    
    .stat-card-3d:hover {
        transform: translateY(-5px) scale(1.02);
    }
    
    .stat-number-3d {
        font-size: 48px;
        font-weight: bold;
        animation: numberPulse 2s ease-in-out infinite;
    }
    
    @keyframes numberPulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.05); text-shadow: 0 0 20px rgba(255,255,255,0.5); }
    }
    
    .stButton > button {
        background: linear-gradient(45deg, #667eea, #764ba2) !important;
        border: none !important;
        border-radius: 50px !important;
        padding: 10px 24px !important;
        color: white !important;
        font-weight: bold !important;
        transition: all 0.3s ease !important;
        width: 100%;
    }
    
    .stButton > button:hover {
        transform: translateY(-3px) !important;
        box-shadow: 0 10px 20px rgba(102,126,234,0.4) !important;
    }
    
    .badge-animated {
        display: inline-block;
        padding: 6px 16px;
        border-radius: 30px;
        font-size: 12px;
        font-weight: bold;
        margin: 3px;
        animation: badgePop 0.5s ease-out;
    }
    
    @keyframes badgePop {
        from { transform: scale(0); opacity: 0; }
        to { transform: scale(1); opacity: 1; }
    }
    
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #667eea15, #764ba215);
        border-radius: 16px;
        padding: 16px;
        backdrop-filter: blur(4px);
        transition: all 0.3s ease;
    }
    
    [data-testid="stMetric"]:hover {
        transform: translateY(-5px);
    }
    
    .dataframe {
        border-radius: 15px !important;
        overflow: hidden !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1) !important;
    }
    
    .dataframe th {
        background: linear-gradient(135deg, #667eea, #764ba2) !important;
        color: white !important;
        font-weight: bold !important;
        padding: 12px !important;
    }
    
    .dataframe tr:hover {
        background: rgba(102,126,234,0.1) !important;
    }
</style>
"""

st.set_page_config(
    page_title="PreView Ads ERP - نظام إدارة الإعلانات",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(ADVANCED_CSS, unsafe_allow_html=True)

# ============================================================
# دوال مساعدة
# ============================================================

def create_metric_card_3d(title, value, icon, color_gradient="primary"):
    gradients = {
        "primary": "linear-gradient(135deg, #667eea, #764ba2)",
        "success": "linear-gradient(135deg, #11998e, #38ef7d)",
        "danger": "linear-gradient(135deg, #f093fb, #f5576c)",
        "warning": "linear-gradient(135deg, #fa709a, #fee140)"
    }
    
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            formatted_value = f"{value:,}"
        else:
            formatted_value = str(value)
    except:
        formatted_value = str(value)
    
    return f"""
    <div class="stat-card-3d" style="background: {gradients.get(color_gradient, gradients['primary'])}">
        <div style="font-size: 36px; opacity: 0.8;">{icon}</div>
        <div class="stat-number-3d">{formatted_value}</div>
        <div style="font-size: 14px; opacity: 0.9;">{title}</div>
    </div>
    """

def badge_animated(text, badge_type="info"):
    return f'<span class="badge-animated">{text}</span>'

def safe_split(value):
    if value is None or pd.isna(value):
        return []
    if isinstance(value, float):
        return []
    value_str = str(value)
    if value_str in ['', 'nan', 'None', 'NaN']:
        return []
    return [v.strip() for v in value_str.split(',') if v.strip()]

def is_admin():
    return st.session_state.get('role') == 'admin'

def _force_rtl_style(p):
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    pPr = p._element.get_or_add_pPr()
    bidi = OxmlElement('w:bidi')
    bidi.set(qn('w:val'), '1')
    pPr.append(bidi)
    for run in p.runs:
        rPr = run._element.get_or_add_rPr()
        rtl = OxmlElement('w:rtl')
        rtl.set(qn('w:val'), '1')
        rPr.append(rtl)

def set_table_rtl(table):
    tblPr = table._element.xpath('w:tblPr')[0]
    bidi = OxmlElement('w:bidiVisual')
    tblPr.append(bidi)

SYRIA_COORDS = {
    "دمشق": [33.5138, 36.2765],
    "ريف دمشق": [33.45, 36.35],
    "حلب": [36.2028, 37.1343],
    "حمص": [34.7328, 36.7156],
    "حماة": [35.135, 36.748],
    "اللاذقية": [35.531, 35.79],
    "طرطوس": [34.883, 35.883],
    "سوريا": [34.802, 38.996]
}

# تهيئة حالة الجلسة
if "auth" not in st.session_state:
    st.session_state.auth = False
if "cart" not in st.session_state:
    st.session_state.cart = {}
if "temp_cust" not in st.session_state:
    st.session_state.temp_cust = ""

# ============================================================
# صفحة تسجيل الدخول
# ============================================================

if not st.session_state.auth:
    st.markdown("""
    <div style="display: flex; justify-content: center; align-items: center; min-height: 80vh;">
        <div style="background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 30px; padding: 40px; width: 100%; max-width: 450px; text-align: center; box-shadow: 0 20px 40px rgba(0,0,0,0.2);">
            <div style="width: 80px; height: 80px; background: linear-gradient(135deg, #667eea, #764ba2); border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 20px;">
                <span style="font-size: 40px;">🎯</span>
            </div>
            <h1 style="color: white;">PreView Ads</h1>
            <p style="color: rgba(255,255,255,0.7);">نظام إدارة الإعلانات</p>
    """, unsafe_allow_html=True)
    
    with st.form("login_form"):
        username = st.text_input("👤 اسم المستخدم", placeholder="أدخل اسم المستخدم")
        password = st.text_input("🔑 كلمة المرور", type="password", placeholder="أدخل كلمة المرور")
        submitted = st.form_submit_button("🚪 دخول", use_container_width=True)
        
        if submitted:
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT username, password, role FROM users WHERE username = %s AND password = %s", (username, password))
                user = cursor.fetchone()
                cursor.close()
                conn.close()
                
                if user:
                    st.session_state.auth = True
                    st.session_state.role = user[2]
                    st.session_state.username = user[0]
                    st.rerun()
                else:
                    st.error("❌ اسم المستخدم أو كلمة المرور غير صحيحة")
            except Exception as e:
                st.error(f"❌ خطأ في الاتصال: {str(e)}")
    
    st.markdown("</div></div>", unsafe_allow_html=True)
    st.stop()

# ============================================================
# الشريط الجانبي
# ============================================================

with st.sidebar:
    st.markdown("""
    <div style="text-align: center; padding: 20px 0;">
        <div style="width: 80px; height: 80px; background: linear-gradient(135deg, #667eea, #764ba2); border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto;">
            <span style="font-size: 40px;">🎯</span>
        </div>
        <h2 style="color: white; margin-top: 15px;">PreView Ads</h2>
        <p style="color: #a0a0a0; font-size: 12px;">نظام إدارة الإعلانات v2.0</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    user_icon = "👑" if is_admin() else "👤"
    st.markdown(f"""
    <div style="background: rgba(255,255,255,0.1); border-radius: 15px; padding: 15px; text-align: center; margin: 10px 0;">
        <div style="font-size: 30px;">{user_icon}</div>
        <div style="font-weight: bold;">{st.session_state.get('username', '')}</div>
        <div style="font-size: 12px; opacity: 0.7;">{'مدير النظام' if is_admin() else 'موظف'}</div>
    </div>
    """, unsafe_allow_html=True)
    
    page = st.radio("📋 القائمة الرئيسية", [
        "🏢 لوحات الشركات",
        "📍 الأعمدة المتاحة",
        "📊 Dashboard",
        "📄 عرض سعر",
        "📋 تقرير الجرد",
        "📅 تقرير التوفر الشهري",
        "🗺️ تقرير جميع المواقع",
        "📐 تقرير تجميعي حسب الحجوم",
        "⚙️ الإعدادات"
    ], key="main_menu")
    
    st.divider()
    
    if st.button("🚪 تسجيل الخروج", use_container_width=True):
        st.session_state.auth = False
        st.session_state.cart = {}
        st.rerun()

# ============================================================
# الاتصال بقاعدة البيانات
# ============================================================

conn = get_connection()

# ============================================================
# دوال استعلامات Supabase (بصيغة PostgreSQL)
# ============================================================

def run_query(query, params=None, fetch=True):
    """تنفيذ استعلام على Supabase"""
    cursor = conn.cursor()
    try:
        cursor.execute(query, params or ())
        if fetch:
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            return pd.DataFrame(rows, columns=columns)
        else:
            conn.commit()
            return cursor.rowcount
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()

def get_fees(draw_df, size, print_type, is_foreign):
    subset = draw_df[draw_df['الحجم'] == size].copy()
    
    if print_type == "عادي":
        f_pr = subset[subset['اسم الرسم'].str.contains("اجور الطباعة عادي", na=False)]
        if f_pr.empty:
            f_pr = subset[subset['اسم الرسم'].str.contains("اجور الطباعة", na=False)]
    else:
        f_pr = subset[subset['اسم الرسم'].str.contains("اجور الطباعة", na=False)]
        f_pr = f_pr[~f_pr['اسم الرسم'].str.contains("عادي", na=False)]
    
    fee_print = float(f_pr['اجرة الرسم'].iloc[0]) if not f_pr.empty else 0.0
    
    if is_foreign:
        f_ad = subset[subset['اسم الرسم'].str.contains("اجور العرض اجنبي", na=False)]
        if f_ad.empty:
            f_ad = subset[subset['اسم الرسم'].str.contains("اجور العرض", na=False)]
    else:
        f_ad = subset[subset['اسم الرسم'].str.contains("اجور العرض", na=False)]
        f_ad = f_ad[~f_ad['اسم الرسم'].str.contains("اجنبي", na=False)]
    
    fee_ads = float(f_ad['اجرة الرسم'].iloc[0]) if not f_ad.empty else 0.0
    
    return fee_print, fee_ads

# ============================================================
# عرض الصفحات
# ============================================================

if page == "🏢 لوحات الشركات":
    st.title("🏢 لوحات الشركات المعلنة")
    
    query = '''
        SELECT 
            "اسم الزبون" as company_name,
            COUNT(DISTINCT "رقم اللوحة") as total_boards,
            COUNT(DISTINCT "فترة الحجز") as total_periods,
            MAX("العام") as last_year,
            MAX("فترة الحجز") as last_period
        FROM "حجوزات1"
        GROUP BY "اسم الزبون"
        ORDER BY "اسم الزبون"
    '''
    
    companies = run_query(query)
    
    if companies.empty:
        st.warning("⚠️ لا توجد شركات معلنة حالياً")
    else:
        for idx, company in companies.iterrows():
            with st.container():
                st.markdown(f"""
                <div class="neumorphic-card" style="margin-bottom: 20px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                        <div><h2 style="margin: 0 0 10px 0;">🏢 {company['company_name']}</h2></div>
                        <div>
                            {badge_animated(f"📊 {company['total_boards']} لوحة", "info")}
                            {badge_animated(f"🗓️ {company['total_periods']} فترة", "success")}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2 = st.columns([3, 1])
                with col2:
                    if st.button("🗺️ عرض الخريطة", key=f"map_{idx}", use_container_width=True):
                        st.session_state['selected_company'] = company['company_name']
                        st.session_state['show_company_map'] = True
                
                st.markdown("<hr>", unsafe_allow_html=True)

elif page == "📊 Dashboard":
    st.markdown("""
    <div style="text-align: center; margin-bottom: 30px;">
        <h1>📊 لوحة التحكم المتقدمة</h1>
        <p style="color: rgba(255,255,255,0.7);">نظرة شاملة على أداء النظام وإحصائيات الإعلانات</p>
    </div>
    """, unsafe_allow_html=True)
    
    current_year = datetime.now().year
    
    all_columns = run_query('SELECT "رقم اللوحة", "المحافظة", "الشبكة", "الحجم", "العدد" FROM "اعمدة انارة"')
    
    booked_query = f'SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" WHERE "العام" = {current_year}'
    booked_df = run_query(booked_query)
    
    booked_boards_list = booked_df['رقم اللوحة'].tolist() if not booked_df.empty else []
    
    all_columns['الحالة'] = all_columns['رقم اللوحة'].apply(lambda x: 'محجوز' if x in booked_boards_list else 'متاح')
    
    total_boards = all_columns['العدد'].sum()
    booked_boards = all_columns[all_columns['الحالة'] == 'محجوز']['العدد'].sum()
    available_boards = total_boards - booked_boards
    occupancy_rate = (booked_boards / total_boards * 100) if total_boards > 0 else 0
    
    cols = st.columns(4)
    metrics_data = [
        ("إجمالي اللوحات", total_boards, "🏢", "primary"),
        ("محجوز", booked_boards, "🔴", "danger"),
        ("متاح", available_boards, "🟢", "success"),
        ("نسبة الإشغال", f"{occupancy_rate:.1f}%", "📈", "warning")
    ]
    
    for idx, (title, value, icon, color) in enumerate(metrics_data):
        with cols[idx]:
            st.markdown(create_metric_card_3d(title, value, icon, color), unsafe_allow_html=True)
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        fig_pie = go.Figure(data=[go.Pie(
            labels=['محجوز', 'متاح'],
            values=[booked_boards, available_boards],
            hole=0.4,
            marker_colors=['#dc2626', '#22c55e'],
            textinfo='percent+label'
        )])
        fig_pie.update_layout(height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col_chart2:
        city_stats = []
        for city in all_columns['المحافظة'].unique():
            city_data = all_columns[all_columns['المحافظة'] == city]
            city_total = city_data['العدد'].sum()
            city_booked = city_data[city_data['الحالة'] == 'محجوز']['العدد'].sum()
            city_stats.append({
                'المحافظة': city,
                'نسبة الإشغال': (city_booked / city_total * 100) if city_total > 0 else 0
            })
        
        city_df = pd.DataFrame(city_stats)
        fig_bar = px.bar(city_df, x='المحافظة', y='نسبة الإشغال', 
                         color='نسبة الإشغال', color_continuous_scale='RdYlGn')
        fig_bar.update_layout(height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_bar, use_container_width=True)
    
    st.divider()
    
    st.subheader("🗺️ توزع اللوحات على الخريطة")
    all_columns_map = run_query('SELECT * FROM "اعمدة انارة"')
    
    m = folium.Map(location=SYRIA_COORDS["سوريا"], zoom_start=7)
    marker_cluster = MarkerCluster().add_to(m)
    
    for _, row in all_columns_map.iterrows():
        if pd.notnull(row.get('latitude')) and pd.notnull(row.get('longitude')) and row.get('latitude') != 0:
            popup_html = f"""
            <div dir="rtl" style="font-family:Arial;text-align:right;min-width:250px;">
                <b>🏢 {row['اسم العمود']}</b><br>
                📍 {row['المحافظة']}<br>
                📡 {row['الشبكة']}<br>
                📏 {row['الحجم']}<br>
                🔢 {row['العدد']} لوحة
            </div>
            """
            
            folium.Marker(
                [row['latitude'], row['longitude']],
                popup=folium.Popup(popup_html, max_width=350),
                icon=folium.Icon(color='green')
            ).add_to(marker_cluster)
    
    st_folium(m, width="100%", height=500)

elif page == "📍 الأعمدة المتاحة":
    st.title("📍 الأعمدة المتاحة للإيجار")
    st.info("📌 اختر محافظة لعرض الأعمدة المتاحة فيها")
    
    current_year = datetime.now().year
    
    booked_query = f'SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" WHERE "العام" = {current_year}'
    booked_df = run_query(booked_query)
    booked_boards = booked_df['رقم اللوحة'].tolist() if not booked_df.empty else []
    
    all_columns = run_query('SELECT * FROM "اعمدة انارة"')
    available = all_columns[~all_columns['رقم اللوحة'].isin(booked_boards)]
    
    if available.empty:
        st.warning("⚠️ لا توجد أعمدة متاحة حالياً")
    else:
        cities = available['المحافظة'].unique()
        
        cols_per_row = 3
        for i in range(0, len(cities), cols_per_row):
            cols = st.columns(cols_per_row)
            for j, col in enumerate(cols):
                if i + j < len(cities):
                    city = cities[i + j]
                    city_data = available[available['المحافظة'] == city]
                    total_boards = city_data['العدد'].sum()
                    
                    with col:
                        st.markdown(f"""
                        <div class="neumorphic-card" style="text-align: center;">
                            <div style="font-size: 48px;">🏙️</div>
                            <h3>{city}</h3>
                            {badge_animated(f"{int(total_boards)} عمود", "info")}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if st.button(f"📋 استكشاف {city}", key=f"city_{city}", use_container_width=True):
                            st.dataframe(city_data[['رقم اللوحة', 'اسم العمود', 'الشبكة', 'الحجم', 'العدد']], use_container_width=True)

elif page == "📄 عرض سعر":
    st.title("📄 بناء عرض سعر جديد")
    
    try:
        draw_df = run_query('SELECT * FROM "اسماء الرسم"')
        
        customer_name = st.text_input("🏢 اسم الزبون", value=st.session_state.get('temp_cust', ""))
        st.session_state.temp_cust = customer_name
        
        col1, col2, col3 = st.columns(3)
        with col1:
            selected_size = st.selectbox("📏 قياس اللوحة:", draw_df['الحجم'].unique().tolist())
        with col2:
            print_type = st.radio("🖨️ نوع الطباعة:", ["عادي", "سكوتش"], horizontal=True)
        with col3:
            year = st.number_input("📅 العام:", min_value=2024, max_value=2030, value=2026)
        
        is_foreign = st.checkbox("🌍 منتج أجنبي")
        
        periods_df = run_query('SELECT namee, no FROM "الفترة" ORDER BY no')
        period_names = periods_df['namee'].tolist()
        
        if not period_names:
            st.error("❌ لا توجد فترات في جدول الفترة")
            st.stop()
        
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            start_p = st.selectbox("📅 من فترة:", period_names)
        with col_p2:
            end_p = st.selectbox("📅 إلى فترة:", period_names, index=len(period_names)-1)
        
        start_idx = period_names.index(start_p)
        end_idx = period_names.index(end_p)
        periods_count = abs(end_idx - start_idx) + 1
        months_count = periods_count / 2
        selected_periods = period_names[start_idx:end_idx+1]
        
        st.info(f"📅 عدد الفترات: {periods_count} | عدد الأشهر: {months_count:.1f}")
        
        fee_print, fee_ads = get_fees(draw_df, selected_size, print_type, is_foreign)
        
        per_column_print = fee_print
        per_column_display = fee_ads * months_count
        per_column_total = per_column_print + per_column_display
        
        st.success(f"""
        💰 **تفاصيل الأسعار:**
        - أجر الطباعة: **{fee_print}$**
        - أجر العرض الشهري: **{fee_ads}$**
        - الإجمالي لكل عمود: **{per_column_total:.2f}$**
        """)
        
        st.divider()
        st.subheader("📍 اختيار المواقع")
        
        cities = run_query('SELECT DISTINCT "المحافظة" FROM "اعمدة انارة"')['المحافظة'].tolist()
        selected_city = st.selectbox("اختر المحافظة:", cities)
        
        available_columns = run_query(f'''
            SELECT "رقم اللوحة", "اسم العمود" as "الموقع", "العدد", "الشبكة", "الحجم" 
            FROM "اعمدة انارة" 
            WHERE "المحافظة" = '{selected_city}' AND "الحجم" = '{selected_size}'
        ''')
        
        period_placeholders = ', '.join([f"'{p}'" for p in selected_periods])
        booked_query = f'''
            SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" 
            WHERE "العام" = {year} 
            AND "فترة الحجز" IN ({period_placeholders})
        '''
        booked_df = run_query(booked_query)
        booked_boards = booked_df['رقم اللوحة'].tolist() if not booked_df.empty else []
        
        available_columns = available_columns[~available_columns['رقم اللوحة'].isin(booked_boards)]
        
        if not available_columns.empty:
            networks = st.multiselect("اختر الشبكات:", available_columns['الشبكة'].unique().tolist())
            if st.button("➕ إضافة إلى السلة", type="primary", use_container_width=True):
                if selected_city not in st.session_state.cart:
                    st.session_state.cart[selected_city] = {}
                for net in networks:
                    net_data = available_columns[available_columns['الشبكة'] == net].copy()
                    net_data['fee_print'] = per_column_print
                    net_data['fee_display'] = per_column_display
                    st.session_state.cart[selected_city][net] = net_data
                st.success(f"✅ تمت الإضافة")
                st.rerun()
        else:
            st.warning("⚠️ لا توجد مواقع متاحة")
        
        if st.session_state.cart:
            st.divider()
            st.subheader("🛒 سلة العروض")
            
            grand_total_print = 0.0
            grand_total_display = 0.0
            
            for city, networks in list(st.session_state.cart.items()):
                for net, df_cart in list(networks.items()):
                    with st.expander(f"📍 {city} - {net}", expanded=True):
                        edited_df = st.data_editor(df_cart, key=f"edit_{city}_{net}", num_rows="dynamic", use_container_width=True)
                        st.session_state.cart[city][net] = edited_df
                        
                        qty = int(edited_df['العدد'].sum())
                        fp = float(edited_df['fee_print'].iloc[0])
                        fd = float(edited_df['fee_display'].iloc[0])
                        
                        section_print = qty * fp
                        section_display = qty * fd
                        
                        grand_total_print += section_print
                        grand_total_display += section_display
                        
                        st.info(f"📊 العدد: {qty} | الطباعة: {section_print:.2f}$ | العرض: {section_display:.2f}$")
            
            grand_total = grand_total_print + grand_total_display
            st.success(f"## 💰 الإجمالي النهائي: {grand_total:,.2f} $")
            
            col_btn1, col_btn2 = st.columns(2)
            
            with col_btn1:
                if st.button("💾 حفظ كمسودة", use_container_width=True):
                    if not customer_name:
                        st.error("❌ الرجاء إدخال اسم الزبون")
                    else:
                        save_data = {"data": {c: {n: df.to_dict() for n, df in ns.items()} for c, ns in st.session_state.cart.items()}}
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO "offers_history" (client_name, cart_json, status, start_p, end_p, year, offer_date) 
                            VALUES (%s, %s, %s, %s, %s, %s, NOW())
                        ''', (customer_name, json.dumps(save_data, ensure_ascii=False), 'Pending', start_p, end_p, year))
                        conn.commit()
                        cursor.close()
                        st.success("✅ تم الحفظ كمسودة")
            
            with col_btn2:
                if st.button("🔴 تفريغ السلة", use_container_width=True):
                    st.session_state.cart = {}
                    st.rerun()
    
    except Exception as e:
        st.error(f"❌ حدث خطأ: {str(e)}")

elif page == "📋 تقرير الجرد":
    st.title("📋 التقرير التجميعي - جرد اللوحات")
    
    try:
        periods_df = run_query('SELECT "no", "namee" FROM "الفترة" ORDER BY "no"')
        period_names = periods_df['namee'].tolist()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            from_period = st.selectbox("من فترة:", period_names)
        with col2:
            to_period = st.selectbox("إلى فترة:", period_names, index=len(period_names)-1)
        with col3:
            report_year = st.number_input("العام:", value=datetime.now().year)
        
        from_idx = int(periods_df[periods_df['namee'] == from_period]['no'].iloc[0])
        to_idx = int(periods_df[periods_df['namee'] == to_period]['no'].iloc[0])
        target_periods = periods_df[(periods_df['no'] >= from_idx) & (periods_df['no'] <= to_idx)]['namee'].tolist()
        
        all_boards = run_query('SELECT "رقم اللوحة", "المحافظة", "الحجم", "العدد" FROM "اعمدة انارة"')
        
        period_placeholders = ', '.join([f"'{p}'" for p in target_periods])
        booked_query = f'''
            SELECT DISTINCT "رقم اللوحة" 
            FROM "حجوزات1" 
            WHERE "العام" = {report_year} 
            AND "فترة الحجز" IN ({period_placeholders})
        '''
        booked_in_period = run_query(booked_query)['رقم اللوحة'].tolist()
        
        all_boards['الحالة'] = all_boards['رقم اللوحة'].apply(lambda x: 'محجوز' if x in booked_in_period else 'متاح')
        
        total_sites = len(all_boards)
        booked_sites = len(booked_in_period)
        
        cols = st.columns(3)
        metrics_data = [
            ("🏢 إجمالي المواقع", total_sites, "🗺️", "primary"),
            ("🔴 المواقع المحجوزة", booked_sites, "📌", "danger"),
            ("📈 نسبة الإشغال", f"{(booked_sites/total_sites*100):.1f}%", "📊", "warning")
        ]
        
        for idx, (title, value, icon, color) in enumerate(metrics_data):
            with cols[idx]:
                st.markdown(create_metric_card_3d(title, value, icon, color), unsafe_allow_html=True)
        
        st.divider()
        
        city_details = []
        for city in all_boards['المحافظة'].unique():
            city_df = all_boards[all_boards['المحافظة'] == city]
            city_total = city_df['العدد'].sum()
            city_booked = city_df[city_df['الحالة'] == 'محجوز']['العدد'].sum()
            city_details.append({
                'المحافظة': city,
                'الإجمالي': int(city_total),
                'محجوز': int(city_booked),
                'متاح': int(city_total - city_booked),
            })
        
        st.dataframe(pd.DataFrame(city_details), use_container_width=True)
        
        csv_data = all_boards.to_csv(index=False, encoding='utf-8-sig')
        st.download_button("📊 تصدير إلى CSV", csv_data, f"Inventory_Report_{report_year}.csv", "text/csv", use_container_width=True)
        
    except Exception as e:
        st.error(f"حدث خطأ في التقرير: {str(e)}")

elif page == "📅 تقرير التوفر الشهري":
    st.title("📋 تقرير الأعمدة المتاحة")
    
    current_year = date.today().year
    
    if st.button("🚀 تشغيل التقرير", use_container_width=True, type="primary"):
        with st.spinner("جاري إنشاء التقرير..."):
            all_columns = run_query('SELECT "رقم اللوحة", "اسم العمود", "المحافظة", "الشبكة", "الحجم", "العدد" FROM "اعمدة انارة"')
            
            bookings_query = f'SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" WHERE "العام" = {current_year}'
            booked_df = run_query(bookings_query)
            booked_boards = booked_df['رقم اللوحة'].tolist() if not booked_df.empty else []
            
            available_df = all_columns[~all_columns['رقم اللوحة'].isin(booked_boards)]
            total_available = len(available_df)
            
            st.success(f"✅ {total_available} موقعاً متاحة")
            
            st.subheader("📊 ملخص حسب المحافظة")
            summary = available_df.groupby('المحافظة').agg({
                'رقم اللوحة': 'count',
                'العدد': 'sum'
            }).rename(columns={'رقم اللوحة': 'عدد المواقع', 'العدد': 'عدد اللوحات'})
            st.dataframe(summary, use_container_width=True)
            
            st.subheader("📋 قائمة الأعمدة المتاحة")
            st.dataframe(available_df[['رقم اللوحة', 'اسم العمود', 'المحافظة', 'الشبكة', 'الحجم', 'العدد']], use_container_width=True)
            
            csv_data = available_df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button("📥 تحميل التقرير (CSV)", csv_data, f"available_columns_{date.today().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)

elif page == "🗺️ تقرير جميع المواقع":
    st.title("🗺️ تقرير جميع المواقع والأعمدة")
    
    all_columns = run_query('SELECT "رقم اللوحة", "اسم العمود", "المحافظة", "الشبكة", "الحجم", "العدد" FROM "اعمدة انارة" ORDER BY "المحافظة", "الشبكة"')
    
    if all_columns.empty:
        st.warning("⚠️ لا توجد بيانات في جدول الأعمدة")
        st.stop()
    
    total_sites = len(all_columns)
    total_boards = all_columns['العدد'].sum()
    
    cols = st.columns(3)
    with cols[0]:
        st.markdown(create_metric_card_3d("إجمالي المواقع", total_sites, "🗺️", "primary"), unsafe_allow_html=True)
    with cols[1]:
        st.markdown(create_metric_card_3d("إجمالي الأعمدة", int(total_boards), "📌", "success"), unsafe_allow_html=True)
    with cols[2]:
        st.markdown(create_metric_card_3d("عدد المحافظات", all_columns['المحافظة'].nunique(), "🏙️", "warning"), unsafe_allow_html=True)
    
    st.divider()
    
    st.subheader("📊 ملخص حسب المحافظة")
    summary = all_columns.groupby('المحافظة').agg({
        'رقم اللوحة': 'count',
        'العدد': 'sum'
    }).rename(columns={'رقم اللوحة': 'عدد المواقع', 'العدد': 'عدد الأعمدة'})
    st.dataframe(summary, use_container_width=True)
    
    csv_data = all_columns.to_csv(index=False, encoding='utf-8-sig')
    st.download_button("📊 تصدير التقرير كاملاً (CSV)", csv_data, f"full_report_{date.today().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)

elif page == "📐 تقرير تجميعي حسب الحجوم":
    st.title("📐 تقرير تجميعي حسب الحجوم")
    
    all_columns = run_query('SELECT "رقم اللوحة", "اسم العمود", "المحافظة", "الشبكة", "الحجم", "العدد" FROM "اعمدة انارة"')
    
    def classify_size(size):
        size_str = str(size).strip()
        if size_str in ['3*6', '3x6', '3 × 6']:
            return 'المجموعة الأولى: حجم 3×6'
        elif size_str in ['2*1', '2x1', '2 × 1', '125*185', '125x185', '125 × 185']:
            return 'المجموعة الثانية: حجمي 2×1 و 125×185'
        else:
            return 'المجموعة الثالثة: باقي الحجوم'
    
    all_columns['المجموعة'] = all_columns['الحجم'].apply(classify_size)
    
    st.subheader("📊 ملخص المجموعات")
    group_summary = all_columns.groupby('المجموعة').agg({
        'رقم اللوحة': 'count',
        'العدد': 'sum'
    }).rename(columns={'رقم اللوحة': 'عدد المواقع', 'العدد': 'عدد الأعمدة'})
    st.dataframe(group_summary, use_container_width=True)
    
    csv_data = all_columns.to_csv(index=False, encoding='utf-8-sig')
    st.download_button("📊 تصدير التقرير (CSV)", csv_data, f"sizes_report_{date.today().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)

elif page == "⚙️ الإعدادات":
    if not is_admin():
        st.error("⛔ هذه الصفحة مخصصة للمديرين فقط")
        st.stop()
    
    st.title("⚙️ إعدادات النظام")
    st.info("يمكن للمدير فقط تعديل البيانات هنا")

# ============================================================
# إغلاق الاتصال
# ============================================================

conn.close()
