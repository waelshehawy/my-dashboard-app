import streamlit as st
import pandas as pd
import sqlite3
import os
import io
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
from docx import Document
from docx.shared import Pt, RGBColor, Cm 
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from arabic_reshaper import reshape
from bidi.algorithm import get_display 

# --- إعدادات الصفحة ---
st.set_page_config(page_title="PreView Ads ERP", layout="wide")

def get_connection():
    return sqlite3.connect('billboards_data.db')

def ar(text):
    """معالجة النصوص العربية"""
    if not text or str(text).strip() == "": return ""
    return get_display(reshape(str(text)))

def set_cell_shading(cell, color):
    """تلوين خلفية خلايا الجدول"""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), color)
    tcPr.append(shd)

# --- دالة تصدير الوورد باستخدام القالب الجاهز ---
def export_word(customer_name, cart_data, period_name):
    # فتح القالب الذي يحتوي على الخلفية (Behind Text) المصممة يدوياً
    if os.path.exists('template.docx'):
        doc = Document('template.docx')
    else:
        st.warning("⚠️ ملف template.docx غير موجود، سيتم إنشاء ملف جديد بدون خلفية.")
        doc = Document()

    # إضافة المحتوى فوق القالب
    # 1. التاريخ (يسار)
    p_date = doc.add_paragraph(f"{ar('التاريخ:')} 2026/05/02")
    p_date.alignment = WD_ALIGN_PARAGRAPH.LEFT

    # 2. اسم الزبون (منتصف)
    p_cust = doc.add_paragraph()
    p_cust.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_c = p_cust.add_run(ar(f"السادة شركة {customer_name} المحترمين"))
    run_c.bold = True
    run_c.font.size = Pt(22)
    run_c.font.color.rgb = RGBColor(102, 0, 153)

    # 3. التحية والفترة
    doc.add_paragraph(ar("تحية طيبة وبعد،")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
    doc.add_paragraph(ar(f"نقدم لكم المواقع المتاحة للفترة: {period_name}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # 4. بناء الجداول الملونة لكل محافظة
    if cart_data:
        for city, networks in cart_data.items():
            doc.add_paragraph(ar(f"■ محافظة {city}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
            for net, df in networks.items():
                doc.add_paragraph(ar(f"شبكة: {net}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
                
                table = doc.add_table(rows=1, cols=4)
                table.style = 'Table Grid'
                table.alignment = WD_ALIGN_PARAGRAPH.CENTER
                
                # تنسيق رأس الجدول
                hdr_cells = table.rows[0].cells
                titles = ["العدد", "الموقع", "العدد", "الموقع"]
                for i, title in enumerate(titles):
                    hdr_cells[i].text = ar(title)
                    set_cell_shading(hdr_cells[i], "660099") # أرجواني
                    run_h = hdr_cells[i].paragraphs[0].runs[0]
                    run_h.font.color.rgb = RGBColor(255, 255, 255) # أبيض
                    run_h.bold = True

                # تعبئة البيانات بشكل ثنائي
                data_list = df.values.tolist()
                for i in range(0, len(data_list), 2):
                    row_cells = table.add_row().cells
                    row_cells[1].text = ar(data_list[i][0]) # الموقع
                    row_cells[0].text = str(data_list[i][1]) # العدد
                    if i + 1 < len(data_list):
                        row_cells[3].text = ar(data_list[i+1][0])
                        row_cells[2].text = str(data_list[i+1][1])
                
                # حساب المجاميع لكل شبكة
                total_n = pd.to_numeric(df.iloc[:, 1], errors='coerce').sum()
                ads_sum = pd.to_numeric(df['أجور العرض'], errors='coerce').sum() if 'أجور العرض' in df.columns else 0
                
                p_sum = doc.add_paragraph()
                p_sum.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                run_s = p_sum.add_run(f"{ar('إجمالي العدد:')} {int(total_n)} | {ar('أجور العرض:')} {ads_sum:,}$")
                run_s.bold = True
                run_s.font.color.rgb = RGBColor(102, 0, 153)

    # حفظ الملف في الذاكرة للتنزيل
    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- واجهة التطبيق (Streamlit) ---
if "auth" not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 تسجيل الدخول - PreView ERP")
    user = st.text_input("اسم المستخدم")
    pwd = st.text_input("كلمة المرور", type="password")
    if st.button("دخول"):
        if user == "admin" and pwd == "preview2026":
            st.session_state.auth = True
            st.rerun()
        else: st.error("بيانات خاطئة")
else:
    conn = get_connection()
    if 'cart' not in st.session_state: st.session_state.cart = {}
    
    with st.sidebar:
        # عرض اللوجو في الشريط الجانبي بحجم متناسق
        if os.path.exists('logo_full.png'):
            st.image('logo_full.png', width=180)
        
        st.header("قائمة التحكم")
        page = st.radio("انتقل إلى:", ["🏠 الداشبورد والخريطة", "📄 إنشاء عرض سعر"])
        if st.button("تسجيل الخروج"):
            st.session_state.auth = False
            st.rerun()

    if page == "🏠 الداشبورد والخريطة":
        st.title("📊 الداشبورد والخريطة التفاعلية")
        try:
            df_all = pd.read_sql("SELECT * FROM [اعمدة انارة]", conn)
            df_booked = pd.read_sql("SELECT [رقم اللوحة], [اسم الزبون] FROM [حجوزات1]", conn)
            df_map = pd.merge(df_all, df_booked, on='رقم اللوحة', how='left')
            
            city = st.selectbox("المحافظة:", ["الكل"] + sorted(df_map['المحافظة'].unique().tolist()))
            f_df = df_map if city == "الكل" else df_map[df_map['المحافظة'] == city]
            
            # الخريطة
            m = folium.Map(location=[33.51, 36.27], zoom_start=12)
            marker_cluster = MarkerCluster().add_to(m)
            for _, row in f_df.iterrows():
                if pd.notnull(row['Latitude']):
                    is_b = pd.notnull(row['اسم الزبون'])
                    pop = f"<div style='direction:rtl;'><b>{row['اسم العمود']}</b><br>{'محجوز' if is_b else 'متاح'}</div>"
                    folium.Marker([row['Latitude'], row['Longitude']], 
                                  popup=folium.Popup(pop, max_width=200),
                                  icon=folium.Icon(color='red' if is_b else 'purple')).add_to(marker_cluster)
            st_folium(m, width="100%", height=500)
            st.dataframe(f_df, use_container_width=True)
        except Exception as e: st.error(f"خطأ في البيانات: {e}")

    elif page == "📄 إنشاء عرض سعر":
        st.title("📄 بناء عرض سعر احترافي")
        try:
            df_periods = pd.read_sql("SELECT namee FROM [الفترة]", conn)['namee'].tolist()
            cust = st.text_input("اسم الزبون")
            period = st.selectbox("اختر الفترة:", df_periods)
            city_list = pd.read_sql("SELECT DISTINCT المحافظة FROM [اعمدة انارة]", conn)['المحافظة'].tolist()
            sel_city = st.selectbox("المحافظة", city_list)
            
            raw = pd.read_sql(f"SELECT [اسم العمود], [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة='{sel_city}'", conn)
            nets = st.multiselect("الشبكات المتاحة:", raw['الشبكة'].unique().tolist())
            
            if st.button("➕ إضافة المختارات للسلة"):
                if sel_city not in st.session_state.cart: st.session_state.cart[sel_city] = {}
                for n in nets:
                    st.session_state.cart[sel_city][n] = raw[raw['الشبكة'] == n].assign(**{'أجور العرض': 0})

            if st.session_state.cart:
                for c, nts in list(st.session_state.cart.items()):
                    for n, df in nts.items():
                        with st.expander(f"📍 {c} - {n}"):
                            st.session_state.cart[c][n] = st.data_editor(df, key=f"ed_{c}_{n}")
                
                if st.button("🚀 تصدير ملف Word"):
                    doc_io = export_word(cust, st.session_state.cart, period)
                    st.download_button("📥 تحميل عرض السعر", doc_io, f"Quotation_{cust}.docx")
                if st.button("🗑️ تفريغ السلة"): 
                    st.session_state.cart = {}
                    st.rerun()
        except Exception as e: st.error(f"حدث خطأ: {e}")
    conn.close()
