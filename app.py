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

# --- دالة التصدير ---
def export_final_quotation(customer_name, cart_data, dates):
    doc = Document()
    doc.sections[0].right_to_left = True
    
    if os.path.exists('logo.png'):
        header = doc.sections[0].header
        p = header.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture('logo.png', width=Inches(2.27))

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
            clean_df = df[['الموقع', 'العدد']].reset_index(drop=True)
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
            
            total = pd.to_numeric(clean_df['العدد']).sum()
            doc.add_paragraph(ar(f"إجمالي المتاح: {int(total)}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
    
    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- واجهة المستخدم ---
st.title("📄 صانع عروض الأسعار (المتاح فقط)")

conn = get_connection()

# 1. إدخال التواريخ
col_d1, col_d2 = st.columns(2)
with col_d1: d_start = st.date_input("تاريخ بدء العرض", value=pd.to_datetime("2026-05-01"))
with col_d2: d_end = st.date_input("تاريخ نهاية العرض", value=pd.to_datetime("2026-05-28"))

st.divider()

col_in, col_view = st.columns(2)

with col_in:
    cust_name = st.text_input("اسم الزبون")
    cities = pd.read_sql("SELECT المحافظة FROM المحافظات", conn)['المحافظة'].tolist()
    sel_city = st.selectbox("المحافظة", cities)

    # --- الجزء الجديد المحدث للفلترة ---
    try:
        # جلب كل اللوحات في المحافظة
        df_poles = pd.read_sql(f"SELECT [رقم اللوحة], [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة = '{sel_city}'", conn)
        # جلب الحجوزات (استخدمنا مسميات الأعمدة بدون همزة)
        df_bookings = pd.read_sql("SELECT [رقم اللوحة], [تاريخ الحجز من], [تاريخ الحجز الى] FROM [حجوزات1]", conn)
        
        # تحويل التواريخ في بايثون للمقارنة
        df_bookings['start_dt'] = pd.to_datetime(df_bookings['تاريخ الحجز من'], errors='coerce')
        df_bookings['end_dt'] = pd.to_datetime(df_bookings['تاريخ الحجز الى'], errors='coerce')
        
        # تصفية المحجوز
        mask = (df_bookings['end_dt'] >= pd.to_datetime(d_start)) & (df_bookings['start_dt'] <= pd.to_datetime(d_end))
        reserved_ids = df_bookings.loc[mask, 'رقم اللوحة'].unique().tolist()
        
        df_filtered = df_poles[~df_poles['رقم اللوحة'].isin(reserved_ids)]
        st.success(f"✅ تم استبعاد {len(reserved_ids)} لوحة محجوزة في هذه الفترة.")
    except Exception as e:
        st.warning(f"⚠️ تعذر الفلترة التلقائية، تم عرض الكل. السبب: {e}")
        df_filtered = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة = '{sel_city}'", conn)
    
    sel_nets = st.multiselect("اختر الشبكات المتاحة:", df_filtered['الشبكة'].unique().tolist() if not df_filtered.empty else [])
    
    if st.button("➕ إضافة للعرض"):
        if sel_nets:
            if 'cart' not in st.session_state: st.session_state.cart = {}
            st.session_state.cart[sel_city] = {n: df_filtered[df_filtered['الشبكة'] == n][['الموقع', 'العدد']] for n in sel_nets}
            st.success(f"تمت إضافة شبكات {sel_city}")

with col_view:
    if 'cart' in st.session_state and st.session_state.cart:
        for c_n, nets in st.session_state.cart.items():
            with st.expander(f"📍 {c_n}", expanded=True):
                for n_n, df in nets.items():
                    st.session_state.cart[c_n][n_n] = st.data_editor(df, key=f"ed_{c_n}_{n_n}")
        
        if st.button("🚀 تصدير الوورد المفلتر"):
            dates = {'start': str(d_start), 'end': str(d_end)}
            out_file = export_final_quotation(cust_name, st.session_state.cart, dates)
            st.download_button("📥 تحميل العرض", out_file, f"Quotation_{cust_name}.docx")
