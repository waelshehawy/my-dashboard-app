import os
import sys
# app_hybrid.py - يجمع بين SQLite المحلي و Supabase السحابي
import streamlit as st
import pandas as pd
import sqlite3
import os
import io
import folium
import json
import time
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from datetime import datetime, timedelta, date
import plotly.graph_objects as go
import plotly.express as px
import base64

# ============================================================
# إعدادات Supabase (للنسخ الاحتياطي والتقارير - اختياري)
# ============================================================
try:
    from supabase import create_client, Client
    SUPABASE_URL = "https://your-project.supabase.co"  # غيّرها
    SUPABASE_KEY = "your-anon-key"  # غيّرها
    supabase_available = True
except ImportError:
    supabase_available = False
    st.warning("⚠️ مكتبة supabase غير مثبتة - لن تعمل المزامنة السحابية")
    st.info("💡 للتثبيت: pip install supabase-python")

# ============================================================
# الاتصال بقاعدة البيانات المحلية (SQLite)
# ============================================================
DB_PATH = "ads_erp_local.db"

def get_connection():
    """اتصال بقاعدة البيانات المحلية"""
    return sqlite3.connect(DB_PATH)

def init_local_db():
    """إنشاء قاعدة البيانات المحلية بكل الجداول"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # جدول أعمدة الإنارة
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS "اعمدة انارة" (
            "رقم اللوحة" TEXT PRIMARY KEY,
            "اسم العمود" TEXT,
            "المحافظة" TEXT,
            "الشبكة" TEXT,
            "الحجم" TEXT,
            "العدد" INTEGER,
            "Latitude" REAL,
            "Longitude" REAL
        )
    ''')
    
    # جدول الحجوزات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS "حجوزات1" (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            "رقم اللوحة" TEXT,
            "اسم الزبون" TEXT,
            "العام" INTEGER,
            "فترة الحجز" TEXT,
            "تاريخ النهاية" DATE
        )
    ''')
    
    # جدول أجور الرسم
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS "اسماء الرسم" (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            "اسم الرسم" TEXT,
            "الحجم" TEXT,
            "اجرة الرسم" REAL
        )
    ''')
    
    # جدول الفترات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS "الفترة" (
            no INTEGER PRIMARY KEY,
            namee TEXT
        )
    ''')
    
    # جدول عروض الأسعار
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS "offers_history" (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT,
            cart_json TEXT,
            status TEXT,
            start_p TEXT,
            end_p TEXT,
            year INTEGER,
            offer_date TIMESTAMP
        )
    ''')
    
    # جدول المستخدمين
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS "users" (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT,
            full_name TEXT,
            created_at TIMESTAMP
        )
    ''')
    
    # إضافة المستخدم الافتراضي
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO users (username, password, role, full_name, created_at) 
            VALUES 
            ('admin', 'admin123', 'admin', 'مدير النظام', datetime('now')),
            ('employee', 'emp123', 'employee', 'موظف', datetime('now'))
        ''')
    
    # إضافة الفترات إذا كانت فارغة
    cursor.execute("SELECT COUNT(*) FROM 'الفترة'")
    if cursor.fetchone()[0] == 0:
        periods = [
            (1, '1-15 كانون الثاني'), (2, '16-31 كانون الثاني'),
            (3, '1-15 شباط'), (4, '16-28 شباط'),
            (5, '1-15 آذار'), (6, '16-31 آذار'),
            (7, '1-15 نيسان'), (8, '16-30 نيسان'),
            (9, '1-15 أيار'), (10, '16-31 أيار'),
            (11, '1-15 حزيران'), (12, '16-30 حزيران'),
            (13, '1-15 تموز'), (14, '16-31 تموز'),
            (15, '1-15 آب'), (16, '16-31 آب'),
            (17, '1-15 أيلول'), (18, '16-30 أيلول'),
            (19, '1-15 تشرين الأول'), (20, '16-31 تشرين الأول'),
            (21, '1-15 تشرين الثاني'), (22, '16-30 تشرين الثاني'),
            (23, '1-15 كانون الأول'), (24, '16-31 كانون الأول')
        ]
        cursor.executemany("INSERT INTO 'الفترة' (no, namee) VALUES (?, ?)", periods)
    
    conn.commit()
    conn.close()
    return True

# تهيئة قاعدة البيانات
if 'db_initialized' not in st.session_state:
    init_local_db()
    st.session_state.db_initialized = True

# ============================================================
# دوال المزامنة مع Supabase (اختيارية)
# ============================================================

def get_supabase():
    """الحصول على اتصال Supabase"""
    if not supabase_available:
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except:
        return None

def sync_local_to_supabase():
    """رفع البيانات من SQLite إلى Supabase (نسخ احتياطي)"""
    if not supabase_available:
        st.error("❌ مكتبة supabase غير مثبتة")
        return False
    
    supabase = get_supabase()
    if not supabase:
        st.error("❌ فشل الاتصال بـ Supabase")
        return False
    
    try:
        conn = get_connection()
        
        # مزامنة أعمدة الإنارة
        df_columns = pd.read_sql('SELECT * FROM "اعمدة انارة"', conn)
        for _, row in df_columns.iterrows():
            supabase.table("اعمدة_انارة").upsert(row.to_dict()).execute()
        st.success(f"✅ تم مزامنة {len(df_columns)} سجل من أعمدة الإنارة")
        
        # مزامنة الحجوزات
        df_bookings = pd.read_sql('SELECT * FROM "حجوزات1"', conn)
        for _, row in df_bookings.iterrows():
            supabase.table("حجوزات1").upsert(row.to_dict()).execute()
        st.success(f"✅ تم مزامنة {len(df_bookings)} سجل من الحجوزات")
        
        conn.close()
        return True
        
    except Exception as e:
        st.error(f"❌ خطأ في المزامنة: {e}")
        return False

# ============================================================
# دوال RTL للـ Word (من الكود القديم)
# ============================================================

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
        rFonts = OxmlElement('w:rFonts')
        rFonts.set(qn('w:cs'), 'Arial')
        rPr.append(rFonts)

def set_table_rtl(table):
    tblPr = table._element.xpath('w:tblPr')[0]
    bidi = OxmlElement('w:bidiVisual')
    tblPr.append(bidi)

# ============================================================
# دوال الصلاحيات
# ============================================================

def is_admin():
    return st.session_state.get('role') == 'admin'

def is_employee():
    return st.session_state.get('role') == 'employee'

# ============================================================
# دوال الأسعار والحسابات
# ============================================================

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
# دوال التصدير (من الكود القديم)
# ============================================================

def export_word_old(customer_name, cart_data, start_p, end_p, grand_total):
    doc = Document('template.docx') if os.path.exists('template.docx') else Document()
    PURPLE_COLOR = "660099"
    doc.add_paragraph()
    today_date = datetime.now().strftime("%d / %m / %Y")
    p_date = doc.add_paragraph()
    p_date.add_run(f"التاريخ: {today_date}")
    _force_rtl_style(p_date)
    doc.add_paragraph()
    
    p_cust = doc.add_paragraph()
    p_cust.add_run(f"السادة شركة {customer_name} المحترمين").bold = True
    _force_rtl_style(p_cust)
    
    p_stat = doc.add_paragraph()
    p_stat.add_run(f"نقدم لكم المواقع المتاحة لعرض إعلانكم الوطني من فترة ({start_p}) ولغاية ({end_p})")
    _force_rtl_style(p_stat)
    
    for city, networks in cart_data.items():
        p_city = doc.add_paragraph()
        p_city.add_run(f"■ محافظة {city}").bold = True
        _force_rtl_style(p_city)
        
        for net, df in networks.items():
            if df.empty:
                continue
            for size_info, group_df in df.groupby(['الحجم']):
                p_size = doc.add_paragraph()
                p_size.add_run(f"الشبكة: {net} | القياس: {size_info}").bold = True
                _force_rtl_style(p_size)
                
                table = doc.add_table(rows=1, cols=2)
                table.style = 'Table Grid'
                set_table_rtl(table)
                
                hdr = table.rows[0].cells
                hdr[0].text = "اسم الموقع (العمود)"
                hdr[1].text = "العدد"
                for cell in hdr:
                    for p in cell.paragraphs:
                        _force_rtl_style(p)
                    tc_pr = cell._element.get_or_add_tcPr()
                    shd = OxmlElement('w:shd')
                    shd.set(qn('w:fill'), PURPLE_COLOR)
                    tc_pr.append(shd)
                    cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
                
                for _, row in group_df.iterrows():
                    row_cells = table.add_row().cells
                    row_cells[0].text = str(row['الموقع'])
                    row_cells[1].text = str(row['العدد'])
                    for cell in row_cells:
                        for p in cell.paragraphs:
                            _force_rtl_style(p)
                
                total_q = pd.to_numeric(group_df['العدد']).sum()
                f_p = float(group_df['fee_print'].iloc[0])
                f_a = float(group_df['fee_ads'].iloc[0])
                sum_print = total_q * f_p
                sum_ads = total_q * f_a
                sum_combined = sum_print + sum_ads
                
                p_fin = doc.add_paragraph()
                txt = (f"إجمالي العدد: {int(total_q)} | "
                       f"أجور الطباعة: {sum_print:,.0f}$ | "
                       f"أجور العرض: {sum_ads:,.0f}$ | "
                       f"المجموع للشبكة: {sum_combined:,.0f}$")
                p_fin.add_run(txt).bold = True
                _force_rtl_style(p_fin)
    
    doc.add_paragraph()
    p_grand = doc.add_paragraph()
    run_g = p_grand.add_run(f"إجمالي القيمة المالية للعرض بالكامل: {grand_total:,.0f} $")
    run_g.bold = True
    run_g.font.size = Pt(14)
    run_g.font.color.rgb = RGBColor(102, 0, 153)
    _force_rtl_style(p_grand)
    
    doc.add_paragraph()
    p_note = doc.add_paragraph()
    run_note = p_note.add_run("• ملاحظة: هذه المواقع متاحة لمدة 48 ساعة.")
    run_note.bold = True
    _force_rtl_style(p_note)
    
    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# ============================================================
# دوال إدارة العروض المنتهية
# ============================================================

def manage_expired_offers(conn):
    st.subheader("⚠️ إدارة العروض التي تجاوزت 48 ساعة")
    
    query = '''
        SELECT id, client_name, offer_date 
        FROM "offers_history" 
        WHERE status = 'Pending' AND offer_date < datetime('now', '-48 hours')
    '''
    expired_df = pd.read_sql_query(query, conn)
    
    if expired_df.empty:
        st.success("✅ لا توجد عروض منتهية الصلاحية.")
        return
    
    for _, row in expired_df.iterrows():
        col1, col2, col3 = st.columns([3, 1, 1])
        col1.write(f"👤 الزبون: **{row['client_name']}** - تاريخ العرض: {row['offer_date']}")
        
        if is_admin():
            if col2.button("✅ تمديد 48 ساعة", key=f"ext_{row['id']}"):
                cur = conn.cursor()
                cur.execute('UPDATE "offers_history" SET offer_date = datetime("now") WHERE id = ?', (row['id'],))
                conn.commit()
                st.success("تم التمديد بنجاح")
                st.rerun()
            
            if col3.button("❌ إلغاء العرض", key=f"del_{row['id']}"):
                cur = conn.cursor()
                cur.execute('UPDATE "offers_history" SET status = "Cancelled" WHERE id = ?', (row['id'],))
                conn.commit()
                st.success("تم إلغاء العرض")
                st.rerun()
        else:
            col2.write("🔒")
            col3.write("🔒")

# ============================================================
# دوال مساعدة
# ============================================================

def safe_split(value):
    if value is None or pd.isna(value):
        return []
    if isinstance(value, float):
        return []
    value_str = str(value)
    if value_str in ['', 'nan', 'None', 'NaN']:
        return []
    return [v.strip() for v in value_str.split(',') if v.strip()]

def filter_valid_coordinates(df, lat_col='Latitude', lon_col='Longitude'):
    if df.empty:
        return df
    if lat_col not in df.columns or lon_col not in df.columns:
        return pd.DataFrame()
    valid = df[
        df[lat_col].notna() & 
        df[lon_col].notna() &
        (df[lat_col] != 0) &
        (df[lon_col] != 0)
    ].copy()
    return valid

# ============================================================
# إعدادات الصفحة
# ============================================================

st.set_page_config(
    page_title="PreView Ads ERP - نظام إدارة الإعلانات",
    page_icon="🎯",
    layout="wide"
)

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
    st.title("🔒 نظام إدارة الإعلانات - تسجيل الدخول")
    
    with st.form("login_form"):
        username = st.text_input("👤 اسم المستخدم")
        password = st.text_input("🔑 كلمة المرور", type="password")
        submitted = st.form_submit_button("🚪 دخول", use_container_width=True)
        
        if submitted:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT username, password, role FROM users WHERE username = ? AND password = ?", (username, password))
            user = cursor.fetchone()
            conn.close()
            
            if user:
                st.session_state.auth = True
                st.session_state.role = user[2]
                st.session_state.username = user[0]
                st.rerun()
            else:
                st.error("❌ اسم المستخدم أو كلمة المرور غير صحيحة")
    
    st.stop()

# ============================================================
# الاتصال بقاعدة البيانات بعد تسجيل الدخول
# ============================================================

conn = get_connection()

# ============================================================
# الشريط الجانبي
# ============================================================

with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/advertising.png", width=80)
    st.title(f"مرحباً {st.session_state.get('username', '')}")
    st.caption(f"الدور: {'مدير' if is_admin() else 'موظف'}")
    st.divider()
    
    page = st.radio("القائمة الرئيسية", [
        "📊 Dashboard",
        "📄 عرض سعر",
        "📋 تقرير الجرد",
        "📅 تقرير التوفر الشهري",
        "🗺️ تقرير جميع المواقع",
        "📐 تقرير تجميعي حسب الحجوم",
        "☁️ مزامنة سحابية",
        "⚙️ الإعدادات"
    ], key="main_menu")
    
    st.divider()
    
    # إحصائيات سريعة
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM 'اعمدة انارة'")
    total_boards = cursor.fetchone()[0]
    st.metric("🏢 إجمالي اللوحات", total_boards)
    
    st.divider()
    
    if st.button("🚪 تسجيل الخروج", use_container_width=True):
        st.session_state.auth = False
        st.session_state.cart = {}
        st.rerun()

# ============================================================
# باقي الصفحات (نفس الكود القديم مع تعديلات بسيطة)
# ============================================================

if page == "📊 Dashboard":
    st.title("📊 لوحة التحكم - نظام إدارة الإعلانات")
    
    current_year = datetime.now().year
    
    all_columns = pd.read_sql_query('SELECT "رقم اللوحة", "المحافظة", "الشبكة", "الحجم", "العدد" FROM "اعمدة انارة"', conn)
    
    booked_query = f'SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" WHERE "العام" = {current_year}'
    booked_df = pd.read_sql_query(booked_query, conn)
    booked_boards_list = booked_df['رقم اللوحة'].tolist() if not booked_df.empty else []
    
    all_columns['الحالة'] = all_columns['رقم اللوحة'].apply(lambda x: 'محجوز' if x in booked_boards_list else 'متاح')
    
    total_boards = all_columns['العدد'].sum()
    booked_boards = all_columns[all_columns['الحالة'] == 'محجوز']['العدد'].sum()
    available_boards = total_boards - booked_boards
    
    col1, col2, col3 = st.columns(3)
    col1.metric("🏢 إجمالي اللوحات", f"{int(total_boards):,}")
    col2.metric("🔴 محجوز", f"{int(booked_boards):,}")
    col3.metric("🟢 متاح", f"{int(available_boards):,}")
    
    st.progress(booked_boards / total_boards if total_boards > 0 else 0, 
                text=f"📈 نسبة الإشغال: {(booked_boards/total_boards*100):.1f}%" if total_boards > 0 else "0%")
    
    st.divider()
    
    st.subheader("🥧 نسبة الإشغال الكلية")
    fig_pie = go.Figure(data=[go.Pie(
        labels=['محجوز', 'متاح'],
        values=[booked_boards, available_boards],
        hole=0.4,
        marker_colors=['#dc2626', '#22c55e']
    )])
    fig_pie.update_layout(height=400)
    st.plotly_chart(fig_pie, use_container_width=True)
    
    st.subheader("🗺️ توزع اللوحات على الخريطة")
    
    all_columns_map = pd.read_sql_query('SELECT * FROM "اعمدة انارة"', conn)
    all_columns_map['الحالة'] = all_columns_map['رقم اللوحة'].apply(lambda x: 'محجوز' if x in booked_boards_list else 'متاح')
    
    m = folium.Map(location=SYRIA_COORDS["سوريا"], zoom_start=7)
    marker_cluster = MarkerCluster().add_to(m)
    
    valid_coords = all_columns_map[
        all_columns_map['Latitude'].notna() & 
        all_columns_map['Longitude'].notna() &
        (all_columns_map['Latitude'] != 0)
    ]
    
    for _, row in valid_coords.iterrows():
        color = 'red' if row['الحالة'] == 'محجوز' else 'green'
        popup_html = f"""
        <div dir="rtl" style="font-family: Arial; text-align: right;">
            <b>{row['اسم العمود']}</b><br>
            المحافظة: {row['المحافظة']}<br>
            الشبكة: {row['الشبكة']}<br>
            الحجم: {row['الحجم']}<br>
            الحالة: {row['الحالة']}
        </div>
        """
        folium.Marker(
            [row['Latitude'], row['Longitude']],
            popup=folium.Popup(popup_html, max_width=250),
            icon=folium.Icon(color=color, icon='info-sign')
        ).add_to(marker_cluster)
    
    st_folium(m, width="100%", height=500)
    
    st.divider()
    st.subheader("📊 إحصائيات حسب المحافظة")
    
    city_stats = []
    for city in all_columns['المحافظة'].unique():
        city_data = all_columns[all_columns['المحافظة'] == city]
        city_total = city_data['العدد'].sum()
        city_booked = city_data[city_data['الحالة'] == 'محجوز']['العدد'].sum()
        city_stats.append({
            'المحافظة': city,
            'الإجمالي': int(city_total),
            'محجوز': int(city_booked),
            'متاح': int(city_total - city_booked),
            'نسبة الإشغال': f"{(city_booked/city_total*100):.1f}%" if city_total > 0 else "0%"
        })
    
    st.dataframe(pd.DataFrame(city_stats), use_container_width=True)

# ============================================================
# صفحة عرض سعر (مختصرة - نفس الكود القديم تقريباً)
# ============================================================

elif page == "📄 عرض سعر":
    st.title("📄 بناء عرض سعر جديد")
    
    try:
        with st.expander("🔔 العروض المنتهية (تحتاج إلى إجراء)", expanded=False):
            manage_expired_offers(conn)
        
        # تحميل البيانات الأساسية
        draw_df = pd.read_sql_query('SELECT * FROM "اسماء الرسم"', conn)
        
        customer_name = st.text_input("🏢 اسم الزبون", value=st.session_state.get('temp_cust', ""))
        st.session_state.temp_cust = customer_name
        
        col1, col2, col3 = st.columns(3)
        with col1:
            selected_size = st.selectbox("📏 قياس اللوحة:", draw_df['الحجم'].unique().tolist())
        with col2:
            print_type = st.radio("🖨️ نوع الطباعة:", ["عادي", "سكوتش"], horizontal=True)
        with col3:
            year = st.number_input("📅 العام:", min_value=2024, max_value=2030, value=2026)
        
        col_opt1, col_opt2 = st.columns(2)
        with col_opt1:
            is_foreign = st.checkbox("🌍 منتج أجنبي")
        
        # حساب بالفترات
        periods_df = pd.read_sql_query('SELECT namee, no FROM "الفترة" ORDER BY no', conn)
        period_names = periods_df['namee'].tolist()
        
        if not period_names:
            st.error("❌ لا توجد فترات في جدول الفترة")
            st.stop()
        
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            start_p = st.selectbox("📅 من فترة:", period_names, key="start_period")
        with col_p2:
            end_p = st.selectbox("📅 إلى فترة:", period_names, index=len(period_names)-1, key="end_period")
        
        start_idx = period_names.index(start_p)
        end_idx = period_names.index(end_p)
        periods_count = abs(end_idx - start_idx) + 1
        days_count = periods_count * 15
        selected_periods = period_names[start_idx:end_idx+1]
        
        st.info(f"📅 عدد الفترات: {periods_count} | عدد الأيام: {days_count} يوم")
        st.write(f"📋 الفترات المحددة: {', '.join(selected_periods)}")
        
        fee_print, fee_ads = get_fees(draw_df, selected_size, print_type, is_foreign)
        per_column_price = fee_print + (fee_ads / 28 * days_count)
        
        st.success(f"""
        💰 **تفاصيل الأسعار:**
        - أجر الطباعة الثابت: **{fee_print}$**
        - أجر العرض الشهري: **{fee_ads}$**
        - **الإجمالي لكل عمود: {per_column_price:.2f}$**
        """)
        
        st.divider()
        st.subheader("📍 اختيار المواقع")
        
        cities = pd.read_sql_query('SELECT DISTINCT "المحافظة" FROM "اعمدة انارة"', conn)['المحافظة'].tolist()
        selected_city = st.selectbox("اختر المحافظة:", cities)
        
        available_columns = pd.read_sql_query(f'''
            SELECT "رقم اللوحة", "اسم العمود" as "الموقع", "العدد", "الشبكة", "الحجم" 
            FROM "اعمدة انارة" 
            WHERE "المحافظة" = '{selected_city}' AND "الحجم" = '{selected_size}'
        ''', conn)
        
        # جلب المواقع المحجوزة
        period_placeholders = ', '.join([f"'{p}'" for p in selected_periods])
        booked_query = f'''
            SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" 
            WHERE "العام" = {year} 
            AND "فترة الحجز" IN ({period_placeholders})
        '''
        booked_df = pd.read_sql_query(booked_query, conn)
        booked_boards = booked_df['رقم اللوحة'].tolist() if not booked_df.empty else []
        
        available_columns = available_columns[~available_columns['رقم اللوحة'].isin(booked_boards)]
        
        if not available_columns.empty:
            networks = st.multiselect("اختر الشبكات:", available_columns['الشبكة'].unique().tolist())
            if st.button("➕ إضافة إلى السلة", type="primary", use_container_width=True):
                if selected_city not in st.session_state.cart:
                    st.session_state.cart[selected_city] = {}
                for net in networks:
                    net_data = available_columns[available_columns['الشبكة'] == net].copy()
                    net_data['fee_print'] = fee_print
                    net_data['fee_ads'] = fee_ads
                    st.session_state.cart[selected_city][net] = net_data
                st.success(f"✅ تمت الإضافة")
                st.rerun()
        else:
            st.warning("⚠️ لا توجد مواقع متاحة")
        
        # عرض السلة
        if st.session_state.cart:
            st.divider()
            st.subheader("🛒 سلة العروض")
            grand_total = 0.0
            
            for city, networks in list(st.session_state.cart.items()):
                for net, df_cart in list(networks.items()):
                    with st.expander(f"📍 {city} - {net}", expanded=True):
                        edited_df = st.data_editor(df_cart, key=f"edit_{city}_{net}", num_rows="dynamic", use_container_width=True)
                        st.session_state.cart[city][net] = edited_df
                        
                        qty = int(edited_df['العدد'].sum())
                        fp = float(edited_df['fee_print'].iloc[0]) if 'fee_print' in edited_df.columns else fee_print
                        fam = float(edited_df['fee_ads'].iloc[0]) if 'fee_ads' in edited_df.columns else fee_ads
                        
                        per_col = fp + (fam / 28 * days_count)
                        section_total = qty * per_col
                        grand_total += section_total
                        
                        st.info(f"العدد: {qty} | لكل عمود: {per_col:.2f}$ | الإجمالي: {section_total:.2f}$")
                        
                        if st.button("🗑️ حذف", key=f"delete_{city}_{net}"):
                            del st.session_state.cart[city][net]
                            st.rerun()
            
            st.markdown(f"## 💰 الإجمالي العام: {grand_total:,.2f} $")
            
            col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)
            
            with col_btn1:
                if st.button("💾 حفظ كمسودة", use_container_width=True, key="save_draft"):
                    if not customer_name:
                        st.error("❌ الرجاء إدخال اسم الزبون")
                    else:
                        save_data = {"data": {c: {n: df.to_dict() for n, df in ns.items()} for c, ns in st.session_state.cart.items()}}
                        cur = conn.cursor()
                        cur.execute('''
                            INSERT INTO "offers_history" (client_name, cart_json, status, start_p, end_p, year, offer_date) 
                            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                        ''', (customer_name, json)

                        save_data = {"data": {c: {n: df.to_dict() for n, df in ns.items()} for c, ns in st.session_state.cart.items()}}
                        cur = conn.cursor()
                        cur.execute('''
                            INSERT INTO "offers_history" (client_name, cart_json, status, start_p, end_p, year, offer_date) 
                            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                        ''', (customer_name, json.dumps(save_data, ensure_ascii=False), 'Pending', start_p, end_p, year))
                        conn.commit()
                        st.success("✅ تم الحفظ")
            
            with col_btn2:
                if is_admin():
                    if st.button("✅ تثبيت نهائي", use_container_width=True, key="confirm_booking"):
                        if not customer_name:
                            st.error("❌ الرجاء إدخال اسم الزبون")
                        else:
                            try:
                                cur = conn.cursor()
                                for city, networks in st.session_state.cart.items():
                                    for net, df in networks.items():
                                        for _, row in df.iterrows():
                                            for period in selected_periods:
                                                cur.execute('''
                                                    INSERT INTO "حجوزات1" ("رقم اللوحة", "اسم الزبون", "العام", "فترة الحجز") 
                                                    VALUES (?, ?, ?, ?)
                                                ''', (str(row['رقم اللوحة']), customer_name, year, period))
                                
                                if 'current_offer_id' in st.session_state:
                                    cur.execute('UPDATE "offers_history" SET status = "Accepted" WHERE id = ?', (st.session_state.current_offer_id,))
                                    del st.session_state.current_offer_id
                                
                                conn.commit()
                                st.session_state.cart = {}
                                st.success("✅ تم تثبيت الحجز بنجاح")
                                st.rerun()
                                
                            except Exception as e:
                                conn.rollback()
                                st.error(f"❌ حدث خطأ: {str(e)}")
                else:
                    st.button("✅ تثبيت نهائي", use_container_width=True, disabled=True, key="confirm_booking_disabled")
                    st.caption("🔒 غير مسموح - فقط للمديرين")
            
            with col_btn3:
                if st.button("📝 تصدير Word", use_container_width=True, key="export_word"):
                    word_file = export_word_old(customer_name, st.session_state.cart, start_p, end_p, grand_total)
                    st.download_button("📥 تحميل العرض", word_file, f"Offer_{customer_name}.docx", key="download_word")
            
            with col_btn4:
                if st.button("🔴 تفريغ السلة", use_container_width=True, key="clear_cart"):
                    st.session_state.cart = {}
                    st.rerun()
    
    except Exception as e:
        st.error(f"❌ حدث خطأ: {str(e)}")

# ============================================================
# صفحة تقرير الجرد الكامل
# ============================================================

elif page == "📋 تقرير الجرد":
    st.title("📋 التقرير التجميعي - جرد اللوحات")
    
    try:
        periods_df = pd.read_sql_query('SELECT "no", "namee" FROM "الفترة" ORDER BY "no"', conn)
        
        if periods_df.empty:
            st.error("❌ لا توجد فترات في جدول الفترة")
            st.stop()
        
        period_names = periods_df['namee'].tolist()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            from_period = st.selectbox("من فترة:", period_names, key="from_period")
        with col2:
            to_period = st.selectbox("إلى فترة:", period_names, index=len(period_names)-1, key="to_period")
        with col3:
            report_year = st.number_input("العام:", value=datetime.now().year, key="report_year")
        
        from_idx = int(periods_df[periods_df['namee'] == from_period]['no'].iloc[0])
        to_idx = int(periods_df[periods_df['namee'] == to_period]['no'].iloc[0])
        target_periods = periods_df[(periods_df['no'] >= from_idx) & (periods_df['no'] <= to_idx)]['namee'].tolist()
        
        if not target_periods:
            st.warning("⚠️ لا توجد فترات في النطاق المحدد")
            st.stop()
        
        all_boards = pd.read_sql_query('SELECT "رقم اللوحة", "المحافظة", "الحجم", "العدد" FROM "اعمدة انارة"', conn)
        
        if all_boards.empty:
            st.warning("⚠️ لا توجد بيانات في جدول الأعمدة")
            st.stop()
        
        period_placeholders = ", ".join([f"'{p}'" for p in target_periods])
        booked_query = f'''
            SELECT DISTINCT "رقم اللوحة" 
            FROM "حجوزات1" 
            WHERE "العام" = {report_year} 
            AND "فترة الحجز" IN ({period_placeholders})
        '''
        booked_in_period = pd.read_sql_query(booked_query, conn)['رقم اللوحة'].tolist()
        
        all_boards['الحالة'] = all_boards['رقم اللوحة'].apply(lambda x: 'محجوز' if x in booked_in_period else 'متاح')
        
        total_sites = len(all_boards)
        booked_sites = len(booked_in_period)
        available_sites = total_sites - booked_sites
        
        total_boards_count = all_boards['العدد'].sum()
        booked_boards_count = all_boards[all_boards['الحالة'] == 'محجوز']['العدد'].sum()
        available_boards_count = total_boards_count - booked_boards_count
        
        st.subheader("📊 إحصائيات عامة")
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric("🏢 المواقع الكلية", total_sites)
            st.metric("📌 الأعمدة الكلية", int(total_boards_count))
        with col_b:
            st.metric("🔴 المواقع المحجوزة", booked_sites)
            st.metric("🔴 الأعمدة المحجوزة", int(booked_boards_count))
        with col_c:
            st.metric("🟢 المواقع المتاحة", available_sites)
            st.metric("🟢 الأعمدة المتاحة", int(available_boards_count))
        
        st.progress(booked_boards_count / total_boards_count if total_boards_count > 0 else 0, 
                    text=f"📈 نسبة إشغال الأعمدة: {(booked_boards_count/total_boards_count*100):.1f}%" if total_boards_count > 0 else "0%")
        
        st.divider()
        
        st.subheader("🥧 نسبة الإشغال الكلية")
        fig_pie = go.Figure(data=[go.Pie(
            labels=['محجوز', 'متاح'],
            values=[booked_boards_count, available_boards_count],
            hole=0.4,
            marker_colors=['#dc2626', '#22c55e']
        )])
        fig_pie.update_layout(height=400)
        st.plotly_chart(fig_pie, use_container_width=True)
        
        # تجميع البيانات حسب المحافظة
        city_data = []
        for city in all_boards['المحافظة'].unique():
            city_df = all_boards[all_boards['المحافظة'] == city]
            city_total = city_df['العدد'].sum()
            city_booked = city_df[city_df['الحالة'] == 'محجوز']['العدد'].sum()
            city_available = city_total - city_booked
            occupancy_rate = (city_booked / city_total * 100) if city_total > 0 else 0
            city_data.append({
                'المحافظة': city,
                'الإجمالي': int(city_total),
                'محجوز': int(city_booked),
                'متاح': int(city_available),
                'نسبة الإشغال': f"{occupancy_rate:.1f}%"
            })
        
        city_stats = pd.DataFrame(city_data)
        
        st.subheader("📊 نسبة إشغال الأعمدة حسب المحافظة")
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=city_stats['المحافظة'],
            y=[float(x.strip('%')) for x in city_stats['نسبة الإشغال']],
            text=city_stats['نسبة الإشغال'],
            textposition='outside',
            marker=dict(
                color=[float(x.strip('%')) for x in city_stats['نسبة الإشغال']],
                colorscale='Reds',
                showscale=True,
                colorbar=dict(title="نسبة الإشغال %"),
                line=dict(width=2, color='black'),
            ),
            name='نسبة الإشغال',
            width=0.6
        ))
        
        fig.update_layout(
            title="نسبة إشغال الأعمدة الإعلانية حسب المحافظة",
            xaxis_title="المحافظة",
            yaxis_title="نسبة الإشغال (%)",
            yaxis=dict(range=[0, 100], gridcolor='lightgray'),
            height=500,
            font=dict(family="Arial", size=14),
            plot_bgcolor='white'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("📋 تفصيل حسب المحافظة")
        st.dataframe(city_stats, use_container_width=True)
        
        st.subheader("📋 تفصيل حسب المحافظة والحجم")
        for city in sorted(all_boards['المحافظة'].unique()):
            city_data_detail = all_boards[all_boards['المحافظة'] == city]
            with st.expander(f"📍 محافظة {city}"):
                size_data = city_data_detail.groupby(['الحجم', 'الحالة']).agg({
                    'رقم اللوحة': 'count',
                    'العدد': 'sum'
                }).rename(columns={'رقم اللوحة': 'عدد المواقع', 'العدد': 'عدد الأعمدة'}).unstack(fill_value=0)
                st.dataframe(size_data, use_container_width=True)
        
        st.divider()
        col_exp1, col_exp2 = st.columns(2)
        
        with col_exp1:
            csv_data = all_boards.to_csv(index=False, encoding='utf-8-sig')
            st.download_button("📊 تصدير إلى CSV", csv_data, f"Inventory_Report_{report_year}.csv", "text/csv", use_container_width=True)
        
        with col_exp2:
            # تصدير Word للتقرير
            doc = Document()
            h = doc.add_heading(f"تقرير حالة الإشغال لعام {report_year}", 0)
            h.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_period = doc.add_paragraph()
            p_period.add_run(f"الفترة من: {from_period} لغاية: {to_period}").bold = True
            _force_rtl_style(p_period)
            doc.add_paragraph()
            p_summary = doc.add_paragraph()
            p_summary.add_run(f"المواقع الكلية: {total_sites} | الأعمدة الكلية: {int(total_boards_count)}")
            _force_rtl_style(p_summary)
            p_summary.add_run(f"\nالمواقع المحجوزة: {booked_sites} | الأعمدة المحجوزة: {int(booked_boards_count)}")
            _force_rtl_style(p_summary)
            p_summary.add_run(f"\nالمواقع المتاحة: {available_sites} | الأعمدة المتاحة: {int(available_boards_count)}")
            _force_rtl_style(p_summary)
            word_out = io.BytesIO()
            doc.save(word_out)
            st.download_button("📝 تصدير إلى Word", word_out.getvalue(), f"Inventory_Report_{report_year}.docx", 
                             "application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
    
    except Exception as e:
        st.error(f"حدث خطأ في التقرير: {str(e)}")

# ============================================================
# صفحة تقرير التوفر الشهري
# ============================================================

elif page == "📅 تقرير التوفر الشهري":
    st.title("📋 تقرير الأعمدة المتاحة")
    st.info("📌 يعرض هذا التقرير الأعمدة المتاحة حالياً أو التي ستصبح متاحة بعد تاريخ محدد")
    
    from datetime import date, timedelta
    
    current_year = date.today().year
    today = date.today()
    
    col_filter1, col_filter2 = st.columns(2)
    with col_filter1:
        show_all = st.checkbox("📅 عرض جميع الأعمدة المتاحة حالياً", value=True)
    with col_filter2:
        future_date = st.date_input("🗓️ عرض الأعمدة التي ستصبح متاحة بعد تاريخ", value=today + timedelta(days=7))
    
    notes = st.text_area("📝 ملاحظات (تظهر في نهاية التقرير)", placeholder="أضف ملاحظاتك هنا...", height=100)
    
    if st.button("🚀 تشغيل التقرير", use_container_width=True, type="primary"):
        with st.spinner("جاري إنشاء التقرير..."):
            all_columns = pd.read_sql_query('SELECT "رقم اللوحة", "اسم العمود", "المحافظة", "الشبكة", "الحجم", "العدد" FROM "اعمدة انارة"', conn)
            
            if show_all:
                bookings_query = f'SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" WHERE "العام" = {current_year}'
            else:
                bookings_query = f'''
                    SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" 
                    WHERE "العام" = {current_year}
                    AND ("تاريخ النهاية" >= '{future_date}' OR "فترة الحجز" IS NOT NULL)
                '''
            
            booked_df = pd.read_sql_query(bookings_query, conn)
            booked_boards = booked_df['رقم اللوحة'].tolist() if not booked_df.empty else []
            
            available_df = all_columns[~all_columns['رقم اللوحة'].isin(booked_boards)]
            total_available = len(available_df)
            total_boards_count = available_df['العدد'].sum() if 'العدد' in available_df.columns else total_available
            
            st.success(f"✅ {total_available} موقعاً ({int(total_boards_count)} لوحة) متاحة")
            
            st.subheader("📊 ملخص حسب المحافظة")
            summary = available_df.groupby('المحافظة').agg({
                'رقم اللوحة': 'count',
                'العدد': 'sum'
            }).rename(columns={'رقم اللوحة': 'عدد المواقع', 'العدد': 'عدد اللوحات'})
            st.dataframe(summary, use_container_width=True)
            
            st.subheader("📋 قائمة الأعمدة المتاحة")
            st.dataframe(available_df[['رقم اللوحة', 'اسم العمود', 'المحافظة', 'الشبكة', 'الحجم', 'العدد']], use_container_width=True, height=400)
            
            # تصدير CSV
            csv_data = available_df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button("📥 تحميل التقرير (CSV)", csv_data, f"available_columns_{date.today().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)

# ============================================================
# صفحة تقرير جميع المواقع (مكتملة)
# ============================================================

elif page == "🗺️ تقرير جميع المواقع":
    st.title("🗺️ تقرير جميع المواقع والأعمدة")
    st.info("📌 يعرض هذا التقرير جميع المواقع والأعمدة الموجودة في النظام بشكل تفصيلي حسب المحافظات والشبكات")
    
    from datetime import date
    
    # جلب البيانات
    all_columns = pd.read_sql_query('SELECT "رقم اللوحة", "اسم العمود", "المحافظة", "الشبكة", "الحجم", "العدد" FROM "اعمدة انارة" ORDER BY "المحافظة", "الشبكة"', conn)
    
    if all_columns.empty:
        st.warning("⚠️ لا توجد بيانات في جدول الأعمدة")
        st.stop()
    
    total_sites = len(all_columns)
    total_boards = all_columns['العدد'].sum() if 'العدد' in all_columns.columns else total_sites
    
    # عرض الإحصائيات
    st.subheader("📊 إحصائيات عامة")
    col1, col2, col3 = st.columns(3)
    col1.metric("🗺️ إجمالي المواقع", total_sites)
    col2.metric("📌 إجمالي الأعمدة", int(total_boards))
    col3.metric("🏢 عدد المحافظات", all_columns['المحافظة'].nunique())
    
    st.divider()
    
    # ملخص حسب المحافظة
    st.subheader("📊 ملخص حسب المحافظة")
    summary = all_columns.groupby('المحافظة').agg({
        'رقم اللوحة': 'count',
        'العدد': 'sum'
    }).rename(columns={'رقم اللوحة': 'عدد المواقع', 'العدد': 'عدد الأعمدة'})
    summary['عدد الأعمدة'] = summary['عدد الأعمدة'].astype(int)
    st.dataframe(summary, use_container_width=True)
    
    st.divider()
    
    # عرض تفصيلي حسب المحافظة والشبكة
    st.subheader("📋 تفصيل حسب المحافظة والشبكة")
    
    for city in sorted(all_columns['المحافظة'].unique()):
        city_df = all_columns[all_columns['المحافظة'] == city]
        with st.expander(f"📍 محافظة {city} ({len(city_df)} موقع - {city_df['العدد'].sum()} لوحة)"):
            
            # ملخص الشبكات في هذه المحافظة
            network_summary = city_df.groupby('الشبكة').agg({
                'رقم اللوحة': 'count',
                'العدد': 'sum'
            }).rename(columns={'رقم اللوحة': 'عدد المواقع', 'العدد': 'عدد الأعمدة'})
            st.write("**📡 توزع الشبكات في المحافظة:**")
            st.dataframe(network_summary, use_container_width=True)
            
            # تفصيل لكل شبكة على حدة
            for network in sorted(city_df['الشبكة'].unique()):
                net_df = city_df[city_df['الشبكة'] == network]
                with st.expander(f"📡 شبكة: {network} ({len(net_df)} موقع - {net_df['العدد'].sum()} لوحة)"):
                    
                    # تفصيل حسب الحجم داخل الشبكة
                    size_summary = net_df.groupby('الحجم').agg({
                        'رقم اللوحة': 'count',
                        'العدد': 'sum'
                    }).rename(columns={'رقم اللوحة': 'عدد المواقع', 'العدد': 'عدد الأعمدة'})
                    st.write("**📏 تفصيل حسب الحجم:**")
                    st.dataframe(size_summary, use_container_width=True)
                    
                    # قائمة جميع المواقع في هذه الشبكة
                    st.write("**📍 قائمة المواقع:**")
                    st.dataframe(net_df[['رقم اللوحة', 'اسم العمود', 'الحجم', 'العدد']], use_container_width=True)
    
    # أزرار التصدير
    st.divider()
    st.subheader("📥 تصدير التقرير")
    
    csv_data = all_columns.to_csv(index=False, encoding='utf-8-sig')
    st.download_button("📊 تصدير إلى CSV", csv_data, f"all_columns_{date.today().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)

# ============================================================
# صفحة تقرير تجميعي حسب الحجوم
# ============================================================

elif page == "📐 تقرير تجميعي حسب الحجوم":
    st.title("📐 تقرير تجميعي حسب الحجوم")
    st.info("📌 يعرض هذا التقرير توزع اللوحات حسب الحجوم المقسمة إلى ثلاث مجموعات")
    
    from datetime import date
    
    # جلب البيانات
    all_columns = pd.read_sql_query('SELECT "رقم اللوحة", "اسم العمود", "المحافظة", "الشبكة", "الحجم", "العدد" FROM "اعمدة انارة" ORDER BY "المحافظة", "الشبكة"', conn)
    
    if all_columns.empty:
        st.warning("⚠️ لا توجد بيانات في جدول الأعمدة")
        st.stop()
    
    # تعريف مجموعات الحجوم
    group1_sizes = ['3*6', '3x6', '3 × 6']
    group2_sizes = ['2*1', '2x1', '2 × 1', '125*185', '125x185', '125 × 185']
    
    def classify_size(size):
        size_str = str(size).strip()
        if size_str in group1_sizes or size_str.replace(' ', '') in ['3*6', '3x6']:
            return 'المجموعة الأولى: حجم 3×6'
        elif size_str in group2_sizes or size_str.replace(' ', '') in ['2*1', '2x1', '125*185', '125x185']:
            return 'المجموعة الثانية: حجمي 2×1 و 125×185'
        else:
            return 'المجموعة الثالثة: باقي الحجوم'
    
    all_columns['المجموعة'] = all_columns['الحجم'].apply(classify_size)
    
    # إحصائيات عامة
    st.subheader("📊 إحصائيات عامة")
    col1, col2, col3 = st.columns(3)
    col1.metric("📌 إجمالي الأعمدة", f"{int(all_columns['العدد'].sum()):,}")
    col2.metric("🗺️ إجمالي المواقع", len(all_columns))
    col3.metric("📏 عدد الأحجام المختلفة", all_columns['الحجم'].nunique())
    
    st.divider()
    
    # ملخص المجموعات
    st.subheader("📊 ملخص المجموعات")
    group_summary = all_columns.groupby('المجموعة').agg({
        'رقم اللوحة': 'count',
        'العدد': 'sum'
    }).rename(columns={'رقم اللوحة': 'عدد المواقع', 'العدد': 'عدد الأعمدة'})
    group_summary['عدد الأعمدة'] = group_summary['عدد الأعمدة'].astype(int)
    st.dataframe(group_summary, use_container_width=True)
    
    st.divider()
    
    # دالة لعرض تفاصيل مجموعة
    def display_group_details(df, group_name):
        st.header(f"📌 {group_name}")
        
        group_df = df[df['المجموعة'] == group_name]
        if group_df.empty:
            st.info(f"لا توجد بيانات في {group_name}")
            return
        
        # إحصائيات المجموعة
        total_sites = len(group_df)
        total_boards = group_df['العدد'].sum()
        st.info(f"📊 إجمالي المواقع: {total_sites} | إجمالي الأعمدة: {int(total_boards)}")
        
        # تفصيل حسب المحافظة
        st.subheader(f"📍 توزع {group_name} حسب المحافظة")
        city_summary = group_df.groupby('المحافظة').agg({
            'رقم اللوحة': 'count',
            'العدد': 'sum'
        }).rename(columns={'رقم اللوحة': 'عدد المواقع', 'العدد': 'عدد الأعمدة'})
        city_summary['عدد الأعمدة'] = city_summary['عدد الأعمدة'].astype(int)
        st.dataframe(city_summary, use_container_width=True)
        
        # تفصيل حسب المحافظة والشبكة
        st.subheader(f"📡 توزع {group_name} حسب المحافظة والشبكة")
        for city in sorted(group_df['المحافظة'].unique()):
            city_df = group_df[group_df['المحافظة'] == city]
            with st.expander(f"📍 محافظة {city} ({len(city_df)} موقع - {city_df['العدد'].sum()} لوحة)"):
                
                # تفصيل حسب الشبكة
                network_summary = city_df.groupby('الشبكة').agg({
                    'رقم اللوحة': 'count',
                    'العدد': 'sum'
                }).rename(columns={'رقم اللوحة': 'عدد المواقع', 'العدد': 'عدد الأعمدة'})
                network_summary['عدد الأعمدة'] = network_summary['عدد الأعمدة'].astype(int)
                st.write("**📡 تفصيل حسب الشبكة:**")
                st.dataframe(network_summary, use_container_width=True)
                
                # قائمة المواقع
                st.write("**📍 قائمة المواقع:**")
                st.dataframe(city_df[['رقم اللوحة', 'اسم العمود', 'الشبكة', 'الحجم', 'العدد']], use_container_width=True)
    
    # عرض المجموعات الثلاث
    display_group_details(all_columns, 'المجموعة الأولى: حجم 3×6')
    st.divider()
    display_group_details(all_columns, 'المجموعة الثانية: حجمي 2×1 و 125×185')
    st.divider()
    display_group_details(all_columns, 'المجموعة الثالثة: باقي الحجوم')
    
    # أزرار التصدير
    st.divider()
    st.subheader("📥 تصدير التقرير")
    
    csv_data = all_columns.to_csv(index=False, encoding='utf-8-sig')
    st.download_button("📊 تصدير التقرير كاملاً (CSV)", csv_data, f"grouped_report_{date.today().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)

# ============================================================
# صفحة المزامنة السحابية (مكتملة - نسخة مصححة)
# ============================================================

elif page == "☁️ مزامنة سحابية":
    st.title("☁️ إدارة النسخ الاحتياطي السحابي")
    
    st.info("""
    📌 **نظام النسخ الاحتياطي**
    
    - **SQLite المحلية**: هي المصدر الأساسي (سريعة - لا تحتاج إنترنت)
    - **Supabase السحابية**: نسخة احتياطية (يمكن الوصول إليها من أي مكان)
    
    يمكنك رفع بياناتك إلى السحاب للنسخ الاحتياطي، أو استرجاعها عند الحاجة.
    """)
    
    if not supabase_available:
        st.error("❌ مكتبة supabase غير مثبتة. للتثبيت: pip install supabase-python")
        st.stop()
    
    # إحصائيات المحلية
    st.subheader("📊 قاعدة البيانات المحلية (SQLite)")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM 'اعمدة انارة'")
    local_boards = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM 'حجوزات1'")
    local_bookings = cursor.fetchone()[0]
    
    col1, col2 = st.columns(2)
    col1.metric("🗺️ أعمدة الإنارة", local_boards)
    col2.metric("📅 الحجوزات", local_bookings)
    
    st.divider()
    
    # أزرار المزامنة
    st.subheader("🔄 عمليات المزامنة")
    
    col_sync1, col_sync2 = st.columns(2)
    
    with col_sync1:
        st.markdown("#### 📤 محلي ← سحاب")
        st.caption("رفع البيانات من SQLite إلى Supabase (نسخ احتياطي)")
        
        if st.button("☁️ نسخ احتياطي كامل", use_container_width=True, type="primary"):
            with st.spinner("جاري رفع البيانات..."):
                if sync_local_to_supabase():
                    st.success("✅ تم رفع البيانات بنجاح إلى Supabase")
                else:
                    st.error("❌ فشل رفع البيانات - تأكد من إعدادات Supabase")
    
    with col_sync2:
        st.markdown("#### 📥 سحاب ← محلي")
        st.caption("استيراد بيانات من Supabase إلى SQLite (عند الحاجة فقط)")
        st.warning("⚠️ استخدم هذا بحذر - قد يؤدي إلى تكرار البيانات")
        
        if st.button("📥 استيراد من السحاب", use_container_width=True):
            st.info("هذه الميزة قيد التطوير - ستسمح باستيراد بيانات محددة")
    
    st.divider()
    
    # تعليمات الإعداد
    with st.expander("📖 تعليمات إعداد Supabase", expanded=False):
        st.markdown("""
        **إعداد Supabase**
        
        1. **إنشاء مشروع** في [Supabase](https://supabase.com)
        2. **إنشاء الجداول** (نفس هيكل SQLite)
        3. **الحصول على المفاتيح** من Settings → API
        4. **تحديث المتغيرات** في بداية هذا الملف
        """)
# ============================================================
# صفحة الإعدادات (المتبقية)
# ============================================================

elif page == "⚙️ الإعدادات":
    if not is_admin():
        st.error("⛔ هذه الصفحة مخصصة للمديرين فقط")
        st.stop()
    
    st.title("⚙️ إعدادات النظام - إدارة الجداول")
    st.warning("⚠️ تحذير: تعديل هذه الجداول يؤثر مباشرة على النظام. يرجى الحذر.")
    
    try:
        tab1, tab2, tab3 = st.tabs(["🗄️ أعمدة الإنارة", "📅 سجل الحجوزات", "💰 أجور الرسم"])
        
        with tab1:
            st.subheader("إدارة بيانات أعمدة الإنارة")
            df_boards = pd.read_sql_query('SELECT * FROM "اعمدة انارة" ORDER BY "المحافظة", "الشبكة"', conn)
            edited_boards = st.data_editor(df_boards, num_rows="dynamic", key="edit_boards", use_container_width=True)
            if st.button("💾 حفظ أعمدة الإنارة", key="save_boards", use_container_width=True):
                cursor = conn.cursor()
                cursor.execute("DELETE FROM 'اعمدة انارة'")
                for _, row in edited_boards.iterrows():
                    cursor.execute('''
                        INSERT INTO "اعمدة انارة" ("رقم اللوحة", "اسم العمود", "المحافظة", "الشبكة", "الحجم", "العدد", "Latitude", "Longitude")
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (row['رقم اللوحة'], row['اسم العمود'], row['المحافظة'], row['الشبكة'], row['الحجم'], row['العدد'], 
                          row.get('Latitude', 0), row.get('Longitude', 0)))
                conn.commit()
                st.success("✅ تم تحديث أعمدة الإنارة")
                st.rerun()
        
        with tab2:
            st.subheader("إدارة سجل الحجوزات")
            df_bookings = pd.read_sql_query('SELECT * FROM "حجوزات1" LIMIT 500', conn)
            edited_bookings = st.data_editor(df_bookings, num_rows="dynamic", key="edit_bookings", use_container_width=True)
            if st.button("💾 حفظ سجل الحجوزات", key="save_bookings", use_container_width=True):
                cursor = conn.cursor()
                cursor.execute("DELETE FROM 'حجوزات1'")
                for _, row in edited_bookings.iterrows():
                    cursor.execute('''
                        INSERT INTO "حجوزات1" ("رقم اللوحة", "اسم الزبون", "العام", "فترة الحجز", "تاريخ النهاية")
                        VALUES (?, ?, ?, ?, ?)
                    ''', (row['رقم اللوحة'], row['اسم الزبون'], row['العام'], row['فترة الحجز'], row.get('تاريخ النهاية')))
                conn.commit()
                st.success("✅ تم تحديث سجل الحجوزات")
                st.rerun()
        
        with tab3:
            st.subheader("إدارة أجور الرسم")
            st.info("💡 أضف 'اجور الطباعة عادي' و 'اجور الطباعة سكوتش' و 'اجور العرض' و 'اجور العرض اجنبي'")
            df_fees = pd.read_sql_query('SELECT * FROM "اسماء الرسم"', conn)
            edited_fees = st.data_editor(df_fees, num_rows="dynamic", key="edit_fees", use_container_width=True)
            if st.button("💾 حفظ أجور الرسم", key="save_fees", use_container_width=True):
                cursor = conn.cursor()
                cursor.execute("DELETE FROM 'اسماء الرسم'")
                for _, row in edited_fees.iterrows():
                    cursor.execute('''
                        INSERT INTO "اسماء الرسم" ("اسم الرسم", "الحجم", "اجرة الرسم")
                        VALUES (?, ?, ?)
                    ''', (row['اسم الرسم'], row['الحجم'], row['اجرة الرسم']))
                conn.commit()
                st.success("✅ تم تحديث أجور الرسم")
                st.rerun()
    
    except Exception as e:
        st.error(f"⚠️ خطأ: {e}")

# ============================================================
# إغلاق الاتصال
# ============================================================

conn.close()

# نهاية الملف
