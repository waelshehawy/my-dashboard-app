import streamlit as st
import pandas as pd
import sqlite3
import os
import io
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from arabic_reshaper import reshape
from bidi.algorithm import get_display

st.set_page_config(page_title="Preview Ads System", layout="wide")

def ar(text):
    if not text: return ""
    return get_display(reshape(str(text)))

def add_float_picture(doc, image_path, width, height):
    header = doc.sections[0].header
    if not header.paragraphs: header.add_paragraph()
    run = header.paragraphs[0].add_run()
    shape = run.add_picture(image_path, width=width, height=height)
    inline = shape._inline
    extent = inline.extent
    doc_pr = inline.docPr
    anchor_xml = f"""
    <wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0" relativeHeight="0" behindDoc="1" locked="0" layoutInCell="1" allowOverlap="1" xmlns:wp="http://openxmlformats.org">
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

def export_final_quotation(customer_name, all_selected_data, dates):
    doc = Document()
    doc.sections[0].right_to_left = True
    
    if os.path.exists('logo.png'):
        add_float_picture(doc, 'logo.png', width=Inches(8.27), height=Inches(11.69))

    for _ in range(5): doc.add_paragraph() 
    
    p_cust = doc.add_paragraph()
    p_cust.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_cust.add_run(ar(f"السادة شركة .. {customer_name} المحترمين")).bold = True
    doc.add_paragraph(ar(f"نقدم لكم المواقع المتاحة من {dates['start']} لغاية {dates['end']} م")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

    for city_name in all_selected_data:
        networks_dict = all_selected_data[city_name]
        
        p_city = doc.add_paragraph()
        p_city.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run_city = p_city.add_run(ar(f"محافظة {city_name}"))
        run_city.font.color.rgb = RGBColor(102, 0, 153)
        run_city.font.size = Pt(16)

        for net_name in networks_dict:
            df = networks_dict[net_name]
            doc.add_paragraph(ar(f"شبكات {net_name}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
            
            # Use only Location and Count columns
            work_df = df[['الموقع', 'العدد']].reset_index(drop=True)
            total_items = len(work_df)
            rows_needed = (total_items + 1) // 2
            
            table = doc.add_table(rows=rows_needed + 1, cols=4)
            table.style = 'Table Grid'
            
            # Set Headers
            table.cell(0, 0).text = ar("العدد")
            table.cell(0, 1).text = ar("الموقع")
            table.cell(0, 2).text = ar("العدد")
            table.cell(0, 3).text = ar("الموقع")

            # Fill using direct index lookup
            for i in range(total_items):
                r_idx = (i // 2) + 1
                c_off = 0 if (i % 2 == 0) else 2
                
                # Direct access by position - NO UNPACKING
                loc_val = work_df.iloc[i, 0] # Column 0: Location
                cnt_val = work_df.iloc[i, 1] # Column 1: Count
                
                table.cell(r_idx, c_off).text = str(cnt_val)
                table.cell(r_idx, c_off + 1).text = ar(loc_val)
            
            total_sum = work_df['العدد'].astype(int).sum()
            doc.add_paragraph(ar(f"العدد: [{total_sum}] | أجور الطباعة: $ | أجور العرض: $")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

if 'cart' not in st.session_state: st.session_state.cart = {}

st.title("🏗️ Preview Quotation Builder")

try:
    conn = sqlite3.connect('billboards_data.db')
    c1, c2 = st.columns(2)

    with c1:
        cust = st.text_input("Customer", "Wael")
        cities = pd.read_sql("SELECT المحافظة FROM المحافظات", conn)['المحافظة'].tolist()
        city_sel = st.selectbox("City", cities)
        raw = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة = '{city_sel}'", conn)
        locs = st.multiselect(f"Locations in {city_sel}", raw['الموقع'].tolist())
        
        if st.button("➕ Add"):
            if locs:
                filt = raw[raw['الموقع'].isin(locs)]
                st.session_state.cart[city_sel] = {n: filt[filt['الشبكة'] == n][['الموقع', 'العدد']] for n in filt['الشبكة'].unique()}
                st.success("Added!")

    with c2:
        if st.session_state.cart:
            for c_name in list(st.session_state.cart.keys()):
                with st.expander(f"📍 {c_name}", expanded=True):
                    for n_name in list(st.session_state.cart[c_name].keys()):
                        st.write(f"🔗 {n_name}")
                        st.session_state.cart[c_name][n_name] = st.data_editor(st.session_state.cart[c_name][n_name], key=f"ed_{c_name}_{n_name}")
            
            if st.button("🗑️ Clear"):
                st.session_state.cart = {}; st.rerun()

            if st.button("🚀 Export"):
                dts = {'start': "1 / 5 / 2026", 'end': "28 / 5 / 2026"}
                out = export_final_quotation(cust, st.session_state.cart, dts)
                st.download_button("📥 Download", out, f"Preview_{cust}.docx")
except Exception as e:
    st.error(f"Error: {e}")
