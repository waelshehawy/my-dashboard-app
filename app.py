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
from datetime import datetime
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
        # --- إضافة مسافة سطرين بين العنوان وبداية العرض ---
    doc.add_paragraph()
        # --- 1. إضافة تاريخ اليوم في أعلى اليمين ---
    today_date = datetime.now().strftime("%d / %m / %Y")
    p_date = doc.add_paragraph()
    p_date.add_run(f"التاريخ: {today_date}")
    _force_rtl_style(p_date) # لضمان ظهوره على اليمين
    doc.add_paragraph()
    # السطر الافتتاحي
    p_cust = doc.add_paragraph()
    p_cust.add_run(f"السادة شركة {customer_name} المحترمين").bold = True
    _force_rtl_style(p_cust)

    p_stat = doc.add_paragraph()
    p_stat.add_run(f"نقدم لكم المواقع المتاحة لعرض إعلانكم الوطني من فترة ({start_p}) ولغاية ({end_p})")
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

        # --- 4. الملاحظة الختامية للالتزام بـ 48 ساعة ---
    doc.add_paragraph() # سطر فارغ قبل الملاحظة
    p_note = doc.add_paragraph()
    run_note = p_note.add_run("• ملاحظة: هذه المواقع متاحة لمدة 48 ساعة.")
    run_note.bold = True
    _force_rtl_style(p_note)
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
    # --- Page: Dashboard (المصحح لإظهار الحالة الحالية فقط) ---
    elif page == "📊 Dashboard":
        st.title("📊 الخريطة التفاعلية - الحالة الحالية")
        
        # 1. تحديد الفترة الحالية بناءً على تاريخ اليوم
        current_month = datetime.now().month
        # نفترض أن جدول الفترة يحتوي على عمود 'no' يمثل رقم الشهر أو تسلسل الفترات
        # سنجلب اسم الفترة الحالية (مثلاً: شهر أيار)
        df_periods = pd.read_sql('SELECT * FROM "الفترة" ORDER BY "no"', conn)
        
        # ملاحظة: يمكنك تعديل منطق اختيار الفترة الحالية بناءً على هيكل جدولك
        # هنا سنفترض أننا نريد الحجوزات التي تشمل الشهر الحالي والعام الحالي
        current_year = datetime.now().year
        
        # 2. جلب الحجوزات النشطة الآن فقط
        query_booked = f"""
            SELECT DISTINCT "رقم اللوحة", "اسم الزبون" 
            FROM "حجوزات1" 
            WHERE "العام" = {current_year} 
        """
        df_booked = pd.read_sql(query_booked, conn)
        
        # 3. جلب كافة الأعمدة
        df_all = pd.read_sql('SELECT * FROM "اعمدة انارة"', conn)
        
        # 4. الربط (Left Join)
        df_merged = pd.merge(df_all, df_booked, on='رقم اللوحة', how='left')
        
        # 5. تنظيف التكرار (لوحة واحدة فقط لكل موقع)
        df_map = df_merged.drop_duplicates(subset=['رقم اللوحة'])
        
        # عرض إحصائية سريعة
        c1, c2, c3 = st.columns(3)
        c1.metric("إجمالي اللوحات", len(df_map))
        c2.metric("محجوز حالياً", df_map['اسم الزبون'].notnull().sum())
        c3.metric("متاح حالياً", df_map['اسم الزبون'].isnull().sum())

        m = folium.Map(location=SYRIA_CITIES_COORDS["سوريا"], zoom_start=7)
        cluster = MarkerCluster().add_to(m)
        
        for _, r in df_map.iterrows():
            if pd.notnull(r.get('Latitude')) and pd.notnull(r.get('Longitude')):
                is_booked = pd.notnull(r['اسم الزبون'])
                color = 'red' if is_booked else 'purple'
                popup_text = f"الموقع: {r['اسم العمود']}<br>الحالة: {'محجوز لـ ' + str(r['اسم الزبون']) if is_booked else 'متاح'}"
                folium.Marker(
                    [r['Latitude'], r['Longitude']], 
                    popup=folium.Popup(popup_text, max_width=200), 
                    icon=folium.Icon(color=color)
                ).add_to(cluster)
                
        st_folium(m, width="100%", height=600)


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
            # --- بداية قسم عرض السلة وإدارة العمليات النهائية ---
            if st.session_state.cart:
                st.divider()
                st.subheader("🛒 تفاصيل العرض المجمع")
                grand_total = 0.0
                
                # تكرار عبر المدن والشبكات في السلة
                for city, nets in list(st.session_state.cart.items()):
                    for net, df in list(nets.items()):
                        with st.expander(f"📍 {city} - {net}", expanded=True):
                            # محرر البيانات للسماح بحذف أسطر أو تعديل أعداد
                            ed_df = st.data_editor(df, key=f"ed_{city}_{net}", num_rows="dynamic")
                            st.session_state.cart[city][net] = ed_df
                            
                            # حساب المجموع بناءً على البيانات المخزنة داخل الجدول المسترجع
                            total_q = pd.to_numeric(ed_df['العدد']).sum()
                            
                            # استخراج الأجور من الأعمدة المخزنة لضمان عدم ظهور قيمة 0 عند الاسترجاع
                            f_p = float(ed_df['fee_print'].max()) if 'fee_print' in ed_df.columns else 0.0
                            f_a = float(ed_df['fee_ads'].max()) if 'fee_ads' in ed_df.columns else 0.0
                            
                            grand_total += total_q * (f_p + f_a)
                            
                            if st.button("حذف هذه الشبكة", key=f"del_{city}_{net}"):
                                del st.session_state.cart[city][net]
                                st.rerun()
                
                # عرض المجموع النهائي في الواجهة
                st.info(f"### 💰 إجمالي القيمة المالية للعرض: {grand_total:,.0f} $")
                
                # أزرار العمليات (حفظ، تثبيت، تصدير، تفريغ)
                b1, b2, b3, b4 = st.columns(4)
                with b1:
                    if st.button("💾 حفظ مسودة (48س)"):
                        if not cust: 
                            st.error("يرجى إدخال اسم الزبون أولاً")
                        else:
                            c_json = json.dumps({c: {n: df.to_dict() for n, df in ns.items()} for c, ns in st.session_state.cart.items()}, ensure_ascii=False)
                            cur = conn.cursor()
                            cur.execute('INSERT INTO "offers_history" (client_name, cart_json, start_p, end_p, year, status) VALUES (%s, %s, %s, %s, %s, %s)', (cust, c_json, start_p, end_p, b_year, 'Pending'))
                            conn.commit()
                            st.success("تم حفظ المسودة بنجاح.")
                
                with b2:
                    if st.button("✅ تثبيت حجز نهائي"):
                        if not cust: 
                            st.error("يرجى إدخال اسم الزبون")
                        else:
                            recs = []
                            for _, ns in st.session_state.cart.items():
                                for _, df in ns.items():
                                    for _, row in df.iterrows():
                                        for p in target_p_names:
                                            recs.append((str(row['رقم اللوحة']), str(cust), str(p), int(b_year)))
                            cur = conn.cursor()
                            cur.executemany('INSERT INTO "حجوزات1" ("رقم اللوحة", "اسم الزبون", "فترة الحجز", "العام") VALUES (%s, %s, %s, %s)', recs)
                            conn.commit()
                            st.session_state.cart = {}
                            st.success("تم تثبيت الحجز في الداتا الأساسية!")
                            st.rerun()
                
                with b3:
                    if st.button("📝 تصدير Word الرسمي"):
                        # نرسل grand_total المحسوب بدقة للدالة
                        doc_io = export_word(cust, st.session_state.cart, start_p, end_p, grand_total)
                        st.download_button("📥 تحميل ملف العرض", doc_io, f"Offer_{cust}.docx")
                
                with b4:
                    if st.button("🔴 تفريغ السلة"):
                        st.session_state.cart = {}
                        st.rerun()



                
                

              
                # --- Page: تقرير الجرد (المصحح للغة العربية ودمشق) ---
        elif page == "📋 تقرير الجرد":
            st.title("📋 تقرير الإشغال والجرد السحابي")
            try:
                # 1. جلب البيانات الأساسية
                df_p = pd.read_sql('SELECT "no", "namee" FROM "الفترة" ORDER BY "no"', conn)
                c1, c2, c3 = st.columns(3)
                with c1: s_p = st.selectbox("من فترة:", df_p['namee'].tolist(), key="s1")
                with c2: e_p = st.selectbox("إلى فترة:", df_p['namee'].tolist(), index=len(df_p)-1, key="s2")
                with c3: yr = st.number_input("العام:", value=2026, key="s3")
                
                # تصحيح سحب الفترات
                s_no = int(df_p[df_p['namee'] == s_p]['no'].iloc[0])
                e_no = int(df_p[df_p['namee'] == e_p]['no'].iloc[0])
                target_list = df_p[(df_p['no'] >= s_no) & (df_p['no'] <= e_no)]['namee'].tolist()
                
                # جلب كافة اللوحات دون استثناء
                all_b = pd.read_sql('SELECT "رقم اللوحة", "المحافظة", "الحجم", "الشبكة" FROM "اعمدة انارة"', conn)
                
                # جلب الحجوزات
                p_placeholders = ", ".join([f"'{p}'" for p in target_list])
                booked_j = pd.read_sql(f'SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" WHERE "العام"={yr} AND "فترة الحجز" IN ({p_placeholders})', conn)['رقم اللوحة'].tolist()
                
                all_b['الحالة'] = all_b['رقم اللوحة'].apply(lambda x: 'محجوز' if x in booked_j else 'متاح')
                
                # عرض البيانات في الواجهة (لضمان وجود دمشق)
                for city in sorted(all_b['المحافظة'].unique()):
                    st.write(f"### 📍 محافظة {city}")
                    city_df = all_b[all_b['المحافظة'] == city]
                    stats = city_df.groupby(['الحجم', 'الحالة']).size().unstack(fill_value=0)
                    if 'محجوز' not in stats.columns: stats['محجوز'] = 0
                    if 'متاح' not in stats.columns: stats['متاح'] = 0
                    st.table(stats)

                st.divider()
                st.subheader("📥 تصدير التقارير")
                exp_col1, exp_col2 = st.columns(2)
                
                # تصحيح ملف الإكسل (CSV مع BOM للغة العربية)
                with exp_col1:
                    # إضافة BOM (Byte Order Mark) ليتمكن إكسل من التعرف على ترميز UTF-8 للعربية
                    csv_data = all_b.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                    st.download_button("Excel تحميل تقرير الجرد التفصيلي", csv_data, f"Inventory_{yr}.csv", "text/csv")

                # تصحيح ملف الوورد (إضافة كافة المحافظات)
                with exp_col2:
                    rep_doc = Document()
                    rep_doc.add_heading(f"تقرير حالة الإشغال لعام {yr}", 0)
                    for city in sorted(all_b['المحافظة'].unique()):
                        rep_doc.add_heading(f"محافظة {city}", level=1)
                        city_stats = all_b[all_b['المحافظة']==city].groupby(['الحجم', 'الحالة']).size().unstack(fill_value=0)
                        table = rep_doc.add_table(rows=1, cols=3)
                        table.style = 'Table Grid'
                        # تفعيل RTL للجدول في تقرير الجرد أيضاً
                        set_table_rtl(table)
                        hdr = table.rows[0].cells
                        hdr[0].text, hdr[1].text, hdr[2].text = "المقاس", "المحجوز", "المتاح"
                        for size, row in city_stats.iterrows():
                            r_cells = table.add_row().cells
                            r_cells[0].text, r_cells[1].text, r_cells[2].text = str(size), str(row.get('محجوز', 0)), str(row.get('متاح', 0))
                    
                    word_out = io.BytesIO()
                    rep_doc.save(word_out)
                    st.download_button("Word تحميل التقرير الرسمي", word_out.getvalue(), f"Report_{yr}.docx")

            except Exception as e:
                st.error(f"⚠️ خطأ في الجرد: {e}")



        conn.close()
