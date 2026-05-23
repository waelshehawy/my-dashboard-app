# utils/database.py
import os
import pandas as pd
import psycopg2
from psycopg2 import pool
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from dotenv import load_dotenv
import streamlit as st

load_dotenv()

class DatabaseManager:
    """مدير اتصال قاعدة البيانات"""
    
    _instance = None
    _pool = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._pool is None:
            self._init_pool()
    
    def _init_pool(self):
        """تهيئة تجمع الاتصالات"""
        try:
            self._pool = psycopg2.pool.SimpleConnectionPool(
                1, 20,
                host=os.getenv("SUPABASE_URL", "aws-1-eu-north-1.pooler.supabase.com"),
                port="6543",
                database="postgres",
                user=os.getenv("SUPABASE_USER", "postgres.ncuofpvbaglwbdqnpman"),
                password=os.getenv("SUPABASE_PASSWORD", "WaelPreview2026"),
                sslmode="require"
            )
        except Exception as e:
            st.error(f"❌ فشل الاتصال بقاعدة البيانات: {e}")
    
    def get_connection(self):
        """الحصول على اتصال من التجمع"""
        if self._pool:
            return self._pool.getconn()
        return None
    
    def return_connection(self, conn):
        """إعادة الاتصال إلى التجمع"""
        if self._pool and conn:
            self._pool.putconn(conn)
    
    def execute_query(self, query, params=None, fetch=True):
        """تنفيذ استعلام SQL"""
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            
            if fetch and query.strip().upper().startswith('SELECT'):
                result = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                return pd.DataFrame(result, columns=columns)
            else:
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            self.return_connection(conn)
    
    def get_dataframe(self, table_name, conditions=None):
        """استرجاع جدول كامل كـ DataFrame"""
        query = f'SELECT * FROM "{table_name}"'
        if conditions:
            query += f" WHERE {conditions}"
        return self.execute_query(query)
    
    def insert_dataframe(self, table_name, df, conflict_handling='ignore'):
        """إدخال DataFrame إلى الجدول"""
        if df.empty:
            return 0
        
        conn = self.get_connection()
        if not conn:
            return 0
        
        try:
            cursor = conn.cursor()
            columns = ', '.join([f'"{col}"' for col in df.columns])
            placeholders = ', '.join(['%s'] * len(df.columns))
            
            base_query = f'INSERT INTO "{table_name}" ({columns}) VALUES ({placeholders})'
            if conflict_handling == 'ignore':
                base_query += ' ON CONFLICT DO NOTHING'
            elif conflict_handling == 'update':
                updates = ', '.join([f'"{col}" = EXCLUDED."{col}"' for col in df.columns])
                base_query += f' ON CONFLICT (id) DO UPDATE SET {updates}'
            
            for _, row in df.iterrows():
                cursor.execute(base_query, tuple(row))
            
            conn.commit()
            return len(df)
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            self.return_connection(conn)
    
    def get_engine(self):
        """الحصول على محرك SQLAlchemy"""
        url_obj = URL.create(
            drivername="postgresql+psycopg2",
            username=os.getenv("SUPABASE_USER", "postgres.ncuofpvbaglwbdqnpman"),
            password=os.getenv("SUPABASE_PASSWORD", "WaelPreview2026"),
            host=os.getenv("SUPABASE_URL", "aws-1-eu-north-1.pooler.supabase.com"),
            port="6543",
            database="postgres",
        )
        return create_engine(url_obj, connect_args={'sslmode': 'require'})

# إنشاء نسخة عامة من مدير قاعدة البيانات
db_manager = DatabaseManager()

def get_connection():
    """دالة مساعدة للتوافق مع الكود القديم"""
    return db_manager.get_connection()

def get_engine():
    """دالة مساعدة للتوافق مع الكود القديم"""
    return db_manager.get_engine()
#جزء2

# utils/auth.py
import streamlit as st
import pandas as pd
from utils.database import db_manager

def authenticate_user(username, password):
    """مصادقة المستخدم"""
    query = """
        SELECT username, password, role, full_name 
        FROM app_users 
        WHERE username = %s AND password = %s AND active = true
    """
    result = db_manager.execute_query(query, (username, password))
    
    if result is not None and not result.empty:
        return result.iloc[0]
    return None

def is_admin():
    """التحقق مما إذا كان المستخدم مديراً"""
    return st.session_state.get('role') == 'admin'

def is_employee():
    """التحقق مما إذا كان المستخدم موظفاً"""
    return st.session_state.get('role') == 'employee'

