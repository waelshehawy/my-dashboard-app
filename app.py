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
st.set_page_config(page_title="Preview Ads - Smart System", layout="wide")

def ar(text):
    if not text: return ""
    return get_display(reshape(str(text)))

def get_connection():
    return sqlite3.connect('billboards_data.db')

# --- دالة التصدير المستقرة ---
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
    doc.add_paragraph(ar(f"نقدم لكم المواقع المتاحة للفترة من {dates['start']} لغاية {dates['end']} م")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

    for city_name in cart_data:
        p_city = doc.add_paragraph()
        p_city.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run_city = p_city.add_run(ar(f"محافظة {city_name}"))
        run_city.font.color.rgb = RGBColor(102, 0, 153)
        run_city.font.size = Pt(16)

        networks = cart_data[city_name]
        for net_name in networks:
            doc.add_paragraph(ar(f"شبكة: {net_name}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
            df = networks[net_name]
            table = doc.add_table(rows=1, cols=2)
            table.style = 'Table Grid'
            hdr = table.rows[0].cells
            hdr[0].text = ar("العدد")
            hdr[1].text = ar("الموقع")

            for i in range(len(df)):
                row = table.add_row().cells
                row[0].text = str(df.iloc[i, 1])
                row[1].text = ar(df.iloc[i, 0])

            total_sum = pd.to_numeric(df.iloc[:, 1]).sum()
            doc.add_paragraph(ar(f"العدد الإجمالي لهذه الشبكة: [{int(total_sum)}]")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- واجهة التطبيق ---
if 'cart' not in st.session_state:
    st.session_state.cart = {}

st.title("🏛️ نظام بريفيو الذكي (إدارة الشبكات والإشغال)")

try:
    conn = get_connection()
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("📍 الفلترة واختيار الشبكات")
        cust = st.text_input("اسم الزبون", "وائل")
        
        col_d1, col_d2 = st.columns(2)
        with col_d1: d_start = st.date_input("من تاريخ", pd.to_datetime("2026-05-01"))
        with col_d2: d_end = st.date_input("إلى تاريخ", pd.to_datetime("2026-05-28"))
        
        cities = pd.read_sql("SELECT المحافظة FROM المحافظات", conn)['المحافظة'].tolist()
        city_sel = st.selectbox("المحافظة", cities)

        # استعلام لجلب المواقع المتاحة فقط (غير محجوزة في هذه الفترة)
        # نقارن مع جدول حجوزات1
        query_available = f"""
        SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] 
        FROM [اعمدة انارة] 
        WHERE المحافظة = '{city_sel}'
        AND [رقم اللوحة] NOT IN (
            SELECT [رقم اللوحة] FROM [حجوزات1]
            WHERE NOT (([تاريخ الحجز الى] < '{d_start}') OR ([تاريخ الحجز من] > '{d_end}'))
        )
        """
        available_df = pd.read_sql(query_available, conn)
        
        # اختيار بالشبكة
        nets_in_city = available_df['الشبكة'].unique().tolist()
        selected_nets = st.multiselect("اختر الشبكات المتاحة:", nets_in_city)
        
        if st.button("➕ إضافة الشبكات المختارة للعرض"):
            if selected_nets:
                city_dict = {}
                for n in selected_nets:
                    city_dict[n] = available_df[available_df['الشبكة'] == n][['الموقع', 'العدد']]
                st.session_state.cart[city_sel] = city_dict
                st.success(f"تمت إضافة شبكات {city_sel}")

    with c2:
        st.subheader("🛒 مراجعة وتعديل العرض")
        if st.session_state.cart:
            for c in list(st.session_state.cart.keys()):
                with st.expander(f"📍 محافظة {c}", expanded=True):
                    for n in list(st.session_state.cart[c].keys()):
                        st.write(f"🔗 {n}")
                        # هنا يمكنك حذف أسطر يدوياً من الجدول
                        st.session_state.cart[c][n] = st.data_editor(st.session_state.cart[c][n], key=f"ed_{c}_{n}", num_rows="dynamic")
            
            if st.button("🗑️ مسح الكل"):
                st.session_state.cart = {}; st.rerun()

            if st.button("🚀 تصدير عرض السعر (Word)"):
                dts = {'start': str(d_start), 'end': str(d_end)}
                final_doc = export_stable_quotation(cust, st.session_state.cart, dts)
                st.download_button("📥 تحميل الوورد", final_doc, f"Preview_{cust}.docx")
        else:
            st.info("لا توجد شبكات مختارة بعد.")

except Exception as e:
    st.error(f"خطأ تقني: {e}")
