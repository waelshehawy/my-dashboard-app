# app.py - النسخة النهائية للإنترنت مع Supabase
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
        password=os.environ.get("SUPABASE_PASSWORD", "W@elPreview2026"),
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
# الاتصال بقاعدة البيانات بعد تسجيل الدخول
# ============================================================

conn = get_connection()

# ============================================================
# الشريط الجانبي
# ============================================================

import streamlit as st
import io
import json
import requests
import speech_recognition as sr
from streamlit_mic_recorder import mic_recorder

# ============================================================
# الشريط الجانبي المطور مع المساعد الذكي
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

    # 🎙️ إضافة المساعد الصوتي في مكان استراتيجي ثابت
# 🎙️ المساعد الصوتي الذكي في الشريط الجانبي
st.markdown("<p style='text-align: center; font-weight: bold; color: #667eea;'>🎙️ المساعد الصوتي الذكي</p>", unsafe_allow_html=True)

# عرض زر المايك
audio = mic_recorder(
    start_prompt="إصدار أمر صوتي 🎤",
    stop_prompt="إيقاف ومعالجة ⏹️",
    key='sidebar_recorder'
)

# هنا نضمن الرد في كل الأحوال
if audio:
    audio_file = io.BytesIO(audio['bytes'])
    r = sr.Recognizer()
    
    # رسالة فورية للمستخدم تشير إلى أن النظام استلم الملف ويقوم بمعالجته الآن
    with st.status("⏳ جاري تحويل صوتك إلى نص...", expanded=True) as status:
        with sr.AudioFile(audio_file) as source:
            # تقليل الضوضاء لرفع دقة العامية
            r.adjust_for_ambient_noise(source, duration=0.5)
            audio_data = r.record(source)
            
            try:
                # محاولة تحويل الصوت
                user_text = r.recognize_google(audio_data, language='ar-SA')
                status.update(label=f"🟢 تم التقاط النص بنجاح!", state="complete", expanded=False)
                
                # طباعة الكلام المفهوم فوراً ليرى المدير أن كلامه وُجد
                st.chat_message("user").write(user_text)
                
                # --- إرسال النص إلى Gemini API ---
                with st.spinner("🧠 جاري تفكيك النية وتوليد الـ SQL..."):
                    GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY") or "ضع_مفتاحك_هنا"
                   # الرابط المحدث لتوجه الاستعلام مباشرة إلى نموذج Flash-Light السريع
gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flashlite:generateContent?key= AQ.Ab8RN6I6OJfePZP_-ww95Qp_SiQJ2V29BCVYANEZ9LOJYbil3w "
                    
                    payload = {"contents": [{"parts": [{"text": user_text}]}]}
                    response = requests.post(gemini_url, json=payload, timeout=10)
                    
                    if response.status_code == 200:
                        ai_result = response.json()['candidates'][0]['content']['parts'][0]['text']
                        clean_json = ai_result.replace("```json", "").replace("```", "").strip()
                        parsed_data = json.loads(clean_json)
                        
                        # تخزين البيانات في الـ session
                        st.session_state['ai_intent'] = parsed_data.get('intent')
                        st.session_state['ai_sql'] = parsed_data.get('extracted_sql')
                        st.session_state['ai_package_details'] = parsed_data.get('package_details')
                        
                        # رد الذكاء الاصطناعي التفاعلي المكتوب
                        st.chat_message("assistant").write(parsed_data.get('spoken_response', 'تمت العملية بنجاح.'))
                    else:
                        st.error("❌ استجاب سيرفر الذكاء الاصطناعي بخطأ، يرجى التحقق من المفتاح.")
                        
            except sr.UnknownValueError:
                # الرد الإجباري في حال عدم فهم الصوت
                status.update(label="❌ لم أستطع سماع أي كلام!", state="error", expanded=True)
                st.warning("⚠️ يبدو أن الصوت لم يكن واضحاً أو المايك بعيد. يرجى الضغط مجدداً والتحدث عن قرب.")
                
            except sr.RequestError:
                status.update(label="❌ خطأ في الاتصال بالشبكة!", state="error", expanded=True)
                st.error("🌐 تعذر الوصول إلى محرك تحويل الصوت. تحقق من اتصال الإنترنت الخاص بك.")
                
            except Exception as e:
                status.update(label="❌ حدث خطأ غير متوقع!", state="error", expanded=True)
                st.error(f"تفاصيل الخطأ: {e}")

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
    
    # إحصائيات سريعة
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM \"اعمدة انارة\"")
    total_boards_sidebar = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT \"اسم الزبون\") FROM \"حجوزات1\"")
    total_clients = cursor.fetchone()[0]
    cursor.close()
    
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.markdown(create_metric_card_3d("اللوحات", total_boards_sidebar, "🗺️", "primary"), unsafe_allow_html=True)
    with col_s2:
        st.markdown(create_metric_card_3d("العملاء", total_clients, "success"), unsafe_allow_html=True)
    
    st.divider()
    
    if st.button("🚪 تسجيل الخروج", use_container_width=True):
        st.session_state.auth = False
        st.session_state.cart = {}
        st.rerun()
import pandas as pd
import io
import docx  # مكتبة python-docx لتوليد الوورد

# ------------------------------------------------------------
# 🔍 منطقة مراجعة وتنفيذ الاستعلام الذكي
# ------------------------------------------------------------

