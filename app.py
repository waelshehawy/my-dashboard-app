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
st.set_page_config(page_title="PreView Ads ERP - Final", layout="wide")

def get_connection():
    return sqlite3.connect('billboards_data.db')

def ar(text):
    if not text: return ""
    return get_display(reshape(str(text)))

# --- دالة إضافة الصور العائمة (خلف النص / في الهوامش) ---
def add_float_picture(doc, image_path, width, height, pos_v="top"):
    header = doc.sections[0].header
    if not header.paragraphs: header.add_paragraph()
    run = header.paragraphs[0].add_run()
    shape = run.add_picture(image_path, width=width, height=height)
    inline = shape._inline
    extent = inline.extent
    doc_pr = inline.docPr
    
    # تحديد الموقع: أعلى الورقة للوجو أو أسفل الورقة للتذييل
    offset_v = 0 if pos_v == "top" else 9500000 # قيمة تقريبية لأسفل الصفحة A4
    
    anchor_xml = f"""
    <wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0" relativeHeight="0" behindDoc="1" locked="0" layoutInCell="1" allowOverlap="1" xmlns:wp="http://openxmlformats.org">
        <wp:simplePos x="0" y="0"/>
        <wp:positionH relativeFrom="page"><wp:posOffset>0</wp:posOffset></wp:positionH>
        <wp:positionV relativeFrom="page"><wp:posOffset>{offset_v}</wp:posOffset></wp:positionV>
        <wp:extent cx="{extent.cx}" cy="{extent.cy}"/><wp:wrapNone/><wp:docPr id="{doc_pr.id}" name="{doc_pr.name}"/>
    </wp:anchor>"""
    anchor = OxmlElement(anchor_xml)
    anchor.append(inline.graphic)
    inline.getparent().replace(inline, anchor)

# --- دالة تصدير الوورد ---
def export_final_quotation(customer_name, cart_data, dates):
    doc = Document()
    doc.sections[0].right_to_left = True
    
    # إضافة اللوجو والتذييل كصور عائمة
    if os.path.exists('logo.png'):
        add_float_picture(doc, 'logo.png', width=Inches(8.27), height=Inches(11.69), pos_v="top")
    if os.path.exists('footer.png'):
        add_float_picture(doc, 'footer.png', width=Inches(8.27), height=Inches(1.5), pos_v="bottom")

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
            
            # جدول مزدوج 4 أعمدة
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
            
            # حساب المجاميع والأسعار
            total_sum = pd.to_numeric(df['العدد']).sum()
            print_val = df['أجور الطباعة'].iloc[0] if 'أجور الطباعة' in df.columns else "0"
            ads_val = df['أجور العرض'].iloc[0] if 'أجور العرض' in df.columns else "0"
            
            footer_text = doc.add_paragraph()
            footer_text.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            footer_text.add_run(ar(f"العدد: [{int(total_sum)}] | أجور الطباعة: ${print_val} | أجور العرض: ${ads_val}"))

    target = io.BytesIO(); doc.save(target); target.seek(0)
    return target

# --- واجهة التطبيق ---
if 'cart' not in st.session_state: st.session_state.cart = {}
st.sidebar.title("💎 PreView Ads ERP")
page = st.sidebar.radio("التنقل:", ["🏠 لوحة التحكم", "📄 صانع العروض"])

conn = get_connection()

if page == "🏠 لوحة التحكم":
    st.title("📊 إحصائيات المواقع")
    df_all = pd.read_sql("SELECT [اسم العمود], [المحافظة], [العدد], [الشبكة] FROM [اعمدة انارة]", conn)
    st.plotly_chart(px.pie(df_all, names='المحافظة', values='العدد', hole=0.3), use_container_width=True)
    st.dataframe(df_all, use_container_width=True)

elif page == "📄 صانع العروض":
    st.title("📄 بناء عرض السعر الذكي")
    col_in, col_view = st.columns(2)
    
    with col_in:
        cust = st.text_input("اسم الزبون")
        cities = pd.read_sql("SELECT المحافظة FROM المحافظات", conn)['المحافظة'].tolist()
        sel_city = st.selectbox("المحافظة", cities)
        raw_df = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة = '{sel_city}'", conn)
        sel_nets = st.multiselect("اختر الشبكات:", raw_df['الشبكة'].unique().tolist())
        
        if st.button("➕ إضافة للسلة"):
            if sel_nets:
                st.session_state.cart[sel_city] = {}
                for n in sel_nets:
                    temp_df = raw_df[raw_df['الشبكة'] == n][['الموقع', 'العدد']].copy()
                    temp_df['أجور الطباعة'] = 0
                    temp_df['أجور العرض'] = 0
                    st.session_state.cart[sel_city][n] = temp_df
                st.success("تمت الإضافة")

    with col_view:
        if st.session_state.cart:
            for cn, nets in st.session_state.cart.items():
                for nn, df in nets.items():
                    with st.expander(f"📍 {cn} - شبكة {nn}", expanded=True):
                        st.session_state.cart[cn][nn] = st.data_editor(df, key=f"ed_{cn}_{nn}")
            
            if st.button("🚀 تصدير الوورد النهائي"):
                out = export_final_quotation(cust, st.session_state.cart, {'period': '2026', 'year': '2026'})
                st.download_button("📥 تحميل المستند", out, f"Preview_{cust}.docx")
            if st.button("🗑️ تفريغ السلة"):
                st.session_state.cart = {}; st.rerun()
