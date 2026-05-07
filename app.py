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

# --- 1. Database Connection (Optimized with Caching) ---
@st.cache_resource
def get_connection():
    try:
        return psycopg2.connect(
            host="://supabase.com",
            port="6543",
            database="postgres",
            user="postgres.ncuofpvbaglwbdqnpman",
            password="WaelPreview2026", # يفضل استخدام st.secrets["DB_PASS"]
            sslmode="require",
            connect_timeout=10
        )
    except Exception as e:
        st.error(f"فشل الاتصال بالقاعدة: {e}")
        return None

def get_engine():
    # تم تصحيح الرابط وإضافة المنفذ الصحيح 6543
    # ملاحظة: إذا كانت كلمة المرور تحتوي على رموز خاصة، يجب كتابتها بدقة
    uri = "postgresql://postgres.ncuofpvbaglwbdqnpman:WaelPreview2026@://supabase.com"
    return create_engine(uri)

# --- 2. Word & RTL Helpers (Same as your logic with improvements) ---
def _force_rtl_style(p):
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT # تصحيح المحاذاة للعربية
    pPr = p._element.get_or_add_pPr()
    bidi = OxmlElement('w:bidi'); bidi.set(qn('w:val'), '1'); pPr.append(bidi)
    for run in p.runs:
        rPr = run._element.get_or_add_rPr()
        rtl = OxmlElement('w:rtl'); rtl.set(qn('w:val'), '1'); rPr.append(rtl)
        rFonts = OxmlElement('w:rFonts'); rFonts.set(qn('w:cs'), 'Arial'); rPr.append(rFonts)

def apply_rtl(obj):
    if hasattr(obj, 'paragraphs'):
        for p in obj.paragraphs: _force_rtl_style(p)
    else: _force_rtl_style(obj)

def set_table_rtl(table):
    tblPr = table._element.xpath('w:tblPr')[0]
    bidi = OxmlElement('w:bidiVisual'); tblPr.append(bidi)

def export_word(customer_name, cart_data, start_p, end_p, grand_total):
    doc = Document() # يفضل وجود template.docx بجانب الكود
    for section in doc.sections: section.top_margin = Cm(2.0)
    PURPLE_COLOR = "660099" 

    p_cust = doc.add_paragraph(); p_cust.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cust.add_run(f"السادة شركة {customer_name} المحترمين").bold = True
    
    p_stat = doc.add_paragraph()
    p_stat.add_run(f"موضوع العرض: حجز مواقع إعلانية للفترة من ({start_p}) ولغاية ({end_p})")
    apply_rtl(p_stat)

    for city, networks in cart_data.items():
        p_city = doc.add_paragraph(f"■ محافظة {city}"); apply_rtl(p_city)
        for net, df in networks.items():
            if df.empty: continue
            group_cols = ['الحجم', 'توصيف العمود'] if 'توصيف العمود' in df.columns else ['الحجم']
            for size_info, group_df in df.groupby(group_cols):
                desc = size_info[1] if isinstance(size_info, tuple) else "مواقع إعلانية"
                size = size_info[0] if isinstance(size_info, tuple) else size_info
                
                p_size = doc.add_paragraph(f"النوع: {desc} | القياس: {size}"); apply_rtl(p_size)
                table = doc.add_table(rows=1, cols=2); table.style = 'Table Grid'; set_table_rtl(table)
                hdr = table.rows[0].cells
                for cell in hdr:
                    shading_elm = OxmlElement('w:shd'); shading_elm.set(qn('w:fill'), PURPLE_COLOR)
                    cell._element.get_or_add_tcPr().append(shading_elm)
                    run = cell.paragraphs[0].add_run(); run.font.color.rgb = RGBColor(255, 255, 255); run.bold = True
                
                hdr[0].text = f"الشبكة: {net}"; hdr[1].text = "العدد"
                for cell in hdr: apply_rtl(cell)
                for _, row in group_df.iterrows():
                    row_cells = table.add_row().cells
                    row_cells[0].text = str(row['الموقع']); row_cells[1].text = str(row['العدد'])
                    for cell in row_cells: apply_rtl(cell)

                total_q = pd.to_numeric(group_df['العدد']).sum()
                f_p, f_a = float(group_df['fee_print'].iloc[0]), float(group_df['fee_ads'].iloc[0])
                sum_total = total_q * (f_p + f_a)
                p_sum = doc.add_paragraph()
                txt = f"إجمالي العدد: {int(total_q)} | المجموع للقسم: {sum_total:,.0f}$"
                run_sum = p_sum.add_run(txt); run_sum.bold = True; apply_rtl(p_sum)

    p_grand = doc.add_paragraph()
    p_grand.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_grand = p_grand.add_run(f"إجمالي القيمة المالية للعرض بالكامل: {grand_total:,.0f} $")
    run_grand.bold = True; run_grand.font.size = Pt(14); run_grand.font.color.rgb = RGBColor(102, 0, 153)
    apply_rtl(p_grand)

    p_note = doc.add_paragraph()
    p_note.add_run("• ملاحظة: هذه المواقع المتاحة سارية لمدة 48 ساعة من تاريخ العرض.").bold = True
    apply_rtl(p_note)
    
    target = io.BytesIO(); doc.save(target); target.seek(0)
    return target

