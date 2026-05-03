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

# --- إعدادات الصفحة ---
st.set_page_config(page_title="PreView Ads ERP", layout="wide")

def get_connection():
    return sqlite3.connect('billboards_data.db')

def apply_rtl(p):
    """إجبار النص على اليمين بالمنطق العكسي وتفعيل Bidi"""
    # ضبط المحاذاة (جرب تبديل LEFT بـ RIGHT إذا لزم الأمر حسب نسخة الوورد)
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
    """جعل الجدول يبدأ من اليمين (العمود الأول يميناً)"""
    tblPr = table._element.xpath('w:tblPr')
    if tblPr:
        bidi = OxmlElement('w:bidiVisual')
        tblPr[0].append(bidi)

def set_cell_background(cell, color):
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), color)
    cell._tc.get_or_add_tcPr().append(shd)

def export_word(customer_name, cart_data, period_name):
    doc = Document('template.docx') if os.path.exists('template.docx') else Document()
    
    # تجاوز اللوغو في كل الصفحات عبر ضبط الهوامش العلوية
    for section in doc.sections:
        section.top_margin = Cm(4.5) 

    # التاريخ
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
                # التجميع حسب "الحجم" ليكون كل مقاس في جدول مستقل
                grouped = df.groupby('الحجم')
                
                for size, group_df in grouped:
                    p_size = doc.add_paragraph(f"قياس اللوحة: {size}")
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

                    # حساب المجاميع لكل مقاس
                    total_q = pd.to_numeric(group_df['العدد'], errors='coerce').sum()
                    f_print = float(group_df['fee_print'].iloc[0]) if 'fee_print' in group_df.columns else 0
                    f_ads = float(group_df['fee_ads'].iloc[0]) if 'fee_ads' in group_df.columns else 0
                    
                    p_sum = doc.add_paragraph()
                    txt = f"العدد: {int(total_q)} | طباعة: {total_q*f_print:,.0f}$ | عرض: {total_q*f_ads:,.0f}$ | الإجمالي: {(total_q*f_print)+(total_q*f_ads):,.0f}$"
                    p_sum.add_run(txt).bold = True
                    apply_rtl(p_sum)
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
    u = st.text_input("اسم المستخدم")
    p = st.text_input("كلمة المرور", type="password")
    if st.button("دخول"):
        if u == "admin" and p == "preview2026":
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("❌ بيانات الدخول خاطئة")
else:
    conn = get_connection()
    # التأكد من تهيئة السلة في ذاكرة الجلسة لضمان عدم اختفائها
    if 'cart' not in st.session_state:
        st.session_state.cart = {}
    
    with st.sidebar:
        if os.path.exists('logo_full.png'):
            st.image('logo_full.png', width=180)
        st.header("PreView Ads")
        page = st.radio("القائمة:", ["📊 الداشبورد", "📄 إنشاء عرض سعر"])
        if st.button("تسجيل الخروج"):
            st.session_state.auth = False
            st.rerun()

    if page == "📊 الداشبورد":
        st.title("📊 حالة المواقع")
        try:
            df_m = pd.read_sql("SELECT * FROM [اعمدة انارة]", conn)
            st.dataframe(df_m, use_container_width=True)
        except Exception as e:
            st.error(f"خطأ في قاعدة البيانات: {e}")

    elif page == "📄 إنشاء عرض سعر":
        st.title("📄 بناء عرض سعر احترافي")
        try:
            # جلب البيانات من الجداول
            draw_df = pd.read_sql("SELECT * FROM [اسماء الرسم]", conn)
            sizes = draw_df['الحجم'].unique().tolist()
            periods = pd.read_sql("SELECT namee FROM [الفترة]", conn)['namee'].tolist()
            
            col_input, col_cart = st.columns([1, 1.5])
            
            with col_input:
                st.subheader("⚙️ إعدادات العرض")
                cust = st.text_input("اسم الزبون")
                sel_period = st.selectbox("اختر الفترة:", periods)
                sel_size = st.selectbox("اختر المقاس:", sizes)
                
                # --- منطق جلب الأجور المزدوجة (طباعة وعرض) ---
                subset = draw_df[draw_df['الحجم'] == sel_size]
                f_print, f_ads = 0.0, 0.0
                for _, row in subset.iterrows():
                    name = str(row['اسم الرسم'])
                    val = float(row['اجرة الرسم'])
                    if "طباعة" in name: f_print = val
                    elif "عرض" in name: f_ads = val
                
                st.info(f"💰 الأسعار المكتشفة: طباعة ({f_print}$)، عرض ({f_ads}$)")

                cities = pd.read_sql("SELECT DISTINCT المحافظة FROM [اعمدة انارة]", conn)['المحافظة'].tolist()
                sel_city = st.selectbox("المحافظة:", cities)
                raw = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة='{sel_city}'", conn)
                nets = st.multiselect("اختر الشبكات المتاحة:", raw['الشبكة'].unique().tolist())

                if st.button("➕ إضافة للسلة"):
                    if sel_city not in st.session_state.cart:
                        st.session_state.cart[sel_city] = {}
                    for n in nets:
                        df_to_add = raw[raw['الشبكة'] == n].copy()
                        # إضافة معلومات الحجم والأجور لكل سطر في السلة
                        df_to_add['الحجم'] = sel_size
                        df_to_add['fee_print'] = f_print
                        df_to_add['fee_ads'] = f_ads
                        st.session_state.cart[sel_city][n] = df_to_add
                    st.success("✅ تمت الإضافة بنجاح")
                    st.rerun()

            with col_cart:
                st.subheader("🛒 السلة الحالية")
                if st.session_state.cart:
                    for c_name, nts in list(st.session_state.cart.items()):
                        for n_name, df_cart in nts.items():
                            with st.expander(f"📍 {c_name} - {n_name}", expanded=True):
                                # السماح للمستخدم بتعديل الأعداد أو الأسعار يدوياً إذا رغب
                                edited_df = st.data_editor(df_cart, key=f"ed_{c_name}_{n_name}")
                                st.session_state.cart[c_name][n_name] = edited_df
                    
                    st.divider()
                    if st.button("🚀 تصدير ملف Word"):
                        if cust:
                            doc_io = export_word(cust, st.session_state.cart, sel_period)
                            st.download_button("📥 تحميل عرض السعر", doc_io, f"Quotation_{cust}.docx")
                        else:
                            st.warning("⚠️ يرجى إدخال اسم الزبون أولاً")
                    
                    if st.button("🗑️ تفريغ السلة"):
                        st.session_state.cart = {}
                        st.rerun()
                else:
                    st.info("السلة فارغة. اختر الشبكات من اليمين واضغط إضافة.")

        except Exception as e:
            st.error(f"حدث خطأ في عرض السعر: {e}")
    conn.close()
