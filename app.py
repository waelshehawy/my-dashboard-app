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

# --- 1. الدوال الأساسية وتنسيق العربي ---

def get_connection():
    return sqlite3.connect('billboards_data.db')

def apply_rtl(p):
    """إجبار النص على اليمين بالمنطق العكسي وتفعيل Bidi"""
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
    """إجبار الجدول بالكامل على أن يكون يمين لليسار"""
    tblPr = table._element.xpath('w:tblPr')[0]
    bidi = OxmlElement('w:bidiVisual')
    tblPr.append(bidi)

def set_cell_background(cell, color):
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), color)
    cell._tc.get_or_add_tcPr().append(shd)

# --- 2. دالة تصدير الوورد المصلحة محاسبياً ومنطقياً ---

def export_word(customer_name, cart_data, period_name):
    doc = Document('template.docx') if os.path.exists('template.docx') else Document()
    for section in doc.sections:
        section.top_margin = Cm(4.5) 

    p_date = doc.add_paragraph(f"التاريخ: 2026/05/03")
    p_date.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    p_cust = doc.add_paragraph()
    p_cust.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_c = p_cust.add_run(f"السادة شركة {customer_name} المحترمين")
    run_c.bold, run_c.font.size = True, Pt(20)

    p_greet = doc.add_paragraph("تحية طيبة وبعد،")
    apply_rtl(p_greet)

    # العبارة المطلوبة بعد سطرين من التحية
    doc.add_paragraph() 
    p_stat = doc.add_paragraph()
    p_stat.add_run("نقدم لكم المواقع المتاحة في المحافظات لعرض إعلانكم الوطني من تاريخ  .................  ولغاية  .................")
    apply_rtl(p_stat)

    if cart_data:
        for city, networks in cart_data.items():
            p_city = doc.add_paragraph(f"■ محافظة {city}")
            apply_rtl(p_city)
            
            for net, df in networks.items():
                grouped = df.groupby('الحجم')
                for size, group_df in grouped:
                    p_size = doc.add_paragraph(f"قياس اللوحة: {size}")
                    apply_rtl(p_size)

                    table = doc.add_table(rows=1, cols=2)
                    table.style = 'Table Grid'
                    set_table_rtl(table) 
                    
                    hdr = table.rows[0].cells
                    hdr[0].text = f"الشبكة: {net}"
                    hdr[1].text = "العدد"
                    
                    for cell in hdr:
                        set_cell_background(cell, "660099")
                        for p in cell.paragraphs:
                            apply_rtl(p)
                            for run in p.runs:
                                run.font.color.rgb, run.bold = RGBColor(255, 255, 255), True

                    for _, row in group_df.iterrows():
                        row_cells = table.add_row().cells
                        row_cells[0].text = str(row.get('الموقع', ''))
                        row_cells[1].text = str(row.get('العدد', 1))
                        for cell in row_cells:
                            for p in cell.paragraphs: apply_rtl(p)

                    # --- الحسابات (منع الأصفار) ---
                    total_q = pd.to_numeric(group_df['العدد'], errors='coerce').sum()
                    # استخدام values[0] بدلاً من iloc[0] لضمان القيمة الصافية
                    f_print = float(group_df['fee_print'].values[0]) if 'fee_print' in group_df.columns else 0
                    f_ads = float(group_df['fee_ads'].values[0]) if 'fee_ads' in group_df.columns else 0
                    
                    res_p = total_q * f_print
                    res_a = total_q * f_ads

                    p_sum = doc.add_paragraph()
                    txt = f"العدد: {int(total_q)} | طباعة: {res_p:,.0f}$ | عرض: {res_a:,.0f}$ | الإجمالي: {res_p + res_a:,.0f}$"
                    p_sum.add_run(txt).bold = True
                    apply_rtl(p_sum)
                    doc.add_paragraph()

    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- 3. واجهة Streamlit ---

if "auth" not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 تسجيل الدخول")
    u, p = st.text_input("User"), st.text_input("Pass", type="password")
    if st.button("Login"):
        if u == "admin" and p == "preview2026":
            st.session_state.auth = True
            st.rerun()
else:
    conn = get_connection()
    if 'cart' not in st.session_state: st.session_state.cart = {}
    
    with st.sidebar:
        if os.path.exists('logo_full.png'): st.image('logo_full.png', width=180)
        page = st.radio("Menu", ["📊 Dashboard", "📄 Quotation"])

    if page == "📄 Quotation":
        st.title("📄 بناء عرض سعر")
        try:
            draw_df = pd.read_sql("SELECT * FROM [اسماء الرسم]", conn)
            sizes = draw_df['الحجم'].unique().tolist()
            cust = st.text_input("Customer Name")
            sel_size = st.selectbox("Select Size:", sizes)
            
            # جلب الأسعار بدقة وتحويلها لـ float فوراً
            subset = draw_df[draw_df['الحجم'] == sel_size]
            f_print = 0.0
            f_ads = 0.0
            for _, row in subset.iterrows():
                name = str(row['اسم الرسم'])
                if "أجور طباعة وتركيب" in name: f_print = float(row['اجرة الرسم'])
                elif "أجور عرض" in name: f_ads = float(row['اجرة الرسم'])

            st.info(f"💰 الأسعار المكتشفة: طباعة {f_print}$, عرض {f_ads}$")

            city_l = pd.read_sql("SELECT DISTINCT المحافظة FROM [اعمدة انارة]", conn)['المحافظة'].tolist()
            sel_city = st.selectbox("City", city_l)
            raw = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة='{sel_city}' AND [الحجم]='{sel_size}'", conn)
            nets = st.multiselect("Nets", raw['الشبكة'].unique().tolist())

            if st.button("➕ Add to Cart"):
                if sel_city not in st.session_state.cart: st.session_state.cart[sel_city] = {}
                for n in nets:
                    st.session_state.cart[sel_city][n] = raw[raw['الشبكة'] == n].assign(**{
                        'الحجم': sel_size, 'fee_print': f_print, 'fee_ads': f_ads
                    })
                st.rerun()

            if st.session_state.cart:
                for c_name, nts in list(st.session_state.cart.items()):
                    for n_name, df_cart in nts.items():
                        with st.expander(f"📍 {c_name} - {n_name}", expanded=True):
                            st.session_state.cart[c_name][n_name] = st.data_editor(df_cart, key=f"ed_{c_name}_{n_name}")
                
                if st.button("🚀 Export Word"):
                    doc_io = export_word(cust, st.session_state.cart, "2026")
                    st.download_button("📥 Download", doc_io, f"Quotation_{cust}.docx")
        except Exception as e: st.error(f"Error: {e}")
        conn.close()


                