# --- 3. Manage Expired Offers (New Function) ---
def manage_expired_offers(conn):
    st.subheader("⚠️ إدارة العروض التي تجاوزت 48 ساعة")
    query = """
    SELECT id, client_name, offer_date 
    FROM "offers_history" 
    WHERE status = 'Pending' 
    AND offer_date < NOW() - INTERVAL '48 hours'
    """
    expired_df = pd.read_sql(query, conn)
    
    if not expired_df.empty:
        st.warning(f"يوجد {len(expired_df)} عروض تجاوزت المهلة المحددة.")
        for _, row in expired_df.iterrows():
            col1, col2, col3 = st.columns([2, 1, 1])
            col1.write(f"الزبون: {row['client_name']} ({row['offer_date']})")
            if col2.button(f"✅ تمديد", key=f"ext_{row['id']}"):
                cur = conn.cursor()
                cur.execute('UPDATE "offers_history" SET offer_date = NOW() WHERE id = %s', (row['id'],))
                conn.commit(); st.rerun()
            if col3.button(f"❌ إلغاء", key=f"can_{row['id']}"):
                cur = conn.cursor()
                cur.execute("UPDATE \"offers_history\" SET status = 'Cancelled' WHERE id = %s", (row['id'],))
                conn.commit(); st.rerun()
    else:
        st.success("لا توجد عروض منتهية الصلاحية حالياً.")
# الجزء الثاني

