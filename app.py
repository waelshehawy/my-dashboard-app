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

# --- وظيفة تصدير الوورد المحسنة ---
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
            
            # حساب الإجماليات
            total_n = pd.to_numeric(df.iloc[:, 1]).sum()
            prnt = df['أجور الطباعة'].iloc[0] if 'أجور الطباعة' in df.columns else 0
            ads = df['أجور العرض'].iloc[0] if 'أجور العرض' in df.columns else 0
            
            f_p = doc.add_paragraph()
            f_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            info_line = ar("العدد: ") + f"{int(total_n)}" + " | " + ar("طباعة: ") + f"{prnt}$" + " | " + ar("عرض: ") + f"{ads}$"
            f_p.add_run(info_line).bold = True
    
    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- نظام الأمان والواجهة ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 تسجيل الدخول - PreView")
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
        if st.button("تسجيل الخروج"):
            st.session_state.authenticated = False
            st.rerun()

    if page == "🏠 الداشبورد والخريطة":
        st.title("📊 الخريطة التفاعلية للمواقع")
        df_all = pd.read_sql("SELECT * FROM [اعمدة انارة]", conn)
        df_booked = pd.read_sql("SELECT [رقم اللوحة], [اسم الزبون], [فترة الحجز] FROM [حجوزات1]", conn)
        df_map = pd.merge(df_all, df_booked, on='رقم اللوحة', how='left')

        # الفلاتر
        with st.sidebar:
            st.divider()
            city_f = st.selectbox("المحافظة:", ["الكل"] + df_map['المحافظة'].unique().tolist())
            stat_f = st.radio("الحالة:", ["الكل", "متاح", "محجوز"])

        if city_f != "الكل": df_map = df_map[df_map['المحافظة'] == city_f]
        if stat_f == "محجوز": df_map = df_map[df_map['اسم الزبون'].notna()]
        elif stat_f == "متاح": df_map = df_map[df_map['اسم الزبون'].isna()]

        # الخريطة
        m = folium.Map(location=[34.8, 38.5], zoom_start=7)
        marker_cluster = MarkerCluster().add_to(m)
        for _, row in df_map.iterrows():
            if pd.notnull(row['Latitude']):
                is_b = pd.notnull(row['اسم الزبون'])
                pop_html = f"<div style='direction:rtl; text-align:right; font-family:Tahoma;'><b>{row['اسم العمود']}</b><br>الشركة: {row['اسم الزبون'] if is_b else 'متاح'}<br>الانتهاء: {row['فترة الحجز'] if is_b else '-'}</div>"
                folium.Marker([row['Latitude'], row['Longitude']], popup=folium.Popup(pop_html, max_width=200), icon=folium.Icon(color='red' if is_b else 'purple')).add_to(marker_cluster)
        
        st_folium(m, width="100%", height=500)
        st.dataframe(df_map.drop(columns=['Latitude', 'Longitude']), use_container_width=True)

    elif page == "📄 إنشاء عرض سعر":
        st.title("📄 بناء عرض سعر")
        col1, col2 = st.columns(2)
        with col1:
            cust = st.text_input("اسم الزبون")
            city = st.selectbox("المحافظة", pd.read_sql("SELECT DISTINCT المحافظة FROM [اعمدة انارة]", conn)['المحافظة'].tolist())
            raw = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة='{city}'", conn)
            nets = st.multiselect("الشبكات:", raw['الشبكة'].unique().tolist())
            if st.button("➕ إضافة"):
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
                    st.download_button("📥 تحميل", doc_out, f"Quotation.docx")
    conn.close()
