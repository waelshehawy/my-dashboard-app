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
        if user == "a" and pwd == "3900":
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
    st.title("📊 الخريطة التفاعلية للمواقع")

    # --- الاتصال وجلب البيانات ---
    conn = get_connection()
    df_all = pd.read_sql("SELECT * FROM [اعمدة انارة]", conn)
    
    # جلب الحجوزات (تأكد من مطابقة أسماء أعمدة جدول حجوزات1)
    try:
        df_booked_info = pd.read_sql("SELECT [رقم اللوحة], [اسم الزبون], [فترة الحجز] FROM [حجوزات1]", conn)
    except:
        # في حال لم تكن الجداول مكتملة بعد
        df_booked_info = pd.DataFrame(columns=['رقم اللوحة', 'اسم الزبون', 'فترة الحجز'])

    # دمج البيانات
    df_map = pd.merge(df_all, df_booked_info, on='رقم اللوحة', how='left')

    # --- الفلاتر الجانبية ---
    with st.sidebar:
        st.subheader("🔍 فلاتر البحث")
        
        # 1. فلتر المحافظة (العمود رقم 4)
        unique_cities = ["الكل"] + df_map['المحافظة'].dropna().unique().tolist()
        city_filter = st.selectbox("المحافظة:", unique_cities)
        
        # 2. فلتر الحالة (بناءً على وجود اسم زبون)
        status_filter = st.radio("حالة المواقع:", ["الكل", "متاح ✅", "محجوز 🚫"])

    # --- تطبيق الفلاتر برمجياً ---
    if city_filter != "الكل":
        df_map = df_map[df_map['المحافظة'] == city_filter]
    
    if status_filter == "محجوز 🚫":
        df_map = df_map[df_map['اسم الزبون'].notna()]
    elif status_filter == "متاح ✅":
        df_map = df_map[df_map['اسم الزبون'].isna()]

    # --- بناء الخريطة ---
    # نقطة المركز (دمشق)
    m = folium.Map(location=[33.51, 36.27], zoom_start=12)
    marker_cluster = MarkerCluster().add_to(m)

    for _, row in df_map.iterrows():
        # التأكد من وجود إحداثيات (العمود 8 و 9)
        if pd.notnull(row['Latitude']) and pd.notnull(row['Longitude']):
            is_booked = pd.notnull(row['اسم الزبون'])
            color = 'red' if is_booked else 'purple'
            
            # محتوى النافذة المنبثقة - استخدام HTML RTL لحل مشكلة الانعكاس
            cust_name = row['اسم الزبون'] if is_booked else "متوفر حالياً"
            expiry_date = row['فترة الحجز'] if is_booked else "-"
            
            popup_html = f"""
            <div style='direction: rtl; text-align: right; font-family: "Tahoma", sans-serif; min-width: 180px;'>
                <h5 style='margin:0; color: #660099;'>{row['اسم العمود']}</h5>
                <hr style='margin: 5px 0;'>
                <b>الشبكة:</b> {row['الشبكة']}<br>
                <b>الشركة:</b> {cust_name}<br>
                <b>تاريخ انتهاء الحجز:</b> {expiry_date}<br>
                <b>الحالة:</b> {'🚫 محجوز' if is_booked else '✅ متاح'}
            </div>
            """
            
            folium.Marker(
                location=[row['Latitude'], row['Longitude']],
                popup=folium.Popup(popup_html, max_width=300),
                icon=folium.Icon(color=color, icon='info-sign')
            ).add_to(marker_cluster)

    # عرض الخريطة
    st_folium(m, width="100%", height=550)
    
    # عرض الجدول التفصيلي أسفل الخريطة
    st.subheader("📋 تفاصيل البيانات")
    st.dataframe(df_map.drop(columns=['Latitude', 'Longitude']), use_container_width=True)


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
                if city not in st.session_state.cart: 
                    st.session_state.cart[city] = {}
                for n in nets:
                    st.session_state.cart[city][n] = raw[raw['الشبكة'] == n].copy()

        with col2:
            if st.session_state.cart:
                for c, nts in list(st.session_state.cart.items()):
                    for n, df in nts.items():
                        with st.expander(f"📍 {c} - {n}"):
                            # تأكد أن الـ data_editor يحمل مفتاحاً فريداً
                            st.session_state.cart[c][n] = st.data_editor(df, key=f"ed_{c}_{n}")
                
                if st.button("🚀 تصدير Word"):
                    doc_out = export_word(cust, st.session_state.cart)
                    st.download_button("📥 تحميل", doc_out, f"Quotation.docx")

    # إغلاق الاتصال يجب أن يكون في نهاية الـ else الكبيرة (نظام الأمان)
    conn.close() 

                    st.download_button("📥 تحميل", doc_out, f"Quotation.docx")
    conn.close()
