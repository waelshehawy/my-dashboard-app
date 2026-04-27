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

# --- Page Config ---
st.set_page_config(page_title="PreView Ads ERP - Final Stable", layout="wide")

def get_connection():
    return sqlite3.connect('billboards_data.db')

def ar(text):
    if not text: return ""
    return get_display(reshape(str(text)))

# --- Stable Export Logic (No XML Hacks) ---
def export_final_quotation(customer_name, cart_data, dates):
    doc = Document()
    
    # 1. Setup Sections (RTL and Margins)
    section = doc.sections[0]
    section.right_to_left = True
    
    # 2. Add Header (Logo) and Footer (Contact Info)
    # Header
    header = section.header
    header_para = header.paragraphs[0]
    header_para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    if os.path.exists('logo.png'):
        run_h = header_para.add_run()
        run_h.add_picture('logo.png', width=Inches(2.27)) # Full width Header

    # Footer
    footer = section.footer
    footer_para = footer.paragraphs[0]
    footer_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    if os.path.exists('footer.png'):
        run_f = footer_para.add_run()
        run_f.add_picture('footer.png', width=Inches(2.27)) # Full width Footer

    # 3. Main Content
    # Add spacing for the header
    for _ in range(3): doc.add_paragraph()
    
    p_cust = doc.add_paragraph()
    p_cust.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_cust.add_run(ar(f"السادة شركة .. {customer_name} المحترمين")).bold = True
    doc.add_paragraph(ar(f"نقدم لكم المواقع المتاحة للفترة: {dates['period']} - {dates['year']}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

    for city, networks in cart_data.items():
        p_city = doc.add_paragraph()
        p_city.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run_city = p_city.add_run(ar(f"محافظة {city}"))
        run_city.font.color.rgb = RGBColor(102, 0, 153)
        run_city.font.size = Pt(16)
        
        for net, df in networks.items():
            doc.add_paragraph(ar(f"شبكات {net}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
            
            # Double Table (4 columns)
            table = doc.add_table(rows=1, cols=4)
            table.style = 'Table Grid'
            # Set Headers
            table.cell(0, 0).text = ar("العدد")
            table.cell(0, 1).text = ar("الموقع")
            table.cell(0, 2).text = ar("العدد")
            table.cell(0, 3).text = ar("الموقع")

            # Get only first 2 columns to prevent errors
            clean_df = df.iloc[:, :2].reset_index(drop=True)
            for i in range(len(clean_df)):
                row_idx = (i // 2) + 1
                col_off = 0 if i % 2 == 0 else 2
                if row_idx >= len(table.rows): table.add_row()
                table.cell(row_idx, col_off).text = str(clean_df.iloc[i, 1])
                table.cell(row_idx, col_off + 1).text = ar(clean_df.iloc[i, 0])
            
            # Financial Totals (from the data editor)
            total_sum = pd.to_numeric(df.iloc[:, 1]).sum()
            print_val = df['أجور الطباعة'].iloc[0] if 'أجور الطباعة' in df.columns else "0"
            ads_val = df['أجور العرض'].iloc[0] if 'أجور العرض' in df.columns else "0"
            
            f_text = doc.add_paragraph()
            f_text.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            f_text.add_run(ar(f"العدد: [{int(total_sum)}] | أجور الطباعة: ${print_val} | أجور العرض: ${ads_val}"))

    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- Streamlit UI ---
if 'cart' not in st.session_state: st.session_state.cart = {}
st.sidebar.title("💎 PreView Ads ERP")
page = st.sidebar.radio("Navigation:", ["📊 Dashboard", "📄 Quotation Builder"])

conn = get_connection()

if page == "📊 Dashboard":
    st.title("📊 System Overview")
    df_all = pd.read_sql("SELECT [اسم العمود], [المحافظة], [العدد], [الشبكة] FROM [اعمدة انارة]", conn)
    st.plotly_chart(px.pie(df_all, names='المحافظة', values='العدد', hole=0.3), use_container_width=True)
    st.dataframe(df_all, use_container_width=True)

elif page == "📄 Quotation Builder":
    st.title("📄 Professional Quotation Builder")
    col_in, col_view = st.columns(2)
    
    with col_in:
        cust = st.text_input("Customer Name")
        cities = pd.read_sql("SELECT المحافظة FROM المحافظات", conn)['المحافظة'].tolist()
        sel_city = st.selectbox("Province", cities)
        raw_df = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة = '{sel_city}'", conn)
        sel_nets = st.multiselect("Select Networks:", raw_df['الشبكة'].unique().tolist())
        
        if st.button("➕ Add Selection to Cart"):
            if sel_nets:
                if sel_city not in st.session_state.cart:
                    st.session_state.cart[sel_city] = {}
                for n in sel_nets:
                    temp_df = raw_df[raw_df['الشبكة'] == n][['الموقع', 'العدد']].copy()
                    temp_df['أجور الطباعة'] = 0
                    temp_df['أجور العرض'] = 0
                    st.session_state.cart[sel_city][n] = temp_df
                st.success(f"Added networks for {sel_city}")

    with col_view:
        if st.session_state.cart:
            for cn, nets in list(st.session_state.cart.items()):
                for nn, df in list(nets.items()):
                    with st.expander(f"📍 {cn} - Network {nn}", expanded=True):
                        st.session_state.cart[cn][nn] = st.data_editor(df, key=f"ed_{cn}_{nn}")
            
            if st.button("🚀 Export Official Word Document"):
                out = export_final_quotation(cust, st.session_state.cart, {'period': '2026', 'year': '2026'})
                st.download_button("📥 Download Document", out, f"Quotation_{cust}.docx")
            if st.button("🗑️ Clear All"):
                st.session_state.cart = {}; st.rerun()
