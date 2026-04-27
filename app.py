import streamlit as st
import pandas as pd
import sqlite3
import os
import io
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from arabic_reshaper import reshape
from bidi.algorithm import get_display

# --- Page Config ---
st.set_page_config(page_title="PreView Ads ERP", layout="wide")

# --- Authentication Logic ---
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("🔒 Login - PreView System")
        user_input = st.text_input("User Name:")
        password_input = st.text_input("Password:", type="password")
        
        # You can add more users here
        users = {"admin": "preview2026", "wael": "wael123"}

        if st.button("Login"):
            if user_input in users and users[user_input] == password_input:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Invalid username or password")
        return False
    return True

if check_password():
    def get_connection():
        return sqlite3.connect('billboards_data.db')

    def ar(text):
        if not text: return ""
        return get_display(reshape(str(text)))

    # --- FIXED: Background Image Logic ---
    def add_float_picture(doc, image_path, width, height):
        header = doc.sections[0].header
        if not header.paragraphs: header.add_paragraph()
        run = header.paragraphs[0].add_run()
        shape = run.add_picture(image_path, width=width, height=height)
        
        inline = shape._inline
        extent = inline.extent
        doc_pr = inline.docPr
        
        # Added missing namespace (xmlns:a) to fix the ValueError
        anchor_xml = f"""
        <wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0" relativeHeight="0" behindDoc="1" locked="0" layoutInCell="1" allowOverlap="1" 
                   xmlns:wp="http://openxmlformats.org"
                   xmlns:a="http://openxmlformats.org">
            <wp:simplePos x="0" y="0"/>
            <wp:positionH relativeFrom="page"><wp:posOffset>0</wp:posOffset></wp:positionH>
            <wp:positionV relativeFrom="page"><wp:posOffset>0</wp:posOffset></wp:positionV>
            <wp:extent cx="{extent.cx}" cy="{extent.cy}"/>
            <wp:effectExtent l="0" t="0" r="0" b="0"/>
            <wp:wrapNone/>
            <wp:docPr id="{doc_pr.id}" name="{doc_pr.name}"/>
        </wp:anchor>"""
        
        anchor = OxmlElement(anchor_xml)
        anchor.append(inline.graphic)
        inline.getparent().replace(inline, anchor)

    def export_final_quotation(customer_name, cart_data, dates):
        doc = Document()
        doc.sections[0].right_to_left = True
        
        if os.path.exists('logo.png'):
            add_float_picture(doc, 'logo.png', width=Inches(8.27), height=Inches(11.69))

        for _ in range(5): doc.add_paragraph() 
        
        p_cust = doc.add_paragraph()
        p_cust.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p_cust.add_run(ar(f"السادة شركة .. {customer_name} المحترمين")).bold = True
        doc.add_paragraph(ar(f"نقدم لكم المواقع المتاحة للفترة من {dates['start']} لغاية {dates['end']} م")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

        for city, networks in cart_data.items():
            p_city = doc.add_paragraph()
            p_city.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            run_city = p_city.add_run(ar(f"محافظة {city}"))
            run_city.font.color.rgb = RGBColor(102, 0, 153)
            run_city.font.size = Pt(16)

            for net, df in networks.items():
                doc.add_paragraph(ar(f"شبكات {net}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
                
                # Table Logic (Clean 2-Column Selection)
                clean_df = df.iloc[:, :2].reset_index(drop=True)
                rows_needed = (len(clean_df) + 1) // 2
                table = doc.add_table(rows=rows_needed + 1, cols=4)
                table.style = 'Table Grid'
                
                # Headers
                table.cell(0, 0).text = ar("العدد")
                table.cell(0, 1).text = ar("الموقع")
                table.cell(0, 2).text = ar("العدد")
                table.cell(0, 3).text = ar("الموقع")

                for i in range(len(clean_df)):
                    row_idx = (i // 2) + 1
                    col_off = 0 if i % 2 == 0 else 2
                    table.cell(row_idx, col_off).text = str(clean_df.iloc[i, 1])
                    table.cell(row_idx, col_off + 1).text = ar(clean_df.iloc[i, 0])
                
                doc.add_paragraph(ar(f"العدد: [{int(clean_df.iloc[:, 1].sum())}]")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
        
        target = io.BytesIO()
        doc.save(target)
        target.seek(0)
        return target

    # --- UI Logic ---
    if 'cart' not in st.session_state: st.session_state.cart = {}
    st.sidebar.title("💎 PreView Ads ERP")
    page = st.sidebar.radio("Navigation:", ["📊 Dashboard", "📄 Quotations & Contracts"])

    if st.sidebar.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.rerun()

    conn = get_connection()

    if page == "📊 Dashboard":
        st.title("📊 Dashboard")
        df_all = pd.read_sql("SELECT * FROM [اعمدة انارة]", conn)
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Sites", len(df_all))
        c2.metric("Provinces", df_all['المحافظة'].nunique())
        c3.metric("Total Count", df_all['العدد'].sum())
        st.dataframe(df_all, use_container_width=True)

    elif page == "📄 Quotations & Contracts":
        st.title("📄 Quotation Builder")
        col_in, col_view = st.columns(2)
        
        with col_in:
            cust_name = st.text_input("Customer Name")
            cities = pd.read_sql("SELECT المحافظة FROM المحافظات", conn)['المحافظة'].tolist()
            sel_city = st.selectbox("Select Province", cities)
            raw_df = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة = '{sel_city}'", conn)
            sel_nets = st.multiselect("Select Networks:", raw_df['الشبكة'].unique().tolist())
            
            if st.button("➕ Add to List"):
                st.session_state.cart[sel_city] = {n: raw_df[raw_df['الشبكة'] == n][['الموقع', 'العدد']] for n in sel_nets}
                st.success(f"Added {sel_city}")

        with col_view:
            if st.session_state.cart:
                for c_n, nets in st.session_state.cart.items():
                    with st.expander(f"📍 {c_n}"):
                        for n_n, df in nets.items():
                            st.session_state.cart[c_n][n_n] = st.data_editor(df, key=f"ed_{c_n}_{n_n}")
                
                if st.button("🚀 Export Word"):
                    dates = {'start': "2026/05/01", 'end': "2026/05/28"}
                    out_file = export_final_quotation(cust_name, st.session_state.cart, dates)
                    st.download_button("📥 Download", out_file, f"Quotation_{cust_name}.docx")
                
                if st.button("🗑️ Clear"):
                    st.session_state.cart = {}; st.rerun()
