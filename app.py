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

st.set_page_config(page_title="Preview Ads - Final System", layout="wide")

def ar(text):
    if not text: return ""
    return get_display(reshape(str(text)))

def get_connection():
    return sqlite3.connect('billboards_data.db')

# --- دالة التصدير (مع الحسابات المالية والجداول المزدوجة) ---
def export_final_quotation(customer_name, cart_data, dates):
    doc = Document()
    section = doc.sections[0]
    section.right_to_left = True
    
    if os.path.exists('logo.png'):
        header = section.header
        p = header.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.add_run().add_picture('logo.png', width=Inches(2.5))

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
            doc.add_paragraph(ar(f"شبكات {net_name}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
            
            # بناء جدول مزدوج (4 أعمدة) كما طلبت سابقاً
            table = doc.add_table(rows=1, cols=4)
            table.style = 'Table Grid'
            hdr = table.rows[0].cells
            hdr[0].text, hdr[1].text = ar("العدد"), ar("الموقع")
            hdr[2].text, hdr[3].text = ar("العدد"), ar("الموقع")

            # توزيع البيانات
            data_list = df.values.tolist()
            for i in range(0, len(data_list), 2):
                row = table.add_row().cells
                row[0].text = str(data_list[i][1]) # العدد
                row[1].text = ar(data_list[i][0])  # الموقع
                if i + 1 < len(data_list):
                    row[2].text = str(data_list[i+1][1])
                    row[3].text = ar(data_list[i+1][0])

            # سطر المجاميع والأسعار
            total_sum = pd.to_numeric(df['العدد']).sum()
            # نأخذ الأسعار من أول سطر في الجدول التفاعلي لكل شبكة
            print_price = df['أجور الطباعة'].iloc[0] if 'أجور الطباعة' in df.columns else 0
            ads_price = df['أجور العرض'].iloc[0] if 'أجور العرض' in df.columns else 0
            
            f_p = doc.add_paragraph()
            f_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            f_p.add_run(ar(f"العدد: [{int(total_sum)}] | أجور الطباعة والتركيب: ${print_price} | أجور العرض: ${ads_price}"))

    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- إدارة الذاكرة ---
if 'cart' not in st.session_state:
    st.session_state.cart = {}

st.title("🏛️ نظام بريفيو - صانع العروض المتكامل")

try:
    conn = get_connection()
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("📍 1. اختيار المواقع")
        cust = st.text_input("اسم الزبون", "وائل")
        city_sel = st.selectbox("المحافظة", pd.read_sql("SELECT المحافظة FROM المحافظات", conn)['المحافظة'].tolist())
        
        query = f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة = '{city_sel}'"
        all_df = pd.read_sql(query, conn)
        selected_nets = st.multiselect("اختر الشبكات:", all_df['الشبكة'].unique().tolist())
        
        if st.button("➕ إضافة الشبكات المختارة"):
            if selected_nets:
                for n in selected_nets:
                    net_df = all_df[all_df['الشبكة'] == n][['الموقع', 'العدد']].copy()
                    # إضافة أعمدة التسعير
                    net_df['أجور الطباعة'] = 0
                    net_df['أجور العرض'] = 0
                    if city_sel not in st.session_state.cart:
                        st.session_state.cart[city_sel] = {}
                    st.session_state.cart[city_sel][n] = net_df
                st.success("تمت الإضافة للسلة")

    with c2:
        st.subheader("📝 2. مراجعة وتعديل الأسعار")
        if st.session_state.cart:
            for city in list(st.session_state.cart.keys()):
                with st.expander(f"📍 {city}", expanded=True):
                    for net in list(st.session_state.cart[city].keys()):
                        st.write(f"🔗 {net}")
                        # محرر الجداول التفاعلي
                        st.session_state.cart[city][net] = st.data_editor(
                            st.session_state.cart[city][net], 
                            key=f"ed_{city}_{net}", 
                            num_rows="dynamic"
                        )
            
            if st.button("🗑️ مسح الكل"):
                st.session_state.cart = {}
                st.rerun()

            if st.button("🚀 تصدير العرض النهائي (Word)"):
                final_doc = export_final_quotation(cust, st.session_state.cart, {'period': 'من تاريخ', 'year': '2026'})
                st.download_button("📥 تحميل ملف الوورد", final_doc, f"Quotation_{cust}.docx")
        else:
            st.info("قم باختيار المحافظة والشبكات للبدء")

except Exception as e:
    st.error(f"خطأ: {e}")