# التحقق من أن الذكاء الاصطناعي قد استخرج استعلاماً وحفظه في الـ Session
if 'ai_sql' in st.session_state and st.session_state['ai_sql']:
    st.markdown("---")
    st.markdown("### 🔍 مراجعة وتأكيد استعلام المساعد الذكي")
    
    # عرض رد الذكاء الاصطناعي للمدير
    if 'spoken_response' in st.session_state:
        st.info(f"💡 **مساعد PreView:** {st.session_state['spoken_response']}")
    
    # منطقة نصية تتيح للمدير رؤية الـ SQL وتعديله يدوياً لو أراد بكل حرية
    editable_sql = st.text_area(
        "تعديل كود الاستعلام (SQL) إذا لزم الأمر:", 
        value=st.session_state['ai_sql'], 
        height=150
    )
    
    # زر التنفيذ والحسم
    if st.button("🚀 تنفيذ الاستعلام وجلب البيانات الحالية", use_container_width=True):
        with st.spinner("جاري الاتصال بـ Supabase وجلب البيانات..."):
            try:
                # فتح الاتصال بالقاعدة باستخدام دالتك الخاصة
                conn = get_connection()
                
                # تنفيذ الاستعلام وقراءة النتائج مباشرة في Pandas DataFrame
                df_results = pd.read_sql_query(editable_sql, conn)
                
                # إغلاق الاتصال فوراً للحفاظ على موارد الـ Pooler
                conn.close()
                
                if df_results.empty:
                    st.warning("⚠️ الاستعلام تم بنجاح، ولكن لا توجد سجلات مطابقة للبحث في قاعدة البيانات.")
                else:
                    st.success(f"📊 تم العثور على {len(df_results)} سجل بنجاح!")
                    
                    # عرض الجدول تفاعلياً أمام المدير للمعاينة الفورية
                    st.dataframe(df_results, use_container_width=True)
                    
                    # قراءة نية المدير المحددة من Gemini لتحديد نوع الملف
                    intent = st.session_state.get('ai_intent', 'استعلام_عادي')
                    
                    # --------------------------------------------------------
                    # 📄 الحالة الأولى: الطلب يتضمن "عرض سعر" -> المخرج Word
                    # --------------------------------------------------------
                    if "عرض" in intent or "سعر" in intent:
                        st.markdown("#### 📥 تحميل عرض السعر الجاهز")
                        
                        # إنشاء ملف الوورد في الذاكرة
                        doc = docx.Document()
                        doc.add_heading('عرض سعر لوحات إعلانية - PreView Ads', level=0)
                        doc.add_paragraph('بناءً على طلبكم، نرفق لكم تفاصيل اللوحات المتاحة وأسعار العروض:')
                        
                        # توليد جدول داخل ملف الوورد ومملوئه بالبيانات المجلوبة
                        table = doc.add_table(rows=1, cols=len(df_results.columns))
                        hdr_cells = table.rows[0].cells
                        for i, col_name in enumerate(df_results.columns):
                            hdr_cells[i].text = str(col_name)
                            
                        for index, row in df_results.iterrows():
                            row_cells = table.add_row().cells
                            for i, item in enumerate(row):
                                row_cells[i].text = str(item)
                        
                        # حفظ الملف في البافر (الذاكرة) دون لمس الهارد ديسك للحماية
                        word_buffer = io.BytesIO()
                        doc.save(word_buffer)
                        word_buffer.seek(0)
                        
                        st.download_button(
                            label="تحميل ملف عرض السعر (Word) 📄",
                            data=word_buffer,
                            file_name="عرض_سعر_preview_ads.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True
                        )
                        
                    # --------------------------------------------------------
                    # 📊 الحالة الثانية: استعلام بيانات عادي -> المخرج Excel
                    # --------------------------------------------------------
                    else:
                        st.markdown("#### 📥 تحميل تقرير البيانات الجاهز")
                        
                        # إنشاء ملف الإكسيل في الذاكرة
                        excel_buffer = io.BytesIO()
                        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                            df_results.to_excel(writer, index=False, sheet_name='التقرير المستخرج')
                        excel_buffer.seek(0)
                        
                        st.download_button(
                            label="تحميل التقرير بصيغة (Excel) 📊",
                            data=excel_buffer,
                            file_name="تقرير_بيانات_preview_ads.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                        
            except Exception as e:
                st.error(f"❌ خطأ أثناء تنفيذ الاستعلام في Supabase: {e}")
# ============================================================
# دوال استعلامات Supabase (بصيغة PostgreSQL)
# ============================================================

def run_query(query, params=None, fetch=True):
    """تنفيذ استعلام على Supabase"""
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

def get_company_bookings():
    """استرجاع بيانات الشركات المحجوزة"""
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

def get_company_locations_with_map(company_name):
    """استرجاع مواقع شركة معينة مع الإحداثيات"""
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

def get_available_by_city():
    """استرجاع الأعمدة المتاحة مجمعة حسب المحافظة"""
    current_year = datetime.now().year
    
    booked_query = 'SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" WHERE "العام" = %s'
    booked_df = run_query(booked_query, (current_year,))
    booked_boards = booked_df['رقم اللوحة'].tolist() if booked_df is not None and not booked_df.empty else []
    
    all_columns = run_query('SELECT * FROM "اعمدة انارة"')
    
    available = all_columns[~all_columns['رقم اللوحة'].isin(booked_boards)]
    
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

def manage_expired_offers():
    """إدارة العروض المنتهية"""
    st.subheader("⚠️ إدارة العروض التي تجاوزت 48 ساعة")
    
    query = '''
        SELECT id, client_name, offer_date 
        FROM "offers_history" 
        WHERE status = 'Pending' AND offer_date < NOW() - INTERVAL '48 hours'
    '''
    expired_df = run_query(query)
    
    if expired_df is None or expired_df.empty:
        st.success("✅ لا توجد عروض منتهية الصلاحية.")
        return
    
    for _, row in expired_df.iterrows():
        col1, col2, col3 = st.columns([3, 1, 1])
        col1.write(f"👤 الزبون: **{row['client_name']}** - تاريخ العرض: {row['offer_date']}")
        
        if is_admin():
            if col2.button("✅ تمديد 48 ساعة", key=f"ext_{row['id']}"):
                cur = conn.cursor()
                cur.execute('UPDATE "offers_history" SET offer_date = NOW() WHERE id = %s', (row['id'],))
                conn.commit()
                cur.close()
                st.success("تم التمديد بنجاح")
                st.rerun()
            
            if col3.button("❌ إلغاء العرض", key=f"del_{row['id']}"):
                cur = conn.cursor()
                cur.execute('UPDATE "offers_history" SET status = %s WHERE id = %s', ('Cancelled', row['id']))
                conn.commit()
                cur.close()
                st.success("تم إلغاء العرض")
                st.rerun()
        else:
            col2.write("🔒")
            col3.write("🔒")

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

# ============================================================
# عرض الصفحات
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
    
    # عرض الخريطة للشركة المختارة
    if st.session_state.get('show_company_map', False):
        st.subheader(f"🗺️ مواقع شركة {st.session_state['selected_company']}")
        
        locations = get_company_locations_with_map(st.session_state['selected_company'])
        
        if locations is not None and not locations.empty:
            locations['Latitude'] = pd.to_numeric(locations['Latitude'], errors='coerce')
            locations['Longitude'] = pd.to_numeric(locations['Longitude'], errors='coerce')
            
            has_coords = locations[
                (locations['Latitude'].notna()) & 
                (locations['Latitude'] != 0) &
                (locations['Longitude'].notna()) & 
                (locations['Longitude'] != 0)
            ].copy()
            
            if not has_coords.empty:
                m = folium.Map(location=[34.8, 38.9], zoom_start=7)
                
                for _, row in has_coords.iterrows():
                    folium.CircleMarker(
                        location=[row['Latitude'], row['Longitude']],
                        radius=8,
                        popup=f"""
                        <div dir="rtl" style="text-align:right; min-width:180px;">
                            <b>{row['اسم العمود']}</b><br>
                            📍 {row['المحافظة']}<br>
                            📏 {row['الحجم']}
                        </div>
                        """,
                        color='#22c55e',
                        fill=True,
                        fill_color='#22c55e',
                        fill_opacity=0.7,
                        weight=2
                    ).add_to(m)
                
                st_folium(m, width="100%", height=500)
            else:
                st.info("📍 لا توجد إحداثيات لعرضها على الخريطة")
        else:
            st.warning("⚠️ لا توجد مواقع لهذه الشركة")
        
        if st.button("🔙 إغلاق الخريطة"):
            st.session_state['show_company_map'] = False
            st.rerun()

elif page == "📍 الأعمدة المتاحة":
    st.title("📍 الأعمدة المتاحة للإيجار")
    st.info("📌 عرض جميع الأعمدة المتاحة في كل المحافظات مع خيار التصفية")
    
    # جلب جميع الأعمدة المتاحة
    available_data = get_available_by_city()
    
    if available_data is None or available_data.empty:
        st.warning("⚠️ لا توجد أعمدة متاحة حالياً")
        st.stop()
    
    # ============================================================
    # خيارات التصفية
    # ============================================================
    col_filter1, col_filter2, col_filter3 = st.columns(3)
    
    with col_filter1:
        # خيار عرض الكل أو محافظة محددة
        cities_list = ["🌍 جميع المحافظات"] + sorted(available_data['المحافظة'].unique().tolist())
        selected_filter = st.selectbox("🔍 تصفية حسب المحافظة:", cities_list)
    
    with col_filter2:
        # تصفية حسب نوع الحجم
        size_types = ["📏 جميع الأحجام", "📏 أعمدة إنارة (2×1)", "📏 منصفات (125×185)", "📏 أحجام أخرى"]
        selected_size_filter = st.selectbox("🔍 تصفية حسب الحجم:", size_types)
    
    with col_filter3:
        # عرض إحصائيات سريعة
        total_available = len(available_data)
        total_boards = available_data['العدد'].sum()
        st.metric("📊 إجمالي الأعمدة المتاحة", f"{total_available:,} موقع")
        st.caption(f"🔢 إجمالي عدد اللوحات: {int(total_boards):,}")
    
    st.divider()
    
    # ============================================================
    # تطبيق التصفية
    # ============================================================
    filtered_data = available_data.copy()
    
    # تصفية حسب المحافظة
    if selected_filter != "🌍 جميع المحافظات":
        filtered_data = filtered_data[filtered_data['المحافظة'] == selected_filter]
    
    # تصفية حسب الحجم
    if selected_size_filter == "📏 أعمدة إنارة (2×1)":
        filtered_data = filtered_data[filtered_data['size_group'] == 'أعمدة إنارة (2×1)']
    elif selected_size_filter == "📏 منصفات (125×185)":
        filtered_data = filtered_data[filtered_data['size_group'] == 'منصفات (125×185)']
    elif selected_size_filter == "📏 أحجام أخرى":
        filtered_data = filtered_data[filtered_data['size_group'] == 'أحجام أخرى']
    
    # ============================================================
    # عرض النتائج
    # ============================================================
    if filtered_data.empty:
        st.warning("⚠️ لا توجد نتائج تطابق معايير التصفية")
    else:
        # إحصائيات النتائج
        st.subheader(f"📊 النتائج ({len(filtered_data)} موقع - {filtered_data['العدد'].sum()} لوحة)")
        
        # عرض الجدول الكامل للنتائج
        st.dataframe(
            filtered_data[['رقم اللوحة', 'اسم العمود', 'المحافظة', 'الشبكة', 'الحجم', 'العدد']],
            use_container_width=True,
            height=400
        )
        
        st.divider()
        
        # ============================================================
        # عرض ملخص حسب المحافظة (للنتائج)
        # ============================================================
        st.subheader("📋 ملخص حسب المحافظة")
        summary = filtered_data.groupby('المحافظة').agg({
            'رقم اللوحة': 'count',
            'العدد': 'sum'
        }).rename(columns={'رقم اللوحة': 'عدد المواقع', 'العدد': 'عدد اللوحات'})
        st.dataframe(summary, use_container_width=True)
        
        st.divider()
        
        # ============================================================
        # عرض ملخص حسب نوع الحجم (للنتائج)
        # ============================================================
        st.subheader("📋 ملخص حسب نوع الحجم")
        size_summary = filtered_data.groupby('size_group').agg({
            'رقم اللوحة': 'count',
            'العدد': 'sum'
        }).rename(columns={'رقم اللوحة': 'عدد المواقع', 'العدد': 'عدد اللوحات'})
        st.dataframe(size_summary, use_container_width=True)
        
        # ============================================================
        # خريطة تفاعلية (عند اختيار محافظة محددة)
        # ============================================================
        if selected_filter != "🌍 جميع المحافظات":
            st.divider()
            st.subheader(f"🗺️ خريطة الأعمدة المتاحة في {selected_filter}")
            
            # تصفية الإحداثيات الصالحة
            valid_coords = filtered_data[
                filtered_data['Latitude'].notna() & 
                (filtered_data['Latitude'] != 0) &
                filtered_data['Longitude'].notna() & 
                (filtered_data['Longitude'] != 0)
            ].copy()
            
            if not valid_coords.empty:
                import folium
                from streamlit_folium import st_folium
                
                # تحديد مركز الخريطة حسب المحافظة المختارة
                city_coords = SYRIA_COORDS.get(selected_filter, SYRIA_COORDS["سوريا"])
                m = folium.Map(location=city_coords, zoom_start=10)
                
                for _, row in valid_coords.iterrows():
                    folium.Marker(
                        [row['Latitude'], row['Longitude']],
                        popup=f"""
                        <b>{row['اسم العمود']}</b><br>
                        📍 {row['المحافظة']}<br>
                        📡 {row['الشبكة']}<br>
                        📏 {row['الحجم']}
                        """,
                        icon=folium.Icon(color='green', icon='info-sign')
                    ).add_to(m)
                
                st_folium(m, width="100%", height=500)
            else:
                st.info("📍 لا توجد إحداثيات لعرضها على الخريطة للمحافظة المختارة")
        
        # ============================================================
        # تصدير التقرير
        # ============================================================
        st.divider()
        csv_data = filtered_data.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            "📥 تحميل التقرير (CSV)", 
            csv_data, 
            f"available_columns_{selected_filter.replace(' ', '_')}_{date.today().strftime('%Y%m%d')}.csv", 
            "text/csv", 
            use_container_width=True
        )

