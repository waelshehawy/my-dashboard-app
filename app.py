import streamlit as st
import pandas as pd
import sqlite3
import os
import io
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from arabic_reshaper import reshape
from bidi.algorithm import get_display

def ar(text):
    if not text: return ""
    return get_display(reshape(str(text)))

def export_watermark_word(grouped_data, customer_name, city, size_name):
    doc = Document()
    
    # 1. إعداد الصفحة لتكون من اليمين لليسار
    section = doc.sections[0]
    section.right_to_left = True

    # 2. إضافة الصورة كعلامة مائية (خلف النص)
    if os.path.exists('logo.png'):
        header = section.header
        # إزالة المسافات الافتراضية في الرأس
        header.paragraphs[0].clear()
        p = header.paragraphs[0]
        run = p.add_run()
        # إضافة الصورة بحجم يغطي الصفحة تقريباً (مثلاً 6.5 بوصة عرض)
        picture = run.add_picture('logo.png', width=Inches(6.5))
        
        # كود تقني لجعل الصورة "خلف النص" (Floating Image)
        # ملاحظة: مكتبة docx الأساسية تضعها في الرأس، لتبدو كخلفية شفافة
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # 3. جسم المستند (النص سيظهر الآن فوق الخلفية)
    doc.add_paragraph("\n\n") # إزاحة بسيطة للأسفل
    
    p_cust = doc.add_paragraph()
    p_cust.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run_c = p_cust.add_run(ar(f"السادة شركة .. {customer_name} المحترمين"))
    run_c.font.size = Pt(16)
    run_c.bold = True

    doc.add_paragraph(ar(f"محافظة: {city} | القياس: {size_name}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # 4. الجداول المزدوجة الاحترافية
    for net, df in grouped_data.items():
        doc.add_paragraph(ar(f"شبكات {net}")).bold = True
        table = doc.add_table(rows=1, cols=4)
        table.style = 'Table Grid'
        
        # رؤوس الجدول
        hdr = table.rows[0].cells
        hdr[0].text, hdr[1].text = ar("العدد"), ar("الموقع")
        hdr[2].text, hdr[3].text = ar("العدد"), ar("الموقع")

        data = df.values.tolist()
        for i in range(0, len(data), 2):
            row = table.add_row().cells
            row[0].text = str(data[i][1]) # العدد
            row[1].text = ar(data[i][0])  # الموقع
            if i + 1 < len(data):
                row[2].text = str(data[i+1][1])
                row[3].text = ar(data[i+1][0])

    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- واجهة المستخدم ---
# (استخدم نفس كود الواجهة السابق للربط بـ SQL و Streamlit)


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
