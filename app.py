import streamlit as st
import pandas as pd
import sqlite3
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from arabic_reshaper import reshape
from bidi.algorithm import get_display
import io

# إعداد الصفحة
st.set_page_config(page_title="صانع عروض بريفيو", layout="wide")

def get_connection():
    return sqlite3.connect('billboards_data.db')

def ar(text):
    if not text: return ""
    return get_display(reshape(str(text)))

# دالة تصدير الوورد المتقدمة
def export_to_word(df, customer_name, city):
    doc = Document()
    # إعداد المستند ليدعم العربي من اليمين لليسار
    for section in doc.sections:
        section.right_to_left = True

    # 1. اللوجو
    try:
        doc.add_picture('logo.png', width=Inches(1.5))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    except:
        pass

    # 2. العنوان
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run(ar("عرض سعر إعلاني"))
    run.font.size = Pt(20)
    run.font.bold = True
    run.font.color.rgb = RGBColor(102, 0, 153) # بنفسجي بريفيو

    # 3. بيانات العميل
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p.add_run(ar(f"السادة: {customer_name} المحترمين")).bold = True
    p.add_run(f"\n{ar('المحافظة:')} {ar(city)}")

    # 4. بناء الجدول بناءً على ما عدله المستخدم في المتصفح
    table = doc.add_table(rows=1, cols=len(df.columns))
    table.style = 'Table Grid'
    
    # العناوين
    hdr_cells = table.rows[0].cells
    for i, col_name in enumerate(df.columns):
        hdr_cells[i].text = ar(col_name)
    
    # الصفوف
    for _, row in df.iterrows():
        row_cells = table.add_row().cells
        for i, value in enumerate(row):
            row_cells[i].text = ar(str(value))

    # 5. التذييل
    doc.add_paragraph("\n")
    footer = doc.add_paragraph(ar("شكراً لثقتكم بنا - فريق بريفيو"))
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER

    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- واجهة المستخدم ---
st.title("🛠️ بناء وتعديل عرض السعر")

conn = get_connection()
cities_list = pd.read_sql("SELECT المحافظة FROM المحافظات", conn)['المحافظة'].tolist()

col_set, col_edit = st.columns([1, 2])

with col_set:
    st.subheader("1. البيانات الأساسية")
    cust_name = st.text_input("اسم العميل", "شركة بريفيو")
    selected_city = st.selectbox("اختر المحافظة", cities_list)
    
    # جلب اللوحات الخاصة بالمحافظة المختارة
    query = f"SELECT [اسم العمود] as الموقع, [العدد], [الحجم] FROM [اعمدة انارة] WHERE المحافظة = '{selected_city}'"
    available_poles = pd.read_sql(query, conn)
    
    selected_items = st.multiselect("اختر المواقع لإضافتها للعرض:", available_poles['الموقع'].tolist())

with col_edit:
    st.subheader("2. تخصيص الجدول (تعديل/حذف/إضافة)")
    
    # إنشاء الجدول الأولي بناءً على الاختيار
    display_df = available_poles[available_poles['الموقع'].isin(selected_items)].copy()
    
    # إضافة أعمدة فارغة للتعبئة اليدوية
    if 'السعر' not in display_df.columns:
        display_df['السعر'] = "0"
    
    # محرر الجداول التفاعلي
    edited_df = st.data_editor(display_df, num_rows="dynamic", use_container_width=True)

    st.divider()
    
    # زر التجهيز والتحميل
    if st.button("🚀 إنشاء ملف الوورد النهائي"):
        if not edited_df.empty:
            word_output = export_to_word(edited_df, cust_name, selected_city)
            
            # ظهور زر التحميل مباشرة بعد التجهيز
            st.download_button(
                label="📥 اضغط هنا لتحميل ملف الوورد",
                data=word_output,
                file_name=f"Quotation_{cust_name}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        else:
            st.warning("يرجى اختيار موقع واحد على الأقل.")