def require_auth():
    """يتطلب مصادقة المستخدم"""
    if not st.session_state.get('auth', False):
        st.switch_page("app.py")
        st.stop()

def require_admin():
    """يتطلب صلاحيات المدير"""
    require_auth()
    if not is_admin():
        st.error("⛔ هذه الصفحة مخصصة للمديرين فقط")
        st.stop()

def login_form():
    """عرض نموذج تسجيل الدخول"""
    st.markdown("""
    <div style="
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 80vh;
    ">
        <div style="
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 30px;
            padding: 40px;
            width: 100%;
            max-width: 450px;
            text-align: center;
            box-shadow: 0 20px 40px rgba(0,0,0,0.2);
        ">
            <div style="
                width: 80px;
                height: 80px;
                background: linear-gradient(135deg, #667eea, #764ba2);
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                margin: 0 auto 20px;
            ">
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
            user = authenticate_user(username, password)
            if user:
                st.session_state.auth = True
                st.session_state.role = user['role']
                st.session_state.username = user['username']
                st.session_state.full_name = user['full_name']
                st.rerun()
            else:
                st.error("❌ اسم المستخدم أو كلمة المرور غير صحيحة")
    
    st.markdown("</div></div>", unsafe_allow_html=True)
#جزء3

# utils/styles.py
import streamlit as st

ADVANCED_CSS = """
<style>
    /* ========== متغيرات الألوان ========== */
    :root {
        --primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        --success-gradient: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        --danger-gradient: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        --warning-gradient: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
    }
    
    /* ========== خلفية متحركة ========== */
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
    
    /* ========== الشريط الجانبي ========== */
    [data-testid="stSidebar"] {
        background: rgba(26, 26, 46, 0.95) !important;
        backdrop-filter: blur(12px) !important;
        border-right: 1px solid rgba(255,255,255,0.2) !important;
    }
    
    [data-testid="stSidebar"] * {
        color: white !important;
    }
    
    /* ========== بطاقات Neumorphism ========== */
    .neumorphic-card {
        background: linear-gradient(145deg, #e6e9f0, #ffffff);
        border-radius: 28px;
        box-shadow: 12px 12px 24px rgba(0,0,0,0.1),
                   -12px -12px 24px rgba(255,255,255,0.7);
        padding: 20px;
        margin: 15px 0;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    .neumorphic-card:hover {
        transform: translateY(-8px);
        box-shadow: 20px 20px 40px rgba(0,0,0,0.15),
                   -20px -20px 40px rgba(255,255,255,0.8);
    }
    
    /* ========== بطاقات إحصائيات ========== */
    .stat-card-3d {
        background: var(--primary-gradient);
        border-radius: 20px;
        padding: 20px;
        text-align: center;
        color: white;
        position: relative;
        overflow: hidden;
        transition: transform 0.3s ease;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    }
    
    .stat-card-3d:hover {
        transform: translateY(-5px) scale(1.02);
    }
    
    .stat-number-3d {
        font-size: 48px;
        font-weight: bold;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        animation: numberPulse 2s ease-in-out infinite;
    }
    
    @keyframes numberPulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.05); text-shadow: 0 0 20px rgba(255,255,255,0.5); }
    }
    
    /* ========== أزرار متحركة ========== */
    .stButton > button {
        background: linear-gradient(45deg, #667eea, #764ba2) !important;
        border: none !important;
        border-radius: 50px !important;
        padding: 10px 24px !important;
        color: white !important;
        font-weight: bold !important;
        transition: all 0.3s ease !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-3px) !important;
        box-shadow: 0 10px 20px rgba(102,126,234,0.4) !important;
    }
    
    /* ========== شارات ملونة ========== */
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
"""

def apply_styles():
    """تطبيق الأنماط على التطبيق"""
    st.set_page_config(
        page_title="PreView Ads ERP - نظام إدارة الإعلانات",
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    st.markdown(ADVANCED_CSS, unsafe_allow_html=True)

def create_metric_card(title, value, icon, color="primary"):
    """إنشاء بطاقة إحصائية"""
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
    
    card_html = f"""
    <div class="stat-card-3d" style="background: {gradients.get(color, gradients['primary'])}">
        <div style="font-size: 36px; opacity: 0.8;">{icon}</div>
        <div class="stat-number-3d">{formatted_value}</div>
        <div style="font-size: 14px; opacity: 0.9;">{title}</div>
    </div>
    """
    return card_html

def badge_animated(text, badge_type="info"):
    """إنشاء شارة متحركة"""
    return f'<span class="badge-animated badge-{badge_type}">{text}</span>'
#جزء4

# utils/helpers.py
import pandas as pd
from datetime import datetime, date, timedelta

def safe_split(value):
    """تقسيم آمن للنصوص - يتعامل مع القيم الفارغة"""
    if value is None or pd.isna(value):
        return []
    if isinstance(value, float):
        return []
    value_str = str(value)
    if value_str in ['', 'nan', 'None', 'NaN']:
        return []
    return [v.strip() for v in value_str.split(',') if v.strip()]

def filter_valid_coordinates(df, lat_col='Latitude', lon_col='Longitude'):
    """تصفية البيانات للحصول على الإحداثيات الصالحة فقط"""
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

def get_current_period():
    """الحصول على الفترة الحالية (1-24)"""
    day = datetime.now().timetuple().tm_yday
    period = ((day - 1) // 15) + 1
    return min(period, 24)

def get_current_year():
    """الحصول على العام الحالي"""
    return datetime.now().year

def format_currency(amount):
    """تنسيق العملة"""
    return f"{amount:,.2f} $"

def calculate_periods_count(start_period, end_period, periods_list):
    """حساب عدد الفترات بين فترتين"""
    start_idx = periods_list.index(start_period)
    end_idx = periods_list.index(end_period)
    periods_count = abs(end_idx - start_idx) + 1
    days_count = periods_count * 15
    months_count = periods_count / 2
    return periods_count, days_count, months_count

# إحداثيات سوريا للخريطة
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
#جزء5
# utils/word_export.py
import io
from datetime import datetime
from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

def _force_rtl_style(p):
    """تطبيق نمط RTL على الفقرة"""
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
    """تطبيق نمط RTL على الجدول"""
    tblPr = table._element.xpath('w:tblPr')[0]
    bidi = OxmlElement('w:bidiVisual')
    tblPr.append(bidi)

def export_offer_to_word(customer_name, cart_data, start_p, end_p, 
                         grand_total_print, grand_total_display, 
                         discount_percent=0, final_total=0):
    """تصدير عرض السعر إلى ملف Word"""
    doc = Document('template.docx') if os.path.exists('template.docx') else Document()
    PURPLE_COLOR = "660099"
    
    today_date = datetime.now().strftime("%d / %m / %Y")
    
    # التاريخ
    p_date = doc.add_paragraph()
    p_date.add_run(f"التاريخ: {today_date}")
    _force_rtl_style(p_date)
    doc.add_paragraph()
    
    # اسم الزبون
    p_cust = doc.add_paragraph()
    p_cust.add_run(f"السادة شركة {customer_name} المحترمين").bold = True
    _force_rtl_style(p_cust)
    
    # نص العرض
    p_stat = doc.add_paragraph()
    p_stat.add_run(f"نقدم لكم المواقع المتاحة لعرض إعلانكم الوطني من فترة ({start_p}) ولغاية ({end_p})")
    _force_rtl_style(p_stat)
    
    # تفاصيل المواقع
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
                fp = float(group_df['fee_print'].iloc[0]) if 'fee_print' in group_df.columns else 0
                fd = float(group_df['fee_display'].iloc[0]) if 'fee_display' in group_df.columns else 0
                sum_print = total_q * fp
                sum_display = total_q * fd
                
                p_fin = doc.add_paragraph()
                txt = (f"إجمالي العدد: {int(total_q)} | "
                       f"أجور الطباعة: {sum_print:,.0f}$ | "
                       f"أجور العرض: {sum_display:,.0f}$ | "
                       f"المجموع: {sum_print + sum_display:,.0f}$")
                p_fin.add_run(txt).bold = True
                _force_rtl_style(p_fin)
    
    doc.add_paragraph()
    
    # تفاصيل الحسم
    if discount_percent > 0:
        p_discount = doc.add_paragraph()
        p_discount.add_run(f"إجمالي أجور الطباعة: {grand_total_print:,.0f} $").bold = True
        _force_rtl_style(p_discount)
        
        p_discount = doc.add_paragraph()
        p_discount.add_run(f"إجمالي أجور العرض قبل الحسم: {grand_total_display:,.0f} $").bold = True
        _force_rtl_style(p_discount)
        
        discount_amount = grand_total_display * (discount_percent / 100)
        p_discount = doc.add_paragraph()
        p_discount.add_run(f"حسم {discount_percent}% على أجور العرض: - {discount_amount:,.0f} $").bold = True
        _force_rtl_style(p_discount)
    else:
        p_total_print = doc.add_paragraph()
        p_total_print.add_run(f"إجمالي أجور الطباعة: {grand_total_print:,.0f} $").bold = True
        _force_rtl_style(p_total_print)
        
        p_total_display = doc.add_paragraph()
        p_total_display.add_run(f"إجمالي أجور العرض: {grand_total_display:,.0f} $").bold = True
        _force_rtl_style(p_total_display)
    
    doc.add_paragraph()
    
    # الإجمالي النهائي
    p_grand = doc.add_paragraph()
    run_g = p_grand.add_run(f"الإجمالي النهائي للعرض: {final_total:,.0f} $")
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
#جزء6

# app.py
import streamlit as st
import sys
import os

# إضافة المسار للوصول إلى الوحدات
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.styles import apply_styles
from utils.auth import login_form, require_auth
from utils.database import db_manager

# تهيئة حالة الجلسة
if "auth" not in st.session_state:
    st.session_state.auth = False
if "cart" not in st.session_state:
    st.session_state.cart = {}
if "temp_cust" not in st.session_state:
    st.session_state.temp_cust = ""

# تطبيق الأنماط
apply_styles()

# صفحة تسجيل الدخول
if not st.session_state.auth:
    login_form()
    st.stop()

# بعد تسجيل الدخول، عرض التطبيق الرئيسي
from utils.auth import is_admin
from utils.styles import create_metric_card, badge_animated

# الشريط الجانبي
with st.sidebar:
    st.markdown("""
    <div style="text-align: center; padding: 20px 0;">
        <div style="
            width: 80px;
            height: 80px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto;
        ">
            <span style="font-size: 40px;">🎯</span>
        </div>
        <h2 style="color: white; margin-top: 15px;">PreView Ads</h2>
        <p style="color: #a0a0a0; font-size: 12px;">نظام إدارة الإعلانات v2.0</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    # معلومات المستخدم
    user_icon = "👑" if is_admin() else "👤"
    st.markdown(f"""
    <div style="background: rgba(255,255,255,0.1); border-radius: 15px; padding: 15px; text-align: center; margin: 10px 0;">
        <div style="font-size: 30px;">{user_icon}</div>
        <div style="font-weight: bold;">{st.session_state.get('username', '')}</div>
        <div style="font-size: 12px; opacity: 0.7;">{'مدير النظام' if is_admin() else 'موظف'}</div>
    </div>
    """, unsafe_allow_html=True)
    
    # إحصائيات سريعة
    cursor = db_manager.get_connection()
    if cursor:
        cur = cursor.cursor()
        cur.execute('SELECT COUNT(*) FROM "اعمدة انارة"')
        total_boards_sidebar = cur.fetchone()[0]
        cur.execute('SELECT COUNT(DISTINCT "اسم الزبون") FROM "حجوزات1"')
        total_clients = cur.fetchone()[0]
        cur.close()
    
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.markdown(create_metric_card("اللوحات", total_boards_sidebar, "🗺️", "primary"), unsafe_allow_html=True)
    with col_s2:
        st.markdown(create_metric_card("العملاء", total_clients, "👥", "success"), unsafe_allow_html=True)
    
    st.divider()
    
    if st.button("🚪 تسجيل الخروج", use_container_width=True):
        st.session_state.auth = False
        st.session_state.cart = {}
        st.rerun()

