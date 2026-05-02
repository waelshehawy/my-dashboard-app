import streamlit as st
import pandas as pd
import sqlite3
import os
import io
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm 
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from arabic_reshaper import reshape
from bidi.algorithm import get_display 

# --- إعدادات الصفحة ---
st.set_page_config(page_title="PreView Ads ERP", layout="wide")

def get_connection():
    return sqlite3.connect('billboards_data.db')

def ar(text):
    """معالجة النصوص العربية"""
    if not text or str(text).strip() == "": return ""
    return get_display(reshape(str(text)))

def set_cell_shading(cell, color):
    """تلوين خلفية الخلايا"""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), color)
    tcPr.append(shd)

# --- دالة تصدير الوورد الاحترافية ---
def export_word(customer_name, cart_data, period_name):
    doc = Document()
    
    # 1. إعدادات الصفحة A4
    section = doc.sections[0]
    section.page_height = Cm(29.7)
    section.page_width = Cm(21)
    section.left_margin = Cm(2)
    section.right_margin = Cm(2)
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2)

    # 2. إضافة الخلفية (خلف النص تماماً وبدون إزاحة)
    header = section.header
    header.is_linked_to_previous = False
    p_head = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
    p_head.alignment = WD_ALIGN_PARAGRAPH.LEFT
    
    if os.path.exists('logo_full.png'):
        run = p_head.add_run()
        pic = run.add_picture('logo_full.png', width=Cm(21), height=Cm(29.7))
        
        try:
            # تحويل الصورة إلى عنصر عائم مطلق خلف النص
            inline = pic._inline
            extent = inline.extent
            doc_pr = inline.docPr
            graphic = inline.graphic
            
            anchor = OxmlElement('wp:behindtext')
            anchor.set(qn('wp:behindDoc'), '1') # جعلها خلف النص
            anchor.set(qn('wp:locked'), '0')
            anchor.set(qn('wp:layoutInCell'), '1')
            anchor.set(qn('wp:allowOverlap'), '1')
            anchor.set(qn('wp:simplePos'), '0')
            anchor.set(qn('wp:relativeHeight'), '0')

            # إحداثيات (0,0) بالنسبة للصفحة
            for axis in ['H', 'V']:
                pos = OxmlElement(f'wp:position{axis}')
                pos.set(qn('relativeFrom'), 'page')
                offset = OxmlElement('wp:posOffset')
                offset.text = '0'
                pos.append(offset)
                anchor.append(pos)

            anchor.append(extent)
            anchor.append(OxmlElement('wp:effectExtent'))
            anchor.append(OxmlElement('wp:wrapNone')) # لا تزيح النص
            anchor.append(doc_pr)
            anchor.append(graphic)
            
            p_head._p.remove(run._r)
            p_head._p.add_run()._r.append(anchor)
        except: pass

    # 3. محتوى العرض (فوق الخلفية)
    doc.add_paragraph()
    p_date = doc.add_paragraph(f"{ar('التاريخ:')} 2026/03/09")
    p_date.alignment = WD_ALIGN_PARAGRAPH.LEFT

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_t = p_title.add_run(ar(f"السادة شركة {customer_name} المحترمين"))
    run_t.bold = True
    run_t.font.size = Pt(20)
    run_t.font.color.rgb = RGBColor(102, 0, 153)

    doc.add_paragraph(ar("تحية طيبة وبعد،")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
    doc.add_paragraph(ar(f"نقدم لكم المواقع المتاحة للفترة الإعلانية: {period_name}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # 4. بناء الجداول
    for city, networks in cart_data.items():
        doc.add_paragraph(ar(f"■ محافظة {city}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
        
        for net, df in networks.items():
            doc.add_paragraph(ar(f"شبكة: {net}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
            
            table = doc.add_table(rows=1, cols=4)
            table.style = 'Table Grid'
            table.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            hdr_cells = table.rows[0].cells
            titles = ["العدد", "الموقع", "العدد", "الموقع"]
            for i, title in enumerate(titles):
                hdr_cells[i].text = ar(title)
                set_cell_shading(hdr_cells[i], "660099")
                run = hdr_cells[i].paragraphs[0].runs[0]
                run.font.color.rgb = RGBColor(255, 255, 255)
                run.bold = True
                hdr_cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

            data_list = df.values.tolist()
            for i in range(0, len(data_list), 2):
                row_cells = table.add_row().cells
                # اليمين
                row_cells[1].text = ar(data_list[i][0])
                row_cells[0].text = str(data_list[i][1])
                # اليسار
                if i + 1 < len(data_list):
                    row_cells[3].text = ar(data_list[i+1][0])
                    row_cells[2].text = str(data_list[i+1][1])
            
            total_n = pd.to_numeric(df.iloc[:, 1], errors='coerce').sum()
            ads = pd.to_numeric(df['أجور العرض'], errors='coerce').sum()
            
            p_price = doc.add_paragraph()
            p_price.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            price_text = f"{ar('إجمالي العدد:')} {int(total_n)} | {ar('أجور العرض:')} {ads:,}$"
            run_p = p_price.add_run(price_text)
            run_p.bold = True
            run_p.font.color.rgb = RGBColor(102, 0, 153)

    # 5. الفوتر
    footer = section.footer
    p_foot = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    p_foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_f = p_foot.add_run(ar("سوريا - دمشق | info@previewsyria.com | +963 9394"))
    run_f.font.size = Pt(9)
    run_f.font.color.rgb = RGBColor(102, 0, 153)

    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- تطبيق Streamlit ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 PreView ERP Login")
    user = st.text_input("User")
    pwd = st.text_input("Password", type="password")
    if st.button("Login"):
        if user == "admin" and pwd == "preview2026":
            st.session_state.authenticated = True
            st.rerun()
        else: st.error("Wrong Credentials")
else:
    conn = get_connection()
    if 'cart' not in st.session_state: st.session_state.cart = {}
    
    with st.sidebar:
        if os.path.exists('logo_full.png'):
            st.image('logo_full.png', width=180)
        st.header("Control Panel")
        page = st.radio("Menu", ["📊 Dashboard", "📄 Create Quotation"])
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.rerun()

    if page == "📊 Dashboard":
        st.title("📊 Dashboard & Map")
        try:
            df_all = pd.read_sql("SELECT * FROM [اعمدة انارة]", conn)
            df_booked = pd.read_sql("SELECT [رقم اللوحة], [اسم الزبون], [فترة الحجز] FROM [حجوزات1]", conn)
            df_map = pd.merge(df_all, df_booked, on='رقم اللوحة', how='left')
            
            with st.sidebar:
                st.divider()
                city_f = st.selectbox("City", ["All"] + sorted(df_map['المحافظة'].unique().tolist()))
                stat_f = st.radio("Status", ["All", "Available", "Booked"])

            f_df = df_map.copy()
            if city_f != "All": f_df = f_df[f_df['المحافظة'] == city_f]
            if stat_f == "Booked": f_df = f_df[f_df['اسم الزبون'].notna()]
            elif stat_f == "Available": f_df = f_df[f_df['اسم الزبون'].isna()]

            m = folium.Map(location=[33.51, 36.27], zoom_start=12)
            marker_cluster = MarkerCluster().add_to(m)
            for _, row in f_df.iterrows():
                if pd.notnull(row['Latitude']):
                    is_b = pd.notnull(row['اسم الزبون'])
                    pop = f"<div style='direction:rtl;'><b>{row['اسم العمود']}</b><br>{'Booked' if is_b else 'Available'}</div>"
                    folium.Marker([row['Latitude'], row['Longitude']], popup=folium.Popup(pop, max_width=200), 
                                  icon=folium.Icon(color='red' if is_b else 'purple')).add_to(marker_cluster)
            st_folium(m, width="100%", height=500)
            st.dataframe(f_df, use_container_width=True)
        except Exception as e: st.error(f"Error: {e}")

    elif page == "📄 Create Quotation":
        st.title("📄 Quotation Builder")
        try:
            df_periods = pd.read_sql("SELECT namee FROM [الفترة]", conn)['namee'].tolist()
            col1, col2 = st.columns(2)
            with col1:
                cust_name = st.text_input("Customer Name")
                period = st.selectbox("Period", df_periods)
                city_list = pd.read_sql("SELECT DISTINCT المحافظة FROM [اعمدة انارة]", conn)['المحافظة'].tolist()
                city = st.selectbox("Select City", city_list)
                raw = pd.read_sql(f"SELECT [اسم العمود], [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة='{city}'", conn)
                nets = st.multiselect("Nets", raw['الشبكة'].unique().tolist())
                
                if st.button("Add to Cart"):
                    if city not in st.session_state.cart: st.session_state.cart[city] = {}
                    for n in nets:
                        d_net = raw[raw['الشبكة'] == n].copy()
                        d_net['أجور العرض'] = 0
                        st.session_state.cart[city][n] = d_net

            with col2:
                if st.session_state.cart:
                    for c, nts in list(st.session_state.cart.items()):
                        for n, df in nts.items():
                            with st.expander(f"📍 {c} - {n}"):
                                st.session_state.cart[c][n] = st.data_editor(df, key=f"ed_{c}_{n}")
                    
                    if st.button("Export Word"):
                        doc_file = export_word(cust_name, st.session_state.cart, period)
                        st.download_button("Download Doc", doc_file, f"Quotation_{cust_name}.docx")
                    if st.button("Clear Cart"): st.session_state.cart = {}; st.rerun()
        except Exception as e: st.error(f"Error: {e}")
    conn.close()
