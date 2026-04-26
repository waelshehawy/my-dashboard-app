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

st.set_page_config(page_title="Preview Ads - Stable System", layout="wide")

def ar(text):
    if not text: return ""
    return get_display(reshape(str(text)))

def get_connection():
    return sqlite3.connect('billboards_data.db')

def export_stable_quotation(customer_name, cart_data, dates):
    doc = Document()
    section = doc.sections[0]
    section.right_to_left = True
    if os.path.exists('logo.png'):
        header = section.header
        p = header.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture('logo.png', width=Inches(7.5))

    doc.add_paragraph("\n\n")
    p_cust = doc.add_paragraph()
    p_cust.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_cust.add_run(ar(f"السادة شركة .. {customer_name} المحترمين")).bold = True
    doc.add_paragraph(ar(f"نقدم لكم المواقع المتاحة للفترة: {dates['period']} لعام {dates['year']}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

    for city_name, networks in cart_data.items():
        p_city = doc.add_paragraph()
        p_city.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run_city = p_city.add_run(ar(f"محافظة {city_name}"))
        run_city.font.color.rgb = RGBColor(102, 0, 153)
        run_city.font.size = Pt(16)

        for net_name, df in networks.items():
            doc.add_paragraph(ar(f"شبكة: {net_name}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
            table = doc.add_table(rows=1, cols=2)
            table.style = 'Table Grid'
            table.cell(0,0).text = ar("العدد")
            table.cell(0,1).text = ar("الموقع")

            for i in range(len(df)):
                row = table.add_row().cells
                row[0].text = str(df.iloc[i, 1])
                row[1].text = ar(df.iloc[i, 0])

            total_sum = pd.to_numeric(df.iloc[:, 1]).sum()
            doc.add_paragraph(ar(f"العدد الإجمالي: [{int(total_sum)}]")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

if 'cart' not in st.session_state: st.session_state.cart = {}

st.title("🏛️ نظام بريفيو - نسخة الاستقرار")

try:
    conn = get_connection()
    c1, c2 = st.columns(2)

    with c1:
        cust = st.text_input("اسم الزبون", "وائل")
        city_sel = st.selectbox("المحافظة", pd.read_sql("SELECT المحافظة FROM المحافظات", conn)['المحافظة'].tolist())
        
        # جلب كافة الشبكات دون فلترة تاريخية معقدة لتجنب انهيار الكود
        query = f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة = '{city_sel}'"
        all_df = pd.read_sql(query, conn)
        
        selected_nets = st.multiselect("اختر الشبكات:", all_df['الشبكة'].unique().tolist())
        
        if st.button("➕ إضافة الشبكات"):
            if selected_nets:
                st.session_state.cart[city_sel] = {n: all_df[all_df['الشبكة'] == n][['الموقع', 'العدد']] for n in selected_nets}
                st.success("تمت الإضافة")

    with c2:
        if st.session_state.cart:
            for c in list(st.session_state.cart.keys()):
                with st.expander(f"📍 {c}", expanded=True):
                    for n in list(st.session_state.cart[c].keys()):
                        st.write(f"🔗 {n}")
                        st.session_state.cart[c][n] = st.data_editor(st.session_state.cart[c][n], key=f"ed_{c}_{n}", num_rows="dynamic")
            
            if st.button("🗑️ مسح الكل"):
                st.session_state.cart = {}; st.rerun()

            if st.button("🚀 تصدير الوورد"):
                final_doc = export_stable_quotation(cust, st.session_state.cart, {'period': 'حسب العرض', 'year': '2026'})
                st.download_button("📥 تحميل الملف", final_doc, f"Preview_{cust}.docx")
except Exception as e:
    st.error(f"خطأ تقني: {e}")
