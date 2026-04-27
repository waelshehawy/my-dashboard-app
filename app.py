import streamlit as st
import pandas as pd
import sqlite3
import os
import io
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from arabic_reshaper import reshape
from bidi.algorithm import get_display

# --- إعدادات الصفحة ---
st.set_page_config(page_title="Preview Ads ERP", layout="wide")

# --- نظام الأمان ---
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.title("🔒 تسجيل الدخول - نظام بريفيو")
        user_input = st.text_input("اسم المستخدم:")
        password_input = st.text_input("كلمة المرور:", type="password")
        users = {"admin": "preview2026", "wael": "wael123"}
        if st.button("دخول"):
            if user_input in users and users[user_input] == password_input:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ خطأ في البيانات")
        return False
    return True

if check_password():
    def get_connection():
        return sqlite3.connect('billboards_data.db')

    def ar(text):
        if not text: return ""
        return get_display(reshape(str(text)))

    # --- تصحيح دالة الصورة الخلفية (طريقة بديلة وأكثر استقراراً) ---
    def add_background_image(doc, image_path):
        header = doc.sections[0].header
        if not header.paragraphs:
            header.add_paragraph()
        p = header.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run()
        # إضافة الصورة في الرأس تجعلها تظهر خلف النص في كل الصفحات تلقائياً
        run.add_picture(image_path, width=Inches(8.27)) 

    def export_final_quotation(customer_name, cart_data, dates):
        doc = Document()
        # إعداد الاتجاه من اليمين لليسار
        section = doc.sections[0]
        section.right_to_left = True
        
        if os.path.exists('logo.png'):
            add_background_image(doc, 'logo.png')

        # ترك مسافة علوية للنص
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
                
                # بناء الجدول بنظام 4 أعمدة
                clean_df = df.iloc[:, :2].reset_index(drop=True)
                rows_needed = (len(clean_df) + 1) // 2
                table = doc.add_table(rows=rows_needed + 1, cols=4)
                table.style = 'Table Grid'
                
                # العناوين
                table.cell(0, 0).text = ar("العدد")
                table.cell(0, 1).text = ar("الموقع")
                table.cell(0, 2).text = ar("العدد")
                table.cell(0, 3).text = ar("الموقع")

                for i in range(len(clean_df)):
                    row_idx = (i // 2) + 1
                    col_off = 0 if i % 2 == 0 else 2
                    table.cell(row_idx, col_off).text = str(clean_df.iloc[i, 1])
                    table.cell(row_idx, col_off + 1).text = ar(clean_df.iloc[i, 0])
                
                doc.add_paragraph(ar(f"العدد الكلي: {int(clean_df.iloc[:, 1].sum())}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
        
        target = io.BytesIO()
        doc.save(target)
        target.seek(0)
        return target

    # --- واجهة المستخدم ---
    if 'cart' not in st.session_state: st.session_state.cart = {}
    st.sidebar.title("💎 PreView Ads ERP")
    page = st.sidebar.radio("القائمة:", ["📊 الداشبورد", "📄 صانع العروض"])

    if st.sidebar.button("🚪 خروج"):
        st.session_state.authenticated = False
        st.rerun()

    conn = get_connection()

    if page == "📊 الداشبورد":
        st.title("📊 حالة النظام")
        df_all = pd.read_sql("SELECT * FROM [اعمدة انارة]", conn)
        st.dataframe(df_all, use_container_width=True)

    elif page == "📄 صانع العروض":
        st.title("📄 بناء عرض السعر")
        col_in, col_view = st.columns(2)
        
        with col_in:
            cust_name = st.text_input("اسم الزبون")
            cities = pd.read_sql("SELECT المحافظة FROM المحافظات", conn)['المحافظة'].tolist()
            sel_city = st.selectbox("المحافظة", cities)
            raw_df = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة = '{sel_city}'", conn)
            sel_nets = st.multiselect("الشبكات:", raw_df['الشبكة'].unique().tolist())
            
            if st.button("➕ إضافة"):
                st.session_state.cart[sel_city] = {n: raw_df[raw_df['الشبكة'] == n][['الموقع', 'العدد']] for n in sel_nets}
                st.success(f"تمت إضافة {sel_city}")

        with col_view:
            if st.session_state.cart:
                for c_n, nets in st.session_state.cart.items():
                    with st.expander(f"📍 {c_n}"):
                        for n_n, df in nets.items():
                            st.session_state.cart[c_n][n_n] = st.data_editor(df, key=f"ed_{c_n}_{n_n}")
                
                if st.button("🚀 تصدير الوورد"):
                    dates = {'start': "2026/05/01", 'end': "2026/05/28"}
                    out_file = export_final_quotation(cust_name, st.session_state.cart, dates)
                    st.download_button("📥 تحميل العرض", out_file, f"Quotation_{cust_name}.docx")
