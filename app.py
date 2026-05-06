import streamlit as st
import pandas as pd
import psycopg2
import os
import io
import folium
import json
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
from docx import Document
from docx.shared import Pt, RGBColor, Cm 
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# --- 1. Database Connection (Supabase) ---
def get_connection():
    return psycopg2.connect(
        host="aws-1-eu-north-1.pooler.supabase.com", # <--- Fixed Host
        port="6543",                                 # <--- Fixed Port
        database="postgres",
        user="postgres.ncuofpvbaglwbdqnpman",
        password="w@EL!@#123$", 
        sslmode="require"
    )


def init_offers_db():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS offers_history (
            id SERIAL PRIMARY KEY,
            client_name TEXT,
            offer_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            cart_json TEXT,
            start_p TEXT,
            end_p TEXT,
            year INTEGER,
            status TEXT DEFAULT 'Pending'
        )''')
        conn.commit()
        conn.close()
    except Exception as e:
        pass

init_offers_db()

# --- 2. RTL & Word Helpers ---
def _force_rtl_style(p):
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT 
    pPr = p._element.get_or_add_pPr()
    bidi = OxmlElement('w:bidi'); bidi.set(qn('w:val'), '1'); pPr.append(bidi)
    for run in p.runs:
        rPr = run._element.get_or_add_rPr()
        rtl = OxmlElement('w:rtl'); rtl.set(qn('w:val'), '1'); rPr.append(rtl)
        rFonts = OxmlElement('w:rFonts'); rFonts.set(qn('w:cs'), 'Arial'); rPr.append(rFonts)

def apply_rtl(obj):
    if hasattr(obj, 'paragraphs'):
        for p in obj.paragraphs: _force_rtl_style(p)
    else: _force_rtl_style(obj)

def set_table_rtl(table):
    tblPr = table._element.xpath('w:tblPr')[0]
    bidi = OxmlElement('w:bidiVisual'); tblPr.append(bidi)

def export_word(customer_name, cart_data, start_p, end_p):
    doc = Document('template.docx') if os.path.exists('template.docx') else Document()
    for section in doc.sections: section.top_margin = Cm(4.5) 
    PURPLE_COLOR = "660099" 
    p_cust = doc.add_paragraph(); p_cust.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cust.add_run(f"السادة شركة {customer_name} المحترمين").bold = True
    p_stat = doc.add_paragraph()
    p_stat.add_run(f"نقدم لكم المواقع المتاحة للفترة من ({start_p}) ولغاية ({end_p})")
    apply_rtl(p_stat)
    for city, networks in cart_data.items():
        p_city = doc.add_paragraph(f"■ محافظة {city}"); apply_rtl(p_city)
        for net, df in networks.items():
            if df.empty: continue
            for (size, desc), group_df in df.groupby(['الحجم', 'توصيف العمود']):
                p_size = doc.add_paragraph(f"النوع: {desc} | القياس: {size}"); apply_rtl(p_size)
                table = doc.add_table(rows=1, cols=2); table.style = 'Table Grid'; set_table_rtl(table)
                hdr = table.rows[0].cells
                for cell in hdr:
                    shading_elm = OxmlElement('w:shd'); shading_elm.set(qn('w:fill'), PURPLE_COLOR)
                    cell._element.get_or_add_tcPr().append(shading_elm)
                    run = cell.paragraphs[0].add_run(); run.font.color.rgb = RGBColor(255, 255, 255)
                hdr[0].text = f"الشبكة: {net}"; hdr[1].text = "العدد"
                for cell in hdr: apply_rtl(cell)
                for _, row in group_df.iterrows():
                    row_cells = table.add_row().cells
                    row_cells[0].text = str(row['الموقع']); row_cells[1].text = str(row['العدد'])
                    for cell in row_cells: apply_rtl(cell)
    target = io.BytesIO(); doc.save(target); target.seek(0)
    return target

# --- 3. Main App ---
st.set_page_config(page_title="PreView Ads ERP", layout="wide")
SYRIA_CITIES_COORDS = {"دمشق": [33.51, 36.27], "حلب": [36.20, 37.13], "سوريا": [34.80, 38.99]}

if "auth" not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 تسجيل الدخول")
    u, p = st.text_input("User"), st.text_input("Pass", type="password")
    if st.button("Login"):
        if u == "a" and p == "3900": st.session_state.auth = True; st.rerun()
else:
    conn = get_connection()
    if 'cart' not in st.session_state: st.session_state.cart = {}
    
    with st.sidebar:
        page = st.radio("القائمة", ["📊 Dashboard", "📄 Quotation", "📋 تقرير الجرد"])
        if st.button("تسجيل الخروج"): st.session_state.auth = False; st.rerun()

    if page == "📄 Quotation":
        st.title("📄 بناء عرض سعر")
        try:
            draw_df = pd.read_sql('SELECT * FROM "اسماء الرسم"', conn)
            df_periods = pd.read_sql('SELECT * FROM "الفترة" ORDER BY "no"', conn)
            cust = st.text_input("اسم الزبون")
            sel_size = st.selectbox("المقاس:", draw_df['الحجم'].unique().tolist())
            start_p = st.selectbox("من فترة:", df_periods['namee'].tolist())
            end_p = st.selectbox("إلى فترة:", df_periods['namee'].tolist(), index=len(df_periods)-1)
            
            s_no = int(df_periods[df_periods['namee'] == start_p]['no'].iloc[0])
            e_no = int(df_periods[df_periods['namee'] == end_p]['no'].iloc[0])
            target_periods = df_periods[(df_periods['no'] >= s_no) & (df_periods['no'] <= e_no)]['namee'].tolist()
            
            # فلترة المتاح
            city_l = pd.read_sql('SELECT DISTINCT "المحافظة" FROM "اعمدة انارة"', conn)['المحافظة'].tolist()
            sel_city = st.selectbox("المحافظة:", city_l)
            
            periods_str = ", ".join([f"'{p}'" for p in target_periods])
            booked = pd.read_sql(f'SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" WHERE "فترة الحجز" IN ({periods_str})', conn)['رقم اللوحة'].tolist()
            
            raw = pd.read_sql(f'SELECT * FROM "اعمدة انارة" WHERE "المحافظة"=\'{sel_city}\' AND "الحجم"=\'{sel_size}\'', conn)
            raw = raw[~raw['رقم اللوحة'].isin(booked)]
            
            if not raw.empty:
                nets = st.multiselect("اختر الشبكات:", raw['الشبكة'].unique().tolist())
                if st.button("➕ إضافة للسلة"):
                    for n in nets:
                        if sel_city not in st.session_state.cart: st.session_state.cart[sel_city] = {}
                        st.session_state.cart[sel_city][n] = raw[raw['الشبكة'] == n].assign(fee_print=0, fee_ads=0, الحجم=sel_size)
                    st.rerun()
            
            if st.session_state.cart:
                st.divider()
                if st.button("🚀 تصدير ملف Word"):
                    doc_io = export_word(cust, st.session_state.cart, start_p, end_p)
                    st.download_button("📥 تحميل العرض", doc_io, f"Quotation_{cust}.docx")
                
                if st.button("✅ تثبيت نهائي"):
                    cursor = conn.cursor()
                    for city, nets in st.session_state.cart.items():
                        for net, df in nets.items():
                            for _, row in df.iterrows():
                                for p_name in target_periods:
                                    cursor.execute('INSERT INTO "حجوزات1" ("رقم اللوحة", "اسم الزبون", "فترة الحجز") VALUES (%s, %s, %s)', (str(row['رقم اللوحة']), cust, p_name))
                    conn.commit()
                    st.success("تم التثبيت!")
                    st.session_state.cart = {}; st.rerun()

        except Exception as e:
            st.error(f"خطأ فني: {e}")

    elif page == "📊 Dashboard":
        st.title("📊 الخريطة الحية")
        df_all = pd.read_sql('SELECT * FROM "اعمدة انارة"', conn)
        m = folium.Map(location=SYRIA_CITIES_COORDS["سوريا"], zoom_start=7)
        st_folium(m, width="100%", height=500)

    conn.close()
