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

# --- إعدادات الصفحة ---
st.set_page_config(page_title="Preview Ads System", layout="wide")

def ar(text):
    if not text: return ""
    return get_display(reshape(str(text)))

def add_float_picture(doc, image_path, width, height):
    header = doc.sections.header
    if not header.paragraphs: header.add_paragraph()
    run = header.paragraphs.add_run()
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

# --- دالة التصدير باستخدام الإحداثيات (أكثر أماناً) ---
def export_final_quotation(customer_name, all_selected_data, dates):
    doc = Document()
    section = doc.sections
    section.right_to_left = True
    
    if os.path.exists('logo.png'):
        add_float_picture(doc, 'logo.png', width=Inches(8.27), height=Inches(11.69))

    for _ in range(5): doc.add_paragraph() 
    
    p_cust = doc.add_paragraph()
    p_cust.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_cust.add_run(ar(f"السادة شركة .. {customer_name} المحترمين")).bold = True
    doc.add_paragraph(ar(f"نقدم لكم المواقع المتاحة للفترة من {dates['start']} لغاية {dates['end']}م")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

    for city, networks in all_selected_data.items():
        p_city = doc.add_paragraph()
        p_city.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run_city = p_city.add_run(ar(f"محافظة {city}"))
        run_city.font.color.rgb = RGBColor(102, 0, 153)
        run_city.font.size = Pt(16)

        for net, df in networks.items():
            doc.add_paragraph(ar(f"شبكات {net}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
            
            # تنظيف البيانات لضمان وجود عمودين فقط (الموقع والعدد)
            current_df = df[['الموقع', 'العدد']].reset_index(drop=True)
            num_rows = (len(current_df) + 1) // 2
            
            # إنشاء الجدول (عدد الصفوف + 1 للرأس، و 4 أعمدة)
            table = doc.add_table(rows=num_rows + 1, cols=4)
            table.style = 'Table Grid'
            
            # 1. تعبئة الرأس يدوياً بالكامل
            table.cell(0, 0).text = ar("العدد")
            table.cell(0, 1).text = ar("الموقع")
            table.cell(0, 2).text = ar("العدد")
            table.cell(0, 3).text = ar("الموقع")

            # 2. تعبئة البيانات باستخدام الإحداثيات (صف، عمود)
            for i in range(len(current_df)):
                row_idx = (i // 2) + 1 # تحديد أي صف في الوورد
                col_offset = 0 if (i % 2 == 0) else 2 # تحديد البدء من العمود 0 أو 2
                
                # تعبئة الخلية (العدد)
                table.cell(row_idx, col_offset).text = str(current_df.iloc[i]['العدد'])
                # تعبئة الخلية (الموقع)
                table.cell(row_idx, col_offset + 1).text = ar(current_df.iloc[i]['الموقع'])
            
            total = current_df['العدد'].astype(int).sum()
            doc.add_paragraph(ar(f"العدد: [{total}] | أجور الطباعة: $ | أجور العرض: $")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- واجهة التطبيق ---
if 'cart' not in st.session_state: st.session_state.cart = {}

st.title("🏗️ Preview Quotation System")

try:
    conn = sqlite3.connect('billboards_data.db')
    col_in, col_view = st.columns()

    with col_in:
        cust = st.text_input("اسم الزبون", "وائل")
        cities = pd.read_sql("SELECT المحافظة FROM المحافظات", conn)['المحافظة'].tolist()
        sel_city = st.selectbox("اختر المحافظة", cities)
        raw_df = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة = '{sel_city}'", conn)
        selected_locs = st.multiselect(f"مواقع {sel_city}:", raw_df['الموقع'].tolist())
        
        if st.button("➕ إضافة للعرض"):
            if selected_locs:
                filtered = raw_df[raw_df['الموقع'].isin(selected_locs)]
                st.session_state.cart[sel_city] = {net: filtered[filtered['الشبكة'] == net][['الموقع', 'العدد']] for net in filtered['الشبكة'].unique()}
                st.success(f"تمت إضافة {sel_city}")

    with col_view:
        if st.session_state.cart:
            for c_name, networks in st.session_state.cart.items():
                with st.expander(f"📍 {c_name}", expanded=True):
                    for n_name, d_frame in networks.items():
                        st.write(f"🔗 شبكة {n_name}")
                        # حفظ التعديلات في الذاكرة
                        st.session_state.cart[c_name][n_name] = st.data_editor(d_frame, key=f"ed_{c_name}_{n_name}")
            
            if st.button("🗑️ مسح الكل"):
                st.session_state.cart = {}; st.rerun()

            if st.button("🚀 تصدير الوورد"):
                dates = {'start': "1 /5 /2026", 'end': "28 /5 /2026"}
                file_out = export_final_quotation(cust, st.session_state.cart, dates)
                st.download_button("📥 تحميل الملف", file_out, f"Preview_{cust}.docx")
        else:
            st.info("القائمة فارغة.")
except Exception as e:
    st.error(f"خطأ: {e}")
