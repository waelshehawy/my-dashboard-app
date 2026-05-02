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
    # تأكد من وجود ملف قاعدة البيانات في نفس المسار
    return sqlite3.connect('billboards_data.db')

def ar(text):
    """دالة لمعالجة النصوص العربية للعرض في المكتبات التي لا تدعم RTL"""
    if not text: return ""
    return get_display(reshape(str(text)))

def set_cell_shading(cell, color):
    """تلوين خلفية خلايا الجدول في Word"""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), color)
    tcPr.append(shd)

# --- وظيفة تصدير الوورد الاحترافية (مع شعار خلف النص) ---
def export_word(customer_name, cart_data, period_name):
    doc = Document()
    
    # ضبط هوامش وأبعاد الصفحة A4
    section = doc.sections[0]
    section.page_height = Cm(29.7)
    section.page_width = Cm(21)
    section.left_margin = Cm(2)
    section.right_margin = Cm(2)
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2)

    # 1. إضافة اللوجو كخلفية (Watermark) عبر الهيدر
    header = section.header
    p_header = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
    
    if os.path.exists('logo_full.png'):
        run = p_header.add_run()
        picture = run.add_picture('logo_full.png', width=Cm(21), height=Cm(29.7))
        
        try:
            # تحويل الصورة إلى عنصر عائم خلف النص (Behind Text)
            inline = picture._inline
            extent = inline.extent
            doc_pr = inline.docPr
            graphic = inline.graphic
            
    
            anchor.set(qn('wp:behind Text'), '1') 


            # التموضع الأفقي من حافة الصفحة
            h_pos = OxmlElement('wp:positionH')
            h_pos.set(qn('relativeFrom'), 'page')
            h_offset = OxmlElement('wp:posOffset')
            h_offset.text = '0'
            h_pos.append(h_offset)

            # التموضع الرأسي من حافة الصفحة
            v_pos = OxmlElement('wp:positionV')
            v_pos.set(qn('relativeFrom'), 'page')
            v_offset = OxmlElement('wp:posOffset')
            v_offset.text = '0'
            v_pos.append(v_offset)

            anchor.append(OxmlElement('wp:simplePos'))
            anchor.get_element(qn('wp:simplePos')).set('x', '0')
            anchor.get_element(qn('wp:simplePos')).set('y', '0')
            anchor.append(h_pos)
            anchor.append(v_pos)
            anchor.append(extent)
            anchor.append(OxmlElement('wp:effectExtent'))
            anchor.append(OxmlElement('wp:wrapNone'))
            anchor.append(doc_pr)
            anchor.append(graphic)

            p_header._p.remove(run._r)
            new_run = p_header.add_run()
            new_run._r.append(anchor)
        except Exception:
            pass

    # 2. محتوى الخطاب
    doc.add_paragraph() # مسافة علوية
    doc.add_paragraph(f"{ar('التاريخ:')} 2026/03/09").alignment = WD_ALIGN_PARAGRAPH.LEFT
    
    p_cust = doc.add_paragraph()
    p_cust.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_c = p_cust.add_run(ar(f"السادة شركة {customer_name} المحترمين"))
    run_c.bold = True
    run_c.font.size = Pt(18)
    run_c.font.color.rgb = RGBColor(102, 0, 153)

    doc.add_paragraph(ar("تحية طيبة،")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
    doc.add_paragraph(ar(f"نقدم لكم المواقع المتاحة للفترة: {period_name}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # 3. بناء الجداول لكل محافظة
    for city, networks in cart_data.items():
        p_city = doc.add_paragraph(ar(f"■ محافظة {city}"))
        p_city.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p_city.runs[0].bold = True
        
        for net, df in networks.items():
            doc.add_paragraph(ar(f"شبكة: {net}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
            
            table = doc.add_table(rows=1, cols=4)
            table.style = 'Table Grid'
            table.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            hdr_cells = table.rows[0].cells
            titles = ["العدد", "الموقع", "العدد", "الموقع"]
            for i, title in enumerate(titles):
                hdr_cells[i].text = ar(title)
                set_cell_shading(hdr_cells[i], "660099")
                run = hdr_cells[i].paragraphs[0].runs[0]
                run.font.color.rgb = RGBColor(255, 255, 255)
                run.bold = True
                hdr_cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

            data = df.values.tolist()
            for i in range(0, len(data), 2):
                row_cells = table.add_row().cells
                row_cells[1].text = ar(data[i][0]) # الموقع
                row_cells[0].text = str(data[i][1]) # العدد
                if i + 1 < len(data):
                    row_cells[3].text = ar(data[i+1][0])
                    row_cells[2].text = str(data[i+1][1])
            
            total_n = pd.to_numeric(df.iloc[:, 1], errors='coerce').sum()
            ads = pd.to_numeric(df['أجور العرض'], errors='coerce').sum()
            
            p_price = doc.add_paragraph()
            p_price.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            price_text = f"{ar('إجمالي العدد:')} {int(total_n)} | {ar('أجور العرض:')} {ads:,}$"
            run_p = p_price.add_run(price_text)
            run_p.bold = True
            run_p.font.color.rgb = RGBColor(102, 0, 153)

    # 4. الفوتر (تذييل الصفحة)
    footer = section.footer
    p_footer = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    p_footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_f = p_footer.add_run(ar("سوريا - دمشق - مزة جبل | هاتف: 9394 (963+) | info@previewsyria.com"))
    run_f.font.size = Pt(9)
    run_f.font.color.rgb = RGBColor(102, 0, 153)

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
        # حل مشكلة حجم اللوجو في السايدبار
        if os.path.exists('logo_full.png'):
            st.image('logo_full.png', width=200)
        
        st.header("PreView Ads")
        page = st.radio("القائمة:", ["🏠 الداشبورد والخريطة", "📄 إنشاء عرض سعر"])
        if st.button("خروج"):
            st.session_state.authenticated = False
            st.rerun()

    if page == "🏠 الداشبورد والخريطة":
        st.title("📊 الخريطة التفاعلية والداشبورد")
        
        try:
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

            # الخريطة
            m = folium.Map(location=[33.51, 36.27], zoom_start=12)
            marker_cluster = MarkerCluster().add_to(m)
            for _, row in filtered_df.iterrows():
                lat, lon = row.get('Latitude'), row.get('Longitude')
                if pd.notnull(lat) and pd.notnull(lon):
                    is_b = pd.notnull(row.get('اسم الزبون'))
                    pop_html = f"<div style='direction:rtl; text-align:right; font-family:Tahoma;'><b>{row['اسم العمود']}</b><br>الشركة: {row['اسم الزبون'] if is_b else 'متاح'}</div>"
                    folium.Marker([lat, lon], popup=folium.Popup(pop_html, max_width=200), 
                                  icon=folium.Icon(color='red' if is_b else 'purple')).add_to(marker_cluster)
            
            st_folium(m, width="100%", height=500)
            st.dataframe(filtered_df.drop(columns=['Latitude', 'Longitude'], errors='ignore'), use_container_width=True)
        except Exception as e:
            st.error(f"خطأ في تحميل البيانات: {e}")

    elif page == "📄 إنشاء عرض سعر":
        st.title("📄 بناء عرض سعر احترافي")
        try:
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
                    
                    if st.button("🗑️ تفريغ السلة"): 
                        st.session_state.cart = {}
                        st.rerun()
        except Exception as e:
            st.error(f"حدث خطأ: {e}")

    conn.close()
