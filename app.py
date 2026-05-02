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

# --- إعدادات الصفحة العامة ---
st.set_page_config(page_title="PreView Ads ERP", layout="wide")

def get_connection():
    """الاتصال بقاعدة البيانات المحلية"""
    return sqlite3.connect('billboards_data.db')

def ar(text):
    """معالجة النصوص العربية للعرض الصحيح RTL"""
    if not text or str(text).strip() == "": return ""
    return get_display(reshape(str(text)))

def set_cell_shading(cell, color):
    """تلوين خلفية خلايا جداول الوورد"""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), color)
    tcPr.append(shd)

# --- دالة تصدير ملف الوورد الاحترافية (حل مشكلة الخلفية) ---
def export_word(customer_name, cart_data, period_name):
    doc = Document()
    
    # 1. إعدادات الصفحة A4 مع هوامش قياسية
    section = doc.sections[0]
    section.page_height = Cm(29.7)
    section.page_width = Cm(21)
    section.left_margin = Cm(2)
    section.right_margin = Cm(2)
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2)

    # 2. إدراج الشعار كخلفية (Behind Text) في الهيدر لضمان ثباته
    header = section.header
    p_head = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
    p_head.alignment = WD_ALIGN_PARAGRAPH.LEFT

    if os.path.exists('logo_full.png'):
        run = p_head.add_run()
        # تصغير العرض والارتفاع بـ 1 ملم فقط لمنع ظهور صفحات فارغة
        pic = run.add_picture('logo_full.png', width=Cm(20.9), height=Cm(29.6))
        
        try:
            # الوصول لعمق XML لتحويل الصورة إلى عنصر عائم خلف النص
            inline = pic._inline
            extent = inline.extent
            doc_pr = inline.docPr
            graphic = inline.graphic
            
            anchor = OxmlElement('wp:anchor')
            anchor.set(qn('wp:behindDoc'), '1') # أهم سطر: جعل الصورة في الخلفية
            anchor.set(qn('wp:locked'), '0')
            anchor.set(qn('wp:layoutInCell'), '1')
            anchor.set(qn('wp:allowOverlap'), '1') # السماح للنص بالظهور فوقها
            anchor.set(qn('wp:simplePos'), '0')
            anchor.set(qn('wp:relativeHeight'), '0')

            # تحديد الموقع الأفقي (Absolute) من حافة الصفحة المطلقة
            h_pos = OxmlElement('wp:positionH')
            h_pos.set(qn('relativeFrom'), 'page')
            h_offset = OxmlElement('wp:posOffset')
            h_offset.text = '0'
            h_pos.append(h_offset)
            anchor.append(h_pos)

            # تحديد الموقع الرأسي (Absolute) من حافة الصفحة المطلقة
            v_pos = OxmlElement('wp:positionV')
            v_pos.set(qn('relativeFrom'), 'page')
            v_offset = OxmlElement('wp:posOffset')
            v_offset.text = '0'
            v_pos.append(v_offset)
            anchor.append(v_pos)

            # الترتيب الإلزامي للعناصر لضمان توافق ملف الوورد
            anchor.append(extent)
            anchor.append(OxmlElement('wp:effectExtent'))
            anchor.append(OxmlElement('wp:wrapNone')) # منع إزاحة النص (Behind Text mode)
            anchor.append(doc_pr)
            anchor.append(graphic)
            
            # استبدال الفقرة الافتراضية بالهيكل الجديد
            p_head._p.remove(run._r)
            p_head._p.add_run()._r.append(anchor)
        except Exception:
            pass

    # 3. محتوى العرض (سيظهر الآن فوق الخلفية)
    for _ in range(2): doc.add_paragraph() # مسافة للبدء تحت رأس الصفحة

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_t = p_title.add_run(ar(f"السادة شركة {customer_name} المحترمين"))
    run_t.bold = True
    run_t.font.size = Pt(22)
    run_t.font.color.rgb = RGBColor(102, 0, 153)

    doc.add_paragraph(ar(f"التاريخ: 2026/03/09")).alignment = WD_ALIGN_PARAGRAPH.LEFT
    doc.add_paragraph(ar("تحية طيبة وبعد،")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
    doc.add_paragraph(ar(f"نقدم لكم المواقع المتاحة للفترة: {period_name}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # 4. بناء الجداول لكل محافظة وشبكة
    if cart_data:
        for city, networks in cart_data.items():
            doc.add_paragraph(ar(f"📍 محافظة {city}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
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
                    run_h = hdr_cells[i].paragraphs[0].runs[0]
                    run_h.font.color.rgb = RGBColor(255, 255, 255)
                    run_h.bold = True
                    hdr_cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

                # تعبئة البيانات بشكل ثنائي (موقعين في كل سطر)
                data_list = df.values.tolist()
                for i in range(0, len(data_list), 2):
                    row_cells = table.add_row().cells
                    row_cells[1].text = ar(data_list[i][0])
                    row_cells[0].text = str(data_list[i][1])
                    if i + 1 < len(data_list):
                        row_cells[3].text = ar(data_list[i+1][0])
                        row_cells[2].text = str(data_list[i+1][1])
                
                # حساب المجاميع
                total_n = pd.to_numeric(df.iloc[:, 1], errors='coerce').sum()
                ads_sum = pd.to_numeric(df['أجور العرض'], errors='coerce').sum() if 'أجور العرض' in df.columns else 0
                
                p_sum = doc.add_paragraph()
                p_sum.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                run_s = p_sum.add_run(f"{ar('إجمالي العدد:')} {int(total_n)} | {ar('أجور العرض:')} {ads_sum:,}$")
                run_s.bold = True
                run_s.font.color.rgb = RGBColor(102, 0, 153)

    # تذييل الصفحة (Footer)
    footer = section.footer
    p_foot = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    p_foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_f = p_foot.add_run(ar("سوريا - دمشق - مزة جبل | هاتف: 9394 (963+) | info@previewsyria.com"))
    run_f.font.size = Pt(9)
    run_f.font.color.rgb = RGBColor(102, 0, 153)

    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- واجهة تطبيق Streamlit ---
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
        # ضبط حجم اللوجو ليكون متناسقاً في الشريط الجانبي
        if os.path.exists('logo_full.png'):
            st.image('logo_full.png', width=200)
        st.header("PreView Ads")
        page = st.radio("القائمة:", ["🏠 الداشبورد والخريطة", "📄 إنشاء عرض سعر"])
        if st.button("خروج"):
            st.session_state.authenticated = False
            st.rerun()

    if page == "🏠 الداشبورد والخريطة":
        st.title("📊 الداشبورد والخريطة التفاعلية")
        try:
            df_all = pd.read_sql("SELECT * FROM [اعمدة انارة]", conn)
            df_booked = pd.read_sql("SELECT [رقم اللوحة], [اسم الزبون] FROM [حجوزات1]", conn)
            df_map = pd.merge(df_all, df_booked, on='رقم اللوحة', how='left')
            
            city = st.selectbox("تصفية بالمحافظة:", ["الكل"] + sorted(df_map['المحافظة'].unique().tolist()))
            f_df = df_map if city == "الكل" else df_map[df_map['المحافظة'] == city]
            
            m = folium.Map(location=[33.51, 36.27], zoom_start=12)
            marker_cluster = MarkerCluster().add_to(m)
            for _, row in f_df.iterrows():
                if pd.notnull(row['Latitude']):
                    is_b = pd.notnull(row['اسم الزبون'])
                    pop = f"<div style='direction:rtl;'><b>{row['اسم العمود']}</b><br>{ar('الشركة')}: {row['اسم الزبون'] if is_b else ar('متاح')}</div>"
                    folium.Marker([row['Latitude'], row['Longitude']], 
                                  popup=folium.Popup(pop, max_width=200),
                                  icon=folium.Icon(color='red' if is_b else 'purple')).add_to(marker_cluster)
            st_folium(m, width="100%", height=500)
            st.dataframe(f_df, use_container_width=True)
        except Exception as e: st.error(f"خطأ: {e}")

    elif page == "📄 إنشاء عرض سعر":
        st.title("📄 بناء عرض سعر احترافي")
        try:
            df_periods = pd.read_sql("SELECT namee FROM [الفترة]", conn)['namee'].tolist()
            cust = st.text_input("اسم الزبون")
            period = st.selectbox("فترة العرض", df_periods)
            city_list = pd.read_sql("SELECT DISTINCT المحافظة FROM [اعمدة انارة]", conn)['المحافظة'].tolist()
            sel_city = st.selectbox("المحافظة المستهدفة", city_list)
            
            raw = pd.read_sql(f"SELECT [اسم العمود], [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة='{sel_city}'", conn)
            nets = st.multiselect("اختر الشبكات المتاحة:", raw['الشبكة'].unique().tolist())
            
            if st.button("➕ إضافة للسلة"):
                if sel_city not in st.session_state.cart: st.session_state.cart[sel_city] = {}
                for n in nets:
                    st.session_state.cart[sel_city][n] = raw[raw['الشبكة'] == n].assign(**{'أجور العرض': 0})

            if st.session_state.cart:
                st.markdown("### 🛒 المواقع المختارة")
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
        except Exception as e: st.error(f"خطأ: {e}")
    conn.close()
