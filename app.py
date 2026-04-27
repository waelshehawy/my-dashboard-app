import streamlit as st
import pandas as pd
import sqlite3
import os
import io
import plotly.express as px
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from arabic_reshaper import reshape
from bidi.algorithm import get_display

# --- Page Setup ---
st.set_page_config(page_title="PreView Ads ERP", layout="wide")

# --- Security ---
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.title("🔒 PreView System Login")
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        if st.button("Login"):
            if user == "admin" and pwd == "preview2026":
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Invalid Credentials")
        return False
    return True

if check_password():
    def get_connection():
        return sqlite3.connect('billboards_data.db')

    def ar(text):
        if not text: return ""
        return get_display(reshape(str(text)))

    # --- Word Export (Watermark + Double Tables) ---
    def export_final_quotation(customer_name, cart_data, dates):
        doc = Document()
        doc.sections[0].right_to_left = True
        if os.path.exists('logo.png'):
            header = doc.sections[0].header
            p = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.add_run().add_picture('logo.png', width=Inches(7.5))

        for _ in range(5): doc.add_paragraph()
        p_cust = doc.add_paragraph()
        p_cust.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p_cust.add_run(ar(f"السادة شركة .. {customer_name} المحترمين")).bold = True
        doc.add_paragraph(ar(f"نقدم لكم المواقع المتاحة للفترة: {dates['period']} - {dates['year']}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

        for city, networks in cart_data.items():
            p_city = doc.add_paragraph()
            p_city.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            run_city = p_city.add_run(ar(f"محافظة {city}"))
            run_city.font.color.rgb = RGBColor(102, 0, 153)
            for net, df in networks.items():
                doc.add_paragraph(ar(f"شبكات {net}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
                # Double Table (4 columns)
                table = doc.add_table(rows=1, cols=4); table.style = 'Table Grid'
                table.cell(0, 0).text = ar("العدد")
                table.cell(0, 1).text = ar("الموقع")
                table.cell(0, 2).text = ar("العدد")
                table.cell(0, 3).text = ar("الموقع")

                clean_df = df.iloc[:, :2].reset_index(drop=True)
                for i in range(len(clean_df)):
                    row_idx, col_off = (i // 2) + 1, (0 if i % 2 == 0 else 2)
                    if row_idx >= len(table.rows): table.add_row()
                    table.cell(row_idx, col_off).text = str(clean_df.iloc[i, 1])
                    table.cell(row_idx, col_off + 1).text = ar(clean_df.iloc[i, 0])
        target = io.BytesIO(); doc.save(target); target.seek(0)
        return target

    # --- Main App ---
    if 'cart' not in st.session_state: st.session_state.cart = {}
    st.sidebar.title("💎 PreView Ads ERP")
    page = st.sidebar.radio("Navigation:", ["🏠 Dashboard", "📄 Create Quotation"])

    conn = get_connection()

    if page == "🏠 Dashboard":
        st.title("📊 Business Statistics")
        df_all = pd.read_sql("SELECT [اسم العمود], [المحافظة], [العدد], [الشبكة] FROM [اعمدة انارة]", conn)
        c1, c2 = st.columns(2)
        c1.metric("Total Locations", len(df_all))
        c2.metric("Total Provinces", df_all['المحافظة'].nunique())
        fig = px.pie(df_all, names='المحافظة', values='العدد', title="Locations by Province")
        st.plotly_chart(fig, use_container_width=True)

    elif page == "📄 Create Quotation":
        st.title("📄 Professional Quotation Builder")
        col_in, col_view = st.columns(2)
        
        with col_in:
            cust = st.text_input("Customer Name")
            cities = pd.read_sql("SELECT المحافظة FROM المحافظات", conn)['المحافظة'].tolist()
            sel_city = st.selectbox("Select Province", cities)
            # Use current columns found in check code
            raw_df = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة = '{sel_city}'", conn)
            sel_nets = st.multiselect("Select Networks:", raw_df['الشبكة'].unique().tolist())
            
            if st.button("➕ Add to List"):
                st.session_state.cart[sel_city] = {n: raw_df[raw_df['الشبكة'] == n][['الموقع', 'العدد']] for n in sel_nets}
                st.success(f"Added {sel_city}")

        with col_view:
            if st.session_state.cart:
                for cn, nets in st.session_state.cart.items():
                    with st.expander(f"📍 {cn}", expanded=True):
                        for nn, df in nets.items():
                            st.session_state.cart[cn][nn] = st.data_editor(df, key=f"ed_{cn}_{nn}")
                
                if st.button("🚀 Export Word Document"):
                    out = export_final_quotation(cust, st.session_state.cart, {'period': '2026', 'year': '2026'})
                    st.download_button("📥 Download Now", out, f"Quotation_{cust}.docx")
                if st.button("🗑️ Clear All"):
                    st.session_state.cart = {}; st.rerun()
