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
from sqlalchemy import create_engine, text

# --- 1. Database Connections ---
def get_connection():
    try:
        return psycopg2.connect(
            # الـ host يجب أن يكون العنوان التقني المباشر بدون http أو ://
            host="aws-1-eu-north-1.pooler.supabase.com", 
            port="6543",
            database="postgres",
            user="postgres.ncuofpvbaglwbdqnpman",
            password="WaelPreview2026",
            sslmode="require",
            connect_timeout=10
        )
    except Exception as e:
        st.error(f"⚠️ فشل الاتصال بالقاعدة: {e}")
        return None

# --- 2. تصحيح دالة المحرك (SQLAlchemy) لصفحة الإعدادات ---
def get_engine():
    # الرابط الكامل والمصحح للإدخال المباشر
    uri = "postgresql://postgres.ncuofpvbaglwbdqnpman:WaelPreview2026@://supabase.com"
    return create_engine(uri)

# --- 2. Word & RTL Helpers ---


# 1. دالة ضبط اتجاه الجدول (يجب تعريفها قبل استخدامها)
def set_table_rtl(table):
    tblPr = table._element.xpath('w:tblPr')[0]
    bidi = OxmlElement('w:bidiVisual')
    tblPr.append(bidi)

# 2. دالة المحاذاة (التي علمتني إياها)
def _force_rtl_style(p):
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT # اليسار هنا يعني اليمين بسبب bidi
    pPr = p._element.get_or_add_pPr()
    bidi = OxmlElement('w:bidi'); bidi.set(qn('w:val'), '1'); pPr.append(bidi)
    for run in p.runs:
        rPr = run._element.get_or_add_rPr()
        rtl = OxmlElement('w:rtl'); rtl.set(qn('w:val'), '1'); rPr.append(rtl)
        rFonts = OxmlElement('w:rFonts'); rFonts.set(qn('w:cs'), 'Arial'); rPr.append(rFonts)

# 3. دالة التصدير الكاملة والمعدلة
def export_word(customer_name, cart_data, start_p, end_p, grand_total):
    doc = Document('template.docx') if os.path.exists('template.docx') else Document()
    PURPLE_COLOR = "660099" 

    # السطر الافتتاحي
    p_cust = doc.add_paragraph()
    p_cust.add_run(f"السادة شركة {customer_name} المحترمين").bold = True
    _force_rtl_style(p_cust)
    
    p_stat = doc.add_paragraph()
    p_stat.add_run(f"موضوع العرض: حجز مواقع إعلانية للفترة من ({start_p}) ولغاية ({end_p})")
    _force_rtl_style(p_stat)

    for city, networks in cart_data.items():
        p_city = doc.add_paragraph()
        p_city.add_run(f"■ محافظة {city}").bold = True
        _force_rtl_style(p_city)
        
        for net, df in networks.items():
            if df.empty: continue
            for size_info, group_df in df.groupby(['الحجم']):
                p_size = doc.add_paragraph()
                p_size.add_run(f"الشبكة: {net} | القياس: {size_info}").bold = True
                _force_rtl_style(p_size)
                
                # إنشاء الجدول مع ضبط الاتجاه
                table = doc.add_table(rows=1, cols=2)
                table.style = 'Table Grid'
                set_table_rtl(table) # تم التأكد من تعريفها أعلاه
                
                hdr = table.rows[0].cells
                hdr[0].text = "اسم الموقع (العمود)"; hdr[1].text = "العدد"
                for cell in hdr:
                    for p in cell.paragraphs: _force_rtl_style(p)
                    tc_pr = cell._element.get_or_add_tcPr()
                    shd = OxmlElement('w:shd'); shd.set(qn('w:fill'), PURPLE_COLOR); tc_pr.append(shd)
                    cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)

                for _, row in group_df.iterrows():
                    row_cells = table.add_row().cells
                    row_cells[0].text = str(row['الموقع']); row_cells[1].text = str(row['العدد'])
                    for cell in row_cells:
                        for p in cell.paragraphs: _force_rtl_style(p)

                # --- الحساب المالي المجمع لكل جدول ---
                total_q = pd.to_numeric(group_df['العدد']).sum()
                f_p = float(group_df['fee_print'].iloc[0])
                f_a = float(group_df['fee_ads'].iloc[0])
                sum_print = total_q * f_p
                sum_ads = total_q * f_a
                sum_combined = sum_print + sum_ads
                
                p_fin = doc.add_paragraph()
                txt = (f"إجمالي العدد: {int(total_q)} | "
                       f"أجور الطباعة: {sum_print:,.0f}$ | "
                       f"أجور العرض: {sum_ads:,.0f}$ | "
                       f"المجموع للقسم: {sum_combined:,.0f}$")
                p_fin.add_run(txt).bold = True
                _force_rtl_style(p_fin)

    # المجموع النهائي العام
    doc.add_paragraph() 
    p_grand = doc.add_paragraph()
    run_g = p_grand.add_run(f"إجمالي القيمة المالية للعرض بالكامل: {grand_total:,.0f} $")
    run_g.bold = True; run_g.font.size = Pt(14); run_g.font.color.rgb = RGBColor(102, 0, 153)
    _force_rtl_style(p_grand)

    target = io.BytesIO(); doc.save(target); target.seek(0)
    return target






