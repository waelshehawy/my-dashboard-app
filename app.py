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

st.set_page_config(page_title="Preview Ads System", layout="wide")

def ar(text):
    if not text: return ""
    return get_display(reshape(str(text)))

def get_connection():
    return sqlite3.connect('billboards_data.db')

# --- 1. دالة تصدير الوورد (عرض السعر) ---
def export_final_quotation(customer_name, cart_data, dates):
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
    doc.add_paragraph(ar(f"نقدم لكم المواقع المتاحة للفترة: {dates['period']}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

    for city_name, networks in cart_data.items():
        p_city = doc.add_paragraph()
        p_city.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run_city = p_city.add_run(ar(f"محافظة {city_name}"))
        run_city.font.color.rgb = RGBColor(102, 0, 153)
        run_city.font.size = Pt(16)
        for net_name, df in networks.items():
            doc.add_paragraph(ar(f"شبكات {net_name}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
            table = doc.add_table(rows=1, cols=4)
            table.style = 'Table Grid'
            for i, text in enumerate(["العدد", "الموقع", "العدد", "الموقع"]):
                table.rows[0].cells[i].text = ar(text)
            data_list = df.values.tolist()
            for i in range(0, len(data_list), 2):
                row = table.add_row().cells
                row[0].text, row[1].text = str(data_list[i][1]), ar(data_list[i][0])
                if i + 1 < len(data_list):
                    row[2].text, row[3].text = str(data_list[i+1][1]), ar(data_list[i+1][0])
            total_sum = pd.to_numeric(df.iloc[:, 1]).sum()
            doc.add_paragraph(ar(f"العدد الإجمالي: [{int(total_sum)}]")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- إدارة الذاكرة (سلة الاختيارات) ---
if 'cart' not in st.session_state:
    st.session_state.cart = {}

# --- واجهة التطبيق الرئيسية ---
st.title("🏗️ نظام بريفيو: العروض وتثبيت العقود")

try:
    conn = get_connection()
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("📍 1. بناء العرض")
        cust = st.text_input("اسم الزبون", "شركة ...")
        cities = pd.read_sql("SELECT المحافظة FROM المحافظات", conn)['المحافظة'].tolist()
        city_sel = st.selectbox("المحافظة", cities)
        
        # جلب الشبكات
        query = f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة = '{city_sel}'"
        all_df = pd.read_sql(query, conn)
        selected_nets = st.multiselect("اختر الشبكات:", all_df['الشبكة'].unique().tolist())
        
        if st.button("➕ إضافة الشبكات المختارة"):
            if selected_nets:
                if city_sel not in st.session_state.cart: st.session_state.cart[city_sel] = {}
                for n in selected_nets:
                    st.session_state.cart[city_sel][n] = all_df[all_df['الشبكة'] == n][['الموقع', 'العدد']].copy()
                st.success("تمت الإضافة")

    with c2:
        st.subheader("🛒 2. مراجعة وتثبيت")
        if st.session_state.cart:
            for city in list(st.session_state.cart.keys()):
                with st.expander(f"📍 {city}", expanded=True):
                    for net in list(st.session_state.cart[city].keys()):
                        st.session_state.cart[city][net] = st.data_editor(st.session_state.cart[city][net], key=f"ed_{city}_{net}", num_rows="dynamic")
            
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("🚀 تصدير العرض (Word)"):
                    final_doc = export_final_quotation(cust, st.session_state.cart, {'period': '2026', 'year': '2026'})
                    st.download_button("📥 تحميل الملف", final_doc, f"Quotation_{cust}.docx")
            
            with col_btn2:
                # --- وظيفة تثبيت العقد (الحجز الفعلي) ---
                if st.button("✅ تثبيت كعقد (حجز المواقع)"):
                    cursor = conn.cursor()
                    for city_n, nets in st.session_state.cart.items():
                        for net_n, df in nets.items():
                            for i in range(len(df)):
                                pole_n = df.iloc[i, 0]
                                # جلب رقم اللوحة
                                p_id = cursor.execute(f"SELECT [رقم اللوحة] FROM [اعمدة انارة] WHERE [اسم العمود] = '{pole_n}'").fetchone()[0]
                                # إدخال في جدول الحجوزات (حجوزات1)
                                cursor.execute("INSERT INTO [حجوزات1] ([رقم اللوحة], [اسم الزبون]) VALUES (?, ?)", (p_id, cust))
                    conn.commit()
                    st.balloons()
                    st.success(f"تم تثبيت العقد وحجز المواقع للزبون {cust}")

            if st.button("🗑️ مسح السلة"):
                st.session_state.cart = {}; st.rerun()
        else:
            st.info("السلة فارغة.")

except Exception as e:
    st.error(f"خطأ: {e}")
