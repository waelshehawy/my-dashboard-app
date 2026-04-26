import streamlit as st
import pandas as pd
import sqlite3
import os
import io
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from arabic_reshaper import reshape
from bidi.algorithm import get_display

# --- إعدادات الصفحة ---
st.set_page_config(page_title="Preview Ads System", layout="wide")

# --- دالة معالجة النصوص العربية ---
def ar(text):
    if not text: return ""
    return get_display(reshape(str(text)))

# --- دالة تصدير الوورد الاحترافية (خلفية شفافة + جداول مجمعة) ---
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

def add_float_picture(doc, image_path, width, height):
    """تضيف صورة عائمة تتجاهل الهوامش (Behind text)"""
    header = doc.sections[0].header
    paragraph = header.paragraphs[0]
    run = paragraph.add_run()
    shape = run.add_picture(image_path, width=width, height=height)
    
    # تحويل الصورة إلى عنصر عائم (Floating) عبر تعديل الـ XML
    inline = shape._inline
    extent = inline.extent
    doc_pr = inline.docPr
    
    # إنشاء هيكل الـ XML للتموضع العائم
    anchor_xml = f"""
    <wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0" relativeHeight="0" behindDoc="1" locked="0" layoutInCell="1" allowOverlap="1" xmlns:wp="http://openxmlformats.org">
        <wp:simplePos x="0" y="0"/>
        <wp:positionH relativeFrom="page">
            <wp:posOffset>0</wp:posOffset>
        </wp:positionH>
        <wp:positionV relativeFrom="page">
            <wp:posOffset>0</wp:posOffset>
        </wp:positionV>
        <wp:extent cx="{extent.cx}" cy="{extent.cy}"/>
        <wp:effectExtent l="0" t="0" r="0" b="0"/>
        <wp:wrapNone/>
        <wp:docPr id="{doc_pr.id}" name="{doc_pr.name}"/>
        <wp:cNvGraphicFramePr>
            <a:graphicFrameLocks noChangeAspect="1" xmlns:a="http://openxmlformats.org"/>
        </wp:cNvGraphicFramePr>
    </wp:anchor>
    """
    anchor = OxmlElement(anchor_xml)
    # نقل بيانات الصورة الأصلية إلى العنصر العائم الجديد
    anchor.append(inline.graphic)
    inline.getparent().replace(inline, anchor)

def export_final_quotation(customer_name, all_selected_data, dates):
    doc = Document()
    section = doc.sections[0]
    section.page_height = Inches(11.69) # A4 Height
    section.page_width = Inches(8.27)   # A4 Width
    
    # 1. إضافة الصورة كخلفية كاملة تتجاهل الهوامش
    if os.path.exists('logo.png'):
        # العرض والارتفاع يغطيان الورقة كاملة (A4)
        add_float_picture(doc, 'logo.png', width=Inches(8.27), height=Inches(11.69))

    # 2. جسم المستند (النص سيظهر الآن فوق الخلفية)
    # ملاحظة: سنترك مسافة علوية (Margin) للنص يدوياً عبر فقرات فارغة
    for i in range(4): doc.add_paragraph() 
    
    p_cust = doc.add_paragraph()
    p_cust.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_cust.add_run(ar(f"السادة شركة .. {customer_name} المحترمين")).bold = True
    
    # (بقية كود الجول تظل كما هي في النسخة السابقة)
    # ...
