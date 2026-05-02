import streamlit as st
import pandas as pd
import sqlite3
import os
import io
from docx import Document
from docx.shared import Pt, RGBColor, Cm 
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# --- إعدادات الصفحة ---
st.set_page_config(page_title="PreView Ads ERP", layout="wide")

def get_connection():
    return sqlite3.connect('billboards_data.db')

def apply_rtl_to_p(paragraph):
    """إجبار الفقرة على المحاذاة لليمين واتجاه النص العربي"""
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT # محاذاة يمين قسرية
    pPr = paragraph._element.get_or_add_pPr()
    
    # ضبط اتجاه الفقرة (Bidi)
    bidi = OxmlElement('w:bidi')
    bidi.set(qn('w:val'), '1')
    pPr.append(bidi)
    
    # ضبط اتجاه النص (RTL) لكل جزء داخل الفقرة
    for run in paragraph.runs:
        rPr = run._element.get_or_add_rPr()
        rtl = OxmlElement('w:rtl')
        rtl.set(qn('w:val'), '1')
        rPr.append(rtl)
        # إجبار استخدام خط يدعم العربية لضمان الاتساق
        rFonts = OxmlElement('w:rFonts')
        rFonts.set(qn('w:cs'), 'Arial')
        rPr.append(rFonts)

def set_rtl(obj):
    """تطبيق الـ RTL على خلية أو فقرة"""
    if hasattr(obj, 'paragraphs'):
        for paragraph in obj.paragraphs:
            apply_rtl_to_p(paragraph)
    else:
        apply_rtl_to_p(obj)

def set_table_rtl(table):
    """جعل الجدول يبدأ من اليمين (العمود الأول على اليمين)"""
    tblPr = table._element.xpath('w:tblPr')[0]
    bidi = OxmlElement('w:bidiVisual')
    tblPr.append(bidi)

def set_cell_shading(cell, color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), color)
    tcPr.append(shd)

def export_word(customer_name, cart_data, period_name):
    doc = Document('template.docx') if os.path.exists('template.docx') else Document()

    # 1. التاريخ (يبقى يسار كما طلبت سابقاً أو نغيره لليمين)
    p_date = doc.add_paragraph(f"التاريخ: 2026/05/02")
    p_date.alignment = WD_ALIGN_PARAGRAPH.LEFT

    # 2. اسم الزبون
    p_cust = doc.add_paragraph()
    p_cust.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_c = p_cust.add_run(f"السادة شركة {customer_name} المحترمين")
    run_c.bold, run_c.font.size = True, Pt(20)
    run_c.font.color.rgb = RGBColor(102, 0, 153)

    # 3. التحية (الآن ستصبح يمين قسرياً)
    p_greet = doc.add_paragraph()
    p_greet.add_run("تحية طيبة وبعد،")
    set_rtl(p_greet)

    p_info = doc.add_paragraph()
    p_info.add_run(f"نقدم لكم المواقع المتاحة للفترة الإعلانية: {period_name}")
    set_rtl(p_info)

    # 4. بناء الجداول المجمعة حسب المقاس
    if cart_data:
        for city, networks in cart_data.items():
            p_city = doc.add_paragraph()
            p_city.add_run(f"■ محافظة {city}")
            set_rtl(p_city) # اسم المحافظة يمين
            
            for net, df in networks.items():
                # التجميع حسب سعر الرسم (المقاس)
                grouped = df.groupby('اجرة الرسم')
                
                for fee, group_df in grouped:
                    p_net = doc.add_paragraph()
                    p_net.add_run(f"الشبكة: {net} (سعر الرسم: {fee}$)")
                    set_rtl(p_net) # عنوان الجدول يمين
                    
                    table = doc.add_table(rows=1, cols=2)
                    table.style = 'Table Grid'
                    set_table_rtl(table)
                    
                    hdr = table.rows[0].cells
                    hdr[0].text, hdr[1].text = "اسم الموقع / العمود", "العدد"
                    
                    for cell in hdr:
                        set_cell_shading(cell, "660099")
                        set_rtl(cell)
                        for run in cell.paragraphs[0].runs:
                            run.font.color.rgb, run.bold = RGBColor(255, 255, 255), True

                    for _, row in group_df.iterrows():
                        row_cells = table.add_row().cells
                        row_cells[0].text = str(row.get('الموقع', ''))
                        row_cells[1].text = str(row.get('العدد', 1))
                        for cell in row_cells: set_rtl(cell)

                    # حساب المجاميع أسفل الجدول مباشرة
                    total_q = pd.to_numeric(group_df['العدد'], errors='coerce').sum()
                    total_d = total_q * fee
                    total_p = pd.to_numeric(group_df.get('أجور الطباعة', 0), errors='coerce').sum()

                    p_sum = doc.add_paragraph()
                    summary = f"العدد: {int(total_q)} | رسم: {total_d:,}$ | طباعة: {total_p:,}$ | المجموع: {total_d + total_p:,}$"
                    p_sum.add_run(summary).bold = True
                    set_rtl(p_sum) # سطر المجموع يمين
                    doc.add_paragraph()

    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- واجهة Streamlit ---
