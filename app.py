# app.py - الملف الرئيسي (خفيف)
import streamlit as st
import pandas as pd
from datetime import date
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

# ============================================================
# إعدادات الصفحة (يجب أن تكون أول شيء)
# ============================================================

st.set_page_config(
    page_title="PreView Ads ERP",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# معرفة IP الخاص بالخادم
import requests
try:
    ip = requests.get('https://api.ipify.org').text
    st.write(f"🌐 IP الخاص بالخادم: {ip}")
except:
    st.write("⚠️ لا يمكن تحديد IP")
# ============================================================
# استيرادات الملفات الداخلية
# ============================================================

from utils.database import get_connection, run_query
from utils.helpers import safe_split, badge_animated, create_metric_card_3d

# ============================================================
# تهيئة session_state
# ============================================================

if 'auth' not in st.session_state:
    st.session_state.auth = False
if 'cart' not in st.session_state:
    st.session_state.cart = {}
if 'role' not in st.session_state:
    st.session_state.role = None
if 'username' not in st.session_state:
    st.session_state.username = None

# ============================================================
# صفحة تسجيل الدخول
# ============================================================

if not st.session_state.auth:
    # واجهة تسجيل الدخول
    st.markdown("""
    <div style="display: flex; justify-content: center; align-items: center; min-height: 80vh;">
        <div style="background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 30px; padding: 40px; width: 100%; max-width: 450px; text-align: center;">
            <h1 style="color: white;">PreView Ads</h1>
            <p style="color: rgba(255,255,255,0.7);">نظام إدارة الإعلانات</p>
    """, unsafe_allow_html=True)
    
    with st.form("login_form"):
        username = st.text_input("👤 اسم المستخدم")
        password = st.text_input("🔑 كلمة المرور", type="password")
        submitted = st.form_submit_button("🚪 دخول", use_container_width=True)
        
        if submitted:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT username, role FROM users WHERE username = %s AND password = %s", (username, password))
            user = cursor.fetchone()
            conn.close()
            
            if user:
                st.session_state.auth = True
                st.session_state.role = user[1]
                st.session_state.username = user[0]
                st.rerun()
            else:
                st.error("❌ اسم المستخدم أو كلمة المرور غير صحيحة")
    
    st.markdown("</div></div>", unsafe_allow_html=True)
    st.stop()

# ============================================================
# الشريط الجانبي
# ============================================================

with st.sidebar:
    st.markdown("""
    <div style="text-align: center; padding: 20px 0;">
        <h2 style="color: white;">🎯 PreView Ads</h2>
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    st.markdown(f"**👤 {st.session_state.get('username', '')}**")
    st.caption(f"الدور: {'مدير' if st.session_state.get('role') == 'admin' else 'موظف'}")
    
    st.divider()
    
    page = st.radio("📋 القائمة الرئيسية", [
        "📊 Dashboard",
        "🏢 لوحات الشركات",
        "📍 الأعمدة المتاحة",
        "📅 لوحة الفترات",
        "📄 عرض سعر",
        "📋 تقرير الجرد",
        "📅 تقرير التوفر الشهري",
        "🗺️ تقرير جميع المواقع",
        "📐 تقرير تجميعي حسب الحجوم",
        "⚙️ الإعدادات"
    ])
    
    st.divider()
    
    if st.button("🚪 تسجيل الخروج", use_container_width=True):
        st.session_state.auth = False
        st.session_state.cart = {}
        st.rerun()

# ============================================================
# استدعاء الصفحات (كل صفحة في ملف منفصل)
# ============================================================



# ============================================================
# استدعاء الصفحات (كل صفحة في ملف منفصل)
# ============================================================

if page == "📊 Dashboard":
    st.info("📊 صفحة Dashboard قيد التطوير")

elif page == "🏢 لوحات الشركات":
    st.info("🏢 صفحة لوحات الشركات قيد التطوير")

elif page == "📍 الأعمدة المتاحة":
    from pages.available_boards import show
    show()

elif page == "📅 لوحة الفترات":
    st.info("📅 صفحة لوحة الفترات قيد التطوير")

elif page == "📄 عرض سعر":
    st.info("📄 صفحة عرض سعر قيد التطوير")

elif page == "📋 تقرير الجرد":
    st.info("📋 صفحة تقرير الجرد قيد التطوير")

elif page == "📅 تقرير التوفر الشهري":
    st.info("📅 صفحة تقرير التوفر الشهري قيد التطوير")

elif page == "🗺️ تقرير جميع المواقع":
    st.info("🗺️ صفحة تقرير جميع المواقع قيد التطوير")

elif page == "📐 تقرير تجميعي حسب الحجوم":
    st.info("📐 صفحة تقرير تجميعي حسب الحجوم قيد التطوير")

elif page == "⚙️ الإعدادات":
    if st.session_state.get('role') != 'admin':
        st.error("⛔ هذه الصفحة مخصصة للمديرين فقط")
        st.stop()
    st.info("⚙️ صفحة الإعدادات قيد التطوير")
