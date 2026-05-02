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

# --- 1. تعريف الدوال الأساسية (يجب أن تكون في البداية) ---

def get_connection():
    """الاتصال بقاعدة البيانات"""
    return sqlite3.connect('billboards_data.db')

def apply_rtl(obj):
    """إجبار الفقرة أو الخلية على المحاذاة لليمين واتجاه النص العربي"""
    if hasattr(obj, 'paragraphs'):
        for p in obj.paragraphs:
            _force_rtl_style(p)
    else:
        _force_rtl_style(obj)

def _force_rtl_style(p):
    """تنسيق الـ XML للفقرة لضمان عدم تقطع الحروف والمحاذاة لليمين"""
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
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
    """جعل الجدول يبدأ من اليمين لليسار"""
    tblPr = table._element.xpath('w:tblPr')[0]
    bidi = OxmlElement('w:bidiVisual')
    tblPr.append(bidi)

# --- 2. دالة تصدير الوورد الاحترافية ---

def export_word(customer_name, cart_data, period_name):
    doc = Document('template.docx') if os.path.exists('template.docx') else Document()
    
    # حل مشكلة الصفحة الأولى: إضافة مسافة علوية لكي لا يغطي اللوغو النص
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_before = Cm(3) 

    # التاريخ
    p_date = doc.add_paragraph(f"التاريخ: 2026/05/02")
    p_date.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # ترويسة الخطاب
    p_cust = doc.add_paragraph()
    p_cust.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_c = p_cust.add_run(f"السادة شركة {customer_name} المحترمين")
    run_c.bold, run_c.font.size = True, Pt(20)
    run_c.font.color.rgb = RGBColor(102, 0, 153)

    p_greet = doc.add_paragraph("تحية طيبة وبعد،")
    apply_rtl(p_greet)

    p_info = doc.add_paragraph(f"نقدم لكم المواقع المتاحة للفترة الإعلانية: {period_name}")
    apply_rtl(p_info)

    if cart_data:
        for city, networks in cart_data.items():
            p_city = doc.add_paragraph(f"■ محافظة {city}")
            apply_rtl(p_city)
            
            for net, df in networks.items():
                # التجميع حسب سعر الرسم (المقاس)
                grouped = df.groupby('اجرة الرسم')
                
                for fee, group_df in grouped:
                    # استخراج اسم المقاس إذا كان موجوداً
                    size_name = group_df['الحجم'].iloc[0] if 'الحجم' in group_df.columns else "قياس مخصص"
                    
                    p_size = doc.add_paragraph(f"القياس: {size_name} (سعر الرسم: {fee}$)")
                    apply_rtl(p_size)
                    p_size.runs[0].bold = True

                    # بناء الجدول
                    table = doc.add_table(rows=1, cols=2)
                    table.style = 'Table Grid'
                    set_table_rtl(table)
                    
                    hdr = table.rows[0].cells
                    hdr[0].text = f"الشبكة: {net}"
                    hdr[1].text = "العدد"
                    
                    for cell in hdr:
                        for p in cell.paragraphs:
                            apply_rtl(p)
                            for run in p.runs:
                                run.font.color.rgb, run.bold = RGBColor(255, 255, 255), True
                        tcPr = cell._tc.get_or_add_tcPr()
                        shd = OxmlElement('w:shd')
                        shd.set(qn('w:fill'), "660099")
                        tcPr.append(shd)

                    for _, row in group_df.iterrows():
                        row_cells = table.add_row().cells
                        row_cells[0].text = str(row.get('الموقع', ''))
                        row_cells[1].text = str(row.get('العدد', 1))
                        for cell in row_cells: apply_rtl(cell)

                    # سطر المجاميع
                    total_q = pd.to_numeric(group_df['العدد'], errors='coerce').sum()
                    total_p = pd.to_numeric(group_df.get('أجور الطباعة', 0), errors='coerce').sum()
                    
                    p_sum = doc.add_paragraph(f"العدد: {int(total_q)} | رسم: {total_q*fee:,}$ | طباعة: {total_p:,}$ | المجموع: {(total_q*fee)+total_p:,}$")
                    apply_rtl(p_sum)
                    p_sum.runs[0].font.color.rgb = RGBColor(102, 0, 153)
                    doc.add_paragraph()

    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- 3. واجهة تطبيق Streamlit ---

if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 تسجيل الدخول - PreView ERP")
    u, p = st.text_input("اسم المستخدم"), st.text_input("كلمة المرور", type="password")
    if st.button("دخول"):
        if u == "admin" and p == "preview2026":
            st.session_state.auth = True
            st.rerun()
        else: st.error("بيانات خاطئة")
else:
    # هنا تم تعريف conn بعد التأكد من وجود الدالة get_connection أعلاه
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

            city_l = pd.read_sql("SELECT DISTINCT المحافظة FROM [اعمدة انارة]", conn)['المحافظة'].tolist()
            sel_city = st.selectbox("المحافظة", city_l)
            
            raw = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة='{sel_city}'", conn)
            nets = st.multiselect("الشبكات", raw['الشبكة'].unique().tolist())

            if st.button("➕ إضافة"):
                if sel_city not in st.session_state.cart: st.session_state.cart[sel_city] = {}
                for n in nets:
                    st.session_state.cart[sel_city][n] = raw[raw['الشبكة'] == n].assign(**{'اجرة الرسم': current_fee, 'أجور الطباعة': 0, 'الحجم': sel_size})

            if st.session_state.cart:
                for c, nts in list(st.session_state.cart.items()):
                    for n, df in nts.items():
                        with st.expander(f"📍 {c} - {n}"):
                            st.session_state.cart[c][n] = st.data_editor(df, key=f"ed_{c}_{n}")
                
                if st.button("🚀 تصدير"):
                    doc_io = export_word(cust, st.session_state.cart, period)
                    st.download_button("📥 تحميل", doc_io, f"Quotation_{cust}.docx")
        except Exception as e: st.error(f"حدث خطأ: {e}")
    conn.close()
