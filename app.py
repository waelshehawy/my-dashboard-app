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
    """تصحيح عرض النصوص العربية RTL"""
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

def set_arabic_format(paragraph):
    """إجبار الفقرة على دعم العربية والاتصال الصحيح للحروف"""
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    # تعديل الـ XML الخاص بالفقرة
    pPr = paragraph._element.get_or_add_pPr()
    bidi = OxmlElement('w:bidi')
    bidi.set(qn('w:val'), '1')
    pPr.append(bidi)
    
    # تعديل الـ XML الخاص بالنص (Run) لضمان عدم تقطع الحروف
    for run in paragraph.runs:
        rPr = run._element.get_or_add_rPr()
        rtl = OxmlElement('w:rtl')
        rtl.set(qn('w:val'), '1')
        rPr.append(rtl)
        # تحديد نوع الخط العربي لضمان الاتصال
        lang = OxmlElement('w:lang')
        lang.set(qn('w:bidi'), 'ar-SA')
        rPr.append(lang)

def export_word(customer_name, cart_data, period_name):
    doc = Document('template.docx') if os.path.exists('template.docx') else Document()

    # 1. التاريخ
    p_date = doc.add_paragraph()
    p_date.add_run(ar(f"التاريخ: 2026/05/02"))
    p_date.alignment = WD_ALIGN_PARAGRAPH.LEFT

    # 2. اسم الزبون
    p_cust = doc.add_paragraph()
    run_c = p_cust.add_run(ar(f"السادة شركة {customer_name} المحترمين"))
    run_c.bold = True
    run_c.font.size = Pt(20)
    set_arabic_format(p_cust) # تطبيق التنسيق العربي

    # 3. التحية
    p_greet = doc.add_paragraph()
    p_greet.add_run(ar("تحية طيبة وبعد،"))
    set_arabic_format(p_greet)

    p_period = doc.add_paragraph()
    p_period.add_run(ar(f"نقدم لكم المواقع المتاحة للفترة: {period_name}"))
    set_arabic_format(p_period)

    # 4. بناء الجداول
    if cart_data:
        for city, networks in cart_data.items():
            p_city = doc.add_paragraph()
            p_city.add_run(ar(f"■ محافظة {city}"))
            set_arabic_format(p_city)
            
            for net, df in networks.items():
                p_net = doc.add_paragraph()
                p_net.add_run(ar(f"شبكة: {net}"))
                set_arabic_format(p_net)
                
                table = doc.add_table(rows=1, cols=2)
                table.style = 'Table Grid'
                table.alignment = WD_ALIGN_PARAGRAPH.CENTER
                
                hdr_cells = table.rows[0].cells
                hdr_cells[0].text = ar("اسم الموقع / العمود")
                hdr_cells[1].text = ar("العدد")
                
                for cell in hdr_cells:
                    set_cell_shading(cell, "660099")
                    set_arabic_format(cell.paragraphs[0])
                    for run in cell.paragraphs[0].runs:
                        run.font.color.rgb = RGBColor(255, 255, 255)
                        run.bold = True

                for _, row in df.iterrows():
                    row_cells = table.add_row().cells
                    row_cells[0].text = ar(row.get('الموقع', ''))
                    row_cells[1].text = str(row.get('العدد', 1))
                    for cell in row_cells:
                        set_arabic_format(cell.paragraphs[0])

                # حساب المجاميع
                total_qty = pd.to_numeric(df['العدد'], errors='coerce').sum()
                fee_val = pd.to_numeric(df['اجرة الرسم'], errors='coerce') if 'اجرة الرسم' in df.columns else 0
                total_drawing = (pd.to_numeric(df['العدد'], errors='coerce') * fee_val).sum()
                total_printing = pd.to_numeric(df.get('أجور الطباعة', 0), errors='coerce').sum()

                p_sum = doc.add_paragraph()
                summary_text = (
                    f"{ar('إجمالي العدد:')} {int(total_qty)} | "
                    f"{ar('إجمالي أجور الرسم:')} {total_drawing:,}$ | "
                    f"{ar('إجمالي أجور الطباعة:')} {total_printing:,}$"
                )
                p_sum.add_run(summary_text).bold = True
                set_arabic_format(p_sum)

    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target


