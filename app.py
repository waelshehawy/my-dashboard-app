#ppart1
# ============================================================
# app.py - النسخة المحسنة مع التصحيحات الإلزامية
# ============================================================

# ============================================================
# الاستيرادات
# ============================================================

import streamlit as st
import pandas as pd
import os
import io
import folium
import json
import hashlib
import secrets
from dotenv import load_dotenv
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
from psycopg2.extras import RealDictCursor, execute_values

# تحميل متغيرات البيئة
load_dotenv()
# ============================================================
# إعدادات Supabase (من متغيرات البيئة فقط - تم إزالة الكلمة الافتراضية)
# ============================================================

@st.cache_resource(ttl=3600)
# ============================================================
# دوال الاتصال والتشفير
# ============================================================

@st.cache_resource(ttl=3600)
def get_connection():
    """اتصال مباشر بـ Supabase PostgreSQL - مع تخزين مؤقت"""
    
    password = os.getenv("SUPABASE_PASSWORD")
    if not password:
        st.error("""
        ⚠️ **كلمة المرور غير موجودة!**
        
        يرجى إنشاء ملف `.env` في المجلد الرئيسي وإضافة:
    
    return psycopg2.connect(
        host=os.environ.get("SUPABASE_HOST", "aws-1-eu-north-1.pooler.supabase.com"),
        port=os.environ.get("SUPABASE_PORT", "6543"),
        database=os.environ.get("SUPABASE_DB", "postgres"),
        user=os.environ.get("SUPABASE_USER", "postgres.ncuofpvbaglwbdqnpman"),
        password=password,
        sslmode="require",
        connect_timeout=30
    )

# ============================================================
# دوال التشفير
# ============================================================

def hash_password(password):
    """تشفير كلمة المرور باستخدام SHA-256 مع ملح"""
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{hashed}"

def verify_password(password, hashed):
    """التحقق من كلمة المرور"""
    try:
        salt, hash_value = hashed.split(':')
        return hash_value == hashlib.sha256((salt + password).encode()).hexdigest()
    except:
        return False
# ============================================================
# دوال إدارة المستخدمين
# ============================================================

@st.cache_data(ttl=60)
def authenticate_user(username, password):
    """مصادقة المستخدم من قاعدة البيانات"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, username, password, role, full_name, is_active 
            FROM users 
            WHERE username = %s AND is_active = TRUE
        """, (username,))
        user = cursor.fetchone()
        
        if user and verify_password(password, user[2]):
            # تحديث آخر تسجيل دخول
            cursor.execute("""
                UPDATE users SET last_login = NOW() 
                WHERE id = %s
            """, (user[0],))
            conn.commit()
            
            return {
                'id': user[0],
                'username': user[1],
                'role': user[3],
                'full_name': user[4],
                'is_active': user[5]
            }
        return None
    except Exception as e:
        st.error(f"❌ خطأ في المصادقة: {str(e)}")
        return None
    finally:
        cursor.close()

@st.cache_data(ttl=300)
def get_all_users():
    """جلب جميع المستخدمين (للوحة الإدارة)"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, username, role, full_name, created_at, last_login, is_active 
            FROM users 
            ORDER BY id
        """)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return pd.DataFrame(rows, columns=columns)
    finally:
        cursor.close()

def create_user(username, password, role, full_name):
    """إنشاء مستخدم جديد"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # تشفير كلمة المرور
        hashed_password = hash_password(password)
        
        cursor.execute("""
            INSERT INTO users (username, password, role, full_name, created_at, is_active)
            VALUES (%s, %s, %s, %s, NOW(), TRUE)
            RETURNING id
        """, (username, hashed_password, role, full_name))
        
        user_id = cursor.fetchone()[0]
        conn.commit()
        st.success(f"✅ تم إنشاء المستخدم {username} بنجاح")
        st.cache_data.clear()  # مسح الكاش
        return user_id
    except Exception as e:
        conn.rollback()
        st.error(f"❌ خطأ في إنشاء المستخدم: {str(e)}")
        return None
    finally:
        cursor.close()

def update_user(user_id, username, role, full_name, is_active=True):
    """تحديث بيانات المستخدم"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE users 
            SET username = %s, role = %s, full_name = %s, is_active = %s
            WHERE id = %s
        """, (username, role, full_name, is_active, user_id))
        conn.commit()
        st.success(f"✅ تم تحديث المستخدم {username}")
        st.cache_data.clear()
        return True
    except Exception as e:
        conn.rollback()
        st.error(f"❌ خطأ في تحديث المستخدم: {str(e)}")
        return False
    finally:
        cursor.close()

def reset_password(user_id, new_password):
    """إعادة تعيين كلمة المرور"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        hashed_password = hash_password(new_password)
        cursor.execute("""
            UPDATE users SET password = %s WHERE id = %s
        """, (hashed_password, user_id))
        conn.commit()
        st.success("✅ تم تحديث كلمة المرور")
        st.cache_data.clear()
        return True
    except Exception as e:
        conn.rollback()
        st.error(f"❌ خطأ في تحديث كلمة المرور: {str(e)}")
        return False
    finally:
        cursor.close()        

# ============================================================
# دوال الاستعلام المحسنة مع Cache
# ============================================================

@st.cache_data(ttl=120)
def run_query(query, params=None, fetch=True):
    """تنفيذ استعلام على Supabase مع تخزين مؤقت"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(query, params or ())
        if fetch and query.strip().upper().startswith('SELECT'):
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
        # لا نغلق conn لأنها مخزنة مؤقتاً
#part2
# ============================================================
# التحسينات البصرية - CSS
# ============================================================

ADVANCED_CSS = '''
<style>
    .stApp {
        background: linear-gradient(-45deg, #ee7752, #e73c7e, #23a6d5, #23d5ab);
        background-size: 400% 400%;
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
'''
#part3
# ============================================================
# دوال المساعدة والمتاح (مع تصحيحات Cache)
# ============================================================

