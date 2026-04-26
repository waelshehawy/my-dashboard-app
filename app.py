import streamlit as st
import pandas as pd
import sqlite3
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from arabic_reshaper import reshape
from bidi.algorithm import get_display
import io
import os

def ar(text):
    if not text: return ""
    return get_display(reshape(str(text)))

def export_final_preview(grouped_data, customer_name, city, size_name, dates):
    doc = Document()
    
    # إعدادات الصفحة واللغة العربية
    for section in doc.sections:
        section.right_to_left = True
        section.left_margin = Inches(0.5)
        section.right_margin = Inches(0.5)

    # 1. إضافة اللوجو في الزاوية اليسرى (كما في الصورة)
    header_para = doc.add_paragraph()
    header_para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    if os.path.exists('logo.png'):
        run_logo = header_para.add_run()
        run_logo.add_picture('logo.png', width=Inches(2.0))
    else:
        header_para.add_run("PreView Logo (logo.png missing)")

    # 2. التاريخ واسم الزبون
    doc.add_paragraph(f"{ar('التاريخ:')} {dates['current']}").alignment = WD_ALIGN_PARAGRAPH.RIGHT
    
    p_cust = doc.add_paragraph()
    p_cust.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_cust.add_run(ar(f"السادة شركة .. {customer_name} .....")).bold = True
    
    doc.add_paragraph(ar("تحية طيبة،")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
    doc.add_paragraph(ar(f"نقدم لكم المواقع المتاحة في المحافظات لعرض إعلانكم الوطني من تاريخ {dates['start']} لغاية {dates['end']}م")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # 3. بيانات المحافظة والقياس
    p_city = doc.add_paragraph()
    p_city.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run_city = p_city.add_run(ar(f"محافظة {city}"))
    run_city.font.color.rgb = RGBColor(102, 0, 153) # البنفسجي
    run_city.font.size = Pt(16)
    
    doc.add_paragraph(ar(f"لوحات قياس {size_name}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # 4. الجداول المزدوجة (تنسيق احترافي)
    for network, df in grouped_data.items():
        doc.add_paragraph(ar(f"شبكات {network}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
        
        # إنشاء جدول بـ 4 أعمدة كما في الصورة
        table = doc.add_table(rows=1, cols=4)
        table.style = 'Table Grid'
        
        # تنسيق الرأس بلون رمادي
        hdr_cells = table.rows[0].cells
        columns_labels = [ar("العدد"), ar("الموقع"), ar("العدد"), ar("الموقع")]
        for i, label in enumerate(columns_labels):
            hdr_cells[i].text = label
            hdr_cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

        # توزيع البيانات على عمودين
        data_rows = df.values.tolist()
        for i in range(0, len(data_rows), 2):
            row_cells = table.add_row().cells
            # العمود الأول والثاني
            row_cells[0].text = str(data_rows[i][1]) # العدد
            row_cells[1].text = ar(data_rows[i][0])  # الموقع
            # العمود الثالث والرابع (إذا وجد سجل ثاني)
            if i + 1 < len(data_rows):
                row_cells[2].text = str(data_rows[i+1][1])
                row_cells[3].text = ar(data_rows[i+1][0])
            
            for cell in row_cells:
                cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

        # سطر المجاميع والأسعار أسفل كل جدول
        total_n = df['العدد'].astype(int).sum()
        f_p = doc.add_paragraph()
        f_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        f_p.add_run(ar(f"العدد: [{total_n}]   أجور الطباعة والتركيب للوجه الواحد: [$ ]   أجور العرض لشهر واحد: [$ ]")).font.size = Pt(10)

    # 5. الشروط النهائية
    doc.add_paragraph("\n")
    doc.add_paragraph(ar("- إذا تم اعتماد المدة شهرين يوجد حسم على سعر العرض")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
    st_p = doc.add_paragraph(ar("- هذه المواقع المتاحة سارية حتى 48 ساعة من تاريخ إرسالها للشركة"))
    st_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    st_p.runs[0].bold = True

    # 6. التذييل (Footer) - صورة الاتصال في الأسفل
    # ملاحظة: يمكنك إضافة صورة التذييل إذا كانت متوفرة لديك
    
    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# (بقية واجهة Streamlit تظل كما هي في الكود السابق)