elif page == "📊 Dashboard":
    st.markdown("""
    <div style="text-align: center; margin-bottom: 30px;">
        <h1>📊 لوحة التحكم المتقدمة</h1>
        <p style="color: rgba(255,255,255,0.7);">نظرة شاملة على أداء النظام وإحصائيات الإعلانات</p>
    </div>
    """, unsafe_allow_html=True)
    
    current_year = datetime.now().year
    
    all_columns = run_query('SELECT "رقم اللوحة", "المحافظة", "الشبكة", "الحجم", "العدد" FROM "اعمدة انارة"')
    
    booked_query = 'SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" WHERE "العام" = %s'
    booked_df = run_query(booked_query, (current_year,))
    
    booked_boards_list = booked_df['رقم اللوحة'].tolist() if booked_df is not None and not booked_df.empty else []
    
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
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.subheader("🥧 نسبة الإشغال الكلية")
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
                         color='نسبة الإشغال', color_continuous_scale='RdYlGn')
        fig_bar.update_layout(height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_bar, use_container_width=True)
    
    st.divider()
    
    st.subheader("🗺️ توزع اللوحات على الخريطة")
    all_columns_map = run_query('SELECT * FROM "اعمدة انارة"')
    
    m = folium.Map(location=SYRIA_COORDS["سوريا"], zoom_start=7)
    marker_cluster = MarkerCluster().add_to(m)
    
    for _, row in all_columns_map.iterrows():
        if pd.notnull(row.get('Latitude')) and pd.notnull(row.get('Longitude')) and row.get('Latitude') != 0:
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
                [row['Latitude'], row['Longitude']],
                popup=folium.Popup(popup_html, max_width=350),
                icon=folium.Icon(color='green')
            ).add_to(marker_cluster)
    
    st_folium(m, width="100%", height=500)