MONTHS_AR = {
    1: "كانون ثاني", 2: "شباط", 3: "اذار", 4: "نيسان",
    5: "ايار", 6: "حزيران", 7: "تموز", 8: "اب",
    9: "ايلول", 10: "تشرين اول", 11: "تشرين ثاني", 12: "كانون اول"
}

@st.cache_data(ttl=3600)
def convert_date_to_period_name(date):
    """تحويل التاريخ إلى اسم الفترة - مع تخزين مؤقت"""
    month_name = MONTHS_AR[date.month]
    if date.day <= 15:
        return f"{month_name} 15-1"
    else:
        return f"{month_name} 30-15"

@st.cache_data(ttl=300)
def get_available_boards_from_date(start_date):
    """اللوحات المتاحة ابتداءً من تاريخ محدد - مع تخزين مؤقت"""
    target_period = convert_date_to_period_name(start_date)
    target_year = start_date.year
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # استعلام محسن باستخدام EXISTS بدلاً من NOT IN
        cursor.execute("""
            SELECT a.* 
            FROM "اعمدة انارة" a
            WHERE NOT EXISTS (
                SELECT 1 FROM "حجوزات1" b
                WHERE b."رقم اللوحة" = a."رقم اللوحة"
                AND b."فترة الحجز" = %s
                AND b."العام" = %s
            )
        """, (target_period, target_year))
        
        columns = [desc[0] for desc in cursor.description]
        data = cursor.fetchall()
    finally:
        cursor.close()
    
    return pd.DataFrame(data, columns=columns)

# ============================================================
# دوال تحويل الفترات (مع Cache)
# ============================================================

@st.cache_data(ttl=3600)
def get_period_number(period_name):
    """تحويل اسم الفترة إلى رقم (1-24) مع تخزين مؤقت"""
    PERIOD_ORDER = get_period_order()
    if period_name is None:
        return 99
    return PERIOD_ORDER.get(period_name, 99)

@st.cache_data(ttl=3600)
def get_period_order():
    """الحصول على ترتيب الفترات من قاعدة البيانات مع تخزين مؤقت"""
    conn = get_connection()
    try:
        df = pd.read_sql_query('SELECT no, namee FROM "الفترة" ORDER BY no', conn)
        return {row['namee']: row['no'] for _, row in df.iterrows()}
    finally:
        conn.close()

@st.cache_data(ttl=3600)
def get_period_from_date(date_obj):
    """تحويل التاريخ إلى رقم الفترة مع تخزين مؤقت"""
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
        if month == 2:
            last_day = 28
        elif month in [4, 6, 9, 11]:
            last_day = 30
        else:
            last_day = 31
        period_name = f"{month_name} {last_day}-16"
    
    PERIOD_ORDER = get_period_order()
    return PERIOD_ORDER.get(period_name, 99)

# ============================================================
# دوال مساعدة أخرى
# ============================================================

def create_metric_card_3d(title, value, icon, color_gradient="primary"):
    """إنشاء بطاقة إحصائية - محسنة للاستخدام مع st.metric"""
    # تم التعديل لاستخدام st.metric بدلاً من HTML
    return {
        'title': title,
        'value': value,
        'icon': icon,
        'gradient': color_gradient
    }

@st.cache_data(ttl=3600)
def safe_split(value):
    """تقسيم آمن مع تخزين مؤقت"""
    if pd.isna(value) or value in [None, 'nan', 'None', 'NaN', '']:
        return []
    if not isinstance(value, str):
        return []
    return [v.strip() for v in value.split(',') if v.strip()]

def is_admin():
    return st.session_state.get('role') == 'admin'

# ============================================================
# تهيئة حالة الجلسة
# ============================================================

if "auth" not in st.session_state:
    st.session_state.auth = False
if "cart" not in st.session_state:
    st.session_state.cart = {}
if "temp_cust" not in st.session_state:
    st.session_state.temp_cust = ""
if "show_company_map" not in st.session_state:
    st.session_state.show_company_map = False
if "selected_company" not in st.session_state:
    st.session_state.selected_company = None
if "show_period_detail" not in st.session_state:
    st.session_state.show_period_detail = False

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
#part4
# ============================================================
# صفحة تسجيل الدخول (مع تشفير كلمات المرور)
# ============================================================

if not st.session_state.auth:
    st.markdown("""
    <div style="display: flex; justify-content: center; align-items: center; min-height: 80vh;">
        <div style="background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 30px; padding: 40px; width: 100%; max-width: 450px; text-align: center; box-shadow: 0 20px 40px rgba(0,0,0,0.2);">
            <div style="width: 80px; height: 80px; background: linear-gradient(135deg, #667eea, #764ba2); border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 20px;">
                <span style="font-size: 40px;">📅</span>
            </div>
            <h1 style="color: white;">PreView Ads</h1>
            <p style="color: rgba(255,255,255,0.7);">نظام إدارة الإعلانات</p>
    """, unsafe_allow_html=True)
    
    with st.form("login_form"):
        username = st.text_input("👤 اسم المستخدم", placeholder="أدخل اسم المستخدم")
        password = st.text_input("🔑 كلمة المرور", type="password", placeholder="أدخل كلمة المرور")
        submitted = st.form_submit_button("🚪 دخول", use_container_width=True)
        
        if submitted:
            if not username or not password:
                st.error("⚠️ يرجى إدخال اسم المستخدم وكلمة المرور")
            else:
                with st.spinner("🔄 جاري التحقق..."):
                    user = authenticate_user(username, password)
                    
                    if user:
                        st.session_state.auth = True
                        st.session_state.role = user['role']
                        st.session_state.username = user['username']
                        st.session_state.user_id = user['id']
                        st.session_state.full_name = user['full_name']
                        st.success(f"✅ مرحباً {user['full_name']}!")
                        st.rerun()
                    else:
                        st.error("❌ اسم المستخدم أو كلمة المرور غير صحيحة")
    
    st.markdown("</div></div>", unsafe_allow_html=True)
    st.stop()
