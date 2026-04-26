import streamlit as st
import pandas as pd
import sqlite3
import os
import io
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from arabic_reshaper import reshape
from bidi.algorithm import get_display

# --- إعدادات الصفحة ---
st.set_page_config(page_title="Preview Ads System", layout="wide")

def ar(text):
    if not text: return ""
    return get_display(reshape(str(text)))

# --- دالة التصدير (الطريقة المبسطة والمستقرة) ---
def export_stable_quotation(customer_name, cart_data, dates):
    doc = Document()
    # إعدادات الورقة
    section = doc.sections[0]
    section.right_to_left = True
    
    # إضافة الخلفية (Watermark) بطريقة كلاسيكية
    if os.path.exists('logo.png'):
        header = section.header
        p = header.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run()
        run.add_picture('logo.png', width=Inches(7.5))

    # نص العرض
    doc.add_paragraph("\n\n")
    p_cust = doc.add_paragraph()
    p_cust.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_cust.add_run(ar(f"السادة شركة .. {customer_name} المحترمين")).bold = True
    doc.add_paragraph(ar(f"نقدم لكم المواقع المتاحة للفترة من {dates['start']} لغاية {dates['end']} م")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # بناء الجداول (جدول بسيط لكل شبكة)
    for city_name in cart_data:
        p_city = doc.add_paragraph()
        p_city.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run_city = p_city.add_run(ar(f"محافظة {city_name}"))
        run_city.font.color.rgb = RGBColor(102, 0, 153)
        run_city.font.size = Pt(16)

        networks = cart_data[city_name]
        for net_name in networks:
            doc.add_paragraph(ar(f"شبكات {net_name}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
            
            df = networks[net_name]
            # بناء جدول بعمودين فقط (الأكثر استقراراً)
            table = doc.add_table(rows=1, cols=2)
            table.style = 'Table Grid'
            
            # الرأس
            hdr_cells = table.rows[0].cells
            hdr_cells[0].text = ar("العدد")
            hdr_cells[1].text = ar("الموقع")

            # إضافة البيانات سطراً بسطر
            for i in range(len(df)):
                row_cells = table.add_row().cells
                # نأخذ القيمة من العمود الأول (الموقع) والثاني (العدد) بغض النظر عن الأسماء
                row_cells[1].text = ar(str(df.iloc[i, 0]))
                row_cells[0].text = str(df.iloc[i, 1])

            total_sum = pd.to_numeric(df.iloc[:, 1]).sum()
            doc.add_paragraph(ar(f"العدد الإجمالي: [{int(total_sum)}] | أجور الطباعة: $ | أجور العرض: $")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- واجهة التطبيق ---
if 'cart' not in st.session_state:
    st.session_state.cart = {}

st.title("🏗️ صانع عروض أسعار بريفيو")

try:
    conn = sqlite3.connect('billboards_data.db')
    c1, c2 = st.columns(2)

    with c1:
        cust = st.text_input("اسم الزبون", "وائل")
        cities = pd.read_sql("SELECT المحافظة FROM المحافظات", conn)['المحافظة'].tolist()
        city_sel = st.selectbox("اختر المحافظة", cities)
        
        # جلب البيانات
        raw = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة = '{city_sel}'", conn)
        locs = st.multiselect("اختر المواقع:", raw['الموقع'].tolist())
        
        if st.button("➕ إضافة للعرض"):
            if locs:
                filt = raw[raw['الموقع'].isin(locs)]
                # تخزين البيانات في سلة التسوق
                city_dict = {}
                for n in filt['الشبكة'].unique():
                    city_dict[n] = filt[filt['الشبكة'] == n][['الموقع', 'العدد']]
                st.session_state.cart[city_sel] = city_dict
                st.success("تمت الإضافة")

    with c2:
        if st.session_state.cart:
            for c in list(st.session_state.cart.keys()):
                with st.expander(f"📍 {c}", expanded=True):
                    for n in list(st.session_state.cart[c].keys()):
                        st.write(f"🔗 {n}")
                        st.session_state.cart[c][n] = st.data_editor(st.session_state.cart[c][n], key=f"ed_{c}_{n}")
            
            if st.button("🗑️ مسح الكل"):
                st.session_state.cart = {}
                st.rerun()

            if st.button("🚀 تصدير الملف النهائي"):
                dts = {'start': "1/5/2026", 'end': "28/5/2026"}
                final_doc = export_stable_quotation(cust, st.session_state.cart, dts)
                st.download_button("📥 تحميل الوورد", final_doc, f"Quotation_{cust}.docx")
        else:
            st.info("سلة المواقع فارغة")

except Exception as e:
    st.error(f"خطأ: {e}")
