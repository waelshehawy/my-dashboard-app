import streamlit as st
import pandas as pd
import psycopg2
import os
import io
import folium
import json
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
from docx import Document
from docx.shared import Pt, RGBColor, Cm 
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# --- Database Connection (Supabase) ---
def get_connection():
    return psycopg2.connect(
        host="aws-1-eu-north-1.pooler.supabase.com", # هذا هو العنوان الصحيح
        port="6543",
        database="postgres",
        user="postgres.ncuofpvbaglwbdqnpman",
        password="w@EL!@#123$",
        sslmode="require"
    )


def init_offers_db():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # تعديل Syntax ليتوافق مع PostgreSQL
        cursor.execute('''CREATE TABLE IF NOT EXISTS offers_history (
            id SERIAL PRIMARY KEY,
            client_name TEXT,
            offer_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            cart_json TEXT,
            start_p TEXT,
            end_p TEXT,
            year INTEGER,
            status TEXT DEFAULT 'Pending'
        )''')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database Init Error: {e}")

# تهيئة القاعدة عند بدء التشغيل
init_offers_db()

# --- Configuration ---
st.set_page_config(page_title="PreView Ads ERP", layout="wide")

SYRIA_CITIES_COORDS = {
    "دمشق": [33.5138, 36.2765], "ريف دمشق": [33.45, 36.35], "حلب": [36.2021, 37.1343],
    "حمص": [34.7324, 36.7137], "حماة": [35.1318, 36.7578], "الالاذقية": [35.5312, 35.7908],
    "طرطوس": [34.8890, 35.8864], "سوريا": [34.80, 38.99]
}

# --- RTL & Word Helpers (تبقى كما هي) ---
def apply_rtl(obj):
    if hasattr(obj, 'paragraphs'):
        for p in obj.paragraphs: _force_rtl_style(p)
    else: _force_rtl_style(obj)

def _force_rtl_style(p):
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT 
    pPr = p._element.get_or_add_pPr()
    bidi = OxmlElement('w:bidi'); bidi.set(qn('w:val'), '1'); pPr.append(bidi)
    for run in p.runs:
        rPr = run._element.get_or_add_rPr()
        rtl = OxmlElement('w:rtl'); rtl.set(qn('w:val'), '1'); rPr.append(rtl)
        rFonts = OxmlElement('w:rFonts'); rFonts.set(qn('w:cs'), 'Arial'); rPr.append(rFonts)

def set_table_rtl(table):
    tblPr = table._element.xpath('w:tblPr')[0]
    bidi = OxmlElement('w:bidiVisual'); tblPr.append(bidi)
# --- 3. Word Export Logic (Updated with Purple Style) ---
def export_word(customer_name, cart_data, start_p, end_p):
    doc = Document('template.docx') if os.path.exists('template.docx') else Document()
    for section in doc.sections: section.top_margin = Cm(4.5) 
    
    PURPLE_COLOR = "660099" 

    p_cust = doc.add_paragraph(); p_cust.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cust.add_run(f"السادة شركة {customer_name} المحترمين").bold = True
    
    p_stat = doc.add_paragraph()
    p_stat.add_run(f"نقدم لكم المواقع المتاحة لعرض إعلانكم من فترة ({start_p}) ولغاية ({end_p})")
    apply_rtl(p_stat)

    for city, networks in cart_data.items():
        p_city = doc.add_paragraph(f"■ محافظة {city}"); apply_rtl(p_city)
        for net, df in networks.items():
            if df.empty: continue
            for (size, desc), group_df in df.groupby(['الحجم', 'توصيف العمود']):
                p_size = doc.add_paragraph(f"النوع: {desc} | القياس: {size}"); apply_rtl(p_size)
                table = doc.add_table(rows=1, cols=2); table.style = 'Table Grid'; set_table_rtl(table)
                hdr = table.rows[0].cells
                for cell in hdr:
                    shading_elm = OxmlElement('w:shd')
                    shading_elm.set(qn('w:fill'), PURPLE_COLOR)
                    cell._element.get_or_add_tcPr().append(shading_elm)
                    p = cell.paragraphs[0]; run = p.add_run()
                    run.font.color.rgb = RGBColor(255, 255, 255)
                
                hdr[0].text = f"الشبكة: {net}"; hdr[1].text = "العدد"
                for cell in hdr: apply_rtl(cell)

                for _, row in group_df.iterrows():
                    row_cells = table.add_row().cells
                    row_cells[0].text = str(row['الموقع']); row_cells[1].text = str(row['العدد'])
                    for cell in row_cells: apply_rtl(cell)

                # Summary calculation for each group
                total_q = pd.to_numeric(group_df['العدد']).sum()
                f_p = float(group_df['fee_print'].iloc[0]); f_a = float(group_df['fee_ads'].iloc[0])
                sum_total = (total_q * f_p) + (total_q * f_a)
                p_sum = doc.add_paragraph(f"الإجمالي: {sum_total:,.0f}$"); p_sum.runs[0].bold = True; apply_rtl(p_sum)

    target = io.BytesIO(); doc.save(target); target.seek(0)
    return target