# --- 3. Manage Expired Offers Logic ---
def manage_expired_offers(conn):
    st.subheader("⚠️ إدارة العروض التي تجاوزت 48 ساعة")
    query = 'SELECT id, client_name, offer_date FROM "offers_history" WHERE status = \'Pending\' AND offer_date < NOW() - INTERVAL \'48 hours\''
    expired_df = pd.read_sql(query, conn)
    if not expired_df.empty:
        for _, row in expired_df.iterrows():
            col1, col2, col3 = st.columns([3, 1, 1])
            col1.write(f"الزبون: {row['client_name']} ({row['offer_date']})")
            if col2.button("✅ تمديد", key=f"ext_{row['id']}"):
                cur = conn.cursor(); cur.execute('UPDATE "offers_history" SET offer_date = NOW() WHERE id = %s', (row['id'],)); conn.commit(); st.rerun()
            if col3.button("❌ إلغاء", key=f"can_{row['id']}"):
                cur = conn.cursor(); cur.execute("UPDATE \"offers_history\" SET status = 'Cancelled' WHERE id = %s", (row['id'],)); conn.commit(); st.rerun()
    else:
        st.success("لا توجد عروض منتهية الصلاحية.")

# --- 4. Main App Interface ---
st.set_page_config(page_title="PreView Ads ERP - Cloud", layout="wide")
SYRIA_CITIES_COORDS = {"دمشق": [33.51, 36.27], "ريف دمشق": [33.45, 36.35], "حلب": [36.20, 37.13], "حمص": [34.73, 36.71], "حماة": [35.13, 36.75], "اللاذقية": [35.53, 35.79], "طرطوس": [34.88, 35.88], "سوريا": [34.80, 38.99]}

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
        page = st.radio("القائمة الرئيسية", ["📊 Dashboard", "📄 Quotation", "📋 تقرير الجرد", "⚙️ الإعدادات"])
        if st.button("🚪 تسجيل الخروج"): st.session_state.auth = False; st.rerun()

    if conn:
        # --- Page: Dashboard ---
        if page == "📊 Dashboard":
            st.title("📊 الخريطة التفاعلية وحالة الإشغال")
            df_all = pd.read_sql('SELECT * FROM "اعمدة انارة"', conn)
            df_booked = pd.read_sql('SELECT "رقم اللوحة", "اسم الزبون" FROM "حجوزات1"', conn)
            df_merged = pd.merge(df_all, df_booked, on='رقم اللوحة', how='left')
            m = folium.Map(location=SYRIA_CITIES_COORDS["سوريا"], zoom_start=7)
            cluster = MarkerCluster().add_to(m)
            for _, r in df_merged.iterrows():
                if pd.notnull(r.get('Latitude')):
                    color = 'red' if pd.notnull(r['اسم الزبون']) else 'purple'
                    folium.Marker([r['Latitude'], r['Longitude']], popup=f"الموقع: {r['اسم العمود']}", icon=folium.Icon(color=color)).add_to(cluster)
            st_folium(m, width="100%", height=600)
            st.dataframe(df_merged, use_container_width=True)

        # --- Page: Quotation ---
        elif page == "📄 Quotation":
            st.title("📄 بناء عرض سعر وتثبيت حجز")
            
            # 1. نظام إدارة العروض المنتهية (48 ساعة)
            with st.expander("🔔 إدارة العروض التي تجاوزت 48 ساعة"):
                manage_expired_offers(conn)

            # 2. استرجاع المسودات
            st.subheader("📂 استرجاع عرض محفوظ")
            saved_off_df = pd.read_sql('SELECT id, client_name, offer_date FROM "offers_history" WHERE status=\'Pending\' ORDER BY offer_date DESC', conn)
            if not saved_off_df.empty:
                off_options = {f"{r['client_name']} ({r['offer_date']})": r['id'] for _, r in saved_off_df.iterrows()}
                sel_label = st.selectbox("اختر عرضاً لتعديله:", ["---"] + list(off_options.keys()))
                if sel_label != "---" and st.button("🔄 تحميل للسلة"):
                    off_id = off_options[sel_label]
                    res = pd.read_sql(f'SELECT cart_json, client_name FROM "offers_history" WHERE id={off_id}', conn)
                    if not res.empty:
                        data = json.loads(res['cart_json'].iloc[0])
                        st.session_state.cart = {c: {n: pd.DataFrame(d) for n, d in ns.items()} for c, ns in data.items()}
                        st.session_state.temp_cust = res['client_name'].iloc[0]
                        st.rerun()

            st.divider()
            
            # 3. جلب البيانات الأساسية
            draw_df = pd.read_sql('SELECT * FROM "اسماء الرسم"', conn)
            df_periods = pd.read_sql('SELECT * FROM "الفترة" ORDER BY "no"', conn)
            cust = st.text_input("اسم الزبون", value=st.session_state.get('temp_cust', ""))
            
            c1, c2, c3 = st.columns(3)
            with c1: sel_size = st.selectbox("المقاس:", draw_df['الحجم'].unique().tolist())
            with c2: print_type = st.radio("الطباعة:", ["عادي", "سكوتش"], horizontal=True)
            with c3: b_year = st.number_input("العام:", value=2026)

            cp1, cp2 = st.columns(2)
            with cp1: start_p = st.selectbox("من فترة:", df_periods['namee'].tolist())
            with cp2: end_p = st.selectbox("إلى فترة:", df_periods['namee'].tolist(), index=len(df_periods)-1)

            # حساب الفترات المختارة
            s_no = int(df_periods[df_periods['namee'] == start_p]['no'].iloc[0])
            e_no = int(df_periods[df_periods['namee'] == end_p]['no'].iloc[0])
            target_p_names = df_periods[(df_periods['no'] >= s_no) & (df_periods['no'] <= e_no)]['namee'].tolist()
            
            # --- إصلاح منطق الأجور (تجنب الصفر) ---
            subset = draw_df[draw_df['الحجم'] == sel_size]
            # بحث مرن عن الطباعة
            f_print_row = subset[subset['اسم الرسم'].str.contains("طباعة", na=False) & subset['اسم الرسم'].str.contains(print_type, na=False)]
            f_print = float(f_print_row['اجرة الرسم'].sum()) if not f_print_row.empty else 0.0
            # بحث مرن عن العرض
            f_ads_row = subset[subset['اسم الرسم'].str.contains("عرض", na=False) & subset['اسم الرسم'].str.contains(print_type, na=False)]
            f_ads = float(f_ads_row['اجرة الرسم'].sum()) if not f_ads_row.empty else 0.0

            if f_print == 0 or f_ads == 0:
                st.warning(f"⚠️ تنبيه: لم يتم العثور على أسعار لـ ({sel_size} - {print_type})")

            # 4. فلترة المواقع المتاحة
            city_l = pd.read_sql('SELECT DISTINCT "المحافظة" FROM "اعمدة انارة"', conn)['المحافظة'].tolist()
            sel_city = st.selectbox("المحافظة:", city_l)
            
            p_placeholders = ", ".join([f"'{p}'" for p in target_p_names])
            booked_ids = pd.read_sql(f'SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" WHERE "العام"={b_year} AND "فترة الحجز" IN ({p_placeholders})', conn)['رقم اللوحة'].tolist()
            
            raw = pd.read_sql(f'SELECT "رقم اللوحة", "اسم العمود" as "الموقع", "العدد", "الشبكة", "توصيف العمود", "الحجم" FROM "اعمدة انارة" WHERE "المحافظة"=\'{sel_city}\' AND "الحجم"=\'{sel_size}\'', conn)
            raw = raw[~raw['رقم اللوحة'].isin(booked_ids)]
            
            if not raw.empty:
                nets = st.multiselect("اختر الشبكات المتاحة:", raw['الشبكة'].unique().tolist())
                if st.button("➕ إضافة للسلة"):
                    if sel_city not in st.session_state.cart: st.session_state.cart[sel_city] = {}
                    for n in nets:
                        st.session_state.cart[sel_city][n] = raw[raw['الشبكة'] == n].assign(fee_print=f_print, fee_ads=f_ads, الحجم=sel_size)
                    st.success("تم التحديث!")
                    st.rerun()

            # 5. إدارة السلة وعرض المالي
