import streamlit as st
import pandas as pd
import sqlite3
import os
import io
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from arabic_reshaper import reshape
from bidi.algorithm import get_display

# --- Page Config ---
st.set_page_config(page_title="PreView Ads ERP v2.0", layout="wide")

# --- Helper Functions ---
def get_connection():
    return sqlite3.connect('billboards_data.db')

def ar(text):
    """Reshapes Arabic text for Word/Matplotlib display"""
    if not text or pd.isna(text): return ""
    return get_display(reshape(str(text)))

# --- Security Logic ---
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.title("🔒 PreView Ads ERP Login")
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        if st.button("Login"):
            if user == "a" and pwd == "3900":
                st.session_state.authenticated = True
                st.rerun()
            else: st.error("❌ Invalid Credentials")
        return False
    return True

# --- Word Export Logic ---
def export_word(customer_name, cart_data):
    doc = Document()
    doc.sections[0].right_to_left = True
    
       # --- Header Logo Replacement ---
    if os.path.exists('logo.png'):
        section = doc.sections[0]
        header = section.header
        # Access the first paragraph or create one if header is empty
        if not header.paragraphs:
            p = header.add_paragraph()
        else:
            p = header.paragraphs[0]
            
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run()
        run.add_picture('logo.png', width=Inches(6))

    
    doc.add_paragraph("\n")
    p_cust = doc.add_paragraph()
    p_cust.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_cust.add_run(ar(f"السادة شركة: {customer_name} المحترمين")).bold = True

    for city, networks in cart_data.items():
        # Governorate Header
        p_city = doc.add_paragraph()
        p_city.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run_city = p_city.add_run(ar(f"محافظة {city}"))
        run_city.font.color.rgb = RGBColor(102, 0, 153)
        run_city.font.size = Pt(18)
        run_city.bold = True
        
        for net, df in networks.items():
            doc.add_paragraph(ar(f"شبكة: {net}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
            
            # Create Table (4 Columns for space saving)
            table = doc.add_table(rows=1, cols=4)
            table.style = 'Table Grid'
            hdr = table.rows[0].cells
            for idx, title in enumerate(["العدد", "الموقع", "العدد", "الموقع"]):
                hdr[idx].text = ar(title)
            
            # Fill Data (Pairing locations in one row)
            data_list = df[['الموقع', 'العدد']].values.tolist()
            for i in range(0, len(data_list), 2):
                row = table.add_row().cells
                row[1].text = ar(data_list[i][0])
                row[0].text = str(data_list[i][1])
                if i + 1 < len(data_list):
                    row[3].text = ar(data_list[i+1][0])
                    row[2].text = str(data_list[i+1][1])
            
            # Pricing Info
            total_n = pd.to_numeric(df['العدد']).sum()
            total_price = df['أجور العرض'].sum() + df['أجور الطباعة'].sum()
            f_p = doc.add_paragraph()
            f_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            f_p.add_run(ar(f"إجمالي العدد: {int(total_n)} | الإجمالي الصافي: {grand_total:,} $")).bold = True
            doc.add_paragraph("_" * 50).alignment = WD_ALIGN_PARAGRAPH.CENTER

    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- Main App ---
if check_password():
    conn = get_connection()
    if 'cart' not in st.session_state: st.session_state.cart = {}

    st.sidebar.image("logo.png", width=150) if os.path.exists("logo.png") else None
    page = st.sidebar.radio("Navigation:", ["🏠 Dashboard & Map", "📄 Quotation Builder"])

    if page == "🏠 Dashboard & Map":
        st.title("📊 Real-time Inventory & Mapping")
        
        # Load Data
        df_all = pd.read_sql("SELECT * FROM [اعمدة انارة]", conn)
        df_booked = pd.read_sql("SELECT DISTINCT [رقم اللوحة] FROM [حجوزات1]", conn)
        booked_ids = df_booked['رقم اللوحة'].tolist()

        # KPIs
        total_locs = len(df_all)
        booked_count = len(booked_ids)
        available_count = total_locs - booked_count
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Billboards", total_locs)
        c2.metric("Available", available_count, delta_color="normal")
        c3.metric("Booked", booked_count, delta="-"+str(booked_count))

        # Dynamic Folium Map with Clustering
        m = folium.Map(location=[33.513, 36.276], zoom_start=12)
        marker_cluster = MarkerCluster().add_to(m)

        for _, row in df_all.iterrows():
            if pd.notnull(row['Latitude']) and pd.notnull(row['Longitude']):
                status_color = 'red' if row['رقم اللوحة'] in booked_ids else 'purple'
                icon_type = 'info-sign'
                
                popup_html = f"""
                <div style='direction: rtl; text-align: right; min-width: 150px;'>
                    <h4 style='margin:0;'>{row['اسم العمود']}</h4>
                    <b>الشبكة:</b> {row['الشبكة']}<br>
                    <b>العدد:</b> {row['العدد']}<br>
                    <b>الحالة:</b> {'🔴 محجوز' if status_color=='red' else '🟢 متاح'}
                </div>
                """
                folium.Marker(
                    location=[row['Latitude'], row['Longitude']],
                    popup=folium.Popup(popup_html, max_width=300),
                    icon=folium.Icon(color=status_color, icon=icon_type)
                ).add_to(marker_cluster)

        st_folium(m, width="100%", height=500)

        # Detailed Data Tables
        tab1, tab2 = st.tabs(["✅ Available Billboards", "🚫 Booked Billboards"])
        with tab1:
            st.dataframe(df_all[~df_all['رقم اللوحة'].isin(booked_ids)], use_container_width=True)
        with tab2:
            df_bk_merged = pd.merge(df_all[df_all['رقم اللوحة'].isin(booked_ids)], 
                                    pd.read_sql("SELECT * FROM [حجوزات1]", conn), 
                                    on='رقم اللوحة', how='left')
            st.dataframe(df_bk_merged, use_container_width=True)

    elif page == "📄 Quotation Builder":
        st.title("📑 Generate Sales Quotation")
        
        col1, col2 = st.columns([1, 2])
        with col1:
            cust_name = st.text_input("Customer Name")
            cities = pd.read_sql("SELECT DISTINCT المحافظة FROM [اعمدة انارة]", conn)['المحافظة'].tolist()
            selected_city = st.selectbox("Governorate", cities)
            
            # Fetch networks for selected city
            city_data = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة='{selected_city}'", conn)
            selected_nets = st.multiselect("Select Networks", city_data['الشبكة'].unique().tolist())
            
            if st.button("➕ Add to Cart"):
                if selected_city not in st.session_state.cart:
                    st.session_state.cart[selected_city] = {}
                for net in selected_nets:
                    net_df = city_data[city_data['الشبكة'] == net].copy()
                    net_df['أجور الطباعة'] = 0
                    net_df['أجور العرض'] = 0
                    st.session_state.cart[selected_city][net] = net_df
                st.success(f"Added {len(selected_nets)} networks from {selected_city}")

        with col2:
            if st.session_state.cart:
                st.subheader("🛒 Cart Review")
                for city, networks in list(st.session_state.cart.items()):
                    for net, df in networks.items():
                        with st.expander(f"📍 {city} - Network {net}"):
                            # Inline editor for prices
                            edited_df = st.data_editor(df, key=f"edit_{city}_{net}", use_container_width=True)
                            st.session_state.cart[city][net] = edited_df
                            if st.button(f"🗑️ Remove {net}", key=f"del_{city}_{net}"):
                                del st.session_state.cart[city][net]
                                if not st.session_state.cart[city]: del st.session_state.cart[city]
                                st.rerun()

                if st.button("🚀 Export to Word"):
                    if cust_name:
                        word_file = export_word(cust_name, st.session_state.cart)
                        st.download_button("📥 Download Document", word_file, f"Quotation_{cust_name}.docx")
                    else:
                        st.warning("Please enter customer name first!")
                
                if st.button("🧹 Clear All"):
                    st.session_state.cart = {}
                    st.rerun()

    conn.close()
