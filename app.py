import streamlit as st
import pandas as pd
import sqlite3
import os
import io
import plotly.express as px
import folium
from streamlit_folium import st_folium
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from arabic_reshaper import reshape
from bidi.algorithm import get_display

# --- إعدادات الصفحة ---
st.set_page_config(page_title="PreView Ads ERP", layout="wide")

# --- مصفوفة الإحداثيات ---
geo_map_data = {
    'طريق يعفور ذهاب': [33.5100, 36.1200], 'من ساحة الامويين حتى السفارة الاماراتية': [33.5135, 36.2765],
    'كورنيش الميدان': [33.4912, 36.2970], 'من المحافظة حتى فكتوريا': [33.5120, 36.2930],
    'شارع الحضارة': [34.7150, 36.7110], 'دوار الجامعة': [34.7125, 36.7075],
    'شارع الدروبي': [34.7305, 36.7135], 'طريق الشام ذهاب': [34.7042, 36.7095]
}

# --- نظام الأمان ---
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.title("🔒 تسجيل الدخول - نظام بريفيو")
        user = st.text_input("اسم المستخدم")
        pwd = st.text_input("كلمة المرور", type="password")
        if st.button("دخول"):
            if user == "admin" and pwd == "3900":
                st.session_state.authenticated = True
                st.rerun()
            else: st.error("❌ بيانات خاطئة")
        return False
    return True

if check_password():
    def get_connection():
        return sqlite3.connect('billboards_data.db')

    def ar(text):
        if not text: return ""
        return get_display(reshape(str(text)))

    # --- دالة تصدير الوورد ---
    def export_word(customer_name, cart_data):
        doc = Document()
        doc.sections[0].right_to_left = True
        if os.path.exists('logo.png'):
            header = doc.sections[0].header
            p = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.add_run().add_picture('logo.png', width=Inches(3))
        
        doc.add_paragraph("\n\n")
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
                table = doc.add_table(rows=1, cols=4); table.style = 'Table Grid'
                hdr = table.rows[0].cells
                hdr[0].text, hdr[1].text, hdr[2].text, hdr[3].text = ar("العدد"), ar("الموقع"), ar("العدد"), ar("الموقع")
                
                data_list = df.iloc[:, :2].values.tolist()
                for i in range(0, len(data_list), 2):
                    row = table.add_row().cells
                    row[0].text, row[1].text = str(data_list[i][1]), ar(data_list[i][0])
                    if i + 1 < len(data_list):
                        row[2].text, row[3].text = str(data_list[i+1][1]), ar(data_list[i+1][0])
                
                total_n = pd.to_numeric(df.iloc[:, 1]).sum()
                prnt = df['أجور الطباعة'].iloc[0] if 'أجور الطباعة' in df.columns else 0
                ads = df['أجور العرض'].iloc[0] if 'أجور العرض' in df.columns else 0
                f_p = doc.add_paragraph()
                f_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                f_p.add_run(ar(f"العدد: [{int(total_n)}] | أجور الطباعة: ${prnt} | أجور العرض: ${ads}"))
        
        target = io.BytesIO(); doc.save(target); target.seek(0)
        return target

    # --- الواجهة ---
    if 'cart' not in st.session_state: st.session_state.cart = {}
    page = st.sidebar.radio("القائمة:", ["🏠 الداشبورد والخريطة", "📄 إنشاء عرض سعر"])
    conn = get_connection()

    if page == "🏠 الداشبورد والخريطة":
        st.title("📊 حالة المواقع والإشغال")
        df_all = pd.read_sql("SELECT [اسم العمود], [المحافظة], [العدد], [الشبكة], [رقم اللوحة] FROM [اعمدة انارة]", conn)
        df_booked_ids = pd.read_sql("SELECT DISTINCT [رقم اللوحة] FROM [حجوزات1]", conn)['رقم اللوحة'].tolist()

        m = folium.Map(location=[34.8, 38.5], zoom_start=7)
        for _, row in df_all.iterrows():
            loc = row['اسم العمود']
            if loc in geo_map_data:
                color = 'red' if row['رقم اللوحة'] in df_booked_ids else 'purple'
                popup_content = f"<div style='direction: rtl; text-align: right;'><b>{loc}</b><br>العدد: {row['العدد']}</div>"
                folium.Marker(geo_map_data[loc], popup=folium.Popup(popup_content, max_width=200), icon=folium.Icon(color=color)).add_to(m)
        st_folium(m, width=1200, height=400)
        
        tab1, tab2 = st.tabs(["✅ المواقع المتاحة", "🚫 المواقع المحجوزة"])
        with tab1:
            df_av = df_all[~df_all['رقم اللوحة'].isin(df_booked_ids)]
            st.dataframe(df_av.drop(columns=['رقم اللوحة']), use_container_width=True)
        with tab2:
            df_bk = df_all[df_all['رقم اللوحة'].isin(df_booked_ids)]
            if not df_bk.empty:
                df_det = pd.read_sql("SELECT [رقم اللوحة], [اسم الزبون], [فترة الحجز] FROM [حجوزات1]", conn)
                st.dataframe(pd.merge(df_bk, df_det, on='رقم اللوحة', how='left').drop(columns=['رقم اللوحة']), use_container_width=True)

    elif page == "📄 إنشاء عرض سعر":
        st.title("📄 بناء عرض سعر")
        col1, col2 = st.columns(2)
        with col1:
            cust = st.text_input("اسم الزبون")
            city = st.selectbox("المحافظة", pd.read_sql("SELECT المحافظة FROM المحافظات", conn)['المحافظة'].tolist())
            raw = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة='{city}'", conn)
            nets = st.multiselect("اختر الشبكات:", raw['الشبكة'].unique().tolist())
            if st.button("➕ إضافة للسلة"):
                if city not in st.session_state.cart: st.session_state.cart[city] = {}
                for n in nets:
                    df_net = raw[raw['الشبكة'] == n][['الموقع', 'العدد']].copy()
                    df_net['أجور الطباعة'], df_net['أجور العرض'] = 0, 0
                    st.session_state.cart[city][n] = df_net

        with col2:
            if st.session_state.cart:
                for c, nts in list(st.session_state.cart.items()):
                    for n, df in nts.items():
                        with st.expander(f"📍 {c} - شبكة {n}"):
                            st.session_state.cart[c][n] = st.data_editor(df, key=f"ed_{c}_{n}")
                if st.button("🚀 تصدير Word"):
                    doc_out = export_word(cust, st.session_state.cart)
                    st.download_button("📥 تحميل العرض", doc_out, f"Quotation_{cust}.docx")
                if st.button("🗑️ تفريغ السلة"): st.session_state.cart = {}; st.rerun()
