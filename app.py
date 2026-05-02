import streamlit as st
import pandas as pd
import sqlite3
import os
import io
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
from docx import Document
from docx.shared import Pt, RGBColor, Cm 
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
    if not text or str(text).strip() == "": return ""
    return get_display(reshape(str(text)))

def set_cell_shading(cell, color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), color)
    tcPr.append(shd)

# --- دالة تصدير الوورد (الخلفية خلف النص تماماً) ---
def export_word(customer_name, cart_data, period_name):
    doc = Document()
    section = doc.sections[0]
    section.page_height, section.page_width = Cm(29.7), Cm(21)
    section.left_margin = section.right_margin = section.top_margin = section.bottom_margin = Cm(2)

    # إضافة الخلفية في الهيدر (خلفية ثابتة لكل الصفحات)
    header = section.header
    p_head = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
    
    if os.path.exists('logo_full.png'):
        run = p_head.add_run()
        pic = run.add_picture('logo_full.png', width=Cm(21), height=Cm(29.7))
        
        try:
            # تحويل الصورة إلى عنصر عائم خلف النص (Behind Text)
            inline = pic._inline
            extent, doc_pr, graphic = inline.extent, inline.docPr, inline.graphic
            
            anchor = OxmlElement('wp:anchor')
            anchor.set(qn('wp:behindDoc'), '1') # جعلها خلف النص قسرياً
            anchor.set(qn('wp:locked'), '0')
            anchor.set(qn('wp:layoutInCell'), '1')
            anchor.set(qn('wp:allowOverlap'), '1')
            anchor.set(qn('wp:simplePos'), '0')
            anchor.set(qn('wp:relativeHeight'), '0')

            # التموضع المطلق (0,0) من حافة الصفحة
            for axis in ['H', 'V']:
                pos = OxmlElement(f'wp:position{axis}')
                pos.set(qn('relativeFrom'), 'page')
                off = OxmlElement('wp:posOffset')
                off.text = '0'
                pos.append(off)
                anchor.append(pos)

            anchor.append(extent)
            anchor.append(OxmlElement('wp:effectExtent'))
            anchor.append(OxmlElement('wp:wrapNone')) # النص يمر فوقها
            anchor.append(doc_pr)
            anchor.append(graphic)
            
            p_head._p.remove(run._r)
            p_head._p.add_run()._r.append(anchor)
        except: pass

    # --- محتوى الخطاب ---
    for _ in range(2): doc.add_paragraph() # مسافة علوية
    
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_t = p_title.add_run(ar(f"عرض سعر للسادة شركة {customer_name}"))
    run_t.bold = True
    run_t.font.size = Pt(22)
    run_t.font.color.rgb = RGBColor(102, 0, 153)

    doc.add_paragraph(ar(f"تاريخ العرض: 2026/03/09")).alignment = WD_ALIGN_PARAGRAPH.LEFT
    doc.add_paragraph(ar(f"الفترة الإعلانية: {period_name}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # بناء الجداول
    if cart_data:
        for city, networks in cart_data.items():
            doc.add_paragraph(ar(f"■ محافظة {city}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
            for net, df in networks.items():
                table = doc.add_table(rows=1, cols=4)
                table.style, table.alignment = 'Table Grid', WD_ALIGN_PARAGRAPH.CENTER
                
                hdr = table.rows[0].cells
                for i, t in enumerate(["العدد", "الموقع", "العدد", "الموقع"]):
                    hdr[i].text = ar(t)
                    set_cell_shading(hdr[i], "660099")
                    r = hdr[i].paragraphs[0].runs[0]
                    r.font.color.rgb, r.bold = RGBColor(255, 255, 255), True

                data = df.values.tolist()
                for i in range(0, len(data), 2):
                    row = table.add_row().cells
                    row[1].text, row[0].text = ar(data[i][0]), str(data[i][1])
                    if i + 1 < len(data):
                        row[3].text, row[2].text = ar(data[i+1][0]), str(data[i+1][1])

    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- واجهة تطبيق Streamlit ---
if "auth" not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 PreView ERP Login")
    u, p = st.text_input("User"), st.text_input("Password", type="password")
    if st.button("Login"):
        if u == "admin" and p == "preview2026":
            st.session_state.auth = True
            st.rerun()
        else: st.error("Error")
else:
    conn = get_connection()
    if 'cart' not in st.session_state: st.session_state.cart = {}
    
    with st.sidebar:
        if os.path.exists('logo_full.png'): st.image('logo_full.png', width=180)
        st.header("PreView Ads")
        page = st.radio("Menu", ["📊 Dashboard", "📄 Quotation"])
        if st.button("Logout"): st.session_state.auth = False; st.rerun()

    if page == "📊 Dashboard":
        st.title("📊 Dashboard & Map")
        try:
            df_all = pd.read_sql("SELECT * FROM [اعمدة انارة]", conn)
            df_b = pd.read_sql("SELECT [رقم اللوحة], [اسم الزبون] FROM [حجوزات1]", conn)
            df_m = pd.merge(df_all, df_b, on='رقم اللوحة', how='left')
            
            city = st.selectbox("City", ["All"] + sorted(df_m['المحافظة'].unique().tolist()))
            f_df = df_m if city == "All" else df_m[df_m['المحافظة'] == city]
            
            m = folium.Map(location=[33.51, 36.27], zoom_start=12)
            for _, r in f_df.iterrows():
                if pd.notnull(r['Latitude']):
                    folium.Marker([r['Latitude'], r['Longitude']], 
                                  popup=ar(r['اسم العمود']),
                                  icon=folium.Icon(color='red' if pd.notnull(r['اسم الزبون']) else 'purple')).add_to(m)
            st_folium(m, width="100%", height=500)
            st.dataframe(f_df, use_container_width=True)
        except Exception as e: st.error(e)

    elif page == "📄 Quotation":
        st.title("📄 Quotation Builder")
        try:
            p_list = pd.read_sql("SELECT namee FROM [الفترة]", conn)['namee'].tolist()
            cust = st.text_input("Customer Name")
            period = st.selectbox("Period", p_list)
            city_l = pd.read_sql("SELECT DISTINCT المحافظة FROM [اعمدة انارة]", conn)['المحافظة'].tolist()
            sel_c = st.selectbox("City", city_l)
            
            raw = pd.read_sql(f"SELECT [اسم العمود], [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة='{sel_c}'", conn)
            nets = st.multiselect("Nets", raw['الشبكة'].unique().tolist())
            
            if st.button("➕ Add"):
                if sel_c not in st.session_state.cart: st.session_state.cart[sel_c] = {}
                for n in nets: st.session_state.cart[sel_c][n] = raw[raw['الشبكة'] == n].assign(**{'أجور العرض': 0})

            if st.session_state.cart:
                for c, nts in list(st.session_state.cart.items()):
                    for n, df in nts.items():
                        st.session_state.cart[c][n] = st.data_editor(df, key=f"ed_{c}_{n}")
                
                if st.button("🚀 Export Word"):
                    doc_io = export_word(cust, st.session_state.cart, period)
                    st.download_button("📥 Download", doc_io, f"Quotation_{cust}.docx")
        except Exception as e: st.error(e)
    conn.close()
