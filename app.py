import streamlit as st
import pandas as pd
import sqlite3
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
# --- Database Helpers ---
def get_connection():
    return sqlite3.connect('billboards_data.db')

def init_offers_db():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS offers_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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

# استدعاء الدالة الآن أصبح آمناً لأن get_connection معرفة فوقها
init_offers_db()

# --- 1. Constants & Configuration ---
st.set_page_config(page_title="PreView Ads ERP - Phase 2", layout="wide")

SYRIA_CITIES_COORDS = {
    "دمشق": [33.5138, 36.2765], "ريف دمشق": [33.45, 36.35], "حلب": [36.2021, 37.1343],
    "حمص": [34.7324, 36.7137], "حماة": [35.1318, 36.7578], "الالاذقية": [35.5312, 35.7908],
    "طرطوس": [34.8890, 35.8864], "سوريا": [34.80, 38.99]
}
def init_offers_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS offers_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_name TEXT,
        offer_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        cart_json TEXT,  -- تخزين السلة بالكامل هنا
        start_p TEXT,
        end_p TEXT,
        year INTEGER,
        status TEXT DEFAULT 'Pending' -- 'Pending' أو 'Confirmed'
    )''')
    conn.commit()
    conn.close()

init_offers_db()

def get_connection():
    return sqlite3.connect('billboards_data.db')

# --- 2. RTL & Word Helpers ---
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

# --- 3. Word Export Logic ---
def export_word(customer_name, cart_data, start_p, end_p):
    doc = Document('template.docx') if os.path.exists('template.docx') else Document()
    for section in doc.sections: section.top_margin = Cm(4.5) 
    
    # لون الموف الخاص باللوجو (RGB: 102, 0, 153) - يمكنك تعديله لدرجة أدق إذا أردت
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
                
                # --- تلوين صف العنوان باللون الموف ---
                for cell in hdr:
                    shading_elm = OxmlElement('w:shd')
                    shading_elm.set(qn('w:fill'), PURPLE_COLOR)
                    cell._element.get_or_add_tcPr().append(shading_elm)
                    # تغيير لون الخط للأبيض ليتناسب مع الخلفية الموف
                    p = cell.paragraphs[0]
                    run = p.add_run()
                    run.font.color.rgb = RGBColor(255, 255, 255)
                
                hdr[0].text = f"الشبكة: {net}"
                hdr[1].text = "العدد"
                for cell in hdr: apply_rtl(cell)

                for _, row in group_df.iterrows():
                    row_cells = table.add_row().cells
                    row_cells[0].text = str(row['الموقع'])
                    row_cells[1].text = str(row['العدد'])
                    for cell in row_cells: apply_rtl(cell)

                # --- حساب الأجور المحدثة (سكوتش / عادي) ---
                total_q = pd.to_numeric(group_df['العدد']).sum()
                f_p = float(group_df['fee_print'].iloc[0])
                f_a = float(group_df['fee_ads'].iloc[0])
                lbl_p = group_df['print_label'].iloc[0]
                lbl_a = group_df['ads_label'].iloc[0]
                
                sum_print = total_q * f_p
                sum_ads = total_q * f_a
                total_all = sum_print + sum_ads
                
                p_sum = doc.add_paragraph()
                txt = (f"العدد: {int(total_q)} | {lbl_p}: {sum_print:,.0f}$ | "
                       f"{lbl_a}: {sum_ads:,.0f}$ | الإجمالي: {total_all:,.0f}$")
                
                run = p_sum.add_run(txt)
                run.bold = True
                run.font.color.rgb = RGBColor(0, 0, 0) # لون موف للنص الإجمالي
                apply_rtl(p_sum)
                    # --- إضافة ملاحظة الصلاحية في نهاية المستند ---
    doc.add_paragraph() # سطر فارغ للتباعد
    p_note = doc.add_paragraph()
    p_note.alignment = WD_ALIGN_PARAGRAPH.LEFT # لضمان الظهور من اليمين في التنسيق العربي
    
    run_note = p_note.add_run("• ملاحظة: هذه المواقع المتاحة سارية حتى 48 ساعة من تاريخ إرسالها للشركة.")
    run_note.bold = True
    run_note.font.size = Pt(12)
    run_note.font.color.rgb = RGBColor(0, 0, 0) # لون أحمر هادئ للتنبيه
    
    apply_rtl(p_note) # تطبيق اتجاه النص العربي
    
    # حفظ الملف

    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target


# استمرار الكود في الدفعة الثانية...
# --- 4. Main App Logic (Part 2) ---
if "auth" not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 تسجيل الدخول")
    u, p = st.text_input("User"), st.text_input("Pass", type="password")
    if st.button("Login"):
        if u == "admin" and p == "preview2026": st.session_state.auth = True; st.rerun()
else:
    conn = get_connection()
    if 'cart' not in st.session_state: st.session_state.cart = {}
    
    with st.sidebar:
        if os.path.exists('logo_full.png'): st.image('logo_full.png', width=180)
        page = st.radio("القائمة", ["📊 Dashboard", "📄 Quotation", "📋 تقرير المتاح المجمع"])
        if st.button("تسجيل الخروج"): st.session_state.auth = False; st.rerun()

        # --- Page: Quotation (نسخة مستقرة وشاملة لمنطق الإتاحة والأجور) ---
    if page == "📄 Quotation":
        st.title("📄 بناء عرض سعر وتثبيت حجز")
        try:
            # 1. جلب البيانات الأساسية من قاعدة البيانات
            draw_df = pd.read_sql("SELECT * FROM [اسماء الرسم]", conn)
            df_periods = pd.read_sql("SELECT [no], [namee] FROM [الفترة] ORDER BY [no]", conn)
            sizes = draw_df['الحجم'].unique().tolist()
            
            cust = st.text_input("اسم الزبون")
            
            c1, c2, c3 = st.columns(3)
            with c1: sel_size = st.selectbox("اختر المقاس:", sizes)
            with c2: print_type = st.radio("نوع الطباعة:", ["عادي", "سكوتش"], horizontal=True)
            with c3: b_year = st.number_input("العام:", value=2026)

            # 2. تحديد الفترات الزمنية (لفحص الإتاحة)
            st.write("---")
            st.subheader("🗓️ تحديد فترة الحجز المطلوب")
            cp1, cp2 = st.columns(2)
            with cp1: start_p = st.selectbox("من فترة:", df_periods['namee'].tolist())
            with cp2: end_p = st.selectbox("إلى فترة:", df_periods['namee'].tolist(), index=len(df_periods)-1)

            # استخراج أرقام الفترات المستهدفة
            s_no = int(df_periods[df_periods['namee'] == start_p]['no'].iloc[0])
            e_no = int(df_periods[df_periods['namee'] == end_p]['no'].iloc[0])
            target_period_names = df_periods[(df_periods['no'] >= s_no) & (df_periods['no'] <= e_no)]['namee'].tolist()

            # 3. حساب الأجور (طباعة وعرض)
            subset = draw_df[draw_df['الحجم'] == sel_size]
            f_print, f_ads = 0.0, 0.0
            for _, row in subset.iterrows():
                name, val = str(row['اسم الرسم']).strip(), float(row['اجرة الرسم'])
                if print_type == "عادي":
                    if "طباعة" in name and "عادي" in name: f_print = val
                    elif "عرض" in name and "عادي" in name: f_ads = val
                else:
                    if "طباعة" in name and "عادي" not in name: f_print = val
                    elif "عرض" in name and "عادي" not in name: f_ads = val

            p_label = f"أجور طباعة وتركيب {'عادي' if print_type=='عادي' else 'سكوتش'}"
            a_label = f"أجور عرض {'عادي' if print_type=='عادي' else 'سكوتش'}"
            st.info(f"💰 {p_label}: {f_print}$ | {a_label}: {f_ads}$")

            # 4. فلترة المواقع المتاحة فقط (التي ليست محجوزة في الفترات المختارة)
            city_l = pd.read_sql("SELECT DISTINCT المحافظة FROM [اعمدة انارة]", conn)['المحافظة'].tolist()
            sel_city = st.selectbox("المحافظة:", city_l)
            
            type_l = pd.read_sql(f"SELECT DISTINCT [توصيف العمود] FROM [اعمدة انارة] WHERE المحافظة='{sel_city}'", conn)['توصيف العمود'].tolist()
            sel_types = st.multiselect("توصيف المواقع:", type_l)

            # استعلام لجلب اللوحات المحجوزة في هذه الفترة
            booked_boards_query = f"SELECT DISTINCT [رقم اللوحة] FROM [حجوزات1] WHERE [العام]={b_year} AND [فترة الحجز] IN ({str(target_period_names)[1:-1]})"
            booked_boards = pd.read_sql(booked_boards_query, conn)['رقم اللوحة'].tolist()

            # استعلام جلب المواقع مع استثناء المحجوز
            main_query = f"SELECT [رقم اللوحة], [اسم العمود] as الموقع, [العدد], [الشبكة], [توصيف العمود] FROM [اعمدة انارة] WHERE المحافظة='{sel_city}' AND [الحجم]='{sel_size}'"
            if booked_boards:
                main_query += f" AND [رقم اللوحة] NOT IN ({str(booked_boards)[1:-1]})"
            if sel_types:
                main_query += f" AND [توصيف العمود] IN ({str(sel_types)[1:-1]})"
            
            raw = pd.read_sql(main_query, conn)
            
            if not raw.empty:
                st.success(f"تم العثور على {len(raw)} موقع متاح")
                nets = st.multiselect("اختر الشبكات للإضافة:", raw['الشبكة'].unique().tolist())
                if st.button("➕ إضافة المتاحة للسلة"):
                    if sel_city not in st.session_state.cart: st.session_state.cart[sel_city] = {}
                    for n in nets:
                        st.session_state.cart[sel_city][n] = raw[raw['الشبكة'] == n].assign(**{
                            'الحجم': sel_size, 'fee_print': f_print, 'fee_ads': f_ads, 
                            'print_label': p_label, 'ads_label': a_label, 'year': b_year
                        })
                    st.rerun()
            else:
                st.warning("⚠️ لا توجد مواقع متاحة لهذا المقاس في الفترات المختارة.")

            # 5. إدارة السلة وتثبيت الحجز
            if st.session_state.cart:
                st.divider()
                st.subheader("🛒 المواقع المختارة في العرض")
                for c_n in list(st.session_state.cart.keys()):
                    for n_n in list(st.session_state.cart[c_n].keys()):
                        with st.expander(f"📍 {c_n} - {n_n}", expanded=True):
                            col_table, col_del = st.columns([5, 1])
                            with col_table:
                                st.session_state.cart[c_n][n_n] = st.data_editor(st.session_state.cart[c_n][n_n], key=f"ed_{c_n}_{n_n}", num_rows="dynamic")
                            with col_del:
                                if st.button("🗑️ حذف", key=f"btn_{c_n}_{n_n}"):
                                    del st.session_state.cart[c_n][n_n]
                                    if not st.session_state.cart[c_n]: del st.session_state.cart[c_n]
                                    st.rerun()

                # العمليات النهائية المحدثة (4 أزرار بدلاً من 3)
                               # --- العمليات النهائية: تصدير، حفظ، تثبيت، تفريغ ---
                # --- العمليات النهائية: تصدير، حفظ، تثبيت، تفريغ ---
                              # --- العمليات النهائية المحدثة (إزاحة مضبوطة) ---
                st.write("---")
                b1, b2, b3, b4 = st.columns(4)
                
                with b1:
                    if st.button("🚀 تصدير ملف Word"):
                        if not cust:
                            st.error("أدخل اسم الزبون")
                        else:
                            doc_io = export_word(cust, st.session_state.cart, start_p, end_p)
                            st.download_button("📥 تحميل العرض", doc_io, f"Quotation_{cust}.docx")

                with b2:
                    if st.button("💾 حفظ كمسودة"):
                        if not cust:
                            st.error("أدخل اسم الزبون أولاً")
                        else:
                            import json
                            cart_json = json.dumps({c: {n: df.to_dict() for n, df in nets.items()} 
                                                 for c, nets in st.session_state.cart.items()}, ensure_ascii=False)
                            cursor = conn.cursor()
                            # تحديد الأعمدة بوضوح لحل خطأ عدد الأعمدة
                            query = """INSERT INTO offers_history 
                                       (client_name, cart_json, start_p, end_p, year, status) 
                                       VALUES (?, ?, ?, ?, ?, ?)"""
                            cursor.execute(query, (cust, cart_json, start_p, end_p, b_year, 'Pending'))
                            conn.commit()
                            st.success(f"✅ تم حفظ عرض {cust} في المسودات.")

                with b3:
                    if st.button("✅ تثبيت نهائي"):
                        if not cust:
                            st.error("أدخل اسم الزبون أولاً")
                        else:
                            new_recs = []
                            for city, nets in st.session_state.cart.items():
                                for net, df in nets.items():
                                    for _, row in df.iterrows():
                                        for p_name in target_period_names:
                                            new_recs.append((str(row['رقم اللوحة']), cust, p_name, b_year))
                            
                            cursor = conn.cursor()
                            cursor.executemany("INSERT INTO حجوزات1 ([رقم اللوحة], [اسم الزبون], [فترة الحجز], [العام]) VALUES (?,?,?,?)", new_recs)
                            conn.commit()
                            st.success(f"تم التثبيت النهائي لـ {len(new_recs)} سجل!")
                            st.session_state.cart = {}
                            st.rerun()

                with b4:
                    if st.button("🔴 تفريغ السلة"):
                        st.session_state.cart = {}
                        st.rerun()

        except Exception as e:
            st.error(f"خطأ فني: {e}")


    elif page == "📋 تقرير المتاح المجمع":
        st.title("📋 تقرير المواقع المتاحة (مجمع)")
        
        df_periods = pd.read_sql("SELECT [no], [namee] FROM [الفترة] ORDER BY [no]", conn)
        
        c1, c2, c3 = st.columns(3)
        with c1: start_p = st.selectbox("من فترة:", df_periods['namee'].tolist(), key="rep_s")
        with c2: end_p = st.selectbox("إلى فترة:", df_periods['namee'].tolist(), index=len(df_periods)-1, key="rep_e")
        with c3: b_year = st.number_input("العام:", value=2026, key="rep_y")

        # منطق استخراج المتاح (نجعله يعمل تلقائياً عند تغيير الاختيارات لضمان وجود المتغير)
        s_no = int(df_periods[df_periods['namee'] == start_p]['no'].iloc[0])
        e_no = int(df_periods[df_periods['namee'] == end_p]['no'].iloc[0])
        target_period_names = df_periods[(df_periods['no'] >= s_no) & (df_periods['no'] <= e_no)]['namee'].tolist()

        # جلب البيانات خارج الـ Button لضمان توفر available_df دائماً
        booked_query = f"SELECT DISTINCT [رقم اللوحة] FROM [حجوزات1] WHERE [العام]={b_year} AND [فترة الحجز] IN ({str(target_period_names)[1:-1]})"
        booked_boards = pd.read_sql(booked_query, conn)['رقم اللوحة'].tolist()
        all_boards = pd.read_sql("SELECT [رقم اللوحة], [اسم العمود] as الموقع, [المحافظة], [الشبكة], [الحجم], [توصيف العمود], [العدد] FROM [اعمدة انارة]", conn)
        
        # هذا هو المتغير الذي سبب الخطأ، الآن هو متاح في كل الصفحة
        available_df = all_boards[~all_boards['رقم اللوحة'].isin(booked_boards)]

        if available_df.empty:
            st.warning("لا توجد مواقع متاحة في هذا النطاق الزمني.")
        else:
            st.info(f"إجمالي المواقع المتاحة حالياً: {len(available_df)}")
            
            # زر التصدير العام
            if st.button("🌍 توليد ملف التقرير العام لجميع المحافظات"):
                with st.spinner("جاري تحضير الملف..."):
                    full_cart = {}
                    for city in available_df['المحافظة'].unique():
                        city_df = available_df[available_df['المحافظة'] == city]
                        full_cart[city] = {net: city_df[city_df['الشبكة']==net].assign(
                            fee_print=0, fee_ads=0, print_label="متاح", ads_label="تقرير"
                        ) for net in city_df['الشبكة'].unique()}
                    
                    doc_io = export_word("تقرير المتاح العام", full_cart, start_p, end_p)
                    st.success("✅ تم تجهيز التقرير")
                    st.download_button("📥 اضغط هنا لتحميل التقرير الكامل", doc_io, "Full_Inventory.docx")

            # عرض المحافظات
            for city in sorted(available_df['المحافظة'].unique()):
                with st.expander(f"📍 محافظة {city}"):
                    city_df = available_df[available_df['المحافظة'] == city]
                    summary = city_df.groupby(['الشبكة', 'الحجم', 'توصيف العمود']).agg({'العدد': 'sum', 'رقم اللوحة': 'count'}).rename(columns={'رقم اللوحة': 'عدد المواقع'})
                    st.table(summary)



 # --- Page: Dashboard ---
    elif page == "📊 Dashboard":
        st.title("📊 حالة الإشغال والخريطة")
        try:
            df_all = pd.read_sql("SELECT * FROM [اعمدة انارة]", conn)
            df_booked = pd.read_sql("SELECT [رقم اللوحة], [اسم الزبون], [فترة الحجز], [العام] FROM [حجوزات1]", conn)
            df_periods = pd.read_sql("SELECT [no], [namee] FROM [الفترة] ORDER BY [no]", conn)

            col1, col2, col3, col4 = st.columns(4)
            with col1: 
                curr_p = st.selectbox("بدءاً من:", df_periods['namee'].tolist())
                curr_no = int(df_periods[df_periods['namee'] == curr_p]['no'].iloc[0])
            with col2: target_ya = st.number_input("العام:", value=2026)
            with col3: city_sel = st.selectbox("المحافظة:", ["الكل"] + sorted(df_all['المحافظة'].unique().tolist()))
            with col4: status_sel = st.radio("الحالة:", ["الكل", "متاح", "محجوز"])

            df_b_t = pd.merge(df_booked, df_periods, left_on='فترة الحجز', right_on='namee', how='left')
            fut_b = df_b_t[(df_b_t['no'] >= curr_no) & (df_b_t['العام'] == target_ya)]
            latest_b = fut_b.sort_values('no').groupby('رقم اللوحة').last().reset_index()
            df_m = pd.merge(df_all, latest_b[['رقم اللوحة', 'اسم الزبون', 'no']], on='رقم اللوحة', how='left')

            if city_sel != "الكل": df_m = df_m[df_m['المحافظة'] == city_sel]
            if status_sel == "محجوز": df_m = df_m[df_m['no'].notna()]
            elif status_sel == "متاح": df_m = df_m[df_m['no'].isna()]

            m_center = SYRIA_CITIES_COORDS.get(city_sel, SYRIA_CITIES_COORDS["سوريا"])
            m = folium.Map(location=m_center, zoom_start=(7 if city_sel == "الكل" else 12))
            cluster = MarkerCluster().add_to(m)
            for _, r in df_m.iterrows():
                if pd.notnull(r['Latitude']):
                    folium.Marker([r['Latitude'], r['Longitude']], popup=f"{r['اسم العمود']}", icon=folium.Icon(color='red' if pd.notnull(r['no']) else 'purple')).add_to(cluster)
            st_folium(m, width="100%", height=500, key=f"map_{city_sel}")
            st.dataframe(df_m.drop(columns=['no'], errors='ignore'), use_container_width=True)
        except Exception as e: st.error(f"Error: {e}")

    conn.close()
