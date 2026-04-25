import streamlit as st
import sqlite3
import pandas as pd
from fpdf import FPDF
from arabic_reshaper import reshape
from bidi.algorithm import get_display

# إعداد الصفحة
st.set_page_config(page_title="نظام بريفيو للإعلانات", layout="wide")

def get_connection():
    return sqlite3.connect('billboards_data.db')

# دالة لتنسيق النصوص العربية
def ar(text):
    if not text: return ""
    return get_display(reshape(str(text)))

# دالة إنشاء ملف PDF (مطابق للنموذج)
def create_quotation_pdf(data):
    pdf = FPDF()
    pdf.add_page()
    # تأكد من رفع ملف الخط Amiri-Regular.ttf إلى GitHub
    try:
        pdf.add_font('ArabicFont', '', 'Amiri-Regular.ttf')
        pdf.set_font('ArabicFont', size=14)
    except:
        pdf.set_font('Arial', size=14) # خط بديل في حال عدم وجود الخط

    # ترويسة الشركة
    pdf.cell(0, 10, ar("شركة بريفيو PreView"), ln=True, align='R')
    pdf.cell(0, 10, ar(f"التاريخ: {data['year']}"), ln=True, align='R')
    pdf.ln(10)
    
    # نص العرض
    pdf.cell(0, 10, ar(f"السادة {data['customer']} المحترمين"), ln=True, align='R')
    pdf.multi_cell(0, 10, ar(f"نقدم لكم عرض سعر في محافظة {data['city']} للفترة: {data['period']}"), align='R')
    
    # جدول المواقع
    pdf.ln(5)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(40, 10, ar("العدد"), border=1, align='C', fill=True)
    pdf.cell(140, 10, ar("الموقع"), border=1, align='C', fill=True)
    pdf.ln()
    
    pdf.cell(40, 10, "1", border=1, align='C')
    pdf.cell(140, 10, ar(data['pole_name']), border=1, align='C')
    pdf.ln(10)
    
    pdf.cell(0, 10, ar(f"إجمالي الرسوم: {data['fees']} $"), ln=True, align='R')
    return pdf.output()

# --- واجهة التطبيق ---
st.title("📄 إصدار عروض الأسعار - بريفيو")

conn = get_connection()
poles_df = pd.read_sql("SELECT [رقم اللوحة], [اسم العمود] FROM [اعمدة انارة]", conn)
cities_df = pd.read_sql("SELECT [المحافظة] FROM [المحافظات]", conn)
periods_df = pd.read_sql("SELECT [namee] FROM [الفترة]", conn)

with st.form("quotation_form"):
    col1, col2 = st.columns(2)
    with col1:
        customer = st.text_input("اسم الزبون")
        selected_pole = st.selectbox("الموقع / العمود", poles_df['اسم العمود'].tolist())
        period = st.selectbox("فترة الحجز", periods_df['namee'].tolist())
    with col2:
        city = st.selectbox("المحافظة", cities_df['المحافظة'].tolist())
        year = st.text_input("العام", value="2026")
        fees = st.number_input("أجور العرض ($)", min_value=0)
    
    submit = st.form_submit_button("حفظ الحجز وتجهيز العرض")

if submit:
    # حفظ البيانات في قاعدة البيانات
    try:
        p_id = int(poles_df[poles_df['اسم العمود'] == selected_pole]['رقم اللوحة'].values[0])
        cursor = conn.cursor()
        cursor.execute("INSERT INTO [حجوزات1] ([رقم اللوحة], [اسم الزبون], [فترة الحجز], [المحافظة], [العام], [رسوم مؤسسة]) VALUES (?, ?, ?, ?, ?, ?)", 
                       (p_id, customer, period, city, year, fees))
        conn.commit()
        st.success("✅ تم حفظ البيانات في النظام")
        
        # تجهيز بيانات الـ PDF
        pdf_info = {
            'customer': customer, 'city': city, 'period': period,
            'year': year, 'fees': fees, 'pole_name': selected_pole
        }
        
        pdf_file = create_quotation_pdf(pdf_info)
        st.download_button(label="📥 تحميل عرض السعر PDF", 
                           data=bytes(pdf_file), 
                           file_name=f"Quotation_{customer}.pdf", 
                           mime="application/pdf")
    except Exception as e:
        st.error(f"حدث خطأ: {e}")
