import streamlit as st
import pandas as pd
import sqlite3
import os
import io
import plotly.express as px
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from arabic_reshaper import reshape
from bidi.algorithm import get_display

# --- إعدادات الصفحة ---
st.set_page_config(page_title="Preview Ads ERP", layout="wide")

def get_connection():
    return sqlite3.connect('billboards_data.db')

def ar(text):
    if not text: return ""
    return get_display(reshape(str(text)))

# --- دالة إضافة الخلفية العائمة للوورد (تتجاهل الهوامش) ---
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

# --- دالة تصدير الوورد ---
def export_final_quotation(customer_name, cart_data, dates):
    doc = Document()
    section = doc.sections[0]
    section.right_to_left = True
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
            table = doc.add_table(rows=1, cols=4); table.style = 'Table Grid'
            for i, txt in enumerate(["العدد", "الموقع", "العدد", "الموقع"]): table.cell(0, i).text = ar(txt)
            clean_df = df.iloc[:, :2].reset_index(drop=True)
            for i in range(len(clean_df)):
                row_idx, col_off = (i // 2) + 1, (0 if i % 2 == 0 else 2)
                table.cell(row_idx, col_off).text = str(clean_df.iloc[i, 1])
                table.cell(row_idx, col_off + 1).text = ar(clean_df.iloc[i, 0])
            doc.add_paragraph(ar(f"العدد: [{int(clean_df.iloc[:, 1].sum())}]")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
    target = io.BytesIO(); doc.save(target); target.seek(0)
    return target

# --- إدارة الحالة (Session State) ---
if 'cart' not in st.session_state: st.session_state.cart = {}

# --- القائمة الجانبية ---
st.sidebar.title("💎 PreView ERP System")
page = st.sidebar.radio("انتقل إلى:", ["🏠 لوحة التحكم والخريطة", "📄 بناء عرض سعر وعقد"])

conn = get_connection()

if page == "🏠 لوحة التحكم والخريطة":
    st.title("🏠 نظرة عامة على التوزع والإشغال")
    df_all = pd.read_sql("SELECT [اسم العمود], [المحافظة], [العدد], [الشبكة], [الحجم] FROM [اعمدة انارة]", conn)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("إجمالي المواقع", len(df_all))
    col2.metric("إجمالي المحافظات", df_all['المحافظة'].nunique())
    col3.metric("إجمالي الأعمدة", df_all['العدد'].sum())

    st.subheader("📍 التوزع حسب المحافظات")
    fig = px.pie(df_all, names='المحافظة', values='العدد', hole=0.3)
    st.plotly_chart(fig, use_container_width=True)
    
    st.subheader("🔎 بيانات المواقع التفصيلية")
    st.dataframe(df_all, use_container_width=True)

elif page == "📄 بناء عرض سعر وعقد":
    st.title("📄 صانع العروض والعقود الذكي")
    c1, c2 = st.columns(2)

    with c1:
        cust = st.text_input("اسم الزبون", "شركة ...")
        cities = pd.read_sql("SELECT المحافظة FROM المحافظات", conn)['المحافظة'].tolist()
        sel_city = st.selectbox("اختر المحافظة", cities)
        
        # استعلام لجلب الشبكات المتاحة (يمكن تفعيل فلتر التاريخ هنا)
        raw_df = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة = '{sel_city}'", conn)
        sel_nets = st.multiselect("اختر الشبكات:", raw_df['الشبكة'].unique().tolist())
        
        if st.button("➕ إضافة للعربة"):
            if sel_nets:
                st.session_state.cart[sel_city] = {n: raw_df[raw_df['الشبكة'] == n][['الموقع', 'العدد']] for n in sel_nets}
                st.success(f"تمت إضافة شبكات {sel_city}")

    with c2:
        if st.session_state.cart:
            for city_n, nets in st.session_state.cart.items():
                with st.expander(f"📍 {city_n}", expanded=True):
                    for net_n, df in nets.items():
                        st.write(f"🔗 {net_n}")
                        st.session_state.cart[city_n][net_n] = st.data_editor(df, key=f"ed_{city_n}_{net_n}", num_rows="dynamic")
            
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("🚀 تصدير ملف Word"):
                    dates = {'start': "2026/05/01", 'end': "2026/05/28"}
                    out = export_final_quotation(cust, st.session_state.cart, dates)
                    st.download_button("📥 تحميل العرض", out, f"Quotation_{cust}.docx")
            
            with col_b2: # تم تصحيح هذا السطر بإزالة :=
                if st.button("✅ تثبيت كعقد (حجز)"):
                    cursor = conn.cursor()
                    for city_name, networks in st.session_state.cart.items():
                        for net_name, df_final in networks.items():
                            for i in range(len(df_final)):
                                pole_n = df_final.iloc[i, 0]
                                p_id_row = cursor.execute(f"SELECT [رقم اللوحة] FROM [اعمدة انارة] WHERE [اسم العمود] = '{pole_n}'").fetchone()
                                if p_id_row:
                                    cursor.execute("INSERT INTO [حجوزات1] ([رقم اللوحة], [اسم الزبون]) VALUES (?, ?)", (p_id_row[0], cust))
                    conn.commit()
                    st.balloons()
                    st.success("تم تثبيت العقد وحجز المواقع!")

            
            if st.button("🗑️ تفريغ العربة"):
                st.session_state.cart = {}; st.rerun()
        else:
            st.info("العربة فارغة.")
