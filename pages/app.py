import streamlit as st
from utils.database import get_connection
from utils.auth import check_login, is_admin
from utils.styles import load_css

# ============================================================
# إعدادات الصفحة
# ============================================================

st.set_page_config(
    page_title="PreView Ads ERP",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# تحميل الـ CSS
load_css()

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
    # ... كود تسجيل الدخول ...
    st.stop()

# ============================================================
# الاتصال بقاعدة البيانات
# ============================================================

conn = get_connection()

# ============================================================
# الشريط الجانبي
# ============================================================

with st.sidebar:
    # ... الشعار والمعلومات ...
    
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

# ============================================================
# استدعاء الصفحات
# ============================================================

if page == "📊 Dashboard":
    from pages.dashboard import show
    show(conn)

elif page == "🏢 لوحات الشركات":
    from pages.company_boards import show
    show(conn)

elif page == "📍 الأعمدة المتاحة":
    from pages.available_boards import show
    show(conn, start_date=date.today())

elif page == "📅 لوحة الفترات":
    from pages.period_board import show
    show(conn)

elif page == "📄 عرض سعر":
    from pages.offer_price import show
    show(conn)

elif page == "📋 تقرير الجرد":
    from pages.inventory_report import show
    show(conn)

elif page == "📅 تقرير التوفر الشهري":
    from pages.availability_report import show
    show(conn)

elif page == "🗺️ تقرير جميع المواقع":
    from pages.all_boards_report import show
    show(conn)

elif page == "📐 تقرير تجميعي حسب الحجوم":
    from pages.size_report import show
    show(conn)

elif page == "⚙️ الإعدادات":
    if not is_admin():
        st.error("⛔ هذه الصفحة مخصصة للمديرين فقط")
        st.stop()
    from pages.settings import show
    show(conn)

# ============================================================
# إغلاق الاتصال
# ============================================================

if conn:
    conn.close()