#part5
# ============================================================
# الشريط الجانبي (مع تخزين الإحصائيات)
# ============================================================

@st.cache_data(ttl=300)
def get_sidebar_stats():
    """جلب الإحصائيات للشريط الجانبي مع تخزين مؤقت"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM \"اعمدة انارة\"")
        total_boards = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(DISTINCT \"اسم الزبون\") FROM \"حجوزات1\"")
        total_clients = cursor.fetchone()[0]
        return total_boards, total_clients
    finally:
        cursor.close()

with st.sidebar:
    st.markdown("""
    <div style="text-align: center; padding: 20px 0;">
        <div style="width: 80px; height: 80px; background: linear-gradient(135deg, #667eea, #764ba2); border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto;">
            <span style="font-size: 40px;">📅</span>
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
    
    st.radio("📋 القائمة الرئيسية", [
        "🏢 لوحات الشركات",
        "📍 الأعمدة المتاحة",
        "📅 لوحة الفترات",
        "📊 Dashboard",
        "📄 عرض سعر",
        "📋 تقرير الجرد",
        "📅 تقرير التوفر الشهري",
        "⚙️ الإعدادات"
    ], key="main_menu")
    
    st.divider()
    
    # إحصائيات سريعة مع Cache
    total_boards_sidebar, total_clients = get_sidebar_stats()
    
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.metric("🗺️ اللوحات", total_boards_sidebar)
    with col_s2:
        st.metric("👥 العملاء", total_clients)
    
    st.divider()
    
    if st.button("🚪 تسجيل الخروج", use_container_width=True):
        st.session_state.auth = False
        st.session_state.cart = {}
        st.rerun()
#part6
# ============================================================
# دوال استعلامات Supabase (مع تصحيحات Cache)
# ============================================================

@st.cache_data(ttl=300)
def get_company_bookings():
    """استرجاع بيانات الشركات المحجوزة مع تخزين مؤقت"""
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
    return run_query(query)

@st.cache_data(ttl=300)
def get_company_locations_with_map(company_name):
    """استرجاع مواقع شركة معينة مع الإحداثيات - مع تخزين مؤقت"""
    query = '''
        SELECT DISTINCT 
            b."رقم اللوحة",
            b."اسم العمود",
            b."المحافظة",
            b."الشبكة",
            b."الحجم",
            b."العدد",
            b."Latitude",
            b."Longitude"
        FROM "اعمدة انارة" b
        INNER JOIN "حجوزات1" h ON b."رقم اللوحة" = h."رقم اللوحة"
        WHERE h."اسم الزبون" = %s
    '''
    return run_query(query, (company_name,))

@st.cache_data(ttl=300)
def get_dashboard_data():
    """جلب جميع بيانات Dashboard دفعة واحدة مع تخزين مؤقت"""
    conn = get_connection()
    try:
        query = """
        SELECT 
            a."رقم اللوحة",
            a."اسم العمود",
            a."المحافظة",
            a."الشبكة",
            a."الحجم",
            a."العدد",
            a."Latitude",
            a."Longitude",
            CASE WHEN h."رقم اللوحة" IS NOT NULL THEN 'محجوز' ELSE 'متاح' END as الحالة
        FROM "اعمدة انارة" a
        LEFT JOIN "حجوزات1" h 
            ON a."رقم اللوحة" = h."رقم اللوحة" 
            AND h."العام" = %s
        """
        return pd.read_sql_query(query, conn, params=(datetime.now().year,))
    finally:
        conn.close()

@st.cache_data(ttl=300)
def get_available_by_city():
    """استرجاع الأعمدة المتاحة مجمعة حسب المحافظة مع تخزين مؤقت"""
    current_year = datetime.now().year
    
    query = """
        SELECT a.*, 
               CASE WHEN h."رقم اللوحة" IS NOT NULL THEN 1 ELSE 0 END as is_booked
        FROM "اعمدة انارة" a
        LEFT JOIN "حجوزات1" h 
            ON a."رقم اللوحة" = h."رقم اللوحة" 
            AND h."العام" = %s
    """
    df = run_query(query, (current_year,))
    
    if df is None or df.empty:
        return df
    
    available = df[df['is_booked'] == 0].copy()
    available.drop('is_booked', axis=1, inplace=True)
    
    def classify_size_for_card(size):
        size_str = str(size).strip()
        if size_str in ['2*1', '2x1', '2 × 1']:
            return 'أعمدة إنارة (2×1)'
        elif size_str in ['125*185', '125x185', '125 × 185']:
            return 'منصفات (125×185)'
        else:
            return 'أحجام أخرى'
    
    available['size_group'] = available['الحجم'].apply(classify_size_for_card)
    return available

@st.cache_data(ttl=60)
def get_expired_offers():
    """العروض المنتهية مع تخزين مؤقت قصير"""
    query = '''
        SELECT id, client_name, offer_date 
        FROM "offers_history" 
        WHERE status = 'Pending' AND offer_date < NOW() - INTERVAL '48 hours'
    '''
    return run_query(query)

def manage_expired_offers():
    """إدارة العروض المنتهية"""
    st.subheader("⚠️ إدارة العروض التي تجاوزت 48 ساعة")
    
    expired_df = get_expired_offers()
    
    if expired_df is None or expired_df.empty:
        st.success("✅ لا توجد عروض منتهية الصلاحية.")
        return
    
    for _, row in expired_df.iterrows():
        col1, col2, col3 = st.columns([3, 1, 1])
        col1.write(f"👤 الزبون: **{row['client_name']}** - تاريخ العرض: {row['offer_date']}")
        
        if is_admin():
            if col2.button("✅ تمديد 48 ساعة", key=f"ext_{row['id']}"):
                conn = get_connection()
                cur = conn.cursor()
                try:
                    cur.execute('UPDATE "offers_history" SET offer_date = NOW() WHERE id = %s', (row['id'],))
                    conn.commit()
                    st.success("تم التمديد بنجاح")
                    st.cache_data.clear()
                finally:
                    cur.close()
            
            if col3.button("❌ إلغاء العرض", key=f"del_{row['id']}"):
                conn = get_connection()
                cur = conn.cursor()
                try:
                    cur.execute('UPDATE "offers_history" SET status = %s WHERE id = %s', ('Cancelled', row['id']))
                    conn.commit()
                    st.success("تم إلغاء العرض")
                    st.cache_data.clear()
                finally:
                    cur.close()
        else:
            col2.write("🔒")
            col3.write("🔒")