# --- واجهة تطبيق Streamlit ---
if "auth" not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 تسجيل الدخول - PreView ERP")
    u, p = st.text_input("Username"), st.text_input("Password", type="password")
    if st.button("دخول"):
        if u == "admin" and p == "preview2026":
            st.session_state.auth = True
            st.rerun()
        else: st.error("بيانات الدخول خاطئة")
else:
    conn = get_connection()
    if 'cart' not in st.session_state: st.session_state.cart = {}
    
    with st.sidebar:
        if os.path.exists('logo_full.png'): st.image('logo_full.png', width=180)
        page = st.radio("القائمة", ["📊 الداشبورد", "📄 إنشاء عرض سعر"])

    if page == "📊 الداشبورد":
        st.title("📊 حالة المواقع والخريطة")
        df_m = pd.read_sql("SELECT * FROM [اعمدة انارة]", conn)
        st.dataframe(df_m, use_container_width=True)

    elif page == "📄 إنشاء عرض سعر":
        st.title("📄 بناء عرض سعر ذكي")
        try:
            # 1. جلب البيانات من الجداول الصحيحة
            df_periods = pd.read_sql("SELECT namee FROM [الفترة]", conn)['namee'].tolist()
            # تصحيح اسم الجدول هنا إلى [اسماء الرسم]
            drawing_df = pd.read_sql("SELECT * FROM [اسماء الرسم]", conn)
            
            cust = st.text_input("اسم الشركة / الزبون")
            period = st.selectbox("اختر الفترة الإعلانية", df_periods)
            
            city_l = pd.read_sql("SELECT DISTINCT المحافظة FROM [اعمدة انارة]", conn)['المحافظة'].tolist()
            sel_c = st.selectbox("المحافظة", city_l)
            
            # اختيار مقاس الرسم لجلب الأجرة
            sel_size = st.selectbox("اختر نوع/مقاس الرسم:", drawing_df['الحجم'].tolist())
            # جلب أجرة الرسم بناءً على الحجم المختار
            current_fee = drawing_df[drawing_df['الحجم'] == sel_size]['اجرة الرسم'].values[0]

            raw = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة='{sel_c}'", conn)
            nets = st.multiselect("اختر الشبكات المتاحة:", raw['الشبكة'].unique().tolist())

            if st.button("➕ إضافة المواقع المختارة"):
                if sel_c not in st.session_state.cart: st.session_state.cart[sel_c] = {}
                for n in nets:
                    df_to_add = raw[raw['الشبكة'] == n].copy()
                    df_to_add['اجرة الرسم'] = current_fee # إضافة أجرة الرسم لكل سطر
                    df_to_add['أجور الطباعة'] = 0
                    st.session_state.cart[sel_c][n] = df_to_add

            # تحرير البيانات وتصديرها
            if st.session_state.cart:
                st.write("---")
                for c, nts in list(st.session_state.cart.items()):
                    for n, df in nts.items():
                        with st.expander(f"📍 {c} - {n}"):
                            st.session_state.cart[c][n] = st.data_editor(df, key=f"ed_{c}_{n}")
                
                if st.button("🚀 تصدير عرض السعر (Word)"):
                    if cust:
                        doc_io = export_word(cust, st.session_state.cart, period)
                        st.download_button("📥 تحميل الملف الجاهز", doc_io, f"Quotation_{cust}.docx")
                    else: st.warning("يرجى إدخال اسم الزبون أولاً")
        except Exception as e:
            st.error(f"حدث خطأ في قاعدة البيانات: {e}")
    conn.close()