# --- 4. Main App Logic (Part 2/2) ---
st.set_page_config(page_title="PreView Ads ERP - Cloud", layout="wide")
SYRIA_CITIES_COORDS = {
    "دمشق": [33.51, 36.27], "ريف دمشق": [33.45, 36.35], "حلب": [36.20, 37.13],
    "حمص": [34.73, 36.71], "حماة": [35.13, 36.75], "اللاذقية": [35.53, 35.79],
    "طرطوس": [34.88, 35.88], "سوريا": [34.80, 38.99]
}

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
        page = st.radio("القائمة", ["📊 Dashboard", "📄 Quotation", "📋 تقرير الجرد", "⚙️ الإعدادات"])
        if st.button("تسجيل الخروج"): 
            st.session_state.auth = False
            st.rerun()

    # --- Page: Dashboard ---

    if page == "📊 Dashboard":
        st.title("📊 الخريطة التفاعلية")
        
        # التأكد من وجود اتصال فعال
        if conn is None:
            st.error("لا يوجد اتصال بقاعدة البيانات. تأكد من إعدادات السيرفر.")
        else:
            try:
                df_all = pd.read_sql('SELECT * FROM "اعمدة انارة"', conn)
                df_booked = pd.read_sql('SELECT "رقم اللوحة", "اسم الزبون" FROM "حجوزات1"', conn)
                # ... باقي كود الخريطة ...
            except Exception as e:
                st.error(f"خطأ في جلب بيانات الخريطة: {e}")
        
        st.title("📊 الخريطة التفاعلية وحالة الإشغال")
        df_all = pd.read_sql('SELECT * FROM "اعمدة انارة"', conn)
        df_booked = pd.read_sql('SELECT "رقم اللوحة", "اسم الزبون" FROM "حجوزات1"', conn)
        
        # ربط البيانات لتحديد الحالة على الخريطة
        df_merged = pd.merge(df_all, df_booked, on='رقم اللوحة', how='left')
        
        c1, c2 = st.columns([3, 1])
        with c2:
            st.info("💡 دليل الألوان:")
            st.markdown("🔴 **أحمر:** محجوز حالياً")
            st.markdown("🟣 **موف:** متاح للإعلان")
            sel_city_map = st.selectbox("تركيز الخريطة على:", list(SYRIA_CITIES_COORDS.keys()), index=7)

        with c1:
            m = folium.Map(location=SYRIA_CITIES_COORDS[sel_city_map], zoom_start=8)
            cluster = MarkerCluster().add_to(m)
            for _, r in df_merged.iterrows():
                if pd.notnull(r.get('Latitude')) and pd.notnull(r.get('Longitude')):
                    is_booked = pd.notnull(r['اسم الزبون'])
                    color = 'red' if is_booked else 'purple'
                    popup_html = f"<b>الموقع:</b> {r['اسم العمود']}<br><b>الحالة:</b> {'محجوز' if is_booked else 'متاح'}"
                    folium.Marker([r['Latitude'], r['Longitude']], 
                                  popup=folium.Popup(popup_html, max_width=200), 
                                  icon=folium.Icon(color=color, icon='info-sign')).add_to(cluster)
            st_folium(m, width="100%", height=500)

    # --- Page: Quotation (The Core) ---
    elif page == "📄 Quotation":
        st.title("📄 بناء عرض سعر وإدارة الحجوزات")
        
        # 1. نظام تنبيه العروض المنتهية (الميزة المطلوبة)
        with st.expander("🔔 تنبيهات العروض المزامنة (48 ساعة)", expanded=False):
            manage_expired_offers(conn)

        # 2. استعادة العروض المحفوظة
        st.subheader("📂 استرجاع عرض من المسودات")
        saved_off_df = pd.read_sql('SELECT id, client_name, offer_date FROM "offers_history" WHERE status=\'Pending\' ORDER BY offer_date DESC', conn)
        if not saved_off_df.empty:
            off_options = {f"{r['client_name']} - بتاريخ {r['offer_date']}": r['id'] for _, r in saved_off_df.iterrows()}
            sel_label = st.selectbox("اختر عرضاً محفوظاً:", ["---"] + list(off_options.keys()))
            if sel_label != "---" and st.button("🔄 استعادة السلة"):
                off_id = off_options[sel_label]
                res = pd.read_sql(f'SELECT cart_json, client_name FROM "offers_history" WHERE id={off_id}', conn)
                if not res.empty:
                    data = json.loads(res['cart_json'].iloc[0])
                    # تحويل الـ dict المسترجع إلى DataFrames مرة أخرى
                    st.session_state.cart = {c: {n: pd.DataFrame(d) for n, d in ns.items()} for c, ns in data.items()}
                    st.session_state.temp_cust = res['client_name'].iloc[0]
                    st.success("تم شحن السلة بالبيانات!")

        st.divider()
        
        # 3. واجهة الاختيار والحساب
        draw_df = pd.read_sql('SELECT * FROM "اسماء الرسم"', conn)
        df_periods = pd.read_sql('SELECT * FROM "الفترة" ORDER BY "no"', conn)
        
        col_a, col_b = st.columns(2)
        with col_a: cust = st.text_input("اسم الزبون المستهدف:", value=st.session_state.get('temp_cust', ""))
        with col_b: b_year = st.number_input("عام الحجز:", value=2026)

        c1, c2, c3 = st.columns(3)
        with c1: sel_size = st.selectbox("مقاس اللوحة:", draw_df['الحجم'].unique().tolist())
        with c2: print_type = st.radio("نوع الطباعة:", ["عادي", "سكوتش"], horizontal=True)
        with c3:
            start_p = st.selectbox("من فترة:", df_periods['namee'].tolist())
            end_p = st.selectbox("إلى فترة:", df_periods['namee'].tolist(), index=len(df_periods)-1)

        # حساب الفترات المستهدفة
        s_no = int(df_periods[df_periods['namee'] == start_p]['no'].iloc[0])
        e_no = int(df_periods[df_periods['namee'] == end_p]['no'].iloc[0])
        target_periods = df_periods[(df_periods['no'] >= s_no) & (df_periods['no'] <= e_no)]['namee'].tolist()
        
        # جلب الأسعار ديناميكياً
        subset = draw_df[draw_df['الحجم'] == sel_size]
        f_print = subset[subset['اسم الرسم'].str.contains(f"طباعة.*{print_type}")]['اجرة الرسم'].sum()
        f_ads = subset[subset['اسم الرسم'].str.contains(f"عرض.*{print_type}")]['اجرة الرسم'].sum()

        # فلترة المتاح في المحافظة المختارة
        city_l = pd.read_sql('SELECT DISTINCT "المحافظة" FROM "اعمدة انارة"', conn)['المحافظة'].tolist()
        sel_city = st.selectbox("اختر المحافظة للمواقع:", city_l)
        
        p_str = ", ".join([f"'{p}'" for p in target_periods])
        booked_ids = pd.read_sql(f'SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" WHERE "العام"={b_year} AND "فترة الحجز" IN ({p_str})', conn)['رقم اللوحة'].tolist()
        
        available_raw = pd.read_sql(f'SELECT "رقم اللوحة", "اسم العمود" as "الموقع", "العدد", "الشبكة", "توصيف العمود", "الحجم" FROM "اعمدة انارة" WHERE "المحافظة"=\'{sel_city}\' AND "الحجم"=\'{sel_size}\'', conn)
        available_raw = available_raw[~available_raw['رقم اللوحة'].isin(booked_ids)]
        
        if not available_raw.empty:
            nets = st.multiselect("الشبكات المتاحة:", available_raw['الشبكة'].unique().tolist())
            if st.button("➕ إضافة الشبكات المختارة للسلة"):
                if sel_city not in st.session_state.cart: st.session_state.cart[sel_city] = {}
                for n in nets:
                    st.session_state.cart[sel_city][n] = available_raw[available_raw['الشبكة'] == n].assign(fee_print=f_print, fee_ads=f_ads, الحجم=sel_size)
                st.rerun()

        # 4. عرض السلة والعمليات النهائية
        if st.session_state.cart:
            st.divider()
            st.subheader("🛒 تفاصيل العرض المجمع")
            grand_total = 0
            for city, nets in list(st.session_state.cart.items()):
                for net, df in list(nets.items()):
                    with st.expander(f"📍 {city} - شبكة {net}", expanded=True):
                        edited = st.data_editor(df, key=f"edit_{city}_{net}", num_rows="dynamic")
                        st.session_state.cart[city][net] = edited
                        total_q = pd.to_numeric(edited['العدد']).sum()
                        grand_total += total_q * (f_print + f_ads)
                        if st.button("حذف هذه الشبكة", key=f"del_{city}_{net}"):
                            del st.session_state.cart[city][net]
                            st.rerun()
            
            st.metric("إجمالي القيمة المالية للعرض", f"{grand_total:,.0f} $")
            
            b1, b2, b3, b4 = st.columns(4)
            with b1:
                if st.button("💾 حفظ كمسودة (48س)"):
                    if not cust: st.error("يرجى إدخال اسم الزبون")
                    else:
                        c_json = json.dumps({c: {n: df.to_dict() for n, df in ns.items()} for c, ns in st.session_state.cart.items()}, ensure_ascii=False)
                        cur = conn.cursor()
                        cur.execute('INSERT INTO "offers_history" (client_name, cart_json, start_p, end_p, year, status) VALUES (%s, %s, %s, %s, %s, %s)', (cust, c_json, start_p, end_p, b_year, 'Pending'))
                        conn.commit(); st.success("تم الحفظ في المسودات.")
            with b2:
                if st.button("✅ تثبيت الحجز نهائياً"):
                    if not cust: st.error("أدخل اسم الزبون للتثبيت")
                    else:
                        recs = []
                        for _, nets in st.session_state.cart.items():
                            for _, df in nets.items():
                                for _, row in df.iterrows():
                                    for p_name in target_periods:
                                        recs.append((str(row['رقم اللوحة']), str(cust), str(p_name), int(b_year)))
                        cur = conn.cursor()
                        cur.executemany('INSERT INTO "حجوزات1" ("رقم اللوحة", "اسم الزبون", "فترة الحجز", "العام") VALUES (%s, %s, %s, %s)', recs)
                        conn.commit(); st.session_state.cart = {}; st.success("تم التثبيت في قاعدة البيانات!"); st.rerun()
            with b3:
                if st.button("📝 تصدير ملف Word"):
                    doc_io = export_word(cust, st.session_state.cart, start_p, end_p, grand_total)
                    st.download_button("📥 تحميل العرض", doc_io, f"Offer_{cust}.docx")
            with b4:
                if st.button("🗑️ تفريغ السلة"): st.session_state.cart = {}; st.rerun()

    # --- Page: تقرير الجرد ---
    elif page == "📋 تقرير الجرد":
        st.title("📋 تقرير الإشغال والجرد السحابي")
        df_periods = pd.read_sql('SELECT "no", "namee" FROM "الفترة" ORDER BY "no"', conn)
        c1, c2, c3 = st.columns(3)
        with c1: start_p = st.selectbox("من فترة:", df_periods['namee'].tolist(), key="r1")
        with c2: end_p = st.selectbox("إلى فترة:", df_periods['namee'].tolist(), index=len(df_periods)-1, key="r2")
        with c3: b_year = st.number_input("العام:", value=2026, key="r3")

        p_names = df_periods[(df_periods['no'] >= int(df_periods[df_periods['namee']==start_p]['no'].iloc[0])) & 
                            (df_periods['no'] <= int(df_periods[df_periods['namee']==end_p]['no'].iloc[0]))]['namee'].tolist()
        
        all_boards = pd.read_sql('SELECT "رقم اللوحة", "المحافظة", "الحجم" FROM "اعمدة انارة"', conn)
        p_placeholders = ", ".join([f"'{p}'" for p in p_names])
        query_booked = f'SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" WHERE "العام"={b_year} AND "فترة الحجز" IN ({p_placeholders})'

        booked_list = pd.read_sql(query_booked, conn)['رقم اللوحة'].tolist()
        all_boards['Status'] = all_boards['رقم اللوحة'].apply(lambda x: 'محجوز' if x in booked_list else 'متاح')

        for city in all_boards['المحافظة'].unique():
            st.subheader(f"📍 {city}")
            city_df = all_boards[all_boards['المحافظة'] == city]
            stats = city_df.groupby(['الحجم', 'Status']).size().unstack(fill_value=0)
            st.table(stats)

    # --- Page: الإعدادات (حفظ آمن) ---
    elif page == "⚙️ الإعدادات":
        st.title("⚙️ إدارة البيانات الأساسية")
        engine = get_engine()
        tab1, tab2 = st.tabs(["📝 اللوحات الإعلانية", "📅 سجل الحجوزات"])
        
        with tab1:
            df = pd.read_sql('SELECT * FROM "اعمدة انارة"', conn)
            new_df = st.data_editor(df, num_rows="dynamic", key="set_b")
            if st.button("حفظ التغييرات في اللوحات"):
                # الحفظ الآمن: حذف القديم وإضافة الجديد في transaction واحدة
                with engine.begin() as sql_conn:
                    sql_conn.execute(text('DELETE FROM "اعمدة انارة"'))
                    new_df.to_sql("اعمدة انارة", sql_conn, if_exists="append", index=False)
                st.success("تم تحديث جدول اللوحات بنجاح.")

        with tab2:
            df_h = pd.read_sql('SELECT * FROM "حجوزات1" ORDER BY id DESC LIMIT 500', conn)
            new_h = st.data_editor(df_h, num_rows="dynamic", key="set_h")
            if st.button("تحديث سجل الحجوزات"):
                with engine.begin() as sql_conn:
                    sql_conn.execute(text('DELETE FROM "حجوزات1"'))
                    new_h.to_sql("حجوزات1", sql_conn, if_exists="append", index=False)
                st.success("تمت مزامنة السجلات.")

    if 'conn' in locals() and conn: conn.close()