@st.cache_data(ttl=3600)
def filter_valid_coordinates(df, lat_col='Latitude', lon_col='Longitude'):
    """تصفية البيانات للحصول على الإحداثيات الصالحة فقط مع تخزين مؤقت"""
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
#part7
# ============================================================
# بداية الهيكل الرئيسي للصفحات
# ============================================================

# الحصول على الصفحة المختارة من القائمة
page = st.session_state.get("main_menu", "🏢 لوحات الشركات")

# ============================================================
# صفحة: لوحات الشركات
# ============================================================

if page == "🏢 لوحات الشركات":
    st.title("🏢 لوحات الشركات المعلنة")
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    
    companies = get_company_bookings()
    
    if companies is None or companies.empty:
        st.warning("⚠️ لا توجد شركات معلنة حالياً")
    else:
        for idx, company in companies.iterrows():
            with st.container():
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.subheader(f"🏢 {company['company_name']}")
                with col2:
                    st.metric("📊 اللوحات", company['total_boards'])
                    st.metric("🗓️ الفترات", company['total_periods'])
                
                if st.button("🗺️ عرض الخريطة", key=f"map_{idx}"):
                    st.session_state['selected_company'] = company['company_name']
                    st.session_state['show_company_map'] = True
                
                st.divider()
    
    # عرض الخريطة للشركة المختارة
    if st.session_state.get('show_company_map', False):
        st.subheader(f"🗺️ مواقع شركة {st.session_state['selected_company']}")
        
        with st.spinner("🔄 جاري تحميل الخريطة..."):
            locations = get_company_locations_with_map(st.session_state['selected_company'])
            
            if locations is not None and not locations.empty:
                locations['Latitude'] = pd.to_numeric(locations['Latitude'], errors='coerce')
                locations['Longitude'] = pd.to_numeric(locations['Longitude'], errors='coerce')
                
                has_coords = filter_valid_coordinates(locations)
                
                if not has_coords.empty:
                    map_obj = create_company_map(st.session_state['selected_company'], has_coords)
                    if map_obj:
                        st_folium(map_obj, width="100%", height=500)
                else:
                    st.info("📍 لا توجد إحداثيات لعرضها على الخريطة")
            else:
                st.warning("⚠️ لا توجد مواقع لهذه الشركة")
        
        if st.button("🔙 إغلاق الخريطة"):
            st.session_state['show_company_map'] = False
            # تم إزالة st.rerun() غير الضروري

# ============================================================
# صفحة: الأعمدة المتاحة
# ============================================================

elif page == "📍 الأعمدة المتاحة":
    st.title("📍 الأعمدة المتاحة للإيجار")
    st.info("📅 عرض الأعمدة حسب حالة الإتاحة مع عدد اللوحات الفعلية")
    
    # استخدام st.form لمنع إعادة التحميل التلقائي
    with st.form(key="filter_form"):
        st.subheader("📅 فلتر تاريخ بداية الإتاحة")
        start_date = st.date_input(
            "عرض الأعمدة المتاحة من تاريخ:",
            value=date.today(),
            help="اختر التاريخ الذي تبدأ منه فترة الإتاحة"
        )
        submitted = st.form_submit_button("🔍 تطبيق الفلتر")
    
    if submitted:
        with st.spinner("🔄 جاري تحميل البيانات..."):
            target_period_num = get_period_from_date(start_date)
            target_year = start_date.year
            
            df = load_available_boards(target_period_num, target_year)
            
            # حساب الإحصائيات باستخدام groupby
            stats = df.groupby('status').agg({
                'رقم اللوحة': 'count',
                'العدد': 'sum'
            }).rename(columns={'رقم اللوحة': 'sites', 'العدد': 'boards'})
            
            # عرض الإحصائيات
            st.subheader("📊 إحصائيات عامة")
            
            status_colors = {
                '🟢 متاح فوراً': ('🟢 متاح فوراً', '#d4edda'),
                '🟡 متاح مؤقتاً': ('🟡 متاح مؤقتاً', '#fff3cd'),
                '🟠 محجوز مؤقتاً': ('🟠 محجوز مؤقتاً', '#ffe5d0'),
                '🔴 محجوز بالكامل': ('🔴 محجوز بالكامل', '#f8d7da')
            }
            
            cols = st.columns(4)
            for idx, (status, color) in enumerate(status_colors.items()):
                with cols[idx]:
                    if status in stats.index:
                        sites = stats.loc[status, 'sites']
                        boards = int(stats.loc[status, 'boards'])
                    else:
                        sites = 0
                        boards = 0
                    st.markdown(f"#### {status}")
                    st.metric("المواقع", sites)
                    st.metric("اللوحات", boards)
            
            st.divider()
            
            # عرض حسب المحافظة
            for city in df['المحافظة'].unique():
                city_data = df[df['المحافظة'] == city]
                
                with st.expander(f"🏙️ {city} - {len(city_data)} موقع", expanded=False):
                    display_df = city_data.copy()
                    
                    @st.cache_data(ttl=3600)
                    def period_to_text(period_num):
                        if pd.isna(period_num):
                            return ""
                        period_map = {
                            1: "1-15 كانون ثاني", 2: "16-30 كانون ثاني",
                            3: "1-15 شباط", 4: "16-28 شباط",
                            5: "1-15 آذار", 6: "16-31 آذار",
                            7: "1-15 نيسان", 8: "16-30 نيسان",
                            9: "1-15 أيار", 10: "16-31 أيار",
                            11: "1-15 حزيران", 12: "16-30 حزيران",
                            13: "1-15 تموز", 14: "16-31 تموز",
                            15: "1-15 آب", 16: "16-31 آب",
                            17: "1-15 أيلول", 18: "16-30 أيلول",
                            19: "1-15 تشرين أول", 20: "16-31 تشرين أول",
                            21: "1-15 تشرين ثاني", 22: "16-30 تشرين ثاني",
                            23: "1-15 كانون أول", 24: "16-31 كانون أول"
                        }
                        return period_map.get(period_num, f"فترة {period_num}")
                    
                    display_df['تاريخ البدء'] = display_df['next_booking_period'].apply(period_to_text)
                    display_df['تاريخ الانتهاء'] = display_df['end_booking_period'].apply(period_to_text)
                    
                    st.dataframe(
                        display_df[['رقم اللوحة', 'اسم العمود', 'الشبكة', 'الحجم', 'العدد', 'status', 'تاريخ البدء', 'تاريخ الانتهاء']],
                        use_container_width=True,
                        height=300
                    )
            
            # تصدير CSV
            csv_data = df[['رقم اللوحة', 'اسم العمود', 'المحافظة', 'الشبكة', 'الحجم', 'العدد', 'status']].to_csv(
                index=False, encoding='utf-8-sig'
            )
            st.download_button(
                "📥 تحميل التقرير (CSV)",
                csv_data,
                f"available_boards_{start_date.strftime('%Y%m%d')}.csv",
                "text/csv",
                use_container_width=True
            )

