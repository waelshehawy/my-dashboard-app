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
    try:
        # تأكد من أن الـ host هو العنوان التقني وليس رابط موقع
        return psycopg2.connect(
            host="aws-1-eu-north-1.pooler.supabase.com", # العنوان الصحيح لسيرفرك
            port="6543",                                 # المنفذ الخاص بالـ Pooler
            database="postgres",
            user="postgres.ncuofpvbaglwbdqnpman",
            password="WaelPreview2026",
            sslmode="require",
            connect_timeout=10
        )
    except Exception as e:
        st.error(f"فشل الاتصال التقني: {e}")
        return None



# --- 2. Word & RTL Helpers ---
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
    p_stat.add_run(f"نقدم لكم المواقع المتاحة لعرض إعلانكم من فترة ({start_p}) ولغاية ({end_p})")
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
                    row_cells[0].text = str(row['الموقع'])
                    row_cells[1].text = str(row['العدد'])
                    for cell in row_cells: apply_rtl(cell)

                # --- حساب الأجور في الوورد ---
                total_q = pd.to_numeric(group_df['العدد']).sum()
                f_p, f_a = float(group_df['fee_print'].iloc[0]), float(group_df['fee_ads'].iloc[0])
                total_all = (total_q * f_p) + (total_q * f_a)
                p_sum = doc.add_paragraph()
                txt = f"العدد: {int(total_q)} | إجمالي التكلفة: {total_all:,.0f}$"
                run = p_sum.add_run(txt); run.bold = True; apply_rtl(p_sum)
                    
    doc.add_paragraph()
    p_note = doc.add_paragraph(); p_note.add_run("• ملاحظة: هذه المواقع متاحة لمدة 48 ساعة.").bold = True; apply_rtl(p_note)
    
    target = io.BytesIO(); doc.save(target); target.seek(0)
    return target
# --- 4. Main App & Logic (Part 2/2) ---
st.set_page_config(page_title="PreView Ads ERP - Cloud", layout="wide")
SYRIA_CITIES_COORDS = {
    "دمشق": [33.51, 36.27], "ريف دمشق": [33.45, 36.35], "حلب": [36.20, 37.13],
    "حمص": [34.73, 36.71], "حماة": [35.13, 36.75], "اللاذقية": [35.53, 35.79],
    "طرطوس": [34.88, 35.88], "سوريا": [34.80, 38.99]
}

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
        page = st.radio("القائمة", ["📊 Dashboard", "📄 Quotation", "📋 تقرير الجرد", "⚙️ الإعدادات"])
        if st.button("تسجيل الخروج"): st.session_state.auth = False; st.rerun()

    # --- Page: Quotation (استعادة السلة والحسابات) ---
    if page == "📄 Quotation":
        st.title("📄 بناء عرض سعر وتثبيت حجز")
        try:
            draw_df = pd.read_sql('SELECT * FROM "اسماء الرسم"', conn)
            df_periods = pd.read_sql('SELECT * FROM "الفترة" ORDER BY "no"', conn)
            
            cust = st.text_input("اسم الزبون")
            c1, c2, c3 = st.columns(3)
            with c1: sel_size = st.selectbox("المقاس:", draw_df['الحجم'].unique().tolist())
            with c2: print_type = st.radio("نوع الطباعة:", ["عادي", "سكوتش"], horizontal=True)
            with c3: b_year = st.number_input("العام:", value=2026)

            cp1, cp2 = st.columns(2)
            with cp1: start_p = st.selectbox("من فترة:", df_periods['namee'].tolist())
            with cp2: end_p = st.selectbox("إلى فترة:", df_periods['namee'].tolist(), index=len(df_periods)-1)

            s_no = int(df_periods[df_periods['namee'] == start_p]['no'].iloc[0])
            e_no = int(df_periods[df_periods['namee'] == end_p]['no'].iloc[0])
            target_periods = df_periods[(df_periods['no'] >= s_no) & (df_periods['no'] <= e_no)]['namee'].tolist()

            # حساب الأجور قبل الفلترة
            subset = draw_df[draw_df['الحجم'] == sel_size]
            f_print, f_ads = 0.0, 0.0
            for _, row in subset.iterrows():
                name, val = str(row['اسم الرسم']).strip(), float(row['اجرة الرسم'])
                if print_type == "عادي":
                    if "طباعة" in name and "عادي" in name: f_print = val
                    elif "عرض" in name and "عادي" in name: f_ads = val
                else:
                    if "طباعة" in name and "عادي" not in name: f_print = val
                    elif "عرض" in name and "عادي" not in name: f_ads = val
            st.info(f"💰 أجور الطباعة: {f_print}$ | أجور العرض: {f_ads}$")

            # فلترة المتاح
            city_l = pd.read_sql('SELECT DISTINCT "المحافظة" FROM "اعمدة انارة"', conn)['المحافظة'].tolist()
            sel_city = st.selectbox("المحافظة:", city_l)
            
            periods_str = ", ".join([f"'{p}'" for p in target_periods])
            booked = pd.read_sql(f'SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" WHERE "العام"={b_year} AND "فترة الحجز" IN ({periods_str})', conn)['رقم اللوحة'].tolist()
            
            raw = pd.read_sql(f'SELECT "رقم اللوحة", "اسم العمود" as "الموقع", "العدد", "الشبكة", "توصيف العمود" FROM "اعمدة انارة" WHERE "المحافظة"=\'{sel_city}\' AND "الحجم"=\'{sel_size}\'', conn)
            raw = raw[~raw['رقم اللوحة'].isin(booked)]
            
            if not raw.empty:
                st.success(f"تم العثور على {len(raw)} موقع متاح")
                nets = st.multiselect("اختر الشبكات للإضافة:", raw['الشبكة'].unique().tolist())
                if st.button("➕ إضافة للسلة"):
                    if sel_city not in st.session_state.cart: st.session_state.cart[sel_city] = {}
                    for n in nets:
                        st.session_state.cart[sel_city][n] = raw[raw['الشبكة'] == n].assign(
                            الحجم=sel_size, fee_print=f_print, fee_ads=f_ads, year=b_year
                        )
                    st.rerun()

            # --- عرض السلة والحسابات (الميزة المستعادة) ---

    # --- Page: Dashboard (استعادة الخريطة الملونة والمعلومات) ---
    elif page == "📊 Dashboard":
        st.title("📊 الخريطة التفاعلية وحالة الإشغال")
        df_all = pd.read_sql('SELECT * FROM "اعمدة انارة"', conn)
        df_booked = pd.read_sql('SELECT * FROM "حجوزات1"', conn)
        df_periods = pd.read_sql('SELECT * FROM "الفترة" ORDER BY "no"', conn)

        # منطق تحديد المحجوز (أحمر) والمتاح (موف)
        df_merged = pd.merge(df_all, df_booked, on='رقم اللوحة', how='left')
        
        m = folium.Map(location=SYRIA_CITIES_COORDS["سوريا"], zoom_start=7)
        cluster = MarkerCluster().add_to(m)
        for _, r in df_merged.iterrows():
            if pd.notnull(r['Latitude']):
                is_booked = pd.notnull(r['اسم الزبون'])
                color = 'red' if is_booked else 'purple'
                popup_text = f"الموقع: {r['اسم العمود']}<br>الحالة: {'محجوز لـ ' + r['اسم الزبون'] if is_booked else 'متاح'}"
                folium.Marker([r['Latitude'], r['Longitude']], popup=popup_text, icon=folium.Icon(color=color)).add_to(cluster)
        st_folium(m, width="100%", height=600)
        st.dataframe(df_merged, use_container_width=True)

    conn.close()
