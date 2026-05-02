import streamlit as st
import pandas as pd
import sqlite3
import os
import io
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm 
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
    if not text: return ""
    return get_display(reshape(str(text)))

# دالة لتلوين خلفية خلايا الجدول (للعناوين)
def set_cell_shading(cell, color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), color)
    tcPr.append(shd)

# --- وظيفة تصدير الوورد الاحترافية (تحديث الصورة المدمجة) ---



def export_word(customer_name, cart_data, period_name):
    doc = Document()
    section = doc.sections[0]
    
        # إعداد الهيدر لوضع الخلفية
    header = doc.sections[0].header
    p = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
    
    if os.path.exists('logo_full.png'):
        run = p.add_run()
        # استخدام Cm بحرف كبير لتفادي الخطأ
        # أبعاد A4: 21cm x 29.7cm
        picture = run.add_picture('logo_full.png', width=Cm(21), height=Cm(29.7))
        
        # كود التموضع المطلق (خلف النص وبدون هوامش)
        try:
            from docx.oxml.ns import qn
            from docx.oxml import OxmlElement

            # تحويل الصورة من inline إلى anchor (عنصر عائم)
            graphic = picture._inline.graphic
            picture._inline.getparent().remove(picture._inline)
            
            anchor = OxmlElement('wp:anchor')
            anchor.set(qn('wp:behindDoc'), '1') # خلف النص
            anchor.set(qn('wp:locked'), '0')
            anchor.set(qn('wp:relativeHeight'), '0')
            
            # تحديد نقطة البداية من زاوية الصفحة (0,0)
            simple_pos = OxmlElement('wp:simplePos')
            simple_pos.set(qn('x'), '0')
            simple_pos.set(qn('y'), '0')
            
            # ضبط الموقع الأفقي والعمودي بالنسبة للصفحة (وليس الهوامش)
            for axis in ['horz', 'vert']:
                pos = OxmlElement(f'wp:{axis}')
                pos.set(qn('relativeFrom'), 'page') # البدء من حافة الصفحة
                pos_offset = OxmlElement('wp:posOffset')
                pos_offset.text = '0'
                pos.append(pos_offset)
                anchor.append(pos)

            anchor.append(simple_pos)
            anchor.append(graphic)
            anchor.append(OxmlElement('wp:wrapNone')) # لا يوجد التفاف للنص
            
            # إضافة العنصر الجديد للـ Run
            p._p.add_run()._r.append(anchor)
        except Exception:
            # في حال فشل الكود المتقدم، سيستمر التصدير بالصورة العادية
            pass

 

    # 2. الفوتر (بيانات الاتصال كما في النموذج)
    footer = section.footer
    p_footer = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    p_footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    # استخدام الخط الأرجواني للفوتر ليتناسب مع الهوية
    contact_info = ar("سوريا - دمشق - مزة جبل | هاتف: 9394 (963+) | info@previewsyria.com")
    run_f = p_footer.add_run(contact_info)
    run_f.font.size = Pt(9)
    run_f.font.color.rgb = RGBColor(102, 0, 153) # لون أرجواني


    # 3. محتوى الخطاب
    doc.add_paragraph(f"{ar('التاريخ:')} 2026/3/9").alignment = WD_ALIGN_PARAGRAPH.LEFT
    
    p_cust = doc.add_paragraph()
    p_cust.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_c = p_cust.add_run(ar(f"السادة شركة {customer_name} المحترمين"))
    run_c.bold = True
    run_c.font.size = Pt(16)

    doc.add_paragraph(ar("تحية طيبة،")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
    doc.add_paragraph(ar(f"نقدم لكم المواقع المتاحة في المحافظات لعرض إعلانكم الوطني للفترة: {period_name}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # 4. بناء الجداول الملونة لكل محافظة
    for city, networks in cart_data.items():
        doc.add_paragraph(ar(f"محافظة {city}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
        
        for net, df in networks.items():
            doc.add_paragraph(ar(f"شبكة: {net}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
            
            # إنشاء جدول 4 أعمدة (العدد | الشبكة | العدد | الشبكة)
            table = doc.add_table(rows=1, cols=4)
            table.style = 'Table Grid'
            table.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            # تنسيق رأس الجدول (تظليل أرجواني ونص أبيض)
            hdr_cells = table.rows[0].cells
            titles = ["العدد", "الشبكة", "العدد", "الشبكة"]
            for i, title in enumerate(titles):
                hdr_cells[i].text = ar(title)
                set_cell_shading(hdr_cells[i], "660099") # لون أرجواني
                run = hdr_cells[i].paragraphs[0].runs[0]
                run.font.color.rgb = RGBColor(255, 255, 255) # نص أبيض
                run.bold = True
                hdr_cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

            # تعبئة البيانات (ثنائية)
            data = df.iloc[:, :2].values.tolist()
            for i in range(0, len(data), 2):
                row_cells = table.add_row().cells
                row_cells[1].text = ar(data[i][0]) # الموقع/الشبكة
                row_cells[0].text = str(data[i][1]) # العدد
                if i + 1 < len(data):
                    row_cells[3].text = ar(data[i+1][0])
                    row_cells[2].text = str(data[i+1][1])
            
            # تذييل الأسعار لكل جدول
            total_n = pd.to_numeric(df.iloc[:, 1], errors='coerce').sum()
            prnt = pd.to_numeric(df['أجور الطباعة'], errors='coerce').sum() if 'أجور الطباعة' in df.columns else 0
            ads = pd.to_numeric(df['أجور العرض'], errors='coerce').sum() if 'أجور العرض' in df.columns else 0
            
            p_price = doc.add_paragraph()
            p_price.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            price_text = f"{ar('العدد:')} {int(total_n)} | {ar('أجور العرض:')} {ads}$ | {ar('أجور الطباعة:')} {prnt}$"
            run_p = p_price.add_run(price_text)
            run_p.bold = True
            run_p.font.color.rgb = RGBColor(102, 0, 153)

    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- واجهة التطبيق (Streamlit) ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 تسجيل الدخول - PreView ERP")
    user = st.text_input("اسم المستخدم")
    pwd = st.text_input("كلمة المرور", type="password")
    if st.button("دخول"):
        if user == "admin" and pwd == "preview2026":
            st.session_state.authenticated = True
            st.rerun()
        else: st.error("❌ بيانات خاطئة")
else:
    conn = get_connection()
    if 'cart' not in st.session_state: st.session_state.cart = {}
    
    with st.sidebar:
        st.header("PreView Ads")
        page = st.radio("القائمة:", ["🏠 الداشبورد والخريطة", "📄 إنشاء عرض سعر"])
        if st.button("خروج"):
            st.session_state.authenticated = False
            st.rerun()

    if page == "🏠 الداشبورد والخريطة":
        st.title("📊 الخريطة التفاعلية والداشبورد")
        df_all = pd.read_sql("SELECT * FROM [اعمدة انارة]", conn).copy()
        df_booked = pd.read_sql("SELECT [رقم اللوحة], [اسم الزبون], [فترة الحجز] FROM [حجوزات1]", conn)
        df_map = pd.merge(df_all, df_booked, on='رقم اللوحة', how='left')
        df_map['المحافظة'] = df_map['المحافظة'].astype(str).str.strip()

        with st.sidebar:
            st.divider()
            city_f = st.selectbox("المحافظة:", ["الكل"] + sorted(df_map['المحافظة'].unique().tolist()))
            stat_f = st.radio("الحالة:", ["الكل", "متاح", "محجوز"])

        filtered_df = df_map.copy()
        if city_f != "الكل": filtered_df = filtered_df[filtered_df['المحافظة'] == city_f]
        if stat_f == "محجوز": filtered_df = filtered_df[filtered_df['اسم الزبون'].notna()]
        elif stat_f == "متاح": filtered_df = filtered_df[filtered_df['اسم الزبون'].isna()]

        m = folium.Map(location=[33.51, 36.27], zoom_start=12)
        marker_cluster = MarkerCluster().add_to(m)
        for _, row in filtered_df.iterrows():
            lat, lon = row.get('Latitude'), row.get('Longitude')
            if pd.notnull(lat) and pd.notnull(lon):
                is_b = pd.notnull(row.get('اسم الزبون'))
                pop_html = f"<div style='direction:rtl; text-align:right; font-family:Tahoma;'><b>{row['اسم العمود']}</b><br>الشركة: {row['اسم الزبون'] if is_b else 'متاح'}<br>الفترة: {row['فترة الحجز'] if is_b else '-'}</div>"
                folium.Marker([lat, lon], popup=folium.Popup(pop_html, max_width=200), icon=folium.Icon(color='red' if is_b else 'purple')).add_to(marker_cluster)
        
        st_folium(m, width="100%", height=500)
        st.dataframe(filtered_df.drop(columns=['Latitude', 'Longitude'], errors='ignore'), use_container_width=True)

    elif page == "📄 إنشاء عرض سعر":
        st.title("📄 بناء عرض سعر احترافي")
        df_periods = pd.read_sql("SELECT namee FROM [الفترة]", conn)['namee'].tolist()
        
        col1, col2 = st.columns(2)
        with col1:
            cust = st.text_input("اسم الزبون")
            selected_period = st.selectbox("اختر الفترة:", df_periods)
            city_list = sorted(pd.read_sql("SELECT DISTINCT المحافظة FROM [اعمدة انارة]", conn)['المحافظة'].tolist())
            sel_city = st.selectbox("المحافظة", city_list)
            raw = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة='{sel_city}'", conn)
            nets = st.multiselect("الشبكات المتاحة:", raw['الشبكة'].unique().tolist())
            
            if st.button("➕ إضافة للسلة"):
                if sel_city not in st.session_state.cart: st.session_state.cart[sel_city] = {}
                for n in nets:
                    df_net = raw[raw['الشبكة'] == n].copy()
                    df_net['أجور الطباعة'], df_net['أجور العرض'] = 0, 0
                    st.session_state.cart[sel_city][n] = df_net

        with col2:
            if st.session_state.cart:
                for c, nts in list(st.session_state.cart.items()):
                    for n, df in nts.items():
                        with st.expander(f"📍 {c} - {n}"):
                            st.session_state.cart[c][n] = st.data_editor(df, key=f"ed_{c}_{n}")
                if st.button("🚀 تصدير Word"):
                    doc_out = export_word(cust, st.session_state.cart, selected_period)
                    st.download_button("📥 تحميل عرض السعر", doc_out, f"Quotation_{cust}.docx")
                if st.button("🗑️ تفريغ السلة"): st.session_state.cart = {}; st.rerun()
    conn.close()