# ============================================================
# صفحة: لوحة الفترات
# ============================================================

elif page == "📅 لوحة الفترات":
    st.title("📅 لوحة التحكم البصرية للفترات")
    st.info("📅 عرض المتاح والمحجوز لكل فترة مع تفاصيل اللوحات المتاحة")
    
    # الحصول على الفترات
    PERIOD_ORDER = get_period_order()
    sorted_periods = sorted(PERIOD_ORDER.items(), key=lambda x: x[1])
    all_period_names = [p[0] for p in sorted_periods]
    
    # الفلاتر
    filter_options = get_filter_options()
    
    col_filter1, col_filter2 = st.columns(2)
    with col_filter1:
        selected_city = st.selectbox("🏙️ اختر المحافظة:", filter_options['cities'])
    with col_filter2:
        selected_size = st.selectbox("📏 اختر الحجم:", filter_options['sizes'])
    
    with st.spinner("🔄 جاري تحميل بيانات الفترات..."):
        boards_df, bookings_df = load_period_data(selected_city, selected_size, PERIOD_ORDER)
    
    # حساب الإحصائيات
    total_boards = boards_df['العدد'].sum()
    period_stats, period_details = calculate_period_stats(boards_df, bookings_df, sorted_periods)
    
    # عرض الإحصائيات العامة
    st.subheader("📊 إحصائيات عامة")
    col1, col2, col3 = st.columns(3)
    col1.metric("🏢 إجمالي اللوحات", int(total_boards))
    col2.metric("📅 عدد الفترات", len(all_period_names))
    col3.metric("👥 عدد الزبائن", bookings_df['اسم الزبون'].nunique())
    
    st.divider()
    
    # عرض الفترات
    st.subheader("📋 الفترات")
    
    for i in range(0, len(all_period_names), 4):
        cols = st.columns(4)
        for j, col in enumerate(cols):
            if i + j < len(all_period_names):
                period_name = all_period_names[i + j]
                stats = period_stats[i + j]
                
                with col:
                    if stats['محجوز'] == 0:
                        bg_color = "#e8f5e9"
                        border_color = "#4CAF50"
                    else:
                        bg_color = "#fff3e0"
                        border_color = "#FF9800"
                    
                    st.markdown(f"""
                    <div style="background:{bg_color};border:2px solid {border_color};border-radius:12px;padding:15px;text-align:center;margin:5px 0;">
                        <div style="font-size:14px;font-weight:bold;">{period_name}</div>
                        <div style="font-size:12px;margin-top:5px;">🟢 {stats['متاح']} | 🔴 {stats['محجوز']}</div>
                        <div style="font-size:11px;margin-top:5px;color:#666;">👥 {stats['الزبائن']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button(f"📋 تفاصيل", key=f"detail_{i+j}"):
                        st.session_state[f'selected_period_{i+j}'] = period_name
                        st.session_state['show_period_detail'] = True
    
    # التفاصيل للفترة المختارة
    if st.session_state.get('show_period_detail', False):
        selected_period = None
        for key in st.session_state:
            if key.startswith('selected_period_'):
                selected_period = st.session_state[key]
                break
        
        if selected_period and selected_period in period_details:
            details = period_details[selected_period]
            
            st.divider()
            st.subheader(f"📋 تفاصيل الفترة: {selected_period}")
            
            period_stat = next(p for p in period_stats if p['الفترة'] == selected_period)
            col1, col2, col3 = st.columns(3)
            col1.metric("📊 إجمالي اللوحات", period_stat['إجمالي اللوحات'])
            col2.metric("🔴 محجوز", period_stat['محجوز'])
            col3.metric("🟢 متاح", period_stat['متاح'])
            
            if len(details['customers']) > 0:
                st.write("**👥 الزبائن في هذه الفترة:**")
                st.write(", ".join(details['customers']))
            else:
                st.write("**👥 الزبائن في هذه الفترة:** لا يوجد")
            
            if not details['available_details'].empty:
                st.write("**📋 اللوحات المتاحة في هذه الفترة:**")
                st.dataframe(
                    details['available_details'][['رقم اللوحة', 'اسم العمود', 'المحافظة', 'الشبكة', 'الحجم', 'العدد']],
                    use_container_width=True
                )
            else:
                st.info("✅ لا توجد لوحات متاحة في هذه الفترة")
            
            if st.button("🔙 إغلاق التفاصيل", key="close_detail"):
                st.session_state['show_period_detail'] = False
                for key in list(st.session_state.keys()):
                    if key.startswith('selected_period_'):
                        del st.session_state[key]
    
    # الرسم البياني
    st.divider()
    st.subheader("📊 رسم بياني للمتاح والمحجوز")
    
    period_df = pd.DataFrame(period_stats)
    fig = create_period_chart(period_df)
    st.plotly_chart(fig, use_container_width=True)

# ============================================================
# صفحة: Dashboard
# ============================================================

elif page == "📊 Dashboard":
    st.markdown("""
    <div style="text-align: center; margin-bottom: 30px;">
        <h1>📊 لوحة التحكم المتقدمة</h1>
        <p style="color: rgba(255,255,255,0.7);">نظرة شاملة على أداء النظام وإحصائيات الإعلانات</p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.spinner("🔄 جاري تحميل البيانات..."):
        df = get_dashboard_data()
        stats = calculate_dashboard_stats(df)
    
    # عرض المقاييس
    cols = st.columns(4)
    metrics_data = [
        ("إجمالي اللوحات", stats['total_boards'], "🏢"),
        ("محجوز", stats['booked_boards'], "🔴"),
        ("متاح", stats['available_boards'], "🟢"),
        ("نسبة الإشغال", f"{stats['occupancy_rate']:.1f}%", "📈")
    ]
    
    for idx, (title, value, icon) in enumerate(metrics_data):
        with cols[idx]:
            st.metric(icon + " " + title, value)
    
    # شريط التقدم
    st.markdown("📊 نسبة الإشغال الحالية")
    st.progress(stats['occupancy_rate'] / 100)
    st.caption(f"{stats['occupancy_rate']:.1f}%")
    
    st.divider()
    
    # الرسوم البيانية
    with st.spinner("🔄 جاري تحميل الرسوم البيانية..."):
        fig_pie, fig_bar = create_dashboard_charts(stats)
    
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.subheader("🥧 نسبة الإشغال الكلية")
        st.plotly_chart(fig_pie, use_container_width=True)
    with col_chart2:
        st.subheader("📊 إحصائيات حسب المحافظة")
        st.plotly_chart(fig_bar, use_container_width=True)
    
    st.divider()
    
    # الخريطة
    st.subheader("🗺️ توزع اللوحات على الخريطة")
    with st.spinner("🔄 جاري تحميل الخريطة..."):
        map_obj = create_dashboard_map(df)
        if map_obj:
            st_folium(map_obj, width="100%", height=500)
        else:
            st.warning("⚠️ لا توجد إحداثيات صالحة لعرضها على الخريطة")

# ============================================================
# صفحة: تقرير الجرد
# ============================================================

elif page == "📋 تقرير الجرد":
    st.title("📋 التقرير التجميعي - جرد اللوحات")
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    
    try:
        with st.spinner("🔄 جاري تحميل البيانات..."):
            periods_df = get_periods()
            period_names = periods_df['namee'].tolist()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            from_period = st.selectbox("من فترة:", period_names, key="from_period")
        with col2:
            to_period = st.selectbox("إلى فترة:", period_names, index=len(period_names)-1, key="to_period")
        with col3:
            report_year = st.number_input("العام:", value=datetime.now().year, key="report_year")
        
        if st.button("🚀 تشغيل التقرير", use_container_width=True):
            with st.spinner("🔄 جاري إنشاء التقرير..."):
                from_idx = int(periods_df[periods_df['namee'] == from_period]['no'].iloc[0])
                to_idx = int(periods_df[periods_df['namee'] == to_period]['no'].iloc[0])
                
                all_boards = get_all_boards_for_inventory()
                booked_in_period = get_booked_boards_for_period(report_year, from_idx, to_idx)
                
                stats = calculate_inventory_stats(all_boards, booked_in_period)
                
                # عرض المقاييس
                cols = st.columns(4)
                metrics_data = [
                    ("🏢 إجمالي المواقع", stats['total_sites']),
                    ("🔴 المواقع المحجوزة", stats['booked_sites']),
                    ("🟢 المواقع المتاحة", stats['available_sites']),
                    ("📈 نسبة الإشغال", f"{(stats['booked_sites']/stats['total_sites']*100):.1f}%" if stats['total_sites'] > 0 else "0%")
                ]
                
                for idx, (title, value) in enumerate(metrics_data):
                    with cols[idx]:
                        st.metric(title, value)
                
                st.divider()
                
                # الرسوم البيانية
                fig_pie, fig_bar = create_inventory_charts(stats)
                col_chart1, col_chart2 = st.columns(2)
                with col_chart1:
                    st.plotly_chart(fig_pie, use_container_width=True)
                with col_chart2:
                    st.plotly_chart(fig_bar, use_container_width=True)
                
                st.divider()
                
                # تفصيل حسب المحافظة
                st.subheader("📋 تفصيل حسب المحافظة")
                city_details = stats['city_stats'].reset_index()
                city_details['occupancy_rate'] = city_details['occupancy_rate'].round(1).astype(str) + '%'
                st.dataframe(city_details, use_container_width=True)
                
                # تصدير
                csv_data = stats['all_boards'].to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    "📊 تصدير إلى CSV", 
                    csv_data, 
                    f"Inventory_Report_{report_year}.csv", 
                    "text/csv", 
                    use_container_width=True
                )
                
    except Exception as e:
        st.error(f"حدث خطأ في التقرير: {str(e)}")

