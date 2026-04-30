import streamlit as st
import pandas as pd
import sqlite3
import os
import io
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
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
    if os.path.exists('logo.png'):
        header = doc.sections[0].header
        p = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture('logo.png', width=Inches(3))
    
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
            doc.add_paragraph(ar(f"شبكة: {net}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
            table = doc.add_table(rows=1, cols=4); table.style = 'Table Grid'
            hdr = table.rows[0].cells
            hdr[0].text, hdr[1].text, hdr[2].text, hdr[3].text = ar("العدد"), ar("الموقع"), ar("العدد"), ar("الموقع")
            
            data_list = df.iloc[:, :2].values.tolist()
            for i in range(0, len(data_list), 2):
                row = table.add_row().cells
                row[0].text, row[1].text = str(data_list[i][1]), ar(data_list[i][0])
                if i + 1 < len(data_list):
                    row[2].text, row[3].text = str(data_list[i+1][1]), ar(data_list[i+1][0])
            
            # معالجة الأجور لتظهر بشكل صحيح
            total_n = pd.to_numeric(df.iloc[:, 1], errors='coerce').sum()
            prnt = pd.to_numeric(df['أجور الطباعة'], errors='coerce').sum() if 'أجور الطباعة' in df.columns else 0
            ads = pd.to_numeric(df['أجور العرض'], errors='coerce').sum() if 'أجور العرض' in df.columns else 0
            
            f_p = doc.add_paragraph(); f_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            info_line = f"{ar('العدد:')} {int(total_n)} | {ar('أجور الطباعة:')} {prnt}$ | {ar('أجور العرض:')} {ads}$"
            f_p.add_run(info_line).bold = True
    
    target = io.BytesIO(); doc.save(target); target.seek(0)
    return target

# --- نظام الأمان ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 تسجيل الدخول - نظام بريفيو")
    user = st.text_input("اسم المستخدم")
    pwd = st.text_input("كلمة المرور", type="password")
    if st.button("دخول"):
        if user == "a" and pwd == "3900":
            st.session_state.authenticated = True
            st.rerun()
        else: st.error("❌ بيانات خاطئة")
else:
    conn = get_connection()
    if 'cart' not in st.session_state: st.session_state.cart = {}
    
    with st.sidebar:
        if os.path.exists("logo.png"): st.image("logo.png")
        page = st.radio("القائمة:", ["🏠 الداشبورد والخريطة", "📄 إنشاء عرض سعر"])
        if st.button("خروج"):
            st.session_state.authenticated = False
            st.rerun()

    if page == "🏠 الداشبورد والخريطة":
        st.title("📊 الخريطة التفاعلية للمواقع")
        df_all = pd.read_sql("SELECT * FROM [اعمدة انارة]", conn)
        
        # 1. كود فحص المحارف (للمعاينة فقط)
        st.subheader("🔍 فحص بيانات المحافظات")
        check_cities = pd.read_sql("SELECT DISTINCT المحافظة FROM [اعمدة انارة]", conn)
        for city in check_cities['المحافظة'].tolist():
            st.code(f"الاسم: '{city}' | الطول: {len(str(city))} | المحارف: {list(str(city))}")

        # 2. جلب الحجوزات والدمج
        df_booked = pd.read_sql("SELECT [رقم اللوحة], [اسم الزبون], [فترة الحجز] FROM [حجوزات1]", conn)
        df_map = pd.merge(df_all, df_booked, on='رقم اللوحة', how='left')

        # 3. تنظيف شامل لكل المحافظات (إزالة الفراغات والمحارف المخفية)
        df_map['المحافظة'] = df_map['المحافظة'].astype(str).str.strip()

        
        # تنظيف المحافظة لحل مشكلة اختفاء دمشق
        df_map['المحافظة'] = df_map['المحافظة'].astype(str).str.strip()

        with st.sidebar:
            st.divider()
            city_f = st.selectbox("المحافظة:", ["الكل"] + sorted(df_map['المحافظة'].unique().tolist()))
            stat_f = st.radio("الحالة:", ["الكل", "متاح", "محجوز"])

        if city_f != "الكل": df_map = df_map[df_map['المحافظة'] == city_f]
        if stat_f == "محجوز": df_map = df_map[df_map['اسم الزبون'].notna()]
        elif stat_f == "متاح": df_map = df_map[df_map['اسم الزبون'].isna()]

        m = folium.Map(location=[33.51, 36.27], zoom_start=12)
        marker_cluster = MarkerCluster().add_to(m)
        for _, row in df_map.iterrows():
            lat, lon = row.get('Latitude'), row.get('Longitude')
            if pd.notnull(lat) and pd.notnull(lon):
                is_b = pd.notnull(row['اسم الزبون'])
                pop_html = f"<div style='direction:rtl; text-align:right; font-family:Tahoma;'><b>{row['اسم العمود']}</b><br>الشركة: {row['اسم الزبون'] if is_b else 'متاح'}<br>الانتهاء: {row['فترة الحجز'] if is_b else '-'}</div>"
                folium.Marker([lat, lon], popup=folium.Popup(pop_html, max_width=200), icon=folium.Icon(color='red' if is_b else 'purple')).add_to(marker_cluster)
        
        st_folium(m, width="100%", height=500)
        st.dataframe(df_map.drop(columns=['Latitude', 'Longitude']), use_container_width=True)

    elif page == "📄 إنشاء عرض سعر":
        st.title("📄 بناء عرض سعر")
        col1, col2 = st.columns(2)
        with col1:
            cust = st.text_input("اسم الزبون")
            city = st.selectbox("المحافظة", sorted(pd.read_sql("SELECT DISTINCT المحافظة FROM [اعمدة انارة]", conn)['المحافظة'].tolist()))
            raw = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة='{city}'", conn)
            nets = st.multiselect("الشبكات:", raw['الشبكة'].unique().tolist())
            if st.button("➕ إضافة للسلة"):
                if city not in st.session_state.cart: st.session_state.cart[city] = {}
                for n in nets:
                    df_net = raw[raw['الشبكة'] == n].copy()
                    df_net['أجور الطباعة'], df_net['أجور العرض'] = 0, 0
                    st.session_state.cart[city][n] = df_net

        with col2:
            if st.session_state.cart:
                for c, nts in list(st.session_state.cart.items()):
                    for n, df in nts.items():
                        with st.expander(f"📍 {c} - {n}"):
                            st.session_state.cart[c][n] = st.data_editor(df, key=f"ed_{c}_{n}")
                if st.button("🚀 تصدير Word"):
                    doc_out = export_word(cust, st.session_state.cart)
                    st.download_button("📥 تحميل العرض", doc_out, f"Quotation_{cust}.docx")
                if st.button("🗑️ تفريغ السلة"): st.session_state.cart = {}; st.rerun()
    conn.close()
