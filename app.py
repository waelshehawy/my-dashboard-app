import streamlit as st
import pandas as pd
import sqlite3
import os
import io
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
from docx import Document
from docx.shared import Pt, RGBColor, Cm 
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from arabic_reshaper import reshape
from bidi.algorithm import get_display 

# --- إعدادات الصفحة ---
st.set_page_config(page_title="PreView Ads ERP", layout="wide")

def get_connection():
    return sqlite3.connect('billboards_data.db')

def ar(text):
    """تصحيح عرض النصوص العربية"""
    if not text or str(text).strip() == "": return ""
    return get_display(reshape(str(text)))

def set_cell_rtl(cell):
    """ضبط اتجاه الخلية لليمين وتفعيل خاصية Bidi العربية"""
    cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p = cell.paragraphs[0]._element
    pPr = p.get_or_add_pPr()
    bidi = OxmlElement('w:bidi')
    bidi.set(qn('w:val'), '1')
    pPr.append(bidi)

def set_cell_shading(cell, color):
    """تلوين خلفية الخلية"""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), color)
    tcPr.append(shd)

def export_word(customer_name, cart_data, period_name):
    # فتح القالب الجاهز (الذي يحتوي على الخلفية Behind Text)
    doc = Document('template.docx') if os.path.exists('template.docx') else Document()

    # ترويسة الخطاب
    p_date = doc.add_paragraph(f"{ar('التاريخ:')} 2026/05/02")
    p_date.alignment = WD_ALIGN_PARAGRAPH.LEFT

    p_cust = doc.add_paragraph()
    p_cust.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_c = p_cust.add_run(ar(f"السادة شركة {customer_name} المحترمين"))
    run_c.bold = True
    run_c.font.size = Pt(20)
    run_c.font.color.rgb = RGBColor(102, 0, 153)

    doc.add_paragraph(ar("تحية طيبة وبعد،")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
    doc.add_paragraph(ar(f"نقدم لكم المواقع المتاحة للفترة: {period_name}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # بناء الجداول
    if cart_data:
        for city, networks in cart_data.items():
            doc.add_paragraph(ar(f"■ محافظة {city}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
            for net, df in networks.items():
                doc.add_paragraph(ar(f"شبكة: {net}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
                
                # جدول عرض المواقع: الموقع | العدد
                table = doc.add_table(rows=1, cols=2)
                table.style = 'Table Grid'
                table.alignment = WD_ALIGN_PARAGRAPH.CENTER
                
                hdr_cells = table.rows[0].cells
                hdr_cells[1].text = ar("اسم الموقع / العمود")
                hdr_cells[0].text = ar("العدد")
                
                for cell in hdr_cells:
                    set_cell_shading(cell, "660099")
                    set_cell_rtl(cell)
                    run_h = cell.paragraphs[0].runs[0]
                    run_h.font.color.rgb = RGBColor(255, 255, 255)
                    run_h.bold = True

                # تعبئة المواقع
                for _, row in df.iterrows():
                    row_cells = table.add_row().cells
                    row_cells[1].text = ar(row.get('الموقع', ''))
                    row_cells[0].text = str(row.get('العدد', 1))
                    for cell in row_cells: set_cell_rtl(cell)

                # الحسابات أسفل الجدول
                total_qty = pd.to_numeric(df['العدد'], errors='coerce').sum()
                
                # حساب (العدد * أجرة الرسم)
                drawing_unit = pd.to_numeric(df['اجرة الرسم'], errors='coerce') if 'اجرة الرسم' in df.columns else 0
                total_drawing = (pd.to_numeric(df['العدد'], errors='coerce') * drawing_unit).sum()
                
                total_printing = pd.to_numeric(df.get('أجور الطباعة', 0), errors='coerce').sum()

                p_sum = doc.add_paragraph()
                p_sum.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                summary_text = (
                    f"{ar('إجمالي العدد:')} {int(total_qty)} | "
                    f"{ar('إجمالي أجور الرسم:')} {total_drawing:,}$ | "
                    f"{ar('إجمالي أجور الطباعة:')} {total_printing:,}$ | "
                    f"{ar('المجموع الكلي:')} {total_drawing + total_printing:,}$"
                )
                run_s = p_sum.add_run(summary_text)
                run_s.bold = True
                run_s.font.color.rgb = RGBColor(102, 0, 153)

    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- Streamlit UI ---
if "auth" not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 تسجيل الدخول")
    u, p = st.text_input("User"), st.text_input("Password", type="password")
    if st.button("Login"):
        if u == "admin" and p == "preview2026": st.session_state.auth = True; st.rerun()
else:
    conn = get_connection()
    if 'cart' not in st.session_state: st.session_state.cart = {}
    
    with st.sidebar:
        if os.path.exists('logo_full.png'): st.image('logo_full.png', width=180)
        page = st.radio("Menu", ["📊 Dashboard", "📄 Quotation"])

    if page == "📊 Dashboard":
        st.title("📊 Dashboard")
        df_m = pd.read_sql("SELECT * FROM [اعمدة انارة]", conn)
        st.dataframe(df_m, use_container_width=True)

    elif page == "📄 Quotation":
        st.title("📄 إنشاء عرض سعر")
        try:
            # جلب فترات وأحجام الرسوم
            p_list = pd.read_sql("SELECT namee FROM [الفترة]", conn)['namee'].tolist()
            drawing_df = pd.read_sql("SELECT * FROM [اسماء الرسم لكل مقاس ونوع لوحات رسم مختلف]", conn)
            
            cust = st.text_input("Customer Name")
            period = st.selectbox("Period", p_list)
            
            city_l = pd.read_sql("SELECT DISTINCT المحافظة FROM [اعمدة انارة]", conn)['المحافظة'].tolist()
            sel_c = st.selectbox("City", city_l)
            
            # اختيار الحجم لجلب أجرة الرسم المناسبة
            sel_size = st.selectbox("اختر قياس/نوع الرسم:", drawing_df['الحجم'].tolist())
            current_fee = drawing_df[drawing_df['الحجم'] == sel_size]['اجرة الرسم'].iloc[0]

            raw = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة='{sel_c}'", conn)
            nets = st.multiselect("Nets", raw['الشبكة'].unique().tolist())

            if st.button("➕ Add to Cart"):
                if sel_c not in st.session_state.cart: st.session_state.cart[sel_c] = {}
                for n in nets:
                    df_to_add = raw[raw['الشبكة'] == n].copy()
                    df_to_add['اجرة الرسم'] = current_fee # تطبيق أجرة الرسم المختارة
                    df_to_add['أجور الطباعة'] = 0
                    st.session_state.cart[sel_c][n] = df_to_add

            if st.session_state.cart:
                for c, nts in list(st.session_state.cart.items()):
                    for n, df in nts.items():
                        with st.expander(f"📍 {c} - {n}"):
                            st.session_state.cart[c][n] = st.data_editor(df, key=f"ed_{c}_{n}")
                
                if st.button("🚀 Export Word"):
                    doc_io = export_word(cust, st.session_state.cart, period)
                    st.download_button("📥 Download", doc_io, f"Quotation_{cust}.docx")
        except Exception as e: st.error(f"Error: {e}")
    conn.close()
