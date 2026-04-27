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

# --- مصفوفة الإحداثيات التي زودتني بها ---
geo_map_data = {
    'طريق يعفور ذهاب': [33.5100, 36.1200],
    'من ساحة الامويين حتى السفارة الاماراتية': [33.5135, 36.2765],
    'كورنيش الميدان': [33.4912, 36.2970],
    'من المحافظة حتى فكتوريا': [33.5120, 36.2930],
    'مدخل باب توما حديقة الصوفانية': [33.5150, 36.3130],
    'شام سنتر من دوار الجوزة الى دوار الكارلتون': [33.4860, 36.2550],
    'الزاهرة الجديدة مقابل بوظة امية': [33.4835, 36.3015],
    'طريق يعفور إياب': [33.5105, 36.1210],
    'طريق الشام ذهاب': [34.7042, 36.7095], 
    'شارع الميدان إياب': [34.7265, 36.7120],
    'شارع الدروبي': [34.7305, 36.7135], 
    'شارع الحضارة': [34.7150, 36.7110], 
    'مفرق الحواش طريق طرطوس الرئيسي': [34.7770, 36.3150],
    'ساحة عدن –كراجات البولمان': [35.5250, 35.8050], 
    'حديقة المنشية -8اذار': [35.5190, 35.7870],
    'المحكمة –الشيخ ضاهر': [35.5215, 35.7830], 
    'شارع المحكمة ذهاب': [34.8950, 35.8820], 
    'مدخل طرطوس مشفى الوطني 1': [34.8720, 35.8890],
    'كورنيش جبلة بوظة رومينزا 1': [35.3620, 35.9180], 
    'جبلة مفرق المشفى 1': [35.3580, 35.9320],
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
            if user == "admin" and pwd == "preview2026":
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
    def export_word(customer_name, cart_data, dates):
        doc = Document()
        section = doc.sections[0]
        section.right_to_left = True
        if os.path.exists('logo.png'):
            header = section.header
            p = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.add_run().add_picture('logo.png', width=Inches(2.27))
        if os.path.exists('footer.png'):
            footer = section.footer
            pf = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
            pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
            pf.add_run().add_picture('footer.png', width=Inches(2.27))

        doc.add_paragraph("\n\n")
        p_cust = doc.add_paragraph()
        p_cust.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p_cust.add_run(ar(f"السادة شركة .. {customer_name} المحترمين")).bold = True

        for city, networks in cart_data.items():
            p_city = doc.add_paragraph()
            p_city.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            run_city = p_city.add_run(ar(f"محافظة {city}"))
            run_city.font.color.rgb = RGBColor(102, 0, 153)
            for net, df in networks.items():
                doc.add_paragraph(ar(f"شبكات {net}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
                table = doc.add_table(rows=1, cols=4); table.style = 'Table Grid'
                hdr = table.rows[0].cells
                hdr[0].text, hdr[1].text, hdr[2].text, hdr[3].text = ar("العدد"), ar("الموقع"), ar("العدد"), ar("الموقع")
                data = df.iloc[:, :2].values.tolist()
                for i in range(0, len(data), 2):
                    row = table.add_row().cells
                    row[0].text, row[1].text = str(data[i][1]), ar(data[i][0])
                    if i + 1 < len(data):
                        row[2].text, row[3].text = str(data[i+1][1]), ar(data[i+1][0])
                total = df.iloc[:, 1].sum()
                doc.add_paragraph(ar(f"العدد: [{int(total)}] | أجور الطباعة: $ | أجور العرض: $")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
        target = io.BytesIO(); doc.save(target); target.seek(0)
        return target

    # --- القائمة الجانبية ---
    if 'cart' not in st.session_state: st.session_state.cart = {}
    page = st.sidebar.radio("القائمة:", ["🏠 الداشبورد والخريطة", "📄 إنشاء عرض سعر"])

    conn = get_connection()

    if page == "🏠 الداشبورد والخريطة":
         if page == "🏠 الداشبورد والخريطة":
        st.title("📊 حالة المواقع")
        df_all = pd.read_sql("SELECT [اسم العمود], [المحافظة], [العدد], [الشبكة] FROM [اعمدة انارة]", conn)
        
        # إنشاء الخريطة
        m = folium.Map(location=[34.8, 38.5], zoom_start=7)
        
        for _, row in df_all.iterrows():
            loc_name = row['اسم العمود']
            if loc_name in geo_map_data:
                # تجهيز النص المعالج ليظهر بشكل صحيح (غير معكوس)
                clean_name = ar(loc_name)
                clean_city = ar(row['المحافظة'])
                
                # صياغة معلومات الـ Popup مع تنسيق HTML بسيط لضمان الاتجاه
                popup_text = f"""
                <div style="direction: rtl; text-align: right; font-family: Arial;">
                    <b>الموقع:</b> {clean_name}<br>
                    <b>المحافظة:</b> {clean_city}<br>
                    <b>العدد:</b> {row['العدد']}
                </div>
                """
                
                folium.Marker(
                    location=geo_map_data[loc_name],
                    popup=folium.Popup(popup_text, max_width=300),
                    tooltip=clean_name, # يظهر عند مرور الماوس
                    icon=folium.Icon(color='purple', icon='info-sign')
                ).add_to(m)
        
        st_folium(m, width=1200, height=450)
        st.dataframe(df_all, use_container_width=True)


    elif page == "📄 إنشاء عرض سعر":
        st.title("📄 بناء عرض سعر جديد")
        col_in, col_view = st.columns(2)
        with col_in:
            cust = st.text_input("اسم الزبون")
            cities = pd.read_sql("SELECT المحافظة FROM المحافظات", conn)['المحافظة'].tolist()
            sel_city = st.selectbox("المحافظة", cities)
            raw = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة = '{sel_city}'", conn)
            nets = st.multiselect("اختر الشبكات:", raw['الشبكة'].unique().tolist())
            if st.button("➕ إضافة للسلة"):
                st.session_state.cart[sel_city] = {n: raw[raw['الشبكة'] == n][['الموقع', 'العدد']] for n in nets}
        
        with col_view:
            if st.session_state.cart:
                for c, nts in list(st.session_state.cart.items()):
                    for n, df in nts.items():
                        st.session_state.cart[c][n] = st.data_editor(df, key=f"ed_{c}_{n}")
                if st.button("🚀 تصدير"):
                    out = export_word(cust, st.session_state.cart, {'start': '2026', 'end': '2026'})
                    st.download_button("📥 تحميل", out, "Quotation.docx")