# --- 4. Main App & Auth ---
if "auth" not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 تسجيل الدخول")
    u, p = st.text_input("User"), st.text_input("Pass", type="password")
    if st.button("Login"):
        if u == "a" and p == "3900": st.session_state.auth = True; st.rerun()
else:
    conn = get_connection()
    if 'cart' not in st.session_state: st.session_state.cart = {}
    
    with st.sidebar:
        if os.path.exists('logo_full.png'): st.image('logo_full.png', width=180)
        page = st.radio("القائمة", ["📊 Dashboard", "📄 Quotation", "📋 تقرير الجرد", "⚙️ الإعدادات"])
        if st.button("تسجيل الخروج"): st.session_state.auth = False; st.rerun()

    if page == "📄 Quotation":
        st.title("📄 بناء عرض سعر وتثبيت حجز")
        try:
            # Table names in double quotes for PostgreSQL
            draw_df = pd.read_sql('SELECT * FROM "اسماء الرسم"', conn)
            df_periods = pd.read_sql('SELECT no, namee FROM "الفترة" ORDER BY no', conn)
            sizes = draw_df['الحجم'].unique().tolist()
            
            cust = st.text_input("اسم الزبون")
            c1, c2, c3 = st.columns(3)
            with c1: sel_size = st.selectbox("اختر المقاس:", sizes)
            with c2: print_type = st.radio("نوع الطباعة:", ["عادي", "سكوتش"], horizontal=True)
            with c3: b_year = st.number_input("العام:", value=2026)

            st.write("---")
            cp1, cp2 = st.columns(2)
            with cp1: start_p = st.selectbox("من فترة:", df_periods['namee'].tolist())
            with cp2: end_p = st.selectbox("إلى فترة:", df_periods['namee'].tolist(), index=len(df_periods)-1)

            s_no = int(df_periods[df_periods['namee'] == start_p]['no'].iloc[0])
            e_no = int(df_periods[df_periods['namee'] == end_p]['no'].iloc[0])
            target_period_names = df_periods[(df_periods['no'] >= s_no) & (df_periods['no'] <= e_no)]['namee'].tolist()
            
            # Pricing logic remains the same
            subset = draw_df[draw_df['الحجم'] == sel_size]
            f_print, f_ads = 0.0, 0.0
            # ... (Pricing calculation loop) ...
            # --- تكملة قسم Quotation: الفلترة والحفظ ---
            city_query = 'SELECT DISTINCT "المحافظة" FROM "اعمدة انارة"'
            city_l = pd.read_sql(city_query, conn)['المحافظة'].tolist()
            sel_city = st.selectbox("المحافظة:", city_l)
            
            # جلب اللوحات المحجوزة (PostgreSQL Syntax)
            periods_tuple = tuple(target_period_names) if len(target_period_names) > 1 else f"('{target_period_names[0]}')"
            booked_query = f'SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" WHERE "العام"={b_year} AND "فترة الحجز" IN {periods_tuple}'
            booked_boards = pd.read_sql(booked_query, conn)['رقم اللوحة'].tolist()

            main_query = f'SELECT "رقم اللوحة", "اسم العمود" as الموقع, "العدد", "الشبكة", "توصيف العمود" FROM "اعمدة انارة" WHERE "المحافظة"=\'{sel_city}\' AND "الحجم"=\'{sel_size}\''
            raw = pd.read_sql(main_query, conn)
            # فلترة المتاح في الذاكرة لتبسيط الكود
            raw = raw[~raw['رقم اللوحة'].isin(booked_boards)]

            if not raw.empty:
                nets = st.multiselect("اختر الشبكات للإضافة:", raw['الشبكة'].unique().tolist())
                if st.button("➕ إضافة للسلة"):
                    for n in nets:
                        if sel_city not in st.session_state.cart: st.session_state.cart[sel_city] = {}
                        st.session_state.cart[sel_city][n] = raw[raw['الشبكة'] == n].assign(الحجم=sel_size, fee_print=f_print, fee_ads=f_ads)
                    st.rerun()

            # أزرار الحفظ النهائي