# ============================================================
# صفحة: تقرير التوفر الشهري
# ============================================================

elif page == "📅 تقرير التوفر الشهري":
    st.title("📋 تقرير الأعمدة المتاحة")
    st.info("📅 يعرض هذا التقرير الأعمدة المتاحة حالياً أو التي ستصبح متاحة بعد تاريخ محدد")
    
    current_year = date.today().year
    today = date.today()
    
    # تخزين التاريخ في session_state
    if 'report_date' not in st.session_state:
        st.session_state.report_date = today
    
    # استخدام st.form لمنع إعادة التحميل التلقائي
    with st.form(key="availability_report_form"):
        col_filter1, col_filter2 = st.columns(2)
        with col_filter1:
            show_all = st.checkbox("📅 عرض جميع الأعمدة المتاحة حالياً", value=True)
        with col_filter2:
            future_date = st.date_input("🗓️ عرض الأعمدة التي ستصبح متاحة بعد تاريخ", value=today + timedelta(days=7))
        
        notes = st.text_area("📝 ملاحظات (تظهر في نهاية التقرير)", placeholder="أضف ملاحظاتك هنا...", height=100)
        submitted = st.form_submit_button("🚀 تشغيل التقرير", use_container_width=True, type="primary")
    
    if submitted:
        with st.spinner("🔄 جاري إنشاء التقرير..."):
            all_columns = run_query('SELECT "رقم اللوحة", "اسم العمود", "المحافظة", "الشبكة", "الحجم", "العدد" FROM "اعمدة انارة"')
            
            if show_all:
                bookings_query = 'SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" WHERE "العام" = %s'
                booked_df = run_query(bookings_query, (current_year,))
            else:
                bookings_query = '''
                    SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" 
                    WHERE "العام" = %s
                    AND ("تاريخ النهاية" >= %s OR "فترة الحجز" IS NOT NULL)
                '''
                booked_df = run_query(bookings_query, (current_year, future_date))
            
            booked_boards = booked_df['رقم اللوحة'].tolist() if booked_df is not None and not booked_df.empty else []
            
            available_df = all_columns[~all_columns['رقم اللوحة'].isin(booked_boards)]
            total_available = len(available_df)
            total_boards_count = available_df['العدد'].sum() if 'العدد' in available_df.columns else total_available
            
            st.success(f"✅ {total_available} موقعاً ({int(total_boards_count)} لوحة) متاحة")
            
            # عرض إحصائيات سريعة
            col1, col2, col3 = st.columns(3)
            col1.metric("📍 المواقع المتاحة", total_available)
            col2.metric("📅 اللوحات المتاحة", int(total_boards_count))
            col3.metric("🏙️ المحافظات", len(available_df['المحافظة'].unique()))
            
            st.subheader("📊 ملخص حسب المحافظة")
            summary = available_df.groupby('المحافظة').agg({
                'رقم اللوحة': 'count',
                'العدد': 'sum'
            }).rename(columns={'رقم اللوحة': 'عدد المواقع', 'العدد': 'عدد اللوحات'})
            
            total_available_boards = summary['عدد اللوحات'].sum()
            summary['النسبة المئوية'] = (summary['عدد اللوحات'] / total_available_boards * 100).round(1).astype(str) + '%'
            st.dataframe(summary, use_container_width=True)
            
            st.subheader("📋 قائمة الأعمدة المتاحة")
            
            # إضافة Search Box
            search_term = st.text_input("🔍 بحث في الأعمدة المتاحة", placeholder="رقم اللوحة أو اسم العمود...")
            if search_term:
                filtered_df = available_df[
                    available_df['رقم اللوحة'].astype(str).str.contains(search_term, case=False) |
                    available_df['اسم العمود'].str.contains(search_term, case=False, na=False)
                ]
            else:
                filtered_df = available_df
            
            st.dataframe(
                filtered_df[['رقم اللوحة', 'اسم العمود', 'المحافظة', 'الشبكة', 'الحجم', 'العدد']], 
                use_container_width=True, 
                height=400
            )
            
            if notes:
                st.info(f"📝 الملاحظات: {notes}")
            
            # استخدام التاريخ المخزن في اسم الملف
            csv_data = available_df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                "📥 تحميل التقرير (CSV)", 
                csv_data, 
                f"available_columns_{st.session_state.report_date.strftime('%Y%m%d')}.csv",
                "text/csv", 
                use_container_width=True
            )