# (استخدم نفس كود تسجيل الدخول والسلة الذي يعمل لديك حالياً)


# --- بقية كود Streamlit (Login, Sidebar, Cart) تبقى كما هي ---
# ... (استخدم كود الواجهة السابق) ...


# --- واجهة الاستخدام (نفس كود السلة والبيانات السابق) ---
# ... (لا تغيير في جزء Streamlit) ...


# --- واجهة التطبيق ---
if "auth" not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 تسجيل الدخول")
    u, p = st.text_input("User"), st.text_input("Pass", type="password")
    if st.button("دخول"):
        if u == "admin" and p == "preview2026":
            st.session_state.auth = True
            st.rerun()
else:
    conn = get_connection()
    if 'cart' not in st.session_state: st.session_state.cart = {}
    
    with st.sidebar:
        if os.path.exists('logo_full.png'): st.image('logo_full.png', width=180)
        page = st.radio("القائمة", ["📊 الداشبورد", "📄 عرض سعر"])

    if page == "📊 الداشبورد":
        st.title("📊 حالة المواقع")
        df_m = pd.read_sql("SELECT * FROM [اعمدة انارة]", conn)
        st.dataframe(df_m, use_container_width=True)

    elif page == "📄 عرض سعر":
        st.title("📄 إنشاء عرض سعر")
        try:
            df_periods = pd.read_sql("SELECT namee FROM [الفترة]", conn)['namee'].tolist()
            drawing_df = pd.read_sql("SELECT * FROM [اسماء الرسم]", conn)
            
            cust = st.text_input("اسم الزبون")
            period = st.selectbox("الفترة", df_periods)
            sel_size = st.selectbox("قياس الرسم:", drawing_df['الحجم'].tolist())
            current_fee = drawing_df[drawing_df['الحجم'] == sel_size]['اجرة الرسم'].values[0]

            city_list = pd.read_sql("SELECT DISTINCT المحافظة FROM [اعمدة انارة]", conn)['المحافظة'].tolist()
            sel_city = st.selectbox("المحافظة", city_list)
            
            raw = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة='{sel_city}'", conn)
            nets = st.multiselect("الشبكات", raw['الشبكة'].unique().tolist())

            if st.button("➕ إضافة"):
                if sel_city not in st.session_state.cart: st.session_state.cart[sel_city] = {}
                for n in nets:
                    st.session_state.cart[sel_city][n] = raw[raw['الشبكة'] == n].assign(**{'اجرة الرسم': current_fee, 'أجور الطباعة': 0})

            if st.session_state.cart:
                for c, nts in list(st.session_state.cart.items()):
                    for n, df in nts.items():
                        with st.expander(f"📍 {c} - {n}"):
                            st.session_state.cart[c][n] = st.data_editor(df, key=f"ed_{c}_{n}")
                
                if st.button("🚀 تصدير"):
                    doc_io = export_word(cust, st.session_state.cart, period)
                    st.download_button("📥 تحميل", doc_io, f"Quotation_{cust}.docx")
        except Exception as e: st.error(e)
    conn.close()