elif page == "📄 عرض سعر":
    st.title("📄 بناء عرض سعر جديد")
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    
    try:
        with st.expander("🔔 العروض المنتهية (تحتاج إلى إجراء)", expanded=False):
            manage_expired_offers()
        
        st.subheader("📂 استرجاع عرض محفوظ")
        saved_offers = run_query('SELECT id, client_name, offer_date, start_p, end_p, year, status FROM "offers_history" WHERE status = %s ORDER BY id DESC', ('Pending',))
        
        if saved_offers is not None and not saved_offers.empty:
            offer_options = {}
            for _, row in saved_offers.iterrows():
                # طريقة آمنة تماماً للحصول على التاريخ
                offer_date = row['offer_date']
                try:
                    # محاولة التحويل إلى string
                    date_str = str(offer_date)[:10] if offer_date else "بدون تاريخ"
                except:
                    date_str = "بدون تاريخ"
                offer_options[f"{row['client_name']} ({date_str})"] = row['id']
            
            selected_offer = st.selectbox("اختر عرضاً محفوظاً:", ["---"] + list(offer_options.keys()), key="load_offer_select")
            
            if selected_offer != "---" and st.button("🔄 تحميل للسلة", key="load_offer_button", use_container_width=True):
                try:
                    offer_id = offer_options[selected_offer]
                    result = run_query('SELECT cart_json, client_name, start_p, end_p, year FROM "offers_history" WHERE id = %s', (offer_id,))
                    
                    if result is not None and not result.empty:
                        row = result.iloc[0]
                        data = json.loads(row['cart_json'])
                        cart_raw = data.get("data", data)
                        st.session_state.cart = {}
                        for city, networks in cart_raw.items():
                            st.session_state.cart[city] = {}
                            for net, df_dict in networks.items():
                                st.session_state.cart[city][net] = pd.DataFrame(df_dict)
                        
                        st.session_state.temp_cust = row['client_name']
                        st.success("✅ تم تحميل العرض بنجاح")
                        st.rerun()
                except Exception as e:
                    st.error(f"خطأ في تحميل العرض: {str(e)}")
        
        st.divider()
        
        draw_df = run_query('SELECT * FROM "اسماء الرسم"')
        
        customer_name = st.text_input("🏢 اسم الزبون", value=st.session_state.get('temp_cust', ""), placeholder="أدخل اسم الشركة أو الزبون")
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
            start_p = st.selectbox("📅 من فترة:", period_names, key="start_period")
        with col_p2:
            end_p = st.selectbox("📅 إلى فترة:", period_names, index=len(period_names)-1, key="end_period")
        
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
        - أجر الطباعة الثابت: **{fee_print}$**
        - أجر العرض الشهري: **{fee_ads}$**
        - المدة: **{months_count:.1f} شهر**
        - الإجمالي لكل عمود: **{per_column_total:.2f}$**
        """)
        
        st.divider()
        st.subheader("📍 اختيار المواقع")
        
        cities = run_query('SELECT DISTINCT "المحافظة" FROM "اعمدة انارة"')['المحافظة'].tolist()
        selected_city = st.selectbox("اختر المحافظة:", cities)
        
        available_columns = run_query('''
            SELECT "رقم اللوحة", "اسم العمود" as "الموقع", "العدد", "الشبكة", "الحجم" 
            FROM "اعمدة انارة" 
            WHERE "المحافظة" = %s AND "الحجم" = %s
        ''', (selected_city, selected_size))
        
        period_placeholders = ','.join([f"'{p}'" for p in selected_periods])
        booked_query = f'''
            SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" 
            WHERE "العام" = %s 
            AND "فترة الحجز" IN ({period_placeholders})
        '''
        booked_df = run_query(booked_query, (year,))
        booked_boards = booked_df['رقم اللوحة'].tolist() if booked_df is not None and not booked_df.empty else []
        
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
                st.success("✅ تمت الإضافة")
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
                        fp = float(edited_df['fee_print'].iloc[0]) if 'fee_print' in edited_df.columns else per_column_print
                        fd = float(edited_df['fee_display'].iloc[0]) if 'fee_display' in edited_df.columns else per_column_display
                        
                        section_print = qty * fp
                        section_display = qty * fd
                        
                        grand_total_print += section_print
                        grand_total_display += section_display
                        
                        st.info(f"📊 العدد: {qty} | الطباعة: {section_print:.2f}$ | العرض: {section_display:.2f}$")
                        
                        if st.button("🗑️ حذف", key=f"delete_{city}_{net}"):
                            del st.session_state.cart[city][net]
                            st.rerun()
            
            st.divider()
            
            st.subheader("💰 خيارات الحسم")
            
            col_disc1, col_disc2 = st.columns([1, 2])
            with col_disc1:
                apply_discount = st.checkbox("🏷️ تطبيق حسم على أجور العرض فقط")
            with col_disc2:
                discount_percent = 0
                if apply_discount:
                    discount_percent = st.slider("نسبة الحسم (%)", min_value=1, max_value=99, value=10, step=1)
            
            if apply_discount and discount_percent > 0:
                discount_amount = grand_total_display * (discount_percent / 100)
                grand_total_display_after = grand_total_display - discount_amount
                grand_total = grand_total_print + grand_total_display_after
                
                st.info(f"""
                💰 **تفاصيل الفاتورة:**
                - إجمالي أجور الطباعة: **{grand_total_print:,.2f} $**
                - إجمالي أجور العرض (قبل الحسم): **{grand_total_display:,.2f} $**
                - حسم **{discount_percent}%**: **- {discount_amount:,.2f} $**
                - إجمالي أجور العرض (بعد الحسم): **{grand_total_display_after:,.2f} $**
                """)
            else:
                grand_total = grand_total_print + grand_total_display
                st.info(f"""
                💰 **تفاصيل الفاتورة:**
                - إجمالي أجور الطباعة: **{grand_total_print:,.2f} $**
                - إجمالي أجور العرض: **{grand_total_display:,.2f} $**
                """)
            
            st.success(f"## 💰 الإجمالي النهائي: {grand_total:,.2f} $")
            
            col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)
            
            with col_btn1:
                if st.button("💾 حفظ كمسودة", use_container_width=True, key="save_draft"):
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
                                                    VALUES (%s, %s, %s, %s)
                                                ''', (str(row['رقم اللوحة']), customer_name, year, period))
                                
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
                    discount = discount_percent if apply_discount else 0
                    
                    doc = Document('template.docx') if os.path.exists('template.docx') else Document()
                    PURPLE_COLOR = "660099"
                    
                    discount_amount = grand_total_display * (discount / 100)
                    grand_total_display_after = grand_total_display - discount_amount
                    final_total = grand_total_print + grand_total_display_after
                    
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
                    
                    for city, networks in st.session_state.cart.items():
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
                                fp = float(group_df['fee_print'].iloc[0])
                                fd = float(group_df['fee_display'].iloc[0])
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
                    
                    if discount > 0:
                        p_discount = doc.add_paragraph()
                        p_discount.add_run(f"إجمالي أجور الطباعة: {grand_total_print:,.0f} $").bold = True
                        _force_rtl_style(p_discount)
                        
                        p_discount = doc.add_paragraph()
                        p_discount.add_run(f"إجمالي أجور العرض قبل الحسم: {grand_total_display:,.0f} $").bold = True
                        _force_rtl_style(p_discount)
                        
                        p_discount = doc.add_paragraph()
                        p_discount.add_run(f"حسم {discount}% على أجور العرض: - {discount_amount:,.0f} $").bold = True
                        _force_rtl_style(p_discount)
                        
                        p_discount = doc.add_paragraph()
                        p_discount.add_run(f"إجمالي أجور العرض بعد الحسم: {grand_total_display_after:,.0f} $").bold = True
                        _force_rtl_style(p_discount)
                    else:
                        p_total_print = doc.add_paragraph()
                        p_total_print.add_run(f"إجمالي أجور الطباعة: {grand_total_print:,.0f} $").bold = True
                        _force_rtl_style(p_total_print)
                        
                        p_total_display = doc.add_paragraph()
                        p_total_display.add_run(f"إجمالي أجور العرض: {grand_total_display:,.0f} $").bold = True
                        _force_rtl_style(p_total_display)
                    
                    doc.add_paragraph()
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
                    
                    st.download_button("📥 تحميل العرض", target, f"Offer_{customer_name}.docx", key="download_word")
            
            with col_btn4:
                if st.button("🔴 تفريغ السلة", use_container_width=True, key="clear_cart"):
                    st.session_state.cart = {}
                    st.rerun()
    
    except Exception as e:
        st.error(f"❌ حدث خطأ: {str(e)}")

elif page == "📋 تقرير الجرد":
    st.title("📋 التقرير التجميعي - جرد اللوحات")
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    
    try:
        periods_df = run_query('SELECT "no", "namee" FROM "الفترة" ORDER BY "no"')
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
        
        all_boards = run_query('SELECT "رقم اللوحة", "المحافظة", "الحجم", "العدد" FROM "اعمدة انارة"')
        
        period_placeholders = ','.join([f"'{p}'" for p in target_periods])
        booked_query = f'''
            SELECT DISTINCT "رقم اللوحة" 
            FROM "حجوزات1" 
            WHERE "العام" = %s 
            AND "فترة الحجز" IN ({period_placeholders})
        '''
        booked_in_period = run_query(booked_query, (report_year,))['رقم اللوحة'].tolist()
        
        all_boards['الحالة'] = all_boards['رقم اللوحة'].apply(lambda x: 'محجوز' if x in booked_in_period else 'متاح')
        
        total_sites = len(all_boards)
        booked_sites = len(booked_in_period)
        available_sites = total_sites - booked_sites
        total_boards_count = all_boards['العدد'].sum()
        booked_boards_count = all_boards[all_boards['الحالة'] == 'محجوز']['العدد'].sum()
        available_boards_count = total_boards_count - booked_boards_count
        
        cols = st.columns(4)
        metrics_data = [
            ("🏢 إجمالي المواقع", total_sites, "🗺️", "primary"),
            ("🔴 المواقع المحجوزة", booked_sites, "📌", "danger"),
            ("🟢 المواقع المتاحة", available_sites, "✅", "success"),
            ("📈 نسبة الإشغال", f"{(booked_sites/total_sites*100):.1f}%", "📊", "warning")
        ]
        
        for idx, (title, value, icon, color) in enumerate(metrics_data):
            with cols[idx]:
                st.markdown(create_metric_card_3d(title, value, icon, color), unsafe_allow_html=True)
        
        st.divider()
        
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            fig_pie = go.Figure(data=[go.Pie(
                labels=['محجوز', 'متاح'],
                values=[booked_boards_count, available_boards_count],
                hole=0.4,
                marker_colors=['#dc2626', '#22c55e'],
                textinfo='percent+label'
            )])
            fig_pie.update_layout(title="نسبة إشغال الأعمدة", height=400)
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col_chart2:
            city_data = []
            for city in all_boards['المحافظة'].unique():
                city_df = all_boards[all_boards['المحافظة'] == city]
                city_total = city_df['العدد'].sum()
                city_booked = city_df[city_df['الحالة'] == 'محجوز']['العدد'].sum()
                city_data.append({
                    'المحافظة': city,
                    'نسبة الإشغال': (city_booked / city_total * 100) if city_total > 0 else 0
                })
            
            city_df = pd.DataFrame(city_data)
            fig_bar = px.bar(city_df, x='المحافظة', y='نسبة الإشغال', 
                           color='نسبة الإشغال', color_continuous_scale='RdYlGn')
            fig_bar.update_layout(height=400)
            st.plotly_chart(fig_bar, use_container_width=True)
        
        st.divider()
        
        st.subheader("📋 تفصيل حسب المحافظة")
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
                'نسبة الإشغال': f"{(city_booked/city_total*100):.1f}%" if city_total > 0 else "0%"
            })
        
        st.dataframe(pd.DataFrame(city_details), use_container_width=True)
        
        st.divider()
        csv_data = all_boards.to_csv(index=False, encoding='utf-8-sig')
        st.download_button("📊 تصدير إلى CSV", csv_data, f"Inventory_Report_{report_year}.csv", "text/csv", use_container_width=True)
        
    except Exception as e:
        st.error(f"حدث خطأ في التقرير: {str(e)}")

elif page == "📅 تقرير التوفر الشهري":
    st.title("📋 تقرير الأعمدة المتاحة")
    st.info("📌 يعرض هذا التقرير الأعمدة المتاحة حالياً أو التي ستصبح متاحة بعد تاريخ محدد")
    
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
            
            st.subheader("📊 ملخص حسب المحافظة")
            summary = available_df.groupby('المحافظة').agg({
                'رقم اللوحة': 'count',
                'العدد': 'sum'
            }).rename(columns={'رقم اللوحة': 'عدد المواقع', 'العدد': 'عدد اللوحات'})
            st.dataframe(summary, use_container_width=True)
            
            st.subheader("📋 قائمة الأعمدة المتاحة")
            st.dataframe(available_df[['رقم اللوحة', 'اسم العمود', 'المحافظة', 'الشبكة', 'الحجم', 'العدد']], use_container_width=True, height=400)
            
            csv_data = available_df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button("📥 تحميل التقرير (CSV)", csv_data, f"available_columns_{date.today().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)

elif page == "🗺️ تقرير جميع المواقع":
    st.title("🗺️ تقرير جميع المواقع والأعمدة")
    st.info("📌 يعرض هذا التقرير جميع المواقع والأعمدة في النظام")
    
    # جلب البيانات
    all_columns = run_query('SELECT "رقم اللوحة", "اسم العمود", "المحافظة", "الشبكة", "الحجم", "العدد" FROM "اعمدة انارة" ORDER BY "المحافظة", "الشبكة"')
    
    # تشخيص سريع
    st.write(f"**Debug:** عدد السجلات = {len(all_columns) if all_columns is not None else 0}")
    if all_columns is not None and not all_columns.empty:
        st.write(f"**Debug:** الأعمدة الموجودة: {all_columns.columns.tolist()}")
    
    if all_columns is None or all_columns.empty:
        st.warning("⚠️ لا توجد بيانات في جدول أعمدة الإنارة")
        st.stop()
    
    # إحصائيات سريعة
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("إجمالي المواقع", len(all_columns))
    with col2:
        st.metric("إجمالي الأعمدة", int(all_columns['العدد'].sum()) if 'العدد' in all_columns.columns else len(all_columns))
    with col3:
        st.metric("عدد المحافظات", all_columns['المحافظة'].nunique() if 'المحافظة' in all_columns.columns else 0)
    
    st.divider()
    
    # عرض الجدول كاملاً أولاً (للتأكد من وجود بيانات)
    st.subheader("📋 جميع البيانات (جدول كامل)")
    st.dataframe(all_columns, use_container_width=True)
    
    st.divider()
    
    # عرض البيانات بشكل منظم حسب المحافظة
    st.subheader("📋 تفصيل حسب المحافظة")
    
    for city in sorted(all_columns['المحافظة'].unique()):
        city_df = all_columns[all_columns['المحافظة'] == city]
        
        with st.expander(f"📍 محافظة {city} ({len(city_df)} موقع - {city_df['العدد'].sum()} لوحة)"):
            
            # عرض جميع مواقع المحافظة
            st.dataframe(city_df[['رقم اللوحة', 'اسم العمود', 'الشبكة', 'الحجم', 'العدد']], use_container_width=True)
            
            # تفصيل حسب الشبكة
            if 'الشبكة' in city_df.columns:
                st.write("**📡 تفصيل حسب الشبكة:**")
                network_summary = city_df.groupby('الشبكة').agg({
                    'رقم اللوحة': 'count',
                    'العدد': 'sum'
                }).rename(columns={'رقم اللوحة': 'عدد المواقع', 'العدد': 'عدد الأعمدة'})
                st.dataframe(network_summary, use_container_width=True)
    
    # تصدير
    st.divider()
    csv_data = all_columns.to_csv(index=False, encoding='utf-8-sig')
    st.download_button("📊 تصدير CSV", csv_data, f"full_report_{date.today().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)

elif page == "📐 تقرير تجميعي حسب الحجوم":
    st.title("📐 تقرير تجميعي حسب الحجوم")
    st.info("📌 يعرض هذا التقرير توزع اللوحات حسب الحجوم المقسمة إلى ثلاث مجموعات")
    
    all_columns = run_query('SELECT "رقم اللوحة", "اسم العمود", "المحافظة", "الشبكة", "الحجم", "العدد" FROM "اعمدة انارة" ORDER BY "المحافظة", "الشبكة"')
    
    if all_columns is None or all_columns.empty:
        st.warning("⚠️ لا توجد بيانات في جدول الأعمدة")
        st.stop()
    
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
    
    cols = st.columns(3)
    with cols[0]:
        st.markdown(create_metric_card_3d("إجمالي الأعمدة", int(all_columns['العدد'].sum()), "📌", "primary"), unsafe_allow_html=True)
    with cols[1]:
        st.markdown(create_metric_card_3d("إجمالي المواقع", len(all_columns), "🗺️", "success"), unsafe_allow_html=True)
    with cols[2]:
        st.markdown(create_metric_card_3d("عدد الأحجام", all_columns['الحجم'].nunique(), "📏", "warning"), unsafe_allow_html=True)
    
    st.divider()
    
    st.subheader("📊 ملخص المجموعات")
    group_summary = all_columns.groupby('المجموعة').agg({
        'رقم اللوحة': 'count',
        'العدد': 'sum'
    }).rename(columns={'رقم اللوحة': 'عدد المواقع', 'العدد': 'عدد الأعمدة'})
    group_summary['عدد الأعمدة'] = group_summary['عدد الأعمدة'].astype(int)
    st.dataframe(group_summary, use_container_width=True)
    
    st.divider()
    
    for group_name in ['المجموعة الأولى: حجم 3×6', 'المجموعة الثانية: حجمي 2×1 و 125×185', 'المجموعة الثالثة: باقي الحجوم']:
        group_df = all_columns[all_columns['المجموعة'] == group_name]
        if not group_df.empty:
            with st.expander(f"📌 {group_name} - {len(group_df)} موقع - {int(group_df['العدد'].sum())} عمود", expanded=False):
                st.subheader("📍 توزع حسب المحافظة")
                city_summary = group_df.groupby('المحافظة').agg({
                    'رقم اللوحة': 'count',
                    'العدد': 'sum'
                }).rename(columns={'رقم اللوحة': 'عدد المواقع', 'العدد': 'عدد الأعمدة'})
                st.dataframe(city_summary, use_container_width=True)
                
                st.subheader("📋 قائمة المواقع")
                st.dataframe(group_df[['رقم اللوحة', 'اسم العمود', 'المحافظة', 'الشبكة', 'الحجم', 'العدد']], use_container_width=True)
    
    st.divider()
    
    csv_data = all_columns.to_csv(index=False, encoding='utf-8-sig')
    st.download_button("📊 تصدير التقرير كاملاً (CSV)", csv_data, f"grouped_report_{date.today().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)

elif page == "⚙️ الإعدادات":
    if not is_admin():
        st.error("⛔ هذه الصفحة مخصصة للمديرين فقط")
        st.stop()
    
    st.title("⚙️ إعدادات النظام - إدارة البيانات")
    st.warning("⚠️ تحذير: تعديل هذه البيانات يؤثر مباشرة على النظام. يرجى الحذر.")
    
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM \"اعمدة انارة\"")
    boards_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM \"حجوزات1\"")
    bookings_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM \"اسماء الرسم\"")
    fees_count = cursor.fetchone()[0]
    cursor.close()
    
    cols = st.columns(3)
    with cols[0]:
        st.markdown(create_metric_card_3d("أعمدة الإنارة", boards_count, "🗺️", "primary"), unsafe_allow_html=True)
    with cols[1]:
        st.markdown(create_metric_card_3d("الحجوزات", bookings_count, "📅", "success"), unsafe_allow_html=True)
    with cols[2]:
        st.markdown(create_metric_card_3d("أجور الرسم", fees_count, "💰", "warning"), unsafe_allow_html=True)
    
    st.divider()
    
    tab1, tab2, tab3, tab4 = st.tabs(["🗄️ أعمدة الإنارة", "📅 سجل الحجوزات", "💰 أجور الرسم", "👥 المستخدمين"])
    
    with tab1:
        st.subheader("إدارة بيانات أعمدة الإنارة")
        df_boards = run_query('SELECT * FROM "اعمدة انارة" ORDER BY "المحافظة", "الشبكة"')
        edited_boards = st.data_editor(df_boards, num_rows="dynamic", key="edit_boards", use_container_width=True)
        if st.button("💾 حفظ أعمدة الإنارة", key="save_boards", use_container_width=True):
            cursor = conn.cursor()
            cursor.execute("DELETE FROM \"اعمدة انارة\"")
            for _, row in edited_boards.iterrows():
                cursor.execute('''
                    INSERT INTO "اعمدة انارة" ("رقم اللوحة", "اسم العمود", "المحافظة", "الشبكة", "الحجم", "العدد", "Latitude", "Longitude")
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ''', (row['رقم اللوحة'], row['اسم العمود'], row['المحافظة'], row['الشبكة'], row['الحجم'], row['العدد'], 
                      row.get('Latitude'), row.get('Longitude')))
            conn.commit()
            cursor.close()
            st.success("✅ تم تحديث أعمدة الإنارة")
            st.rerun()
    
    with tab2:
        st.subheader("إدارة سجل الحجوزات")
        df_bookings = run_query('SELECT * FROM "حجوزات1"')
        edited_bookings = st.data_editor(df_bookings, num_rows="dynamic", key="edit_bookings", use_container_width=True)
        if st.button("💾 حفظ سجل الحجوزات", key="save_bookings", use_container_width=True):
            cursor = conn.cursor()
            cursor.execute("DELETE FROM \"حجوزات1\"")
            for _, row in edited_bookings.iterrows():
                cursor.execute('''
                    INSERT INTO "حجوزات1" ("رقم اللوحة", "اسم الزبون", "العام", "فترة الحجز", "تاريخ النهاية")
                    VALUES (%s, %s, %s, %s, %s)
                ''', (row['رقم اللوحة'], row['اسم الزبون'], row['العام'], row['فترة الحجز'], row.get('تاريخ النهاية')))
            conn.commit()
            cursor.close()
            st.success("✅ تم تحديث سجل الحجوزات")
            st.rerun()
    
    with tab3:
        st.subheader("إدارة أجور الرسم")
        st.info("💡 أضف 'اجور الطباعة عادي' و 'اجور الطباعة سكوتش' و 'اجور العرض شهري' و 'اجور العرض اجنبي شهري'")
        df_fees = run_query('SELECT * FROM "اسماء الرسم"')
        edited_fees = st.data_editor(df_fees, num_rows="dynamic", key="edit_fees", use_container_width=True)
        if st.button("💾 حفظ أجور الرسم", key="save_fees", use_container_width=True):
            cursor = conn.cursor()
            cursor.execute("DELETE FROM \"اسماء الرسم\"")
            for _, row in edited_fees.iterrows():
                cursor.execute('''
                    INSERT INTO "اسماء الرسم" ("اسم الرسم", "الحجم", "اجرة الرسم")
                    VALUES (%s, %s, %s)
                ''', (row['اسم الرسم'], row['الحجم'], row['اجرة الرسم']))
            conn.commit()
            cursor.close()
            st.success("✅ تم تحديث أجور الرسم")
            st.rerun()
    
    with tab4:
        st.subheader("👥 إدارة المستخدمين")
        df_users = run_query('SELECT id, username, role, full_name, created_at FROM users')
        edited_users = st.data_editor(df_users, num_rows="dynamic", key="edit_users", use_container_width=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 حفظ المستخدمين", key="save_users", use_container_width=True):
                cursor = conn.cursor()
                for _, row in edited_users.iterrows():
                    cursor.execute('''
                        UPDATE users SET username=%s, role=%s, full_name=%s WHERE id=%s
                    ''', (row['username'], row['role'], row['full_name'], row['id']))
                conn.commit()
                cursor.close()
                st.success("✅ تم تحديث المستخدمين")
                st.rerun()
        
        with col2:
            with st.expander("➕ إضافة مستخدم جديد"):
                new_username = st.text_input("اسم المستخدم")
                new_password = st.text_input("كلمة المرور", type="password")
                new_role = st.selectbox("الدور", ["admin", "employee"])
                new_full_name = st.text_input("الاسم الكامل")
                if st.button("إضافة مستخدم", use_container_width=True):
                    cursor = conn.cursor()
                    try:
                        cursor.execute('''
                            INSERT INTO users (username, password, role, full_name, created_at)
                            VALUES (%s, %s, %s, %s, NOW())
                        ''', (new_username, new_password, new_role, new_full_name))
                        conn.commit()
                        cursor.close()
                        st.success("✅ تم إضافة المستخدم")
                        st.rerun()
                    except Exception as e:
                        st.error(f"خطأ: {e}")

# ============================================================
# إغلاق الاتصال
# ============================================================

conn.close()
