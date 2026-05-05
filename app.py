import streamlit as st
import pandas as pd
import psycopg2  # تم التغيير من sqlite3 إلى psycopg2
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

# --- 1. Database Helpers (تعديل للربط مع Supabase) ---
def get_connection():
    # تأكد من أن host هو العنوان التقني للسيرفر وليس رابط موقع
    return psycopg2.connect(
        host="aws-1-eu-north-1.pooler.supabase.com", 
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
        # SERIAL في PostgreSQL تعادل AUTOINCREMENT في SQLite
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
        st.error(f"خطأ في تهيئة قاعدة البيانات: {e}")

# استدعاء تهيئة الجدول المؤقت عند بدء التطبيق
init_offers_db()

# --- 2. Constants & Configuration ---
st.set_page_config(page_title="PreView Ads ERP - Cloud Version", layout="wide")

SYRIA_CITIES_COORDS = {
    "دمشق": [33.5138, 36.2765], "ريف دمشق": [33.45, 36.35], "حلب": [36.2021, 37.1343],
    "حمص": [34.7324, 36.7137], "حماة": [35.1318, 36.7578], "الالاذقية": [35.5312, 35.7908],
    "طرطوس": [34.8890, 35.8864], "سوريا": [34.80, 38.99]
}


# --- 4. Main App Logic (Part 2 - Cloud Version) ---
if "auth" not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 تسجيل الدخول")
    u, p = st.text_input("User"), st.text_input("Pass", type="password")
    if st.button("Login"):
        if u == "a" and p == "3900": 
            st.session_state.auth = True
            st.rerun()
else:
    conn = get_connection()
    if 'cart' not in st.session_state: st.session_state.cart = {}
    
    with st.sidebar:
        if os.path.exists('logo_full.png'): st.image('logo_full.png', width=180)
        page = st.radio("القائمة", ["📊 Dashboard", "📄 Quotation", "📋 تقرير المتاح المجمع", "⚙️ الإعدادات"])
        if st.button("تسجيل الخروج"): 
            st.session_state.auth = False
            st.rerun()

    if page == "📄 Quotation":
        st.title("📄 بناء عرض سعر وتثبيت حجز")
        try:
            # 1. جلب البيانات (تعديل الأقواس المربعة لعلامات تنصيص مزدوجة لتناسب PostgreSQL)
            draw_df = pd.read_sql('SELECT * FROM "اسماء الرسم"', conn)
            df_periods = pd.read_sql('SELECT "no", "namee" FROM "الفترة" ORDER BY "no"', conn)
            sizes = draw_df['الحجم'].unique().tolist()
            
            cust = st.text_input("اسم الزبون")
            
            c1, c2, c3 = st.columns(3)
            with c1: sel_size = st.selectbox("اختر المقاس:", sizes)
            with c2: print_type = st.radio("نوع الطباعة:", ["عادي", "سكوتش"], horizontal=True)
            with c3: b_year = st.number_input("العام:", value=2026)

            # 2. تحديد الفترات
            st.write("---")
            st.subheader("🗓️ تحديد فترة الحجز المطلوب")
            cp1, cp2 = st.columns(2)
            with cp1: start_p = st.selectbox("من فترة:", df_periods['namee'].tolist())
            with cp2: end_p = st.selectbox("إلى فترة:", df_periods['namee'].tolist(), index=len(df_periods)-1)

            s_no = int(df_periods[df_periods['namee'] == start_p]['no'].iloc[0])
            e_no = int(df_periods[df_periods['namee'] == end_p]['no'].iloc[0])
            target_period_names = df_periods[(df_periods['no'] >= s_no) & (df_periods['no'] <= e_no)]['namee'].tolist()

            # 3. حساب الأجور
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

            # 4. فلترة المواقع المتاحة (PostgreSQL Syntax)
            city_l = pd.read_sql('SELECT DISTINCT "المحافظة" FROM "اعمدة انارة"', conn)['المحافظة'].tolist()
            sel_city = st.selectbox("المحافظة:", city_l)
            
            type_l = pd.read_sql(f'SELECT DISTINCT "توصيف العمود" FROM "اعمدة انارة" WHERE "المحافظة"=\'{sel_city}\'', conn)['توصيف العمود'].tolist()
            sel_types = st.multiselect("توصيف المواقع:", type_l)

            # تحويل قائمة الفترات لصيغة تناسب استعلام SQL
            periods_str = ", ".join([f"'{p}'" for p in target_period_names])

            # جلب المحجوز
            booked_boards_query = f'SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" WHERE "العام"={b_year} AND "فترة الحجز" IN ({periods_str})'
            booked_boards = pd.read_sql(booked_boards_query, conn)['رقم اللوحة'].tolist()

            # جلب المتاح
            main_query = f'SELECT "رقم اللوحة", "اسم العمود" as الموقع, "العدد", "الشبكة", "توصيف العمود" FROM "اعمدة انارة" WHERE "المحافظة"=\'{sel_city}\' AND "الحجم"=\'{sel_size}\''
            
            raw = pd.read_sql(main_query, conn)
            # الفلترة داخل بايثون أضمن مع الأسماء المعقدة
            if booked_boards:
                raw = raw[~raw['رقم اللوحة'].isin(booked_boards)]
            if sel_types:
                raw = raw[raw['توصيف العمود'].isin(sel_types)]
            
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

            # 5. إدارة السلة وتثبيت الحجز (تعديل للحفظ السحابي)
            if st.session_state.cart:
                st.divider()
                st.subheader("🛒 المواقع المختارة في العرض")
                for c_n in list(st.session_state.cart.keys()):
                    for n_n in list(st.session_state.cart[c_n].keys()):
                        with st.expander(f"📍 {c_n} - {n_n}", expanded=True):
                            col_table, col_del = st.columns([5, 1])
                            with col_table:
                                st.session_state.cart[c_n][n_n] = st.data_editor(st.session_state.cart[c_n][n_n], key=f"ed_{c_n}_{n_n}")
                            with col_del:
                                if st.button("🗑️ حذف", key=f"btn_{c_n}_{n_n}"):
                                    del st.session_state.cart[c_n][n_n]
                                    if not st.session_state.cart[c_n]: del st.session_state.cart[c_n]
                                    st.rerun()

                st.write("---")
                b1, b2, b3, b4 = st.columns(4)
                
                with b1:
                    if st.button("🚀 تصدير ملف Word"):
                        if not cust: st.error("أدخل اسم الزبون")
                        else:
                            doc_io = export_word(cust, st.session_state.cart, start_p, end_p)
                            st.download_button("📥 تحميل العرض", doc_io, f"Quotation_{cust}.docx")

                with b2:
                    if st.button("💾 حفظ كمسودة"):
                        if not cust: st.error("أدخل اسم الزبون أولاً")
                        else:
                            cart_json = json.dumps({c: {n: df.to_dict() for n, df in nets.items()} 
                                                 for c, nets in st.session_state.cart.items()}, ensure_ascii=False)
                            cursor = conn.cursor()
                            # تم استبدال ? بـ %s لتوافق PostgreSQL
                            query = 'INSERT INTO offers_history (client_name, cart_json, start_p, end_p, year, status) VALUES (%s, %s, %s, %s, %s, %s)'
                            cursor.execute(query, (cust, cart_json, start_p, end_p, b_year, 'Pending'))
                            conn.commit()
                            st.success(f"✅ تم حفظ المسودة لـ {cust}")

                with b3:
                    if st.button("✅ تثبيت نهائي"):
                        if not cust: st.error("أدخل اسم الزبون أولاً")
                        else:
                            new_recs = []
                            for city, nets in st.session_state.cart.items():
                                for net, df in nets.items():
                                    for _, row in df.iterrows():
                                        for p_name in target_period_names:
                                            new_recs.append((str(row['رقم اللوحة']), cust, p_name, int(b_year)))
                            
                            cursor = conn.cursor()
                            # تنفيذ الحفظ الجماعي (PostgreSQL Syntax)
                            sql_insert = 'INSERT INTO "حجوزات1" ("رقم اللوحة", "اسم الزبون", "فترة الحجز", "العام") VALUES (%s, %s, %s, %s)'
                            cursor.executemany(sql_insert, new_recs)
                            conn.commit()
                            st.success(f"تم التثبيت الدائم لـ {len(new_recs)} سجل!")
                            st.session_state.cart = {}
                            st.rerun()

                with b4:
                    if st.button("🔴 تفريغ السلة"):
                        st.session_state.cart = {}
                        st.rerun()

        except Exception as e:
            st.error(f"خطأ فني: {e}")

    # --- دالة تصدير Word (يجب أن توضع في أعلى الملف) ---
def export_word(customer_name, cart_data, start_p, end_p):
    doc = Document('template.docx') if os.path.exists('template.docx') else Document()
    for section in doc.sections: section.top_margin = Cm(4.5) 
    
    PURPLE_COLOR = "660099" 

    p_cust = doc.add_paragraph(); p_cust.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cust.add_run(f"السادة شركة {customer_name} المحترمين").bold = True
    
    p_stat = doc.add_paragraph()
    p_stat.add_run(f"نقدم لكم المواقع المتاحة للفترة من ({start_p}) ولغاية ({end_p})")
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
                    run = cell.paragraphs[0].add_run()
                    run.font.color.rgb = RGBColor(255, 255, 255)
                
                hdr[0].text = f"الشبكة: {net}"
                hdr[1].text = "العدد"
                for cell in hdr: apply_rtl(cell)

                for _, row in group_df.iterrows():
                    row_cells = table.add_row().cells
                    row_cells[0].text = str(row['الموقع'])
                    row_cells[1].text = str(row['العدد'])
                    for cell in row_cells: apply_rtl(cell)
                    
    target = io.BytesIO()
    doc.save(target)
    target.seek(0)
    return target
    except Exception as e:
        st.error(f"خطأ فني: {e}")

    # --- Page: تقرير الجرد (تعديل الاستعلامات) ---
    elif page == "📋 تقرير المتاح المجمع":
        st.title("📋 تقرير المتاح المفصل")
        
        df_periods = pd.read_sql('SELECT "no", "namee" FROM "الفترة" ORDER BY "no"', conn)
        c1, c2, c3 = st.columns(3)
        with c1: start_p = st.selectbox("من فترة:", df_periods['namee'].tolist(), key="rep_s")
        with c2: end_p = st.selectbox("إلى فترة:", df_periods['namee'].tolist(), index=len(df_periods)-1, key="rep_e")
        with c3: b_year = st.number_input("العام:", value=2026, key="rep_y")

        s_no = int(df_periods[df_periods['namee'] == start_p]['no'].iloc[0])
        e_no = int(df_periods[df_periods['namee'] == end_p]['no'].iloc[0])
        target_period_names = df_periods[(df_periods['no'] >= s_no) & (df_periods['no'] <= e_no)]['namee'].tolist()

        all_boards = pd.read_sql('SELECT "رقم اللوحة", "المحافظة", "الشبكة", "الحجم", "العدد" FROM "اعمدة انارة"', conn)
        
        periods_str = ", ".join([f"'{p}'" for p in target_period_names])
        booked_query = f'SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" WHERE "العام"={b_year} AND "فترة الحجز" IN ({periods_str})'
        booked_list = pd.read_sql(booked_query, conn)['رقم اللوحة'].tolist()

        all_boards['is_booked'] = all_boards['رقم اللوحة'].apply(lambda x: 1 if x in booked_list else 0)

        # (بقية كود عرض التقارير والمجموع النهائي تبقى كما هي مع التأكد من استخدام أسماء الأعمدة المحدثة)
    # --- تابع لصفحة تقرير الجرد (الإغلاق النهائي وتصدير Word) ---
    # ملاحظة: الكود الذي أرسلته أنت في الدفعة الأخيرة يوضع هنا مباشرة مع التأكد من إغلاق التنسيقات

    # --- Page: Dashboard (الخريطة والبيانات الحية) ---
    elif page == "📊 Dashboard":
        st.title("📊 حالة الإشغال والخريطة التفاعلية")
        try:
            # جلب البيانات من السحابة (PostgreSQL Syntax)
            df_all = pd.read_sql('SELECT * FROM "اعمدة انارة"', conn)
            df_booked = pd.read_sql('SELECT "رقم اللوحة", "اسم الزبون", "فترة الحجز", "العام" FROM "حجوزات1"', conn)
            df_periods = pd.read_sql('SELECT "no", "namee" FROM "الفترة" ORDER BY "no"', conn)

            col1, col2, col3, col4 = st.columns(4)
            with col1: 
                curr_p = st.selectbox("بدءاً من:", df_periods['namee'].tolist())
                curr_no = int(df_periods[df_periods['namee'] == curr_p]['no'].iloc[0])
            with col2: target_ya = st.number_input("العام:", value=2026)
            with col3: city_sel = st.selectbox("المحافظة:", ["الكل"] + sorted(df_all['المحافظة'].unique().tolist()))
            with col4: status_sel = st.radio("الحالة:", ["الكل", "متاح", "محجوز"])

            # منطق الربط لتحديد المحجوز حالياً
            df_b_t = pd.merge(df_booked, df_periods, left_on='فترة الحجز', right_on='namee', how='left')
            fut_b = df_b_t[(df_b_t['no'] >= curr_no) & (df_b_t['العام'] == target_ya)]
            latest_b = fut_b.sort_values('no').groupby('رقم اللوحة').last().reset_index()
            df_m = pd.merge(df_all, latest_b[['رقم اللوحة', 'اسم الزبون', 'no']], on='رقم اللوحة', how='left')

            if city_sel != "الكل": df_m = df_m[df_m['المحافظة'] == city_sel]
            if status_sel == "محجوز": df_m = df_m[df_m['no'].notna()]
            elif status_sel == "متاح": df_m = df_m[df_m['no'].isna()]

            # رسم الخريطة باستخدام الإحداثيات السحابية
            m_center = SYRIA_CITIES_COORDS.get(city_sel, SYRIA_CITIES_COORDS["سوريا"])
            m = folium.Map(location=m_center, zoom_start=(7 if city_sel == "الكل" else 12))
            cluster = MarkerCluster().add_to(m)
            
            for _, r in df_m.iterrows():
                if pd.notnull(r['Latitude']):
                    color = 'red' if pd.notnull(r['no']) else 'purple'
                    folium.Marker(
                        [r['Latitude'], r['Longitude']], 
                        popup=f"الموقع: {r['اسم العمود']}<br>الحالة: {'محجوز' if pd.notnull(r['no']) else 'متاح'}",
                        icon=folium.Icon(color=color)
                    ).add_to(cluster)
            
            st_folium(m, width="100%", height=500, key=f"map_{city_sel}")
            st.dataframe(df_m.drop(columns=['no'], errors='ignore'), use_container_width=True)
            
        except Exception as e:
            st.error(f"خطأ في الداشبورد: {e}")

    # --- Page: الإعدادات (إدارة البيانات السحابية مباشرة) ---
    elif page == "⚙️ الإعدادات":
        st.title("⚙️ إدارة البيانات الأساسية (السحابة)")
        st.info("التعديلات هنا تُحفظ فوراً في Supabase.")
        
        tab1, tab2 = st.tabs(["📍 اللوحات", "📅 سجل الحجوزات"])
        
        with tab1:
            df_all = pd.read_sql('SELECT * FROM "اعمدة انارة"', conn)
            edited_df = st.data_editor(df_all, num_rows="dynamic", key="edit_boards")
            if st.button("💾 حفظ تغييرات اللوحات"):
                # ملاحظة: توخي الحذر عند استخدام to_sql مع PostgreSQL
                edited_df.to_sql("اعمدة انارة", engine, if_exists="replace", index=False)
                st.success("تم التحديث!")

        with tab2:
            df_booked = pd.read_sql('SELECT * FROM "حجوزات1"', conn)
            edited_booked = st.data_editor(df_booked, num_rows="dynamic", key="edit_bookings")
            if st.button("💾 تحديث سجل الحجوزات"):
                edited_booked.to_sql("حجوزات1", engine, if_exists="replace", index=False)
                st.success("تم تحديث السجلات!")



    elif page == "⚙️ الإعدادات":
        st.title("⚙️ إدارة البيانات الأساسية")
        st.info("من هنا يمكنك إضافة لوحات جديدة، تعديل الأسعار، أو حذف الحجوزات.")
        
        tab1, tab2, tab3 = st.tabs(["📍 اللوحات", "💰 الأسعار والمقاسات", "📅 إدارة الحجوزات"])
        
        # ملاحظة: نحتاج لتعريف engine في بداية الكود خارج الدوال ليعمل مع to_sql
        # engine = create_engine(conn_str)

        with tab1:
            st.subheader("إدارة بيانات اللوحات")
            try:
                df_all = pd.read_sql('SELECT * FROM "اعمدة انارة"', conn)
                edited_df = st.data_editor(df_all, num_rows="dynamic", key="edit_all_boards", use_container_width=True)
                
                if st.button("💾 حفظ تغييرات اللوحات"):
                    # استخدام engine بدلاً من conn في to_sql للسحابة
                    edited_df.to_sql("اعمدة انارة", engine, if_exists="replace", index=False)
                    st.success("✅ تم تحديث بيانات اللوحات في السحابة!")
                    st.rerun()
            except Exception as e:
                st.error(f"خطأ: {e}")

        with tab2:
            st.subheader("إدارة أجور الرسم والطباعة")
            try:
                df_prices = pd.read_sql('SELECT * FROM "اسماء الرسم"', conn)
                edited_prices = st.data_editor(df_prices, num_rows="dynamic", key="edit_prices", use_container_width=True)
                if st.button("💾 حفظ قائمة الأسعار"):
                    edited_prices.to_sql("اسماء الرسم", engine, if_exists="replace", index=False)
                    st.success("✅ تم تحديث قائمة الأسعار سحابياً!")
                    st.rerun()
            except Exception as e:
                st.error(f"خطأ: {e}")

        with tab3:
            st.subheader("إدارة سجل الحجوزات")
            try:
                df_bookings = pd.read_sql('SELECT * FROM "حجوزات1"', conn)
                edited_bookings = st.data_editor(df_bookings, num_rows="dynamic", key="edit_bookings", use_container_width=True)
                if st.button("💾 تحديث سجل الحجوزات"):
                    edited_bookings.to_sql("حجوزات1", engine, if_exists="replace", index=False)
                    st.success("✅ تم مزامنة السجلات مع السحابة!")
                    st.rerun()
            except Exception as e:
                st.error(f"خطأ: {e}")

    # --- Page: Dashboard ---
    elif page == "📊 Dashboard":
        st.title("📊 حالة الإشغال والخريطة")
        try:
            # PostgreSQL Syntax: "" بدلاً من []
            df_all = pd.read_sql('SELECT * FROM "اعمدة انارة"', conn)
            df_booked = pd.read_sql('SELECT "رقم اللوحة", "اسم الزبون", "فترة الحجز", "العام" FROM "حجوزات1"', conn)
            df_periods = pd.read_sql('SELECT "no", "namee" FROM "الفترة" ORDER BY "no"', conn)

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
                    color = 'red' if pd.notnull(r['no']) else 'purple'
                    folium.Marker(
                        [r['Latitude'], r['Longitude']], 
                        popup=f"{r['اسم العمود']}", 
                        icon=folium.Icon(color=color)
                    ).add_to(cluster)
            
            st_folium(m, width="100%", height=500, key=f"map_{city_sel}")
            st.dataframe(df_m.drop(columns=['no'], errors='ignore'), use_container_width=True)
            
        except Exception as e: 
            st.error(f"حدث خطأ في عرض البيانات: {e}")

    # إغلاق الاتصال بأمان
    if 'conn' in locals():
        conn.close()

