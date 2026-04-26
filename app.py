import streamlit as st
import pandas as pd
import sqlite3
from docx import Document
import io

# --- 1. إعدادات وقاعدة البيانات ---
def get_connection():
    return sqlite3.connect('billboards_data.db')

st.set_page_config(page_title="Preview Quotation Builder", layout="wide")

# --- 2. واجهة بناء العرض ---
st.title("🛠️ صانع عروض الأسعار التفاعلي")

col_settings, col_preview = st.columns([1, 2])

with col_settings:
    st.subheader("⚙️ إعدادات العرض")
    customer = st.text_input("اسم الزبون", "شركة ...")
    city = st.selectbox("المحافظة", pd.read_sql("SELECT المحافظة FROM المحافظات", get_connection()))
    
    # اختيار الشبكات المراد إضافتها للعرض
    all_poles = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد] FROM [اعمدة انارة] WHERE المحافظة='{city}'", get_connection())
    selected_indices = st.multiselect("اختر المواقع لإضافتها للجدول:", all_poles['الموقع'].tolist())

with col_preview:
    st.subheader("📝 مراجعة وتعديل الجدول قبل التصدير")
    
    # بناء الجدول التفاعلي بناءً على الاختيارات
    df_to_edit = all_poles[all_poles['الموقع'].isin(selected_indices)].copy()
    
    # إضافة أعمدة إضافية يدوية (السعر مثلاً)
    df_to_edit['السعر'] = 0.0
    
    # ميزة التعديل المباشر (يمكنك حذف سطر أو تغيير رقم أو اسم)
    edited_df = st.data_editor(
        df_to_edit, 
        num_rows="dynamic", # تتيح لك إضافة وحذف أسطر بضغط زر
        use_container_width=True,
        key="quotation_editor"
    )

    # زر التصدير
    if st.button("🚀 تصدير العرض النهائي إلى Word"):
        # كود التصدير (سأضعه لك في الأسفل)
        st.success("جاري تجهيز الملف...")

# --- 3. دالة التصدير الذكية ---
# هذه الدالة تأخذ الجدول "بعد تعديلك له" وتحوله لوورد
def export_to_word(df, customer_info):
    doc = Document()
    doc.add_heading(f"عرض سعر: {customer_info}", 0)
    
    # إضافة الجدول المنسق
    table = doc.add_table(rows=1, cols=len(df.columns))
    table.style = 'Table Grid'
    
    # رؤوس الأعمدة
    hdr_cells = table.rows[0].cells
    for i, column in enumerate(df.columns):
        hdr_cells[i].text = str(column)
    
    # البيانات المعدلة
    for _, row in df.iterrows():
        row_cells = table.add_row().cells
        for i, value in enumerate(row):
            row_cells[i].text = str(value)
            
    # حفظ وتجهيز التحميل
    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target
