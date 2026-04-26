import streamlit as st
import pandas as pd
import sqlite3
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from arabic_reshaper import reshape
from bidi.algorithm import get_display
import io

st.set_page_config(page_title="Preview Quotation System", layout="wide")

def get_connection():
    return sqlite3.connect('billboards_data.db')

def ar(text):
    if not text: return ""
    return get_display(reshape(str(text)))

# --- دالة التصدير المتقدمة (جداول متعددة حسب الشبكة) ---
def export_advanced_word(grouped_data, customer_name, city, size_name):
    doc = Document()
    for section in doc.sections:
        section.right_to_left = True

    # 1. اللوجو في اليسار
    try:
        doc.add_picture('logo.png', width=Inches(1.2))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.LEFT
    except: pass

    # 2. العنوان والبيانات
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run(ar(f"عرض سعر إعلاني - محافظة {city}"))
    run.font.size, run.font.bold, run.font.color.rgb = Pt(18), True, RGBColor(102, 0, 153)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p.add_run(ar(f"السادة: {customer_name} المحترمين")).bold = True
    p.add_run(f"\n{ar('القياس:')} {ar(size_name)}")

    # 3. إنشاء جداول منفصلة لكل شبكة
    for network_name, group_df in grouped_data.items():
        doc.add_paragraph("\n")
        doc.add_paragraph(ar(f"شبكة: {network_name}")).bold = True
        
        table = doc.add_table(rows=1, cols=len(group_df.columns))
        table.style = 'Table Grid'
        
        # الرؤوس
        for i, col in enumerate(group_df.columns):
            table.rows[0].cells[i].text = ar(col)
        
        # البيانات
        for _, row in group_df.iterrows():
            row_cells = table.add_row().cells
            for i, val in enumerate(row):
                row_cells[i].text = ar(str(val))
        
        # تذييل الجدول (المجاميع والأسعار)
        total_poles = group_df['العدد'].astype(int).sum()
        footer = doc.add_paragraph()
        footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        footer.add_run(ar(f"مجموع الأعمدة: {total_poles} | "))
        footer.add_run(ar("أجور الطباعة والتركيب للوجه الواحد: $_____ | "))
        footer.add_run(ar("أجور العرض لشهر واحد: $_____"))

    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- الواجهة ---
st.title("🏛️ صانع العروض المبوب (حسب الشبكات)")

conn = get_connection()
# جلب المقاسات والمحافظات
sizes_df = pd.read_sql("SELECT [الحجم] FROM [اساسي حجم]", conn)
cities_list = pd.read_sql("SELECT المحافظة FROM المحافظات", conn)['المحافظة'].tolist()

col_s, col_e = st.columns([1, 2])

with col_s:
    cust_name = st.text_input("اسم العميل")
    city = st.selectbox("اختر المحافظة", cities_list)
    size = st.selectbox("اختر مقاس اللوحة", sizes_df['الحجم'].tolist())
    
    # جلب البيانات مجمعة حسب الشبكة
    query = f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة = '{city}' AND [الحجم] = '{size}'"
    raw_data = pd.read_sql(query, conn)
    
    selected_locations = st.multiselect("اختر المواقع:", raw_data['الموقع'].tolist())

with col_e:
    if selected_locations:
        filtered_df = raw_data[raw_data['الموقع'].isin(selected_locations)]
        
        # تقسيم البيانات برمجياً لعرضها في المتصفح
        networks = filtered_df['الشبكة'].unique()
        final_grouped_data = {}

        for net in networks:
            st.write(f"🔗 **شبكة: {net}**")
            net_df = filtered_df[filtered_df['الشبكة'] == net][['الموقع', 'العدد']]
            edited = st.data_editor(net_df, key=f"edit_{net}", num_rows="dynamic")
            final_grouped_data[net] = edited

        if st.button("🚀 تصدير العرض المبوب (Word)"):
            doc_file = export_advanced_word(final_grouped_data, cust_name, city, size)
            st.download_button("📥 تحميل العرض النهائي", doc_file, f"Quotation_{city}.docx")
    else:
        st.info("يرجى اختيار المحافظة والمقاس ثم تحديد المواقع للبدء.")