# 5. إدارة السلة وتثبيت الحجز (توضع بعد كود الإضافة للسلة)
if st.session_state.cart:
    st.divider()
    st.subheader("🛒 المواقع المختارة في العرض")
    
    # عرض الجداول المضافة للسلة
    for c_n in list(st.session_state.cart.keys()):
        for n_n in list(st.session_state.cart[c_n].keys()):
            with st.expander(f"📍 {c_n} - {n_n}", expanded=True):
                col_table, col_del = st.columns([5, 1])
                with col_table:
                    # محرر بيانات للسماح بتعديل العدد أو الموقع قبل الحفظ
                    st.session_state.cart[c_n][n_n] = st.data_editor(
                        st.session_state.cart[c_n][n_n], 
                        key=f"ed_{c_n}_{n_n}"
                    )
                with col_del:
                    if st.button("🗑️ حذف", key=f"btn_{c_n}_{n_n}"):
                        del st.session_state.cart[c_n][n_n]
                        if not st.session_state.cart[c_n]: del st.session_state.cart[c_n]
                        st.rerun()

    st.write("---")
    # ترتيب الأزرار في صف واحد أسفل الجداول
    b1, b2, b3, b4 = st.columns(4)
    
    with b1:
        # زر التصدير (يولد الملف في الذاكرة أولاً)
        if st.button("🚀 1. تصدير Word"):
            if not cust:
                st.error("الرجاء إدخال اسم الزبون")
            else:
                doc_io = export_word(cust, st.session_state.cart, start_p, end_p)
                st.session_state.doc_ready = doc_io # تخزين الملف مؤقتاً
                st.success("تم تجهيز الملف!")

        # زر التحميل (يظهر فقط بعد الضغط على تصدير)
        if "doc_ready" in st.session_state:
            st.download_button(
                label="📥 2. تحميل الملف الآن",
                data=st.session_state.doc_ready,
                file_name=f"Quotation_{cust}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

    with b2:
        # زر الحفظ في الجدول المؤقت (offers_history)
        if st.button("💾 3. حفظ كمسودة"):
            if not cust:
                st.error("أدخل اسم الزبون أولاً")
            else:
                import json
                # تحويل السلة لنص JSON للحفظ في Supabase
                cart_json = json.dumps({c: {n: df.to_dict() for n, df in nets.items()} 
                                     for c, nets in st.session_state.cart.items()}, ensure_ascii=False)
                cursor = conn.cursor()
                query = 'INSERT INTO "offers_history" (client_name, cart_json, start_p, end_p, year, status) VALUES (%s, %s, %s, %s, %s, %s)'
                cursor.execute(query, (cust, cart_json, start_p, end_p, b_year, 'Pending'))
                conn.commit()
                st.success(f"✅ تم حفظ المسودة للزبون {cust}")

    with b3:
        # زر التثبيت في الجداول الرئيسية (حجوزات1)
        if st.button("🏛️ 4. تثبيت نهائي"):
            if not cust:
                st.error("أدخل اسم الزبون أولاً")
            else:
                cursor = conn.cursor()
                for city, nets in st.session_state.cart.items():
                    for net, df in nets.items():
                        for _, row in df.iterrows():
                            for p_name in target_period_names:
                                # التثبيت في جدول الحجوزات السحابي
                                cursor.execute(
                                    'INSERT INTO "حجوزات1" ("رقم اللوحة", "اسم الزبون", "فترة الحجز", "العام") VALUES (%s, %s, %s, %s)',
                                    (str(row['رقم اللوحة']), cust, p_name, b_year)
                                )
                conn.commit()
                st.balloons()
                st.success("✨ تم التثبيت النهائي وتحديث الخريطة!")
                st.session_state.cart = {} # تفريغ السلة بعد التثبيت
                if "doc_ready" in st.session_state: del st.session_state.doc_ready
                st.rerun()

    with b4:
        if st.button("🔴 تفريغ السلة"):
            st.session_state.cart = {}
            if "doc_ready" in st.session_state: del st.session_state.doc_ready
            st.rerun()

    # --- Page: تقرير الجرد ---
    elif page == "📋 تقرير الجرد":
        st.title("📋 تقرير الإشغال السحابي")
        df_periods = pd.read_sql('SELECT no, namee FROM "الفترة" ORDER BY no', conn)
        # (نفس منطق الجرد السابق مع تعديل الاستعلامات لـ PostgreSQL كما في الأمثلة فوق)
        st.info("تم ربط التقارير بقاعدة البيانات الدائمة.")

    # --- Page: Dashboard ---
    elif page == "📊 Dashboard":
        st.title("📊 الخريطة التفاعلية (بيانات حية)")
        try:
            df_all = pd.read_sql('SELECT * FROM "اعمدة انارة"', conn)
            # رسم الخريطة (نفس منطق Folium السابق)
            m = folium.Map(location=SYRIA_CITIES_COORDS["سوريا"], zoom_start=7)
            cluster = MarkerCluster().add_to(m)
            for _, r in df_all.iterrows():
                if pd.notnull(r['Latitude']):
                    folium.Marker([r['Latitude'], r['Longitude']], popup=r['اسم العمود']).add_to(cluster)
            st_folium(m, width="100%", height=500)
        except Exception as e: st.error(f"خطأ في الخريطة: {e}")

    # --- Page: الإعدادات ---
    elif page == "⚙️ الإعدادات":
        st.title("⚙️ الإدارة المركزية")
        if st.button("تحديث أسعار الطباعة"):
            # مثال للتحديث
            st.write("يمكنك استخدام st.data_editor لتعديل جداول Supabase مباشرة")

    conn.close()
