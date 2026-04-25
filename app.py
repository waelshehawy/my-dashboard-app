from fpdf import FPDF
from arabic_reshaper import reshape
from bidi.algorithm import get_display

# دالة لتنسيق النصوص العربية للـ PDF
def ar(text):
    return get_display(reshape(str(text)))

def create_pdf(customer_name, province, date_from, date_to, locations_df):
    pdf = FPDF()
    pdf.add_page()
    # يجب رفع ملف خط عربي (مثل Amiri-Regular.ttf) إلى GitHub بجانب الكود
    pdf.add_font('Arabic', '', 'Amiri-Regular.ttf') 
    pdf.set_font('Arabic', size=14)
    
    # الترويسة
    pdf.cell(0, 10, ar("شركة بريفيو PreView"), ln=True, align='R')
    pdf.cell(0, 10, ar(f"التاريخ: {date_from}"), ln=True, align='R')
    pdf.ln(10)
    
    # نص العرض
    pdf.cell(0, 10, ar(f"السادة {customer_name} المحترمين"), ln=True, align='R')
    pdf.multi_cell(0, 10, ar(f"نقدم لكم عرض سعر على المواقع المتاحة في محافظة {province} من {date_from} لغاية {date_to}"), align='R')
    
    # الجدول
    pdf.set_fill_color(200, 200, 200)
    pdf.cell(40, 10, ar("العدد"), border=1, align='C', fill=True)
    pdf.cell(100, 10, ar("الموقع"), border=1, align='C', fill=True)
    pdf.ln()
    
    total_count = 0
    for index, row in locations_df.iterrows():
        pdf.cell(40, 10, str(row['العدد']), border=1, align='C')
        pdf.cell(100, 10, ar(row['الموقع']), border=1, align='C')
        pdf.ln()
        total_count += int(row['العدد'])
    
    # المبالغ (كمثال)
    pdf.ln(5)
    pdf.cell(0, 10, ar(f"إجمالي العدد: {total_count}"), ln=True, align='R')
    pdf.cell(0, 10, ar("المبلغ الإجمالي: $3,120"), ln=True, align='R')
    
    return pdf.output()

# في واجهة Streamlit نضيف الزر:
if st.button("توليد عرض السعر PDF"):
    pdf_data = create_pdf(customer, city, date_from, date_to, selected_locations_df)
    st.download_button(label="تحميل الملف الآن", data=pdf_data, file_name="Quotation.pdf", mime="application/pdf")
