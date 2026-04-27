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
st.set_page_config(page_title="PreView Ads ERP - Available Only", layout="wide")

def get_connection():
    return sqlite3.connect('billboards_data.db')

def ar(text):
    if not text: return ""
    return get_display(reshape(str(text)))

# --- دالة التصدير (تنسيق بريفيو الرسمي) ---
def export_final_quotation(customer_name, cart_data, dates):
    doc = Document()
    doc.sections[0].right_to_left = True
    
    if os.path.exists('logo.png'):
        header = doc.sections[0].header
        p = header.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture('logo.png', width=Inches(8.27))

    for _ in range(5): doc.add_paragraph() 
    
    p_cust = doc.add_paragraph()
    p_cust.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_cust.add_run(ar(f"السادة شركة .. {customer_name} المحترمين")).bold = True
    doc.add_paragraph(ar(f"نقدم لكم المواقع المتاحة للفترة من {dates['start']} لغاية {dates['end']} م")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

    for city, networks in cart_data.items():
        p_city = doc.add_paragraph()
        p_city.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run_city = p_city.add_run(ar(f"محافظة {city}"))
        run_city.font.color.rgb = RGBColor(102, 0, 153)
        run_city.font.size = Pt(16)

        for net, df in networks.items():
            doc.add_paragraph(ar(f"شبكات {net}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
            clean_df = df.iloc[:, :2].reset_index(drop=True)
            rows_needed = (len(clean_df) + 1) // 2
            table = doc.add_table(rows=rows_needed + 1, cols=4)
            table.style = 'Table Grid'
            
            table.cell(0, 0).text = ar("العدد")
            table.cell(0, 1).text = ar("الموقع")
            table.cell(0, 2).text = ar("العدد")
            table.cell(0, 3).text = ar("الموقع")

            for i in range(len(clean_df)):
                row_idx = (i // 2) + 1
                col_off = 0 if i % 2 == 0 else 2
                table.cell(row_idx, col_off).text = str(clean_df.iloc[i, 1])
                table.cell(row_idx, col_off + 1).text = ar(clean_df.iloc[i, 0])
            
            doc.add_paragraph(ar(f"إجمالي المتاح في هذه الشبكة: {int(clean_df.iloc[:, 1].sum())}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
    
    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- واجهة المستخدم الذكية ---
if 'cart' not in st.session_state: st.session_state.cart = {}
st.title("📄 صانع عروض الأسعار (المواقع المتاحة فقط)")

conn = get_connection()

# 1. إدخال التواريخ للفلترة
col_d1, col_d2 = st.columns(2)
with col_d1: d_start = st.date_input("تاريخ بدء العرض", value=pd.to_datetime("2026-05-01"))
with col_d2: d_end = st.date_input("تاريخ نهاية العرض", value=pd.to_datetime("2026-05-28"))

st.divider()

col_in, col_view = st.columns(2)

with col_in:
    cust_name = st.text_input("اسم الزبون")
    cities = pd.read_sql("SELECT المحافظة FROM المحافظات", conn)['المحافظة'].tolist()
    sel_city = st.selectbox("المحافظة", cities)

    # استعلام SQL للفلترة التلقائية (المواقع التي ليس لها حجز في هذه الفترة)
    query_available = f"""
    SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] 
    FROM [اعمدة انارة] 
    WHERE المحافظة = '{sel_city}'
    AND [رقم اللوحة] NOT IN (
        SELECT [رقم اللوحة] FROM [حجوزات1]
        WHERE NOT (([تاريخ الحجز الى] < '{d_start}') OR ([تاريخ الحجز من] > '{d_end}'))
    )
    """
    df_filtered = pd.read_sql(query_available, conn)
    
    sel_nets = st.multiselect("اختر الشبكات (تظهر فقط الشبكات التي بها متاح):", df_filtered['الشبكة'].unique().tolist())
    
    if st.button("➕ إضافة المتاح للعرض"):
        if sel_nets:
            st.session_state.cart[sel_city] = {n: df_filtered[df_filtered['الشبكة'] == n][['الموقع', 'العدد']] for n in sel_nets}
            st.success(f"تمت إضافة المواقع المتاحة في شبكات {sel_city}")

with col_view:
    if st.session_state.cart:
        for c_n, nets in st.session_state.cart.items():
            with st.expander(f"📍 {c_n}"):
                for n_n, df in nets.items():
                    st.session_state.cart[c_n][n_n] = st.data_editor(df, key=f"ed_{c_n}_{n_n}")
        
        if st.button("🚀 تصدير الوورد المفلتر"):
            dates = {'start': str(d_start), 'end': str(d_end)}
            out_file = export_final_quotation(cust_name, st.session_state.cart, dates)
            st.download_button("📥 تحميل العرض", out_file, f"Quotation_{cust_name}.docx")
