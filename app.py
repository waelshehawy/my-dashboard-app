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

# --- دالة معالجة النصوص العربية ---
def ar(text):
    if not text: return ""
    return get_display(reshape(str(text)))

# --- دالة إنشاء مستند الوورد ---
def export_final_word(grouped_data, customer_name, city, size_name):
    doc = Document()
    for section in doc.sections:
        section.right_to_left = True

    # إضافة اللوجو بأمان
    if os.path.exists('logo.png'):
        try:
            para = doc.add_paragraph()
            para.alignment = WD_ALIGN_PARAGRAPH.LEFT
            para.add_run().add_picture('logo.png', width=Inches(1.8))
        except: pass

    # العنوان والبيانات
    doc.add_paragraph(ar(f"السادة شركة .. {customer_name} المحترمين")).bold = True
    p_city = doc.add_paragraph()
    run_city = p_city.add_run(ar(f"محافظة {city} - قياس {size_name}"))
    run_city.font.color.rgb = RGBColor(102, 0, 153)

    # بناء الجداول
    for net, df in grouped_data.items():
        doc.add_paragraph(ar(f"شبكة: {net}"))
        table = doc.add_table(rows=1, cols=2)
        table.style = 'Table Grid'
        table.rows[0].cells[0].text = ar("العدد")
        table.rows[0].cells[1].text = ar("الموقع")
        
        for _, row in df.iterrows():
            row_cells = table.add_row().cells
            row_cells[0].text = str(row['العدد'])
            row_cells[1].text = ar(row['الموقع'])

    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- واجهة Streamlit الرئيسية ---
st.title("🛠️ نظام بريفيو لعروض الأسعار")

try:
    conn = sqlite3.connect('billboards_data.db')
    
    # القوائم المنسدلة
    cities = pd.read_sql("SELECT المحافظة FROM المحافظات", conn)['المحافظة'].tolist()
    sizes = pd.read_sql("SELECT [الحجم] FROM [اساسي حجم]", conn)['الحجم'].tolist()

    cust = st.text_input("اسم الزبون")
    sel_city = st.selectbox("المحافظة", cities)
    sel_size = st.selectbox("المقاس", sizes)

    # جلب المواقع
    query = f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة = '{sel_city}' AND [الحجم] = '{sel_size}'"
    df_raw = pd.read_sql(query, conn)
    
    selected_locs = st.multiselect("اختر المواقع:", df_raw['الموقع'].tolist())

    if selected_locs:
        filtered = df_raw[df_raw['الموقع'].isin(selected_locs)]
        final_groups = {}
        for net in filtered['الشبكة'].unique():
            st.write(f"🔗 شبكة: {net}")
            net_df = filtered[filtered['الشبكة'] == net][['الموقع', 'العدد']]
            final_groups[net] = st.data_editor(net_df, key=f"edit_{net}")

        if st.button("🚀 تصدير الملف"):
            file = export_final_word(final_groups, cust, sel_city, sel_size)
            st.download_button("📥 تحميل الوورد", file, "Quotation.docx")

except Exception as e:
    st.error(f"يوجد خطأ في تشغيل التطبيق: {e}")
