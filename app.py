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
    if not text or str(text).strip() == "": return ""
    return get_display(reshape(str(text)))

def set_cell_rtl(cell):
    """ضبط اتجاه النص داخل الخلية ليكون من اليمين لليسار"""
    cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p = cell.paragraphs[0]._element
    pPr = p.get_or_add_pPr()
    bidi = OxmlElement('w:bidi')
    bidi.set(qn('w:val'), '1')
    pPr.append(bidi)

def set_cell_shading(cell, color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), color)
    tcPr.append(shd)

def export_word(customer_name, cart_data, period_name):
    if os.path.exists('template.docx'):
        doc = Document('template.docx')
    else:
        doc = Document()

    # 1. التاريخ
    p_date = doc.add_paragraph(f"{ar('التاريخ:')} 2026/05/02")
    p_date.alignment = WD_ALIGN_PARAGRAPH.LEFT

    # 2. العنوان
    p_cust = doc.add_paragraph()
    p_cust.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_c = p_cust.add_run(ar(f"السادة شركة {customer_name} المحترمين"))
    run_c.bold = True
    run_c.font.size = Pt(20)
    run_c.font.color.rgb = RGBColor(102, 0, 153)

    doc.add_paragraph(ar("تحية طيبة وبعد،")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
    doc.add_paragraph(ar(f"نقدم لكم المواقع المتاحة للفترة: {period_name}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # 3. الجداول
    if cart_data:
        for city, networks in cart_data.items():
            doc.add_paragraph(ar(f"■ محافظة {city}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
            for net, df in networks.items():
                doc.add_paragraph(ar(f"شبكة: {net}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
                
                # جدول بـ 6 أعمدة لإظهار أجور الطباعة والعرض
                table = doc.add_table(rows=1, cols=3)
                table.style = 'Table Grid'
                table.alignment = WD_ALIGN_PARAGRAPH.CENTER
                
                hdr_cells = table.rows[0].cells
                titles = ["أجور الطباعة", "أجور العرض", "الموقع"]
                for i, title in enumerate(titles):
                    hdr_cells[i].text = ar(title)
                    set_cell_shading(hdr_cells[i], "660099")
                    set_cell_rtl(hdr_cells[i])
                    run_h = hdr_cells[i].paragraphs[0].runs[0]
                    run_h.font.color.rgb = RGBColor(255, 255, 255)
                    run_h.bold = True

                # تعبئة البيانات
                for _, row in df.iterrows():
                    row_cells = table.add_row().cells
                    row_cells[2].text = ar(row['اسم العمود'])
                    row_cells[1].text = f"{row.get('أجور العرض', 0):,}$"
                    row_cells[0].text = f"{row.get('أجور الطباعة', 0):,}$"
                    for cell in row_cells: set_cell_rtl(cell)

                # حساب المجاميع للشبكة
                sum_ads = pd.to_numeric(df['أجور العرض'], errors='coerce').sum()
                sum_print = pd.to_numeric(df['أجور الطباعة'], errors='coerce').sum()
                grand_total = sum_ads + sum_print

                p_sum = doc.add_paragraph()
                p_sum.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                total_text = f"{ar('إجمالي العرض:')} {sum_ads:,}$ | {ar('إجمالي الطباعة:')} {sum_print:,}$ | {ar('المجموع الكلي:')} {grand_total:,}$"
                run_s = p_sum.add_run(total_text)
                run_s.bold = True
                run_s.font.color.rgb = RGBColor(102, 0, 153)

    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- Streamlit Interface ---
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    st.title("🔒 تسجيل الدخول")
    u, p = st.text_input("Username"), st.text_input("Password", type="password")
    if st.button("Login"):
        if u == "admin" and p == "preview2026": st.session_state.auth = True; st.rerun()
else:
    conn = get_connection()
    if 'cart' not in st.session_state: st.session_state.cart = {}
    
    with st.sidebar:
        if os.path.exists('logo_full.png'): st.image('logo_full.png', width=180)
        page = st.radio("Menu", ["🏠 الداشبورد", "📄 عرض سعر"])

    if page == "🏠 الداشبورد":
        st.title("📊 الخريطة والبيانات")
        df_all = pd.read_sql("SELECT * FROM [اعمدة انارة]", conn)
        df_b = pd.read_sql("SELECT [رقم اللوحة], [اسم الزبون] FROM [حجوزات1]", conn)
        df_m = pd.merge(df_all, df_b, on='رقم اللوحة', how='left')
        st.dataframe(df_m, use_container_width=True)

    elif page == "📄 عرض سعر":
        st.title("📄 بناء عرض سعر")
        df_periods = pd.read_sql("SELECT namee FROM [الفترة]", conn)['namee'].tolist()
        cust = st.text_input("اسم الزبون")
        period = st.selectbox("الفترة", df_periods)
        
        city_l = pd.read_sql("SELECT DISTINCT المحافظة FROM [اعمدة انارة]", conn)['المحافظة'].tolist()
        sel_c = st.selectbox("المحافظة", city_l)
        raw = pd.read_sql(f"SELECT [اسم العمود], [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة='{sel_c}'", conn)
        nets = st.multiselect("الشبكات", raw['الشبكة'].unique().tolist())

        if st.button("➕ إضافة"):
            if sel_c not in st.session_state.cart: st.session_state.cart[sel_c] = {}
            for n in nets:
                st.session_state.cart[sel_c][n] = raw[raw['الشبكة'] == n].assign(**{'أجور العرض': 0, 'أجور الطباعة': 0})

        if st.session_state.cart:
            for c, nts in list(st.session_state.cart.items()):
                for n, df in nts.items():
                    with st.expander(f"📍 {c} - {n}"):
                        st.session_state.cart[c][n] = st.data_editor(df, key=f"ed_{c}_{n}")
            
            if st.button("🚀 تصدير"):
                doc_io = export_word(cust, st.session_state.cart, period)
                st.download_button("📥 تحميل", doc_io, f"Quotation_{cust}.docx")
