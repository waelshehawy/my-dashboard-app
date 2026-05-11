import streamlit as st
import pandas as pd
import psycopg2
import os, io, json, folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from sqlalchemy import create_engine, text
from datetime import datetime

# --- 1. قاعدة البيانات والاتصال ---
# --- 1. تصحيح إعدادات الاتصال (إزالة البروتوكول الزائد) ---
DB_CONFIG = {
    # تم إزالة البروتوكول وأي زوائد، فقط اسم السيرفر
    "host": "aws-1-eu-north-1.pooler.supabase.com", 
    "port": "5432", 
    "database": "postgres",
    "user": "postgres.ncuofpvbaglwbdqnpman",
    "password": "WaelPreview2026",
    "sslmode": "require",
    "connect_timeout": 10
}

def get_connection():
    try:
        # استخدام إرسال البارامترات مباشرة لضمان عدم حدوث خطأ في الترجمة
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        st.error(f"❌ فشل الاتصال بقاعدة البيانات: {e}")
        return None

# --- إضافة فحص داخل الكود الرئيسي لمنع الـ AttributeError ---
if st.session_state.auth:
    conn = get_connection()
    if conn: # تأكد أن الاتصال ناجح قبل تنفيذ أي استعلام
        # ... كود الصفحات ...
    else:
        st.warning("⚠️ لا يمكن الوصول للسيرفر حالياً، يرجى المحاولة لاحقاً.")

# --- 2. دوال التنسيق المتقدمة (Word RTL) ---
def set_rtl(obj):
    pPr = obj._element.get_or_add_pPr()
    bidi = OxmlElement('w:bidi'); bidi.set(qn('w:val'), '1'); pPr.append(bidi)
    for run in obj.runs:
        rPr = run._element.get_or_add_rPr()
        rtl = OxmlElement('w:rtl'); rtl.set(qn('w:val'), '1'); rPr.append(rtl)

def set_table_rtl(table):
    tblPr = table._element.xpath('w:tblPr')[0]
    bidi = OxmlElement('w:bidiVisual'); tblPr.append(bidi)

# --- 3. دالة تصدير الوورد الاحترافية (تشمل الأجنبي) ---
def export_word(customer_name, cart_data, start_p, end_p, grand_total, is_foreign):
    doc = Document()
    today_date = datetime.now().strftime("%d / %m / %Y")
    
    p_date = doc.add_paragraph(); p_date.add_run(f"التاريخ: {today_date}"); set_rtl(p_date)
    doc.add_paragraph()
    
    p_cust = doc.add_paragraph(); p_cust.add_run(f"السادة شركة {customer_name} المحترمين").bold = True; set_rtl(p_cust)
    
    adv_type = "الأجنبي" if is_foreign else "الوطني"
    p_stat = doc.add_paragraph()
    p_stat.add_run(f"نقدم لكم المواقع المتاحة لعرض إعلانكم {adv_type} من فترة ({start_p}) ولغاية ({end_p})"); set_rtl(p_stat)

    for city, networks in cart_data.items():
        p_city = doc.add_paragraph(); p_city.add_run(f"■ محافظة {city}").bold = True; set_rtl(p_city)
        for net, items in networks.items():
            df = pd.DataFrame(items)
            p_net = doc.add_paragraph(); p_net.add_run(f"الشبكة: {net} | القياس: {df['الحجم'].iloc[0]}").bold = True; set_rtl(p_net)
            
            table = doc.add_table(rows=1, cols=2); table.style = 'Table Grid'; set_table_rtl(table)
            hdr = table.rows[0].cells
            hdr[0].text, hdr[1].text = "اسم الموقع (العمود)", "العدد"
            for cell in hdr:
                for p in cell.paragraphs: set_rtl(p)
                cell._element.get_or_add_tcPr().append(OxmlElement('w:shd')) # تظليل بسيط
            
            for _, row in df.iterrows():
                row_cells = table.add_row().cells
                row_cells[0].text, row_cells[1].text = str(row['الموقع']), str(row['العدد'])
                for cell in row_cells:
                    for p in cell.paragraphs: set_rtl(p)

    doc.add_paragraph()
    p_total = doc.add_paragraph()
    run_t = p_total.add_run(f"إجمالي القيمة المالية للعرض: {grand_total:,.0f} $"); run_t.bold = True; set_rtl(p_total)
    
    target = io.BytesIO(); doc.save(target); target.seek(0)
    return target

# --- 4. واجهة التطبيق الرئيسية ---
st.set_page_config(page_title="PreView ERP", layout="wide")

if "auth" not in st.session_state: st.session_state.auth = False
if "cart" not in st.session_state: st.session_state.cart = {}

if not st.session_state.auth:
    st.title("🔐 تسجيل الدخول")
    u, p = st.text_input("User"), st.text_input("Pass", type="password")
    if st.button("Login"):
        if u == "a" and p == "3900": st.session_state.auth = True; st.rerun()