# القائمة الرئيسية
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

# توجيه إلى الصفحات
if page == "📊 Dashboard":
    from pages import dashboard
    dashboard.show()
elif page == "🏢 لوحات الشركات":
    from pages import companies
    companies.show()
elif page == "📍 الأعمدة المتاحة":
    from pages import available_columns
    available_columns.show()
elif page == "📄 عرض سعر":
    from pages import offer_price
    offer_price.show()
elif page == "📋 تقرير الجرد":
    from pages import inventory_report
    inventory_report.show()
elif page == "📅 تقرير التوفر الشهري":
    from pages import monthly_report
    monthly_report.show()
elif page == "🗺️ تقرير جميع المواقع":
    from pages import locations_report
    locations_report.show()
elif page == "📐 تقرير تجميعي حسب الحجوم":
    from pages import sizes_report
    sizes_report.show()
elif page == "⚙️ الإعدادات":
    from pages import settings
    settings.show()
#جزء7

-- supabase/migrations.sql
-- هيكل قاعدة البيانات لـ Supabase

-- جدول المستخدمين
CREATE TABLE IF NOT EXISTS app_users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'employee',
    full_name VARCHAR(200),
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- جدول أعمدة الإنارة
CREATE TABLE IF NOT EXISTS "اعمدة انارة" (
    "رقم اللوحة" VARCHAR(100) PRIMARY KEY,
    "اسم العمود" VARCHAR(200),
    "المحافظة" VARCHAR(100),
    "الشبكة" VARCHAR(100),
    "الحجم" VARCHAR(50),
    "العدد" INTEGER DEFAULT 1,
    "Latitude" DECIMAL(10, 8),
    "Longitude" DECIMAL(11, 8),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- جدول الحجوزات
CREATE TABLE IF NOT EXISTS "حجوزات1" (
    id SERIAL PRIMARY KEY,
    "رقم اللوحة" VARCHAR(100),
    "اسم الزبون" VARCHAR(200),
    "العام" INTEGER,
    "فترة الحجز" VARCHAR(50),
    "تاريخ النهاية" DATE,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY ("رقم اللوحة") REFERENCES "اعمدة انارة"("رقم اللوحة") ON DELETE CASCADE
);

-- جدول أجور الرسم
CREATE TABLE IF NOT EXISTS "اسماء الرسم" (
    id SERIAL PRIMARY KEY,
    "اسم الرسم" VARCHAR(200),
    "الحجم" VARCHAR(50),
    "اجرة الرسم" DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT NOW()
);

-- جدول الفترات
CREATE TABLE IF NOT EXISTS "الفترة" (
    id SERIAL PRIMARY KEY,
    "no" INTEGER,
    "namee" VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- جدول عروض الأسعار
CREATE TABLE IF NOT EXISTS "offers_history" (
    id SERIAL PRIMARY KEY,
    "client_name" VARCHAR(200),
    "cart_json" JSONB,
    "status" VARCHAR(50) DEFAULT 'Pending',
    "start_p" VARCHAR(50),
    "end_p" VARCHAR(50),
    "year" INTEGER,
    "offer_date" TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

-- إنشاء الفهارس
CREATE INDEX IF NOT EXISTS idx_bookings_board ON "حجوزات1"("رقم اللوحة");
CREATE INDEX IF NOT EXISTS idx_bookings_client ON "حجوزات1"("اسم الزبون");
CREATE INDEX IF NOT EXISTS idx_bookings_year_period ON "حجوزات1"("العام", "فترة الحجز");
CREATE INDEX IF NOT EXISTS idx_offers_client ON "offers_history"("client_name");
CREATE INDEX IF NOT EXISTS idx_offers_status ON "offers_history"("status");

-- إدخال بيانات الفترات الأولية (1-24)
INSERT INTO "الفترة" ("no", "namee") VALUES
(1, 'فترة 1'), (2, 'فترة 2'), (3, 'فترة 3'), (4, 'فترة 4'),
(5, 'فترة 5'), (6, 'فترة 6'), (7, 'فترة 7'), (8, 'فترة 8'),
(9, 'فترة 9'), (10, 'فترة 10'), (11, 'فترة 11'), (12, 'فترة 12'),
(13, 'فترة 13'), (14, 'فترة 14'), (15, 'فترة 15'), (16, 'فترة 16'),
(17, 'فترة 17'), (18, 'فترة 18'), (19, 'فترة 19'), (20, 'فترة 20'),
(21, 'فترة 21'), (22, 'فترة 22'), (23, 'فترة 23'), (24, 'فترة 24')
ON CONFLICT (id) DO NOTHING;

-- إدخال مستخدم افتراضي
INSERT INTO app_users (username, password, role, full_name, active) 
VALUES ('admin', 'admin123', 'admin', 'مدير النظام', true)
ON CONFLICT (username) DO NOTHING;

-- دالة لتحديث updated_at تلقائياً
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- تطبيق الدالة على الجداول
CREATE TRIGGER update_app_users_updated_at 
    BEFORE UPDATE ON app_users 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_اعمدة_انارة_updated_at 
    BEFORE UPDATE ON "اعمدة انارة" 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
#جزء8

# pages/dashboard.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from utils.database import db_manager
from utils.styles import create_metric_card
from utils.helpers import SYRIA_COORDS
from datetime import datetime
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster

def show():
    st.markdown("""
    <div style="text-align: center; margin-bottom: 30px;">
        <h1>📊 لوحة التحكم المتقدمة</h1>
        <p style="color: rgba(255,255,255,0.7);">نظرة شاملة على أداء النظام وإحصائيات الإعلانات</p>
    </div>
    """, unsafe_allow_html=True)
    
    current_year = datetime.now().year
    
    # استرجاع البيانات
    all_columns = db_manager.get_dataframe("اعمدة انارة")
    
    if all_columns.empty:
        st.warning("⚠️ لا توجد بيانات لعرضها")
        return
    
    # استرجاع الحجوزات
    booked_query = f'SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" WHERE "العام" = {current_year}'
    booked_df = db_manager.execute_query(booked_query)
    
    booked_boards_list = booked_df['رقم اللوحة'].tolist() if booked_df is not None and not booked_df.empty else []
    
    all_columns['الحالة'] = all_columns['رقم اللوحة'].apply(lambda x: 'محجوز' if x in booked_boards_list else 'متاح')
    
    total_boards = all_columns['العدد'].sum()
    booked_boards = all_columns[all_columns['الحالة'] == 'محجوز']['العدد'].sum()
    available_boards = total_boards - booked_boards
    occupancy_rate = (booked_boards / total_boards * 100) if total_boards > 0 else 0
    
    # عرض البطاقات
    cols = st.columns(4)
    metrics_data = [
        ("إجمالي اللوحات", total_boards, "🏢", "primary"),
        ("محجوز", booked_boards, "🔴", "danger"),
        ("متاح", available_boards, "🟢", "success"),
        ("نسبة الإشغال", f"{occupancy_rate:.1f}%", "📈", "warning")
    ]
    
    for idx, (title, value, icon, color) in enumerate(metrics_data):
        with cols[idx]:
            st.markdown(create_metric_card(title, value, icon, color), unsafe_allow_html=True)
    
    # شريط تقدم
    st.markdown(f"""
    <div style="margin: 20px 0;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
            <span>📊 نسبة الإشغال الحالية</span>
            <span style="font-weight: bold;">{occupancy_rate:.1f}%</span>
        </div>
        <div style="height: 12px; background: rgba(0,0,0,0.1); border-radius: 10px; overflow: hidden;">
            <div style="width: {occupancy_rate}%; height: 100%; background: linear-gradient(90deg, #667eea, #764ba2); border-radius: 10px;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    # رسوم بيانية
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.subheader("🥧 نسبة الإشغال الكلية")
        fig_pie = go.Figure(data=[go.Pie(
            labels=['محجوز', 'متاح'],
            values=[booked_boards, available_boards],
            hole=0.4,
            marker_colors=['#dc2626', '#22c55e'],
            textinfo='percent+label',
            textposition='auto'
        )])
        fig_pie.update_layout(height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col_chart2:
        st.subheader("📊 إحصائيات حسب المحافظة")
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
                         color='نسبة الإشغال', color_continuous_scale='RdYlGn',
                         title='نسبة الإشغال حسب المحافظة')
        fig_bar.update_layout(height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_bar, use_container_width=True)
    
    st.divider()
    
    # الخريطة
    st.subheader("🗺️ توزع اللوحات على الخريطة")
    
    all_columns_map = db_manager.get_dataframe("اعمدة انارة")
    all_columns_map['الحالة'] = all_columns_map['رقم اللوحة'].apply(lambda x: 'محجوز' if x in booked_boards_list else 'متاح')
    
    m = folium.Map(location=SYRIA_COORDS["سوريا"], zoom_start=7)
    marker_cluster = MarkerCluster().add_to(m)
    
    for _, row in all_columns_map.iterrows():
        if pd.notnull(row.get('Latitude')) and pd.notnull(row.get('Longitude')) and row.get('Latitude') != 0:
            popup_html = f"""
            <div dir="rtl" style="font-family:Arial;text-align:right;min-width:250px;background:white;border-radius:10px;overflow:hidden;">
                <div style="background:linear-gradient(135deg,#667eea,#764ba2);padding:10px;color:white;">
                    <b>🏢 {row['اسم العمود']}</b>
                </div>
                <div style="padding:10px;">
                    📍 {row['المحافظة']}<br>
                    📡 {row['الشبكة']}<br>
                    📏 {row['الحجم']}<br>
                    🔢 {row['العدد']} لوحة
                </div>
            </div>
            """
            
            folium.Marker(
                [row['Latitude'], row['Longitude']],
                popup=folium.Popup(popup_html, max_width=350),
                icon=folium.Icon(color='red' if row['الحالة'] == 'محجوز' else 'green')
            ).add_to(marker_cluster)
    
    st_folium(m, width="100%", height=500)
#جزء9
