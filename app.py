import streamlit as st
import pandas as pd
import sqlite3
import os
import io
from docx import Document
from docx.shared import Pt, RGBColor, Cm 
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
# إحداثيات مراكز المحافظات السورية
SYRIA_CITIES_COORDS = {
    "دمشق": [33.5138, 36.2765],
    "ريف دمشق": [33.5138, 36.2765],
    "حلب": [36.2021, 37.1343],
    "حمص": [34.7324, 36.7137],
    "حماة": [35.1318, 36.7578],
    "اللاذقية": [35.5312, 35.7908],
    "طرطوس": [34.8890, 35.8864],
    "إدلب": [35.9300, 36.6333],
    "دير الزور": [35.3333, 40.1500],
    "الرقة": [35.9500, 39.0167],
    "الحسكة": [36.5024, 40.7477],
    "درعا": [32.6167, 36.1000],
    "السويداء": [32.7081, 36.5663],
    "القنيطرة": [33.1256, 35.8239],
    "سوريا": [34.8021, 38.9968] # مركز تقريبي لسوريا كاملة
}


# --- 1. الدوال الأساسية وتنسيق العربي ---

def get_connection():
    return sqlite3.connect('billboards_data.db')

def apply_rtl(p):
    """إجبار النص على اليمين بالمنطق العكسي وتفعيل Bidi"""
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT 
    pPr = p._element.get_or_add_pPr()
    bidi = OxmlElement('w:bidi')
    bidi.set(qn('w:val'), '1')
    pPr.append(bidi)
    for run in p.runs:
        rPr = run._element.get_or_add_rPr()
        rtl = OxmlElement('w:rtl')
        rtl.set(qn('w:val'), '1')
        rPr.append(rtl)

def set_table_rtl(table):
    """إجبار الجدول بالكامل على أن يكون يمين لليسار"""
    tblPr = table._element.xpath('w:tblPr')[0]
    bidi = OxmlElement('w:bidiVisual')
    tblPr.append(bidi)

def set_cell_background(cell, color):
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), color)
    cell._tc.get_or_add_tcPr().append(shd)

# --- 2. دالة تصدير الوورد المصلحة محاسبياً ومنطقياً ---

def export_word(customer_name, cart_data, period_name):
    doc = Document('template.docx') if os.path.exists('template.docx') else Document()
    for section in doc.sections:
        section.top_margin = Cm(4.5) 

    p_date = doc.add_paragraph(f"التاريخ: 2026/05/03")
    p_date.alignment = WD_ALIGN_PARAGRAPH.LEFT

    p_cust = doc.add_paragraph()
    p_cust.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_c = p_cust.add_run(f"السادة شركة {customer_name} المحترمين")
    run_c.bold, run_c.font.size = True, Pt(20)

    p_greet = doc.add_paragraph("تحية طيبة وبعد،")
    apply_rtl(p_greet)

    # العبارة المطلوبة بعد سطرين من التحية

    p_stat = doc.add_paragraph()
    p_stat.add_run("نقدم لكم المواقع المتاحة في المحافظات لعرض إعلانكم الوطني من تاريخ  .................  ولغاية  .................")
    apply_rtl(p_stat)

    if cart_data:
        for city, networks in cart_data.items():
            p_city = doc.add_paragraph(f"■ محافظة {city}")
            apply_rtl(p_city)
            
            for net, df in networks.items():
                grouped = df.groupby('الحجم')
                for size, group_df in grouped:
                    p_size = doc.add_paragraph(f"قياس اللوحة: {size}")
                    apply_rtl(p_size)

                    table = doc.add_table(rows=1, cols=2)
                    table.style = 'Table Grid'
                    set_table_rtl(table) 
                    
                    hdr = table.rows[0].cells
                    hdr[0].text = f"الشبكة: {net}"
                    hdr[1].text = "العدد"
                    
                    for cell in hdr:
                        set_cell_background(cell, "660099")
                        for p in cell.paragraphs:
                            apply_rtl(p)
                            for run in p.runs:
                                run.font.color.rgb, run.bold = RGBColor(255, 255, 255), True

                    for _, row in group_df.iterrows():
                        row_cells = table.add_row().cells
                        row_cells[0].text = str(row.get('الموقع', ''))
                        row_cells[1].text = str(row.get('العدد', 1))
                        for cell in row_cells:
                            for p in cell.paragraphs: apply_rtl(p)

                    # --- الحسابات (منع الأصفار) ---
                    total_q = pd.to_numeric(group_df['العدد'], errors='coerce').sum()
                    # استخدام values[0] بدلاً من iloc[0] لضمان القيمة الصافية
                    f_print = float(group_df['fee_print'].values[0]) if 'fee_print' in group_df.columns else 0
                    f_ads = float(group_df['fee_ads'].values[0]) if 'fee_ads' in group_df.columns else 0
                    
                    res_p = total_q * f_print
                    res_a = total_q * f_ads

                    p_sum = doc.add_paragraph()
                    txt = f"العدد: {int(total_q)} | طباعة: {res_p:,.0f}$ | عرض: {res_a:,.0f}$ | الإجمالي: {res_p + res_a:,.0f}$"
                    p_sum.add_run(txt).bold = True
                    apply_rtl(p_sum)
                    doc.add_paragraph()

    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target