else:
    conn = get_connection()
    with st.sidebar:
        st.image("https://placeholder.com", caption="PreView Ads") # ضع شعارك هنا
        page = st.radio("القائمة", ["📊 Dashboard", "📄 Quotation", "📋 تقرير الجرد", "⚙️ الإعدادات"])
        if st.button("🚪 خروج"): st.session_state.auth = False; st.rerun()

    # --- Page 1: Dashboard ---
    if page == "📊 Dashboard":
        st.title("📊 لوحة التحكم")
        df_all = pd.read_sql('SELECT * FROM "اعمدة انارة"', conn)
        df_booked = pd.read_sql(f'SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" WHERE "العام" = {datetime.now().year}', conn)
        df_all['الحالة'] = df_all['رقم اللوحة'].apply(lambda x: 'محجوز' if x in df_booked['رقم اللوحة'].values else 'متاح')
        
        c1, c2, c3 = st.columns(3)
        c1.metric("الإجمالي", len(df_all))
        c2.metric("محجوز", len(df_all[df_all['الحالة']=='محجوز']))
        c3.metric("متاح", len(df_all[df_all['الحالة']=='متاح']))
        
        m = folium.Map(location=[34.8, 39.0], zoom_start=7)
        cluster = MarkerCluster().add_to(m)
        for _, r in df_all.iterrows():
            color = 'red' if r['الحالة']=='محجوز' else 'purple'
            folium.Marker([r['Latitude'], r['Longitude']], icon=folium.Icon(color=color)).add_to(cluster)
        st_folium(m, width="100%", height=500)

    # --- Page 2: Quotation (المحرك المالي المعدل) ---
    elif page == "📄 Quotation":
        st.title("📄 بناء العرض")
        prices_df = pd.read_sql('SELECT * FROM "اسماء الرسم"', conn)
        periods_df = pd.read_sql('SELECT * FROM "الفترة" ORDER BY "no"', conn)
        
        cust = st.text_input("اسم الزبون")
        col_a, col_b, col_c = st.columns(3)
        with col_a: sz = st.selectbox("المقاس:", prices_df['الحجم'].unique())
        with col_b: pt = st.radio("الطباعة:", ["عادي", "سكوتش"], horizontal=True)
        with col_c: is_foreign = st.checkbox("🚩 إعلان أجنبي")
        
        col_d, col_e = st.columns(2)
        with col_d: calc_method = st.radio("طريقة الحساب:", ["بالفترة", "بالأيام"], horizontal=True)
        with col_e: days = st.number_input("المدة (بالأيام):", min_value=1, value=15) if calc_method == "بالأيام" else 15

        # البحث عن السعر (أجنبي/محلي)
        subset = prices_df[prices_df['الحجم'] == sz].copy()
        subset['name_clean'] = subset['اسم الرسم'].str.replace('أ', 'ا')
        
        f_print = subset[subset['name_clean'].str.contains(f"طباعة.*{pt.replace('أ','ا')}", na=False)]['اجرة الرسم'].sum()
        
        if is_foreign:
            f_ads_base = subset[subset['name_clean'].str.contains("عرض.*اجنبي", na=False)]['اجرة الرسم'].sum()
        else:
            f_ads_base = subset[subset['name_clean'].str.contains("عرض", na=False) & ~subset['name_clean'].str.contains("اجنبي", na=False)]['اجرة الرسم'].sum()

        f_ads_final = (f_ads_base / 15) * days if calc_method == "بالأيام" else f_ads_base

        # اختيار المواقع
        sel_city = st.selectbox("المحافظة:", pd.read_sql('SELECT DISTINCT "المحافظة" FROM "اعمدة انارة"', conn))
        raw = pd.read_sql(f"SELECT * FROM \"اعمدة انارة\" WHERE \"المحافظة\"='{sel_city}' AND \"الحجم\"='{sz}'", conn)
        
        if not raw.empty:
            nets = st.multiselect("الشبكات:", raw['الشبكة'].unique())
            if st.button("➕ إضافة للسلة"):
                if sel_city not in st.session_state.cart: st.session_state.cart[sel_city] = {}
                for n in nets:
                    st.session_state.cart[sel_city][n] = raw[raw['الشبكة']==n].assign(fee_print=f_print, fee_ads=f_ads_final, الحجم=sz).to_dict('records')
                st.rerun()

        # عرض السلة والتحميل
        if st.session_state.cart:
            st.divider()
            g_total = 0
            for c, ns in list(st.session_state.cart.items()):
                for n, items in list(ns.items()):
                    df_item = pd.DataFrame(items)
                    st.write(f"📍 {c} - {n}")
                    g_total += (pd.to_numeric(df_item['العدد']).sum() * (f_print + f_ads_final))
            
            st.info(f"إجمالي العرض: {g_total:,.0f} $")
            if st.button("📝 تصدير Word"):
                file = export_word(cust, st.session_state.cart, "فترة البداية", "فترة النهاية", g_total, is_foreign)
                st.download_button("📥 تحميل", file, f"Offer_{cust}.docx")

    # --- Page 3: Inventory ---
    elif page == "📋 تقرير الجرد":
        st.title("📋 الجرد")
        df_inv = pd.read_sql('SELECT "رقم اللوحة", "المحافظة", "الحجم" FROM "اعمدة انارة"', conn)
        st.dataframe(df_inv, use_container_width=True)

    # --- Page 4: Settings ---
    elif page == "⚙️ الإعدادات":
        st.title("⚙️ الإعدادات")
        engine = get_engine()
        df_p = pd.read_sql('SELECT * FROM "اسماء الرسم"', conn)
        new_df = st.data_editor(df_p, num_rows="dynamic")
        if st.button("حفظ"):
            new_df.to_sql("اسماء الرسم", engine, if_exists="replace", index=False)
            st.success("تم التحديث")

    conn.close()
