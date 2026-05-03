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

# --- 1. الدوال الأساسية ---

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
        rFonts = OxmlElement('w:rFonts')
        rFonts.set(qn('w:cs'), 'Arial')
        rPr.append(rFonts)

def set_table_rtl(table):
    tblPr = table._element.xpath('w:tblPr')
    if tblPr:
        bidi = OxmlElement('w:bidiVisual')
        tblPr[0].append(bidi)

def set_cell_background(cell, color):
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), color)
    cell._tc.get_or_add_tcPr().append(shd)

# --- 2. دالة تصدير الوورد المصححة ---

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
                # التجميع حسب الحجم
                grouped = df.groupby('الحجم')
                
                for size, group_df in grouped:
                    p_size = doc.add_paragraph(f"قياس اللوحة: {size}")
                    apply_rtl(p_size)
                    p_size.runs[0].bold = True

                    # بناء الجدول
                    table = doc.add_table(rows=1, cols=2)
                    table.style = 'Table Grid'
                    set_table_rtl(table)
                    
                    # تصحيح الخطأ: الوصول لكل خلية في الرأس بشكل منفصل
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
                            for p in cell.paragraphs: apply_rtl(p)

                    # الحسابات
                    # --- منطق الحساب المضمون ---
                    total_q = pd.to_numeric(group_df['العدد'], errors='coerce').sum()
                    
                    # جلب الأجور مع التأكد من أنها أرقام وليست مصفوفات
                    fee_print = 0
                    if 'fee_print' in group_df.columns:
                        val = group_df['fee_print'].iloc[0]
                        fee_print = float(val) if pd.notnull(val) else 0
                        
                    fee_ads = 0
                    if 'fee_ads' in group_df.columns:
                        val = group_df['fee_ads'].iloc[0]
                        fee_ads = float(val) if pd.notnull(val) else 0
                    
                    # عملية الضرب
                    total_print = total_q * fee_print
                    total_ads = total_q * fee_ads
                    grand_total = total_print + total_ads

                    # كتابة السطر الملون والمحاذى لليمين
                    p_sum = doc.add_paragraph()
                    summary_text = (
                        f"العدد الإجمالي: {int(total_q)} | "
                        f"أجور الطباعة: {total_print:,.0f}$ | "
                        f"أجور العرض: {total_ads:,.0f}$ | "
                        f"الإجمالي: {grand_total:,.0f}$"
                    )
                    p_sum.add_run(summary_text).bold = True
                    apply_rtl(p_sum)
                    doc.add_paragraph() # مسافة للفصل


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
        else: st.error("Error")
else:
    conn = get_connection()
    if 'cart' not in st.session_state: st.session_state.cart = {}
    
    with st.sidebar:
        if os.path.exists('logo_full.png'): st.image('logo_full.png', width=180)
        page = st.radio("Menu", ["📊 Dashboard", "📄 Quotation"])

    if page == "📊 Dashboard":
        st.title("📊 حالة المواقع")
        try:
            df_m = pd.read_sql("SELECT * FROM [اعمدة انارة]", conn)
            st.dataframe(df_m, use_container_width=True)
        except: st.error("Database Error")

    elif page == "📄 عرض سعر":
        st.title("📄 بناء عرض سعر")
        try:
            # 1. جلب البيانات من الجداول
            drawing_df = pd.read_sql("SELECT * FROM [اسماء الرسم]", conn)
            sizes = drawing_df['الحجم'].unique().tolist()
            
            cust = st.text_input("اسم الزبون")
            period_list = pd.read_sql("SELECT namee FROM [الفترة]", conn)['namee'].tolist()
            sel_period = st.selectbox("الفترة", period_list)
            
            # اختر المقاس (الحجم)
            sel_size = st.selectbox("اختر المقاس:", sizes)

            # --- الجزء الجديد: جلب الأجور (ضعه هنا واحذف القديم) ---
            size_subset = drawing_df[drawing_df['الحجم'] == sel_size]
            f_print, f_ads = 0.0, 0.0
            
            for _, row in size_subset.iterrows():
                label = str(row['اسم الرسم'])
                value = float(row['اجرة الرسم'])
                if "طباعة" in label:
                    f_print = value
                elif "عرض" in label:
                    f_ads = value
            
            # عرض رسالة للتأكد من جلب الأرقام
            st.info(f"✅ أجور المكتشفة: طباعة {f_print}$ | عرض {f_ads}$")
            # ---------------------------------------------------

            city_l = pd.read_sql("SELECT DISTINCT المحافظة FROM [اعمدة انارة]", conn)['المحافظة'].tolist()
            sel_city = st.selectbox("المحافظة", city_l)
            raw = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة='{sel_city}'", conn)
            nets = st.multiselect("الشبكات", raw['الشبكة'].unique().tolist())

            if st.button("➕ إضافة للسلة"):
                if sel_city not in st.session_state.cart: st.session_state.cart[sel_city] = {}
                for n in nets:
                    # إضافة البيانات مع الأجور المكتشفة
                    st.session_state.cart[sel_city][n] = raw[raw['الشبكة'] == n].assign(**{
                        'الحجم': sel_size, 
                        'fee_print': f_print, 
                        'fee_ads': f_ads
                    })
                st.success("تمت الإضافة بنجاح")

            # عرض السلة وتصدير الوورد
            if st.session_state.cart:
                for c, nts in list(st.session_state.cart.items()):
                    for n, df in nts.items():
                        with st.expander(f"📍 {c} - {n}"):
                            st.session_state.cart[c][n] = st.data_editor(df, key=f"ed_{c}_{n}")
                
                if st.button("🚀 تصدير"):
                    doc_io = export_word(cust, st.session_state.cart, sel_period)
                    st.download_button("📥 تحميل", doc_io, f"Quotation_{cust}.docx")

        except Exception as e:
            st.error(f"حدث خطأ: {e}")

