import streamlit as st
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from arabic_reshaper import reshape
from bidi.algorithm import get_display
import io

# دالة لتنسيق النصوص العربية للورد
def ar(text):
    return get_display(reshape(str(text)))

def create_word_quotation(data):
    doc = Document()
    
    # إعداد اتجاه الصفحة للعربي
    section = doc.sections[0]
    section.right_to_left = True

    # 1. إضافة اللوجو (تأكد من وجود ملف logo.png)
    try:
        doc.add_picture('logo.png', width=Inches(1.5))
        last_paragraph = doc.paragraphs[-1]
        last_paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    except:
        st.warning("لم يتم العثور على ملف logo.png")

    # 2. الترويسة والعنوان بالألوان (بنفسجي مثلاً)
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run(ar("عرض سعر إعلاني - شركة بريفيو"))
    run.font.size = Pt(24)
    run.font.bold = True
    run.font.color.rgb = RGBColor(102, 0, 153) # لون بنفسجي

    # 3. بيانات العميل
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = p.add_run(ar(f"السادة: {data['customer']} المحترمين"))
    run.font.size = Pt(14)
    p.add_run(f"\n{ar('التاريخ:')} {data['year']}")

    # 4. الجدول بتنسيق ملون
    table = doc.add_table(rows=1, cols=3)
    table.style = 'Table Grid'
    
    # تلوين رأس الجدول
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = ar("القيمة")
    hdr_cells[1].text = ar("الموقع")
    hdr_cells[2].text = ar("العدد")
    
    for cell in hdr_cells:
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        # تعبئة خلفية الخلية (تحتاج كود متقدم أو استخدام ستايل جاهز)

    # إضافة البيانات
    row_cells = table.add_row().cells
    row_cells[0].text = str(data['fees'])
    row_cells[1].text = ar(data['pole_name'])
    row_cells[2].text = "1"

    # 5. التذييل
    doc.add_paragraph("\n")
    footer = doc.add_paragraph(ar("شكراً لتعاملكم معنا - فريق بريفيو"))
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # حفظ الملف في ذاكرة مؤقتة
    file_stream = io.BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)
    return file_stream

# في واجهة Streamlit (داخل زر الحفظ)
if st.button("تصدير عرض السعر Word"):
    # (نفس بيانات الحجز السابقة)
    data = {
        'customer': customer, 'city': city, 'period': period,
        'year': year, 'fees': fees, 'pole_name': selected_pole
    }
    word_file = create_word_quotation(data)
    st.download_button(
        label="📥 تحميل ملف Word",
        data=word_file,
        file_name=f"Quotation_{customer}.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
