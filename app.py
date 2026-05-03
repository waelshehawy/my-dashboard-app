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

# --- 1. الدوال الأساسية وتصحيح الاتجاه ---

def get_connection():
    return sqlite3.connect('billboards_data.db')

def apply_rtl(p):
    """إجبار النص على اليمين بالمنطق العكسي وتفعيل Bidi"""
    # في بعض البيئات، الضبط على LEFT مع Bidi يظهر النص في اليمين بشكل صحيح
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
    """ضبط اتجاه الجدول ليبدأ من اليمين (العمود الأول يميناً)"""
    tblPr = table._element.xpath('w:tblPr')
    if tblPr:
        bidi = OxmlElement('w:bidiVisual')
        tblPr[0].append(bidi)

def set_cell_background(cell, color):
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), color)
    cell._tc.get_or_add_tcPr().append(shd)

# --- 2. دالة تصدير الوورد بتجميع المقاسات ---

def export_word(customer_name, cart_data, period_name):
    doc = Document('template.docx') if os.path.exists('template.docx') else Document()
    
    # تجاوز اللوغو في كافة الصفحات عبر ضبط الهوامش العلوية
    for section in doc.sections:
        section.top_margin = Cm(4.5) 

    # التاريخ (محاذاة يمين ليظهر في مكانه الصحيح)
    p_date = doc.add_paragraph(f"التاريخ: 2026/05/03")
    p_date.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # ترويسة الخطاب
    p_cust = doc.add_paragraph()
    p_cust.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_c = p_cust.add_run(f"السادة شركة {customer_name} المحترمين")
    run_c.bold, run_c.font.size = True, Pt(20)
    run_c.font.color.rgb = RGBColor(102, 0, 153)

    p_greet = doc.add_paragraph("تحية طيبة وبعد،")
    apply_rtl(p_greet)

    p_info = doc.add_paragraph(f"نقدم لكم المواقع المتاحة للفترة: {period_name}")
    apply_rtl(p_info)

    if cart_data:
        for city, networks in cart_data.items():
            p_city = doc.add_paragraph(f"■ محافظة {city}")
            apply_rtl(p_city)
            
            for net, df in networks.items():
                # التجميع حسب "الحجم" (المقاس)
                grouped = df.groupby('الحجم')
                
                for size, group_df in grouped:
                    p_size = doc.add_paragraph(f"قياس اللوحة: {size}")
                    apply_rtl(p_size)
                    p_size.runs[0].bold = True

                    # بناء الجدول (الشبكة في الرأس كما طلبت)
                    table = doc.add_table(rows=1, cols=2)
                    table.style = 'Table Grid'
                    set_table_rtl(table)
                    
                    hdr = table.rows[0].cells
                    hdr.text = f"الشبكة: {net}"
                    hdr.text = "العدد"
                    
                    for cell in hdr:
                        set_cell_background(cell, "660099")
                        for p in cell.paragraphs:
                            apply_rtl(p)
                            for run in p.runs:
                                run.font.color.rgb, run.bold = RGBColor(255, 255, 255), True

                    # تعبئة المواقع
                    for _, row in group_df.iterrows():
                        row_cells = table.add_row().cells
                        row_cells[0].text = str(row.get('الموقع', ''))
                        row_cells[1].text = str(row.get('العدد', 1))
                        for cell in row_cells:
                            for p in cell.paragraphs: apply_rtl(p)

                    # حساب المجاميع لكل مقاس (ضرب المجموع الكلي في الأجور)
                    total_q = pd.to_numeric(group_df['العدد'], errors='coerce').sum()
                    fee_print = group_df['fee_print'].iloc[0] if 'fee_print' in group_df.columns else 0
                    fee_ads = group_df['fee_ads'].iloc[0] if 'fee_ads' in group_df.columns else 0
                    
                    total_print = total_q * fee_print
                    total_ads = total_q * fee_ads

                    p_sum = doc.add_paragraph()
                    summary_text = f"العدد: {int(total_q)} | أجور الطباعة: {total_print:,}$ | أجور العرض: {total_ads:,}$ | الإجمالي: {total_print + total_ads:,}$"
                    p_sum.add_run(summary_text).bold = True
                    apply_rtl(p_sum)
                    doc.add_paragraph()

    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- 3. واجهة تطبيق Streamlit ---

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

    if page == "📊 Dashboard":
        st.title("📊 حالة المواقع")
        df_m = pd.read_sql("SELECT * FROM [اعمدة انارة]", conn)
        st.dataframe(df_m, use_container_width=True)

    elif page == "📄 Quotation":
        st.title("📄 بناء عرض سعر")
        try:
            # جلب المقاسات الفريدة من جدول اسماء الرسم
            drawing_df = pd.read_sql("SELECT * FROM [اسماء الرسم]", conn)
            sizes = drawing_df['الحجم'].unique().tolist()
            
            cust = st.text_input("Customer Name")
            period = pd.read_sql("SELECT namee FROM [الفترة]", conn)['namee'].tolist()
            sel_period = st.selectbox("Period", period)
            sel_size = st.selectbox("Select Size:", sizes)
            
            # جلب أجور الطباعة والعرض لهذا المقاس تلقائياً
            size_data = drawing_df[drawing_df['الحجم'] == sel_size]
            fee_print = size_data[size_data['اسم الرسم'].str.contains("طباعة", na=False)]['اجرة الرسم'].iloc[0] if not size_data[size_data['اسم الرسم'].str.contains("طباعة", na=False)].empty else 0
            fee_ads = size_data[size_data['اسم الرسم'].str.contains("عرض", na=False)]['اجرة الرسم'].iloc[0] if not size_data[size_data['اسم الرسم'].str.contains("عرض", na=False)].empty else 0

            city_l = pd.read_sql("SELECT DISTINCT المحافظة FROM [اعمدة انارة]", conn)['المحافظة'].tolist()
            sel_city = st.selectbox("City", city_l)
            raw = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة='{sel_city}'", conn)
            nets = st.multiselect("Nets", raw['الشبكة'].unique().tolist())

            if st.button("➕ Add to Cart"):
                if sel_city not in st.session_state.cart: st.session_state.cart[sel_city] = {}
                for n in nets:
                    st.session_state.cart[sel_city][n] = raw[raw['الشبكة'] == n].assign(**{
                        'الحجم': sel_size,
                        'fee_print': fee_print,
                        'fee_ads': fee_ads
                    })

            if st.session_state.cart:
                for c, nts in list(st.session_state.cart.items()):
                    for n, df in nts.items():
                        with st.expander(f"📍 {c} - {n}"):
                            st.session_state.cart[c][n] = st.data_editor(df, key=f"ed_{c}_{n}")
                
                if st.button("🚀 Export Word"):
                    doc_io = export_word(cust, st.session_state.cart, sel_period)
                    st.download_button("📥 Download", doc_io, f"Quotation_{cust}.docx")
        except Exception as e: st.error(f"Error: {e}")
    conn.close()
