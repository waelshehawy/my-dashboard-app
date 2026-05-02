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
    """إجبار النص على اليمين بالمنطق العكسي (Left لتظهر Right عندك)"""
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

def set_cell_background(cell, color):
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), color)
    cell._tc.get_or_add_tcPr().append(shd)

# --- 2. دالة تصدير الوورد ---

def export_word(customer_name, cart_data, period_name):
    doc = Document('template.docx') if os.path.exists('template.docx') else Document()
    
    # حل مشكلة اللوغو: ضبط هامش علوي كبير لكل الصفحات لضمان عدم تداخل النص
    for section in doc.sections:
        section.top_margin = Cm(4.5) 

    # التاريخ (محاذاة يمين ليظهر يساراً كما كان صحيحاً عندك)
    p_date = doc.add_paragraph(f"التاريخ: 2026/05/02")
    p_date.alignment = WD_ALIGN_PARAGRAPH.LEFT

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
                # 1. التجميع حسب السعر (الذي يمثل المقاس/الحجم)
                grouped = df.groupby('اجرة الرسم')
                
                for fee, group_df in grouped:
                    # جلب مسمى الرسم (مثلاً: أجور طباعة فلكس أو أجور عرض لوحة)
                    drawing_name = group_df['اسم الرسم'].iloc[0] if 'اسم الرسم' in group_df.columns else ""
                    
                    # عنوان الجدول الفرعي
                    p_size = doc.add_paragraph(f"البيان: {drawing_name} (سعر الوحدة: {fee}$)")
                    apply_rtl(p_size)
                    p_size.runs[0].bold = True

                    # بناء الجدول (الموقع | العدد)
                    table = doc.add_table(rows=1, cols=2)
                    table.style = 'Table Grid'
                    table._element.xpath('w:tblPr')[0].append(OxmlElement('w:bidiVisual'))
                    
                    hdr = table.rows[0].cells
                    hdr[0].text = "اسم الموقع / العمود"
                    hdr[1].text = "العدد"
                    for cell in hdr:
                        set_cell_background(cell, "660099")
                        for p in cell.paragraphs:
                            apply_rtl(p)
                            for r in p.runs: r.font.color.rgb, r.bold = RGBColor(255, 255, 255), True

                    # تعبئة الصفوف
                    for _, row in group_df.iterrows():
                        row_cells = table.add_row().cells
                        row_cells[0].text = str(row.get('الموقع', ''))
                        row_cells[1].text = str(row.get('العدد', 1))
                        for cell in row_cells:
                            for p in cell.paragraphs: apply_rtl(p)

                    # --- منطق الحساب الذكي ---
                    total_q = pd.to_numeric(group_df['العدد'], errors='coerce').sum()
                    total_value = total_q * fee
                    
                    # تحديد هل المبلغ يتبع للطباعة أم للعرض بناءً على "اسم الرسم"
                    print_total = 0
                    ads_total = 0
                    
                    if "طباعة" in drawing_name:
                        print_total = total_value
                    elif "عرض" in drawing_name:
                        ads_total = total_value
                    else:
                        # إذا لم يوجد مسمى صريح، نضعها في العرض كافتراض
                        ads_total = total_value

                    # سطر المجاميع أسفل الجدول
                    p_sum = doc.add_paragraph()
                    # بناء نص المجموع بناءً على النوع المكتشف
                    summary_text = f"إجمالي العدد: {int(total_q)} | "
                    if print_total > 0: summary_text += f"إجمالي أجور الطباعة: {print_total:,}$"
                    if ads_total > 0: summary_text += f"إجمالي أجور العرض: {ads_total:,}$"
                    
                    p_sum.add_run(summary_text).bold = True
                    apply_rtl(p_sum)
                    doc.add_paragraph() # سطر فارغ للفصل

                    # بناء الجدول
                    table = doc.add_table(rows=1, cols=2)
                    table.style = 'Table Grid'
                    # تفعيل اتجاه الجدول RTL
                    table._element.xpath('w:tblPr')[0].append(OxmlElement('w:bidiVisual'))
                    
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

                    # سطر المجاميع
                    total_q = pd.to_numeric(group_df['العدد'], errors='coerce').sum()
                    total_p = pd.to_numeric(group_df.get('أجور الطباعة', 0), errors='coerce').sum()
                    
                    p_sum = doc.add_paragraph(f"العدد: {int(total_q)} | رسم: {total_q*fee:,}$ | طباعة: {total_p:,}$ | المجموع: {(total_q*fee)+total_p:,}$")
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
    u = st.text_input("User")
    p = st.text_input("Password", type="password")
    if st.button("دخول"):
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
            df_periods = pd.read_sql("SELECT namee FROM [الفترة]", conn)['namee'].tolist()
            drawing_df = pd.read_sql("SELECT * FROM [اسماء الرسم]", conn)
            
            cust = st.text_input("Customer Name")
            period = st.selectbox("Period", df_periods)
            sel_size = st.selectbox("Size/Drawing Type:", drawing_df['الحجم'].tolist())
            
            # جلب البيانات من جدول اسماء الرسم
            drawing_info = drawing_df[drawing_df['الحجم'] == sel_size].iloc[0]
            current_fee = drawing_info['اجرة الرسم']
            drawing_name = drawing_info['اسم الرسم']

            city_l = pd.read_sql("SELECT DISTINCT المحافظة FROM [اعمدة انارة]", conn)['المحافظة'].tolist()
            sel_city = st.selectbox("City", city_l)
            
            raw = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة='{sel_city}'", conn)
            nets = st.multiselect("Nets", raw['الشبكة'].unique().tolist())

            if st.button("➕ Add to Cart"):
                if sel_city not in st.session_state.cart: st.session_state.cart[sel_city] = {}
                for n in nets:
                    st.session_state.cart[sel_city][n] = raw[raw['الشبكة'] == n].assign(**{
                        'اجرة الرسم': current_fee, 
                        'اسم الرسم': drawing_name,
                        'أجور الطباعة': 0
                    })

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
