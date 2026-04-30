import streamlit as st
import pandas as pd
import sqlite3
import os
import io
import folium
from streamlit_folium import st_folium
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from arabic_reshaper import reshape
from bidi.algorithm import get_display

# --- إعدادات الصفحة ---
st.set_page_config(page_title="PreView Ads ERP", layout="wide")

# --- دوال مساعدة ---
def get_connection():
    return sqlite3.connect('billboards_data.db')

def ar(text):
    if not text: return ""
    return get_display(reshape(str(text)))

# --- وظيفة تصدير الوورد ---
def export_word(customer_name, cart_data):
    doc = Document()
    doc.sections[0].right_to_left = True
    
    # إضافة اللوجو للهيدر إذا وجد
    if os.path.exists('logo.png'):
        header = doc.sections[0].header
        p = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture('logo.png', width=Inches(6))
    
    doc.add_paragraph("\n")
    p_cust = doc.add_paragraph()
    p_cust.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_cust.add_run(ar(f"السادة شركة .. {customer_name} المحترمين")).bold = True

    for city, networks in cart_data.items():
        p_city = doc.add_paragraph()
        p_city.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run_city = p_city.add_run(ar(f"محافظة {city}"))
        run_city.font.color.rgb = RGBColor(102, 0, 153)
        run_city.font.size = Pt(16)
        
        for net, df in networks.items():
            doc.add_paragraph(ar(f"شبكات {net}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
            table = doc.add_table(rows=1, cols=4)
            table.style = 'Table Grid'
            hdr = table.rows[0].cells
            hdr[0].text, hdr[1].text, hdr[2].text, hdr[3].text = ar("العدد"), ar("الموقع"), ar("العدد"), ar("الموقع")
            
            data_list = df.iloc[:, :2].values.tolist()
            for i in range(0, len(data_list), 2):
                row = table.add_row().cells
                row[0].text, row[1].text = str(data_list[i][1]), ar(data_list[i][0])
                if i + 1 < len(data_list):
                    row[2].text, row[3].text = str(data_list[i+1][1]), ar(data_list[i+1][0])
            
            total_n = pd.to_numeric(df.iloc[:, 1]).sum()
            f_p = doc.add_paragraph()
            f_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            f_p.add_run(ar(f"إجمالي العدد: {int(total_n)}"))
    
    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- نظام الأمان ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 تسجيل الدخول")
    user = st.text_input("اسم المستخدم")
    pwd = st.text_input("كلمة المرور", type="password")
    if st.button("دخول"):
        if user == "admin" and pwd == "preview2026":
            st.session_state.authenticated = True
            st.rerun()
        else: st.error("❌ بيانات خاطئة")
else:
    # --- واجهة التطبيق الرئيسية ---
    conn = get_connection()
    if 'cart' not in st.session_state: st.session_state.cart = {}
    
    # شريط جانبي نظيف
    with st.sidebar:
        if os.path.exists("logo.png"):
            st.image("logo.png", width=150)
        page = st.radio("القائمة:", ["🏠 الداشبورد والخريطة", "📄 إنشاء عرض سعر"])

    if page == "🏠 الداشبورد والخريطة":
        st.title("📊 حالة المواقع والإشغال")
        df_all = pd.read_sql("SELECT * FROM [اعمدة انارة]", conn)
        df_booked_ids = pd.read_sql("SELECT DISTINCT [رقم اللوحة] FROM [حجوزات1]", conn)['رقم اللوحة'].tolist()

        # الخريطة الديناميكية
        m = folium.Map(location=[33.51, 36.27], zoom_start=12)
        for _, row in df_all.iterrows():
            if pd.notnull(row['Latitude']) and pd.notnull(row['Longitude']):
                color = 'red' if row['رقم اللوحة'] in df_booked_ids else 'purple'
                folium.Marker(
                    [row['Latitude'], row['Longitude']], 
                    popup=ar(row['اسم العمود']), 
                    icon=folium.Icon(color=color)
                ).add_to(m)
        st_folium(m, width=1200, height=450)
        
        st.dataframe(df_all, use_container_width=True)

    elif page == "📄 إنشاء عرض سعر":
        st.title("📄 بناء عرض سعر")
        col1, col2 = st.columns(2)
        with col1:
            cust = st.text_input("اسم الزبون")
            cities = pd.read_sql("SELECT DISTINCT المحافظة FROM [اعمدة انارة]", conn)['المحافظة'].tolist()
            city = st.selectbox("المحافظة", cities)
            raw = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة='{city}'", conn)
            nets = st.multiselect("الشبكات:", raw['الشبكة'].unique().tolist())
            if st.button("➕ إضافة"):
                if city not in st.session_state.cart: st.session_state.cart[city] = {}
                for n in nets:
                    st.session_state.cart[city][n] = raw[raw['الشبكة'] == n].copy()

        with col2:
            if st.session_state.cart:
                for c, nts in list(st.session_state.cart.items()):
                    for n, df in nts.items():
                        with st.expander(f"📍 {c} - {n}"):
                            st.session_state.cart[c][n] = st.data_editor(df, key=f"ed_{c}_{n}")
                
                if st.button("🚀 تصدير Word"):
                    doc_out = export_word(cust, st.session_state.cart)
                    st.download_button("📥 تحميل", doc_out, f"Quotation.docx")
    conn.close()