if st.session_state.cart:
    st.divider()
    grand_total = 0
    for city, nets in list(st.session_state.cart.items()):
        for net, df in list(nets.items()):
            with st.expander(f"📍 {city} - {net}", expanded=True):
                ed_df = st.data_editor(df, key=f"ed_{city}_{net}", num_rows="dynamic")
                st.session_state.cart[city][net] = ed_df
                
                # --- التعديل الجوهري هنا ---
                # نأخذ الأجور من الأعمدة المخزنة في السلة نفسها لضمان عدم ضياعها عند الاسترجاع
                total_q = pd.to_numeric(ed_df['العدد']).sum()
                # نستخدم .max() للحصول على القيمة المخزنة في العمود لهذا الجدول
                row_f_print = float(ed_df['fee_print'].max()) if 'fee_print' in ed_df.columns else 0
                row_f_ads = float(ed_df['fee_ads'].max()) if 'fee_ads' in ed_df.columns else 0
                
                grand_total += total_q * (row_f_print + row_f_ads)
                
                if st.button("حذف الشبكة", key=f"del_{city}_{net}"):
                    del st.session_state.cart[city][net]
                    st.rerun()
    
    st.info(f"### 💰 إجمالي القيمة المالية للعرض: {grand_total:,.0f} $")


                
                b1, b2, b3, b4 = st.columns(4)
                with b1:
                    if st.button("💾 حفظ مسودة (48س)"):
                        if not cust: st.error("أدخل اسم الزبون")
                        else:
                            c_json = json.dumps({c: {n: df.to_dict() for n, df in ns.items()} for c, ns in st.session_state.cart.items()}, ensure_ascii=False)
                            cur = conn.cursor()
                            cur.execute('INSERT INTO "offers_history" (client_name, cart_json, start_p, end_p, year, status) VALUES (%s, %s, %s, %s, %s, %s)', (cust, c_json, start_p, end_p, b_year, 'Pending'))
                            conn.commit(); st.success("تم حفظ المسودة بنجاح.")
                with b2:
                    if st.button("✅ تثبيت حجز نهائي"):
                        if not cust: st.error("أدخل اسم الزبون")
                        else:
                            recs = [(str(r['رقم اللوحة']), str(cust), str(p), int(b_year)) for city, ns in st.session_state.cart.items() for n, df in ns.items() for _, r in df.iterrows() for p in target_p_names]
                            cur = conn.cursor(); cur.executemany('INSERT INTO "حجوزات1" ("رقم اللوحة", "اسم الزبون", "فترة الحجز", "العام") VALUES (%s, %s, %s, %s)', recs)
                            conn.commit(); st.session_state.cart = {}; st.success("تم التثبيت نهائياً!"); st.rerun()
                with b3:
                    if st.button("📝 تصدير Word الرسمي"):
                        # استدعاء دالة التصدير التي تستخدم القالب (Template)
                        doc_io = export_word(cust, st.session_state.cart, start_p, end_p, grand_total)
                        st.download_button("📥 تحميل ملف العرض", doc_io, f"Offer_{cust}.docx")
                with b4:
                    if st.button("🔴 تفريغ السلة"):
                        st.session_state.cart = {}; st.rerun()

        # --- Page: تقرير الجرد ---
        elif page == "📋 تقرير الجرد":
            st.title("📋 تقرير الإشغال والجرد السحابي")
            df_p = pd.read_sql('SELECT "no", "namee" FROM "الفترة" ORDER BY "no"', conn)
            s_p = st.selectbox("من فترة:", df_p['namee'].tolist(), key="s1")
            e_p = st.selectbox("إلى فترة:", df_p['namee'].tolist(), index=len(df_p)-1, key="s2")
            yr = st.number_input("العام:", value=2026, key="s3")
            
            target_list = df_p[(df_p['no'] >= int(df_p[df_p['namee']==s_p]['no'].iloc[0])) & (df_p['no'] <= int(df_p[df_p['namee']==e_p]['no'].iloc[0]))]['namee'].tolist()
            all_b = pd.read_sql('SELECT "رقم اللوحة", "المحافظة", "الحجم" FROM "اعمدة انارة"', conn)
            p_str_j = ", ".join([f"'{p}'" for p in target_list])
            booked_j = pd.read_sql(f'SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" WHERE "العام"={yr} AND "فترة الحجز" IN ({p_str_j})', conn)['رقم اللوحة'].tolist()
            all_b['الحالة'] = all_b['رقم اللوحة'].apply(lambda x: 'محجوز' if x in booked_j else 'متاح')
            for city in all_b['المحافظة'].unique():
                st.write(f"### 📍 {city}")
                st.table(all_b[all_b['المحافظة']==city].groupby(['الحجم', 'الحالة']).size().unstack(fill_value=0))

        # --- Page: الإعدادات ---
        elif page == "⚙️ الإعدادات":
            st.title("⚙️ إدارة البيانات")
            engine = get_engine()
            tab1, tab2 = st.tabs(["📍 اللوحات", "📅 الحجوزات"])
            with tab1:
                df_set = pd.read_sql('SELECT * FROM "اعمدة انارة"', conn)
                new_set = st.data_editor(df_set, num_rows="dynamic", key="set_b")
                if st.button("حفظ اللوحات"):
                    with engine.begin() as cn:
                        cn.execute(text('DELETE FROM "اعمدة انارة"'))
                        new_set.to_sql("اعمدة انارة", cn, if_exists="append", index=False)
                    st.success("تم التحديث")
            with tab2:
                df_h = pd.read_sql('SELECT * FROM "حجوزات1" ORDER BY id DESC LIMIT 200', conn)
                new_h = st.data_editor(df_h, num_rows="dynamic", key="set_h")
                if st.button("تحديث السجل"):
                    with engine.begin() as cn:
                        cn.execute(text('DELETE FROM "حجوزات1"'))
                        new_h.to_sql("حجوزات1", cn, if_exists="append", index=False)
                    st.success("تمت المزامنة")

        conn.close()
