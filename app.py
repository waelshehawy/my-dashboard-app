import streamlit as st
import pandas as pd
import sqlite3
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from arabic_reshaper import reshape
from bidi.algorithm import get_display
import io

st.set_page_config(page_title="Preview Quotation Generator", layout="wide")

def get_connection():
    return sqlite3.connect('billboards_data.db')

def ar(text):
    if not text: return ""
    return get_display(reshape(str(text)))

# --- دالة التصدير المتطابقة مع النموذج الصوري ---
def export_preview_word(grouped_data, customer_name, city, size_name, date_info):
    doc = Document()
    for section in doc.sections:
        section.right_to_left = True
        section.top_margin = Inches(0.5)

    # 1. الشعار في الزاوية اليسرى العليا
    try:
        doc.add_picture('logo.png', width=Inches(1.8))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.LEFT
    except: pass

    # 2. التاريخ واسم الزبون
    p_date = doc.add_paragraph()
    p_date.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_date.add_run(ar(f"التاريخ: {date_info['current_date']}"))

    p_cust = doc.add_paragraph()
    p_cust.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_cust.add_run(ar(f"السادة شركة .. {customer_name} .....")).bold = True
    
    doc.add_paragraph(ar("تحية طيبة،")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
    doc.add_paragraph(ar(f"نقدم لكم المواقع المتاحة في المحافظات لعرض إعلانكم الوطني من تاريخ {date_info['start']} لغاية {date_info['end']}م")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # 3. بيانات المحافظة والقياس
    p_city = doc.add_paragraph()
    p_city.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run_city = p_city.add_run(ar(f"محافظة {city}"))
    run_city.font.color.rgb = RGBColor(102, 0, 153) # البنفسجي
    
    doc.add_paragraph(ar(f"لوحات قياس {size_name}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # 4. تكرار الجداول حسب الشبكة
    for network, df in grouped_data.items():
        doc.add_paragraph(ar(f"شبكات {network}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
        
        # إنشاء الجدول (4 أعمدة كما في الصورة لتقسيم العرض)
        table = doc.add_table(rows=1, cols=4)
        table.style = 'Table Grid'
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text, hdr_cells[1].text = ar("العدد"), ar("الموقع")
        hdr_cells[2].text, hdr_cells[3].text = ar("العدد"), ar("الموقع")
        
        # ملء البيانات (توزيع المواقع على عمودين مزدوجين)
        rows = df.values.tolist()
        for i in range(0, len(rows), 2):
            row_cells = table.add_row().cells
            row_cells[0].text = str(rows[i][1]) # العدد
            row_cells[1].text = ar(rows[i][0])   # الموقع
            if i + 1 < len(rows):
                row_cells[2].text = str(rows[i+1][1])
                row_cells[3].text = ar(rows[i+1][0])

        # تذييل الجدول المالي
        total = df['العدد'].astype(int).sum()
        f_p = doc.add_paragraph()
        f_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        f_p.add_run(ar(f"العدد: [{total}]  أجور الطباعة والتركيب للوحة الواحدة للوجه الواحد: [$ ]  أجور العرض للوحة الواحدة لشهر واحد: [$ ]"))

    # 5. الشروط النهائية
    doc.add_paragraph("\n")
    doc.add_paragraph(ar("- إذا تم اعتماد المدة شهرين يوجد حسم على سعر العرض")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
    last_p = doc.add_paragraph(ar("- هذه المواقع المتاحة سارية حتى 48 ساعة من تاريخ إرسالها للشركة"))
    last_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    last_p.runs[0].bold = True

    # 6. التذييل (معلومات الاتصال) - محاكاة بسيطة
    doc.add_paragraph("\n" + "_"*50)
    contact = doc.add_paragraph(ar("Syria - Aleppo - Damascus | Tel: +963 93 94 | info@previewsyria.com"))
    contact.alignment = WD_ALIGN_PARAGRAPH.CENTER

    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- واجهة المستخدم ---
st.title("🛠️ مولد عروض أسعار بريفيو الاحترافي")

conn = get_connection()
sizes = pd.read_sql("SELECT [الحجم] FROM [اساسي حجم]", conn)['الحجم'].tolist()
cities = pd.read_sql("SELECT المحافظة FROM المحافظات", conn)['المحافظة'].tolist()

with st.sidebar:
    st.header("بيانات العرض")
    cust = st.text_input("اسم الزبون")
    sel_city = st.selectbox("المحافظة", cities)
    sel_size = st.selectbox("القياس", sizes)
    date_s = st.text_input("تاريخ البدء", "1 /5 /2026")
    date_e = st.text_input("تاريخ الانتهاء", "28 /5 /2026")

# جلب البيانات
query = f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة = '{sel_city}' AND [الحجم] = '{sel_size}'"
raw_df = pd.read_sql(query, conn)

selected_locs = st.multiselect("اختر المواقع المختارة:", raw_df['الموقع'].tolist())

if selected_locs:
    filtered = raw_df[raw_df['الموقع'].isin(selected_locs)]
    networks = filtered['الشبكة'].unique()
    final_data = {}

    for net in networks:
        st.subheader(f"🔗 شبكة: {net}")
        net_df = filtered[filtered['الشبكة'] == net][['الموقع', 'العدد']]
        final_data[net] = st.data_editor(net_df, key=f"ed_{net}", num_rows="dynamic")

    if st.button("🚀 تصدير العرض النهائي (Word)"):
        dates = {'current_date': "2026/04/26", 'start': date_s, 'end': date_e}
        file = export_preview_word(final_data, cust, sel_city, sel_size, dates)
        st.download_button("📥 تحميل مستند العرض", file, f"Quotation_{cust}.docx")