# ============================================================
# صفحة: الإعدادات
# ============================================================

elif page == "⚙️ الإعدادات":
    if not is_admin():
        st.error("⛔ هذه الصفحة مخصصة للمديرين فقط")
        st.stop()
    
    st.title("⚙️ إعدادات النظام - إدارة البيانات")
    st.warning("⚠️ تحذير: تعديل هذه البيانات يؤثر مباشرة على النظام. يرجى الحذر.")
    
    @st.cache_data(ttl=300)
    def get_admin_stats():
        """جلب إحصائيات الإعدادات مع تخزين مؤقت"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM \"اعمدة انارة\"")
            boards_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM \"حجوزات1\"")
            bookings_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM \"اسماء الرسم\"")
            fees_count = cursor.fetchone()[0]
            return boards_count, bookings_count, fees_count
        finally:
            cursor.close()
    
    boards_count, bookings_count, fees_count = get_admin_stats()
    
    cols = st.columns(3)
    with cols[0]:
        st.metric("🗺️ أعمدة الإنارة", boards_count)
    with cols[1]:
        st.metric("📅 الحجوزات", bookings_count)
    with cols[2]:
        st.metric("💰 أجور الرسم", fees_count)
    
    st.divider()
    
    @st.cache_data(ttl=60)
    def get_boards_data():
        return run_query('SELECT * FROM "اعمدة انارة" ORDER BY "المحافظة", "الشبكة"')
    
    @st.cache_data(ttl=60)
    def get_bookings_data():
        return run_query('SELECT * FROM "حجوزات1"')
    
    @st.cache_data(ttl=60)
    def get_fees_data():
        return run_query('SELECT * FROM "اسماء الرسم"')
    
    @st.cache_data(ttl=60)
    def get_users_data():
        return run_query('SELECT id, username, role, full_name, created_at FROM users')
    
    def save_data_with_upsert(table_name, df, columns, conflict_column):
        """حفظ البيانات باستخدام UPSERT"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            for _, row in df.iterrows():
                placeholders = ','.join(['%s'] * len(columns))
                updates = ','.join([f'"{col}" = EXCLUDED."{col}"' for col in columns if col != conflict_column])
                query = f'''
                    INSERT INTO "{table_name}" ({','.join([f'"{col}"' for col in columns])})
                    VALUES ({placeholders})
                    ON CONFLICT ("{conflict_column}") 
                    DO UPDATE SET {updates}
                '''
                cursor.execute(query, [row[col] for col in columns])
            conn.commit()
            st.success(f"✅ تم تحديث {table_name}")
            st.cache_data.clear()
        except Exception as e:
            conn.rollback()
            st.error(f"❌ خطأ في الحفظ: {str(e)}")
        finally:
            cursor.close()
    
    tab1, tab2, tab3, tab4 = st.tabs(["🗄️ أعمدة الإنارة", "📅 سجل الحجوزات", "💰 أجور الرسم", "👥 المستخدمين"])
    
    with tab1:
        st.subheader("إدارة بيانات أعمدة الإنارة")
        df_boards = get_boards_data()
        edited_boards = st.data_editor(df_boards, num_rows="dynamic", key="edit_boards", use_container_width=True)
        if st.button("💾 حفظ أعمدة الإنارة", key="save_boards", use_container_width=True):
            if st.checkbox("☑️ تأكيد حفظ البيانات"):
                save_data_with_upsert(
                    "اعمدة انارة", 
                    edited_boards, 
                    ['رقم اللوحة', 'اسم العمود', 'المحافظة', 'الشبكة', 'الحجم', 'العدد', 'Latitude', 'Longitude'],
                    'رقم اللوحة'
                )
            else:
                st.warning("⚠️ يرجى تأكيد الحفظ أولاً")
    
    with tab2:
        st.subheader("إدارة سجل الحجوزات")
        df_bookings = get_bookings_data()
        edited_bookings = st.data_editor(df_bookings, num_rows="dynamic", key="edit_bookings", use_container_width=True)
        if st.button("💾 حفظ سجل الحجوزات", key="save_bookings", use_container_width=True):
            if st.checkbox("☑️ تأكيد حفظ البيانات", key="confirm_bookings"):
                save_data_with_upsert(
                    "حجوزات1", 
                    edited_bookings, 
                    ['رقم اللوحة', 'اسم الزبون', 'العام', 'فترة الحجز', 'تاريخ النهاية'],
                    'رقم اللوحة'
                )
            else:
                st.warning("⚠️ يرجى تأكيد الحفظ أولاً")
    
    with tab3:
        st.subheader("إدارة أجور الرسم")
        st.info("💡 أضف 'اجور الطباعة عادي' و 'اجور الطباعة سكوتش' و 'اجور العرض شهري' و 'اجور العرض اجنبي شهري'")
        df_fees = get_fees_data()
        edited_fees = st.data_editor(df_fees, num_rows="dynamic", key="edit_fees", use_container_width=True)
        if st.button("💾 حفظ أجور الرسم", key="save_fees", use_container_width=True):
            if st.checkbox("☑️ تأكيد حفظ البيانات", key="confirm_fees"):
                save_data_with_upsert(
                    "اسماء الرسم", 
                    edited_fees, 
                    ['اسم الرسم', 'الحجم', 'اجرة الرسم'],
                    'اسم الرسم'
                )
            else:
                st.warning("⚠️ يرجى تأكيد الحفظ أولاً")
    
    with tab4:
        st.subheader("👥 إدارة المستخدمين")
        df_users = get_users_data()
        edited_users = st.data_editor(df_users, num_rows="dynamic", key="edit_users", use_container_width=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 حفظ المستخدمين", key="save_users", use_container_width=True):
                if st.checkbox("☑️ تأكيد حفظ البيانات", key="confirm_users"):
                    conn = get_connection()
                    cursor = conn.cursor()
                    try:
                        for _, row in edited_users.iterrows():
                            cursor.execute('''
                                UPDATE users SET username=%s, role=%s, full_name=%s WHERE id=%s
                            ''', (row['username'], row['role'], row['full_name'], row['id']))
                        conn.commit()
                        st.success("✅ تم تحديث المستخدمين")
                        st.cache_data.clear()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"❌ خطأ: {str(e)}")
                    finally:
                        cursor.close()
                else:
                    st.warning("⚠️ يرجى تأكيد الحفظ أولاً")
        
        with col2:
            with st.expander("➕ إضافة مستخدم جديد"):
                new_username = st.text_input("اسم المستخدم")
                new_password = st.text_input("كلمة المرور", type="password")
                new_role = st.selectbox("الدور", ["admin", "employee"])
                new_full_name = st.text_input("الاسم الكامل")
                if st.button("إضافة مستخدم", use_container_width=True):
                    if new_username and new_password:
                        conn = get_connection()
                        cursor = conn.cursor()
                        try:
                            hashed_password = hash_password(new_password)
                            cursor.execute('''
                                INSERT INTO users (username, password, role, full_name, created_at)
                                VALUES (%s, %s, %s, %s, NOW())
                            ''', (new_username, hashed_password, new_role, new_full_name))
                            conn.commit()
                            st.success("✅ تم إضافة المستخدم")
                            st.cache_data.clear()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"خطأ: {e}")
                        finally:
                            cursor.close()
                    else:
                        st.warning("⚠️ يرجى إدخال اسم المستخدم وكلمة المرور")

# ============================================================
# نهاية الملف - تم حذف conn.close() نهائياً
# ============================================================
# ✅ تم حذف conn.close() - الاتصال يدار بواسطة @st.cache_resource

# ============================================================
# نهاية الملف - تم حذف conn.close() نهائياً
# ============================================================
# ✅ تم حذف conn.close() - الاتصال يدار بواسطة @st.cache_resource
