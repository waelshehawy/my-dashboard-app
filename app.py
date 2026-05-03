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

# --- 1. Core Functions & RTL Logic ---

def get_connection():
    return sqlite3.connect('billboards_data.db')

def apply_rtl(obj):
    """Applies RTL and Right Alignment (using Inverse Logic for Word Compatibility)"""
    if hasattr(obj, 'paragraphs'):
        for p in obj.paragraphs:
            _force_rtl_style(p)
    else:
        _force_rtl_style(obj)

def _force_rtl_style(p):
    # Setting to LEFT often correctly aligns Arabic to RIGHT in many Word versions
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
    tblPr = table._element.xpath('w:tblPr')
    if tblPr:
        bidi = OxmlElement('w:bidiVisual')
        tblPr.append(bidi)

def set_cell_background(cell, color):
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), color)
    cell._tc.get_or_add_tcPr().append(shd)

# --- 2. Word Export Logic ---

def export_word(customer_name, cart_data, period_name):
    doc = Document('template.docx') if os.path.exists('template.docx') else Document()
    
    for section in doc.sections:
        section.top_margin = Cm(4.5) 

    p_date = doc.add_paragraph(f"التاريخ: 2026/05/03")
    p_date.alignment = WD_ALIGN_PARAGRAPH.LEFT

    # اسم الزبون
    p_cust = doc.add_paragraph()
    p_cust.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_c = p_cust.add_run(f"السادة شركة {customer_name} المحترمين")
    run_c.bold, run_c.font.size = True, Pt(20)

    # التحية
    p_greet = doc.add_paragraph("تحية طيبة وبعد،")
    apply_rtl(p_greet)

    # إضافة العبارة بعد سطرين من التحية
    doc.add_paragraph() # سطر فارغ أول
    doc.add_paragraph() # سطر فارغ ثاني
    
    p_statement = doc.add_paragraph()
    p_statement.add_run("نقدم لكم المواقع المتاحة في المحافظات لعرض إعلانكم الوطني من تاريخ  .................  ولغاية  .................")
    apply_rtl(p_statement)

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
                    
                    # FIX: Access the first row explicitly
                    hdr_cells = table.rows[0].cells
                    hdr_cells[0].text = f"الشبكة: {net}"
                    hdr_cells[1].text = "العدد"
                    
                    for cell in hdr_cells:
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
                            apply_rtl(cell)

                    # Calculations
                    total_q = pd.to_numeric(group_df['العدد'], errors='coerce').sum()
                    f_print = float(group_df['fee_print'].iloc[0]) if 'fee_print' in group_df.columns else 0
                    f_ads = float(group_df['fee_ads'].iloc[0]) if 'fee_ads' in group_df.columns else 0
                    
                    p_sum = doc.add_paragraph()
                    txt = f"العدد: {int(total_q)} | طباعة: {total_q*f_print:,.0f}$ | عرض: {total_q*f_ads:,.0f}$ | الإجمالي: {(total_q*f_print)+(total_q*f_ads):,.0f}$"
                    p_sum.add_run(txt).bold = True
                    apply_rtl(p_sum)
    
    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- 3. Streamlit Interface ---

if "auth" not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 PreView ERP Login")
    u, p = st.text_input("User"), st.text_input("Pass", type="password")
    if st.button("Login"):
        if u == "admin" and p == "preview2026":
            st.session_state.auth = True
            st.rerun()
        else: st.error("Access Denied")
else:
    conn = get_connection()
    if 'cart' not in st.session_state: st.session_state.cart = {}
    
    with st.sidebar:
        if os.path.exists('logo_full.png'): st.image('logo_full.png', width=180)
        page = st.radio("القائمة", ["📊 الداشبورد", "📄 إنشاء عرض سعر"])

    if page == "📄 إنشاء عرض سعر":
        st.title("📄 بناء عرض سعر احترافي")
        try:
            draw_df = pd.read_sql("SELECT * FROM [اسماء الرسم]", conn)
            sizes = draw_df['الحجم'].unique().tolist()
            
            cust = st.text_input("اسم الزبون")
            sel_size = st.selectbox("اختر المقاس (لفلترة المواقع وجلب الأجور):", sizes)
            
            subset = draw_df[draw_df['الحجم'] == sel_size]
            f_print, f_ads = 0.0, 0.0
            for _, row in subset.iterrows():
                name = str(row['اسم الرسم'])
                if " أجور طباعة وتركيب" in name: f_print = float(row['اجرة الرسم'])
                elif "أجور عرض" in name: f_ads = float(row['اجرة الرسم'])

            st.info(f"💡 المقاس {sel_size} | أجر الطباعة: {f_print}$ | أجر العرض: {f_ads}$")

            city_l = pd.read_sql("SELECT DISTINCT المحافظة FROM [اعمدة انارة]", conn)['المحافظة'].tolist()
            sel_city = st.selectbox("المحافظة:", city_l)
            
            # METHODOLOGICAL FIX: Ensure size match in query
            query = f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة='{sel_city}' AND [الحجم]='{sel_size}'"
            raw = pd.read_sql(query, conn)
            
            if raw.empty:
                st.warning(f"⚠️ لا توجد لوحات بمقاس {sel_size} في محافظة {sel_city}")
            else:
                nets = st.multiselect("الشبكات المتاحة لهذا المقاس:", raw['الشبكة'].unique().tolist())

                if st.button("➕ إضافة للسلة"):
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
                
                if st.button("🚀 تصدير Word"):
                    doc_io = export_word(cust, st.session_state.cart, "2026")
                    st.download_button("📥 تحميل المستند", doc_io, f"Quotation_{cust}.docx")
                if st.button("🗑️ تفريغ"): st.session_state.cart = {}; st.rerun()
        except Exception as e: st.error(f"Error: {e}")
    conn.close()