حجم يغطي الصفحة

    # 2. بيانات الزبون
    doc.add_paragraph("\n\n") 
    p_cust = doc.add_paragraph()
    p_cust.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_cust.add_run(ar(f"السادة شركة .. {customer_name} المحترمين")).bold = True
    doc.add_paragraph(ar(f"نقدم لكم المواقع المتاحة للفترة من {dates['start']} لغاية {dates['end']}م")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # 3. بناء المحتوى لكل محافظة تم اختيارها
    for city, networks in all_selected_data.items():
        p_city = doc.add_paragraph()
        p_city.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run_city = p_city.add_run(ar(f"محافظة {city}"))
        run_city.font.color.rgb = RGBColor(102, 0, 153)
        run_city.font.size = Pt(16)

        for net, df in networks.items():
            doc.add_paragraph(ar(f"شبكات {net}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
            
            # جدول 4 أعمدة (مزدوج) كما في النموذج
            table = doc.add_table(rows=1, cols=4)
            table.style = 'Table Grid'
            hdr = table.rows[0].cells
            hdr[0].text, hdr[1].text = ar("العدد"), ar("الموقع")
            hdr[2].text, hdr[3].text = ar("العدد"), ar("الموقع")

            data_list = df.values.tolist()
            for i in range(0, len(data_list), 2):
                row = table.add_row().cells
                row[0].text = str(data_list[i][1]) # العدد
                row[1].text = ar(data_list[i][0])  # الموقع
                if i + 1 < len(data_list):
                    row[2].text = str(data_list[i+1][1])
                    row[3].text = ar(data_list[i+1][0])
            
            total = df['العدد'].astype(int).sum()
            doc.add_paragraph(ar(f"العدد: [{total}] | أجور الطباعة: $ | أجور العرض: $")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- إدارة الذاكرة (للاحتفاظ بالاختيارات عند تغيير المحافظة) ---
if 'cart' not in st.session_state:
    st.session_state.cart = {} # {City: {Network: DataFrame}}

# --- واجهة التطبيق ---
st.title("🏗️ صانع عروض أسعار بريفيو (متعدد المحافظات)")

try:
    conn = sqlite3.connect('billboards_data.db')
    
    col_input, col_cart = st.columns([1, 2])

    with col_input:
        st.subheader("📍 اختيار المواقع")
        cust = st.text_input("اسم الزبون", "شركة ...")
        cities = pd.read_sql("SELECT المحافظة FROM المحافظات", conn)['المحافظة'].tolist()
        sel_city = st.selectbox("اختر المحافظة", cities)
        
        # جلب البيانات
        raw_df = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة = '{sel_city}'", conn)
        selected_locs = st.multiselect(f"مواقع {sel_city}:", raw_df['الموقع'].tolist())
        
        if st.button("➕ إضافة هذه المواقع للعرض"):
            if selected_locs:
                filtered = raw_df[raw_df['الموقع'].isin(selected_locs)]
                city_data = {}
                for net in filtered['الشبكة'].unique():
                    city_data[net] = filtered[filtered['الشبكة'] == net][['الموقع', 'العدد']]
                st.session_state.cart[sel_city] = city_data
                st.success(f"تمت إضافة مواقع {sel_city} للقائمة")

    with col_cart:
        st.subheader("🛒 المواقع المختارة حالياً")
        if st.session_state.cart:
            for c_name, networks in st.session_state.cart.items():
                with st.expander(f"📌 محافظة {c_name}", expanded=True):
                    for n_name, d_frame in networks.items():
                        st.write(f"🔗 شبكة {n_name}")
                        st.session_state.cart[c_name][n_name] = st.data_editor(d_frame, key=f"edit_{c_name}_{n_name}")
            
            if st.button("🗑️ مسح كل الاختيارات"):
                st.session_state.cart = {}
                st.rerun()

            st.divider()
            if st.button("🚀 تصدير العرض النهائي الشامل (Word)"):
                dates = {'start': "1 /5 /2026", 'end': "28 /5 /2026"}
                final_file = export_final_quotation(cust, st.session_state.cart, dates)
                st.download_button("📥 تحميل المستند الآن", final_file, f"Preview_Quotation_{cust}.docx")
        else:
            st.info("القائمة فارغة، اختر محافظة ومواقع ثم اضغط 'إضافة'.")

except Exception as e:
    st.error(f"خطأ: {e}")
