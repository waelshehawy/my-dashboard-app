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

    elif page == "📄 إنشاء عرض سعر":
        st.title("📄 بناء عرض سعر احترافي")
        
        # التأكد من تهيئة السلة في ذاكرة الجلسة
        if 'cart' not in st.session_state:
            st.session_state.cart = {}

        try:
            # 1. جلب البيانات الأساسية
            drawing_df = pd.read_sql("SELECT * FROM [اسماء الرسم]", conn)
            sizes = drawing_df['الحجم'].unique().tolist()
            periods_list = pd.read_sql("SELECT namee FROM [الفترة]", conn)['namee'].tolist()
            
            # تقسيم الشاشة لسهولة العرض
            col_input, col_cart = st.columns([1, 1.5])
            
            with col_input:
                st.subheader("⚙️ إعدادات العرض")
                cust = st.text_input("اسم الزبون")
                period = st.selectbox("اختر الفترة:", periods_list)
                sel_size = st.selectbox("اختر المقاس:", sizes)

                # جلب الأسعار المزدوجة للمقاس المختار
                size_subset = drawing_df[drawing_df['الحجم'] == sel_size]
                f_print, f_ads = 0.0, 0.0
                for _, row in size_subset.iterrows():
                    label = str(row['اسم الرسم'])
                    val = float(row['اجرة الرسم']) if pd.notnull(row['اجرة الرسم']) else 0.0
                    if "طباعة" in label: f_print = val
                    elif "عرض" in label: f_ads = val
                
                st.info(f"💰 أجور المقاس: طباعة ({f_print}$)، عرض ({f_ads}$)")

                # جلب المحافظات والشبكات
                cities = pd.read_sql("SELECT DISTINCT المحافظة FROM [اعمدة انارة]", conn)['المحافظة'].tolist()
                sel_city = st.selectbox("المحافظة:", cities)
                raw = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة='{sel_city}'", conn)
                nets = st.multiselect("اختر الشبكات:", raw['الشبكة'].unique().tolist())

                if st.button("➕ إضافة للسلة"):
                    if sel_city not in st.session_state.cart:
                        st.session_state.cart[sel_city] = {}
                    for n in nets:
                        df_to_add = raw[raw['الشبكة'] == n].copy()
                        df_to_add['الحجم'] = sel_size
                        df_to_add['fee_print'] = f_print
                        df_to_add['fee_ads'] = f_ads
                        st.session_state.cart[sel_city][n] = df_to_add
                    st.success("تمت الإضافة!")
                    st.rerun() # إجبار المتصفح على التحديث لرؤية النتائج فوراً

            with col_cart:
                st.subheader("🛒 السلة الحالية")
                if st.session_state.cart:
                    # تكرار عرض الجداول الموجودة في السلة
                    for city_name, nets_in_city in list(st.session_state.cart.items()):
                        for net_name, df_in_cart in nets_in_city.items():
                            with st.expander(f"📍 {city_name} - {net_name}", expanded=True):
                                # عرض الجدول والسماح بالتعديل
                                updated_df = st.data_editor(df_in_cart, key=f"editor_{city_name}_{net_name}")
                                st.session_state.cart[city_name][net_name] = updated_df
                    
                    st.divider()
                    if st.button("🚀 تصدير ملف Word"):
                        if cust:
                            doc_io = export_word(cust, st.session_state.cart, period)
                            st.download_button("📥 تحميل الآن", doc_io, f"Quotation_{cust}.docx")
                        else:
                            st.warning("⚠️ أدخل اسم الزبون أولاً")
                    
                    if st.button("🗑️ تفريغ"):
                        st.session_state.cart = {}
                        st.rerun()
                else:
                    st.warning("السلة فارغة. اختر المواقع من اليمين واضغط إضافة.")

        except Exception as e:
            st.error(f"حدث خطأ: {e}")