# --- 3. واجهة Streamlit ---

if "auth" not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 تسجيل الدخول")
    u, p = st.text_input("User"), st.text_input("Pass", type="password")
    if st.button("Login"):
        if u == "admin" and p == "preview2026":
            st.session_state.auth = True
            st.rerun()
else:
    conn = get_connection()
    if 'cart' not in st.session_state: st.session_state.cart = {}
    
    with st.sidebar:
        if os.path.exists('logo_full.png'): st.image('logo_full.png', width=180)
        page = st.radio("Menu", ["📊 Dashboard", "📄 Quotation"])

       # --- صفحة عرض السعر (Quotation) ---
    if page == "📄 Quotation":
        st.title("📄 بناء عرض سعر ذكي")
        try:
            draw_df = pd.read_sql("SELECT * FROM [اسماء الرسم]", conn)
            sizes = draw_df['الحجم'].unique().tolist()
            
            cust = st.text_input("Customer Name")
            
            c1, c2 = st.columns(2)
            with c1:
                sel_size = st.selectbox("Select Size:", sizes)
            with c2:
                # الفلتر الجديد للتمييز بين عادي وسكوتش
                print_type = st.radio("Quality / النوع:", ["عادي", "سكوتش (بدون كلمة عادي)"], horizontal=True)

            # --- منطق جلب الأجور المطور بناءً على الفلتر ---
            subset = draw_df[draw_df['الحجم'] == sel_size]
            f_print = 0.0
            f_ads = 0.0
            
            for _, row in subset.iterrows():
                name = str(row['اسم الرسم']).strip()
                val = float(row['اجرة الرسم'])
                
                if print_type == "عادي":
                    if "طباعة" in name and "عادي" in name: f_print = val
                    elif "عرض" in name and "عادي" in name: f_ads = val
                else:
                    # للسكوتش: نبحث عن الكلمة دون وجود كلمة "عادي" في النص
                    if "طباعة" in name and "عادي" not in name: f_print = val
                    elif "عرض" in name and "عادي" not in name: f_ads = val

            # تحديد المسميات النهائية التي ستظهر في ملف الوورد
            p_label = "أجور طباعة وتركيب" + (" عادي" if print_type == "عادي" else "")
            a_label = "أجور عرض" + (" عادي" if print_type == "عادي" else "")

            st.info(f"📍 {p_label}: {f_print}$ | {a_label}: {f_ads}$")

            city_l = pd.read_sql("SELECT DISTINCT المحافظة FROM [اعمدة انارة]", conn)['المحافظة'].tolist()
            sel_city = st.selectbox("City", city_l)
            
            # فلترة الأعمدة حسب المقاس المختار والمحافظة
            query = f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة='{sel_city}' AND [الحجم]='{sel_size}'"
            raw = pd.read_sql(query, conn)

            if not raw.empty:
                nets = st.multiselect("Nets", raw['الشبكة'].unique().tolist())
                if st.button("➕ Add to Cart"):
                    if sel_city not in st.session_state.cart: st.session_state.cart[sel_city] = {}
                    for n in nets:
                        st.session_state.cart[sel_city][n] = raw[raw['الشبكة'] == n].assign(**{
                            'الحجم': sel_size, 
                            'fee_print': f_print, 
                            'fee_ads': f_ads,
                            'print_label': p_label, 
                            'ads_label': a_label
                        })
                    st.rerun()

            if st.session_state.cart:
                for c_name, nts in list(st.session_state.cart.items()):
                    for n_name, df_cart in nts.items():
                        with st.expander(f"📍 {c_name} - {n_name}", expanded=True):
                            st.session_state.cart[c_name][n_name] = st.data_editor(df_cart, key=f"ed_{c_name}_{n_name}")
                
                if st.button("🚀 Export Word"):
                    doc_io = export_word(cust, st.session_state.cart, "2026")
                    st.download_button("📥 Download", doc_io, f"Quotation_{cust}.docx")
        except Exception as e: st.error(f"Error: {e}")

    
    # الداشبورد
    if page == "📊 Dashboard":
        st.title("📊 حالة الإشغال والخريطة التفاعلية")
        try:
            # 1. Fetching Data
            df_all = pd.read_sql("SELECT * FROM [اعمدة انارة]", conn)
            df_booked = pd.read_sql("SELECT [رقم اللوحة], [اسم الزبون], [فترة الحجز], [العام] FROM [حجوزات1]", conn)
            df_periods = pd.read_sql("SELECT [no], [namee] FROM [الفترة] ORDER BY [no]", conn)

            # --- Filters Section ---
            st.subheader("🔍 فلاتر البحث")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                p_names = df_periods['namee'].tolist()
                current_p_name = st.selectbox("الفحص بدءاً من فترة:", p_names)
                # FIX: Use .iloc[0] or .values[0] to get the exact integer
                current_no = int(df_periods[df_periods['namee'] == current_p_name]['no'].values[0])
            
            with col2:
                target_year = st.number_input("العام:", value=2026)
            
            with col3:
                city_list = ["الكل"] + sorted([str(x) for x in df_all['المحافظة'].unique() if x])
                city_sel = st.selectbox("المحافظة:", city_list)
            
            with col4:
                status_sel = st.radio("الحالة:", ["الكل", "متاح", "محجوز"], horizontal=True)

            # --- Logic Processing ---
            df_booked_timed = pd.merge(df_booked, df_periods, left_on='فترة الحجز', right_on='namee', how='left')
            
            # Filtering future bookings based on period number 'no'
            future_bookings = df_booked_timed[
                (df_booked_timed['no'] >= current_no) & 
                (df_booked_timed['العام'] == target_year)
            ]

            latest_booking = future_bookings.sort_values('no').groupby('رقم اللوحة').last().reset_index()
            df_m = pd.merge(df_all, latest_booking[['رقم اللوحة', 'اسم الزبون', 'فترة الحجز', 'no']], on='رقم اللوحة', how='left')

            # --- Map Centering Logic ---
            if city_sel == "الكل":
                map_center = SYRIA_CITIES_COORDS["سوريا"]
                zoom_val = 7
            else:
                map_center = SYRIA_CITIES_COORDS.get(city_sel, SYRIA_CITIES_COORDS["سوريا"])
                zoom_val = 12

            # Apply final display filters
            df_f = df_m.copy()
            if city_sel != "الكل":
                df_f = df_f[df_f['المحافظة'] == city_sel]
            
            if status_sel == "محجوز":
                df_f = df_f[df_f['no'].notna()]
            elif status_sel == "متاح":
                df_f = df_f[df_f['no'].isna()]

            # --- Folium Map Rendering ---
            st.subheader(f"📍 خريطة {city_sel if city_sel != 'الكل' else 'سوريا'}")
            
            m = folium.Map(location=map_center, zoom_start=zoom_val)
            marker_cluster = MarkerCluster().add_to(m)

            for _, row in df_f.iterrows():
                if pd.notnull(row['Latitude']) and pd.notnull(row['Longitude']):
                    is_b = pd.notnull(row['no'])
                    color = 'red' if is_b else 'purple'
                    pop = f"<div style='direction:rtl; text-align:right; font-family:tahoma;'><b>{row['اسم العمود']}</b><br>{'محجوز لـ: ' + str(row['اسم الزبون']) if is_b else 'متاح'}</div>"
                    folium.Marker([row['Latitude'], row['Longitude']], 
                                  popup=folium.Popup(pop, max_width=200),
                                  icon=folium.Icon(color=color)).add_to(marker_cluster)

            # The dynamic key ensures the map moves when the city selection changes
            st_folium(m, width="100%", height=500, key=f"map_{city_sel}_{current_no}")
            
            st.dataframe(df_f.drop(columns=['no'], errors='ignore'), use_container_width=True)

        except Exception as e:
            st.error(f"⚠️ حدث خطأ: {e}")
            



      
