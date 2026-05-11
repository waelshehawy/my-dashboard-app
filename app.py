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
from datetime import datetime, timedelta

# --- 1. Database Connections ---
from sqlalchemy.engine import URL

def get_connection():
    try:
        return psycopg2.connect(
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

def get_engine():
    clean_host = "aws-1-eu-north-1.pooler.supabase.com"
    url_obj = URL.create(
        drivername="postgresql+psycopg2",
        username="postgres.ncuofpvbaglwbdqnpman",
        password="WaelPreview2026",
        host=clean_host,
        port=6543,
        database="postgres",
    )
    return create_engine(url_obj, connect_args={'sslmode': 'require'})

# --- 2. Helper Functions ---
def set_table_rtl(table):
    tblPr = table._element.xpath('w:tblPr')[0]
    bidi = OxmlElement('w:bidiVisual')
    tblPr.append(bidi)

def _force_rtl_style(p):
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    pPr = p._element.get_or_add_pPr()
    bidi = OxmlElement('w:bidi'); bidi.set(qn('w:val'), '1'); pPr.append(bidi)
    for run in p.runs:
        rPr = run._element.get_or_add_rPr()
        rtl = OxmlElement('w:rtl'); rtl.set(qn('w:val'), '1'); rPr.append(rtl)
        rFonts = OxmlElement('w:rFonts'); rFonts.set(qn('w:cs'), 'Arial'); rPr.append(rFonts)

def get_fees(draw_df, size, print_type, is_foreign):
    """حساب أجور الطباعة والعرض مع دعم العملاء الأجانب"""
    subset = draw_df[draw_df['الحجم'] == size].copy()
    subset['search_name'] = subset['اسم الرسم'].str.strip().str.replace('أ', 'ا')
    target_pt = print_type.replace('أ', 'ا')
    
    # أجور الطباعة
    f_pr_row = subset[subset['search_name'].str.contains("طباعة", na=False) & 
                      subset['search_name'].str.contains(target_pt, na=False)]
    if f_pr_row.empty and print_type == "عادي":
        f_pr_row = subset[subset['search_name'].str.contains("طباعة", na=False)]
    fee_print = float(f_pr_row['اجرة الرسم'].sum()) if not f_pr_row.empty else 0.0

    # أجور العرض - بحث عن "اجنبي" إذا كان العميل أجنبي
    search_keyword = "اجنبي" if is_foreign else "عرض"
    f_ad_row = subset[subset['search_name'].str.contains(search_keyword, na=False)]
    
    if is_foreign and f_ad_row.empty:
        f_ad_row = subset[subset['search_name'].str.contains("عرض", na=False)]
    
    fee_ads = float(f_ad_row['اجرة الرسم'].sum()) if not f_ad_row.empty else 0.0
    return fee_print, fee_ads

def calculate_days_between(start_period, end_period, periods_df):
    """حساب عدد الأيام بين فترتين من جدول الفترة"""
    try:
        start_row = periods_df[periods_df['namee'] == start_period].iloc[0]
        end_row = periods_df[periods_df['namee'] == end_period].iloc[0]
        
        if 'start_date' in start_row and 'end_date' in end_row:
            if pd.notnull(start_row['start_date']) and pd.notnull(end_row['end_date']):
                return (end_row['end_date'] - start_row['start_date']).days + 1
        return 7
    except:
        return 7

def calculate_total_amount(qty, fee_print, fee_ads, calc_method, days=1):
    """حساب المبلغ الإجمالي"""
    if calc_method == "حساب بالأيام":
        return qty * (fee_print + fee_ads) * days
    else:
        return qty * (fee_print + fee_ads)

def export_word(customer_name, cart_data, start_p, end_p, grand_total, calc_method, days_count, is_foreign):
    """تصدير العرض إلى Word"""
    doc = Document('template.docx') if os.path.exists('template.docx') else Document()
    PURPLE_COLOR = "660099"
    
    doc.add_paragraph()
    today_date = datetime.now().strftime("%d / %m / %Y")
    p_date = doc.add_paragraph()
    p_date.add_run(f"التاريخ: {today_date}")
    _force_rtl_style(p_date)
    doc.add_paragraph()
    
    p_cust = doc.add_paragraph()
    cust_type = " (عميل أجنبي)" if is_foreign else ""
    p_cust.add_run(f"السادة شركة {customer_name} المحترمين{cust_type}").bold = True
    _force_rtl_style(p_cust)

    method_text = f"طريقة الحساب: {calc_method}"
    if calc_method == "حساب بالأيام":
        method_text += f" | عدد الأيام: {days_count}"
    p_method = doc.add_paragraph()
    p_method.add_run(method_text)
    _force_rtl_style(p_method)

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
                
                table = doc.add_table(rows=1, cols=2)
                table.style = 'Table Grid'
                set_table_rtl(table)
                
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

                total_q = pd.to_numeric(group_df['العدد']).sum()
                f_p = float(group_df['fee_print'].iloc[0])
                f_a = float(group_df['fee_ads'].iloc[0])
                sum_print = total_q * f_p
                sum_ads = total_q * f_a
                
                if calc_method == "حساب بالأيام":
                    sum_print *= days_count
                    sum_ads *= days_count
                
                sum_combined = sum_print + sum_ads
                
                p_fin = doc.add_paragraph()
                txt = (f"إجمالي العدد: {int(total_q)} | "
                       f"أجور الطباعة: {sum_print:,.0f}$ | "
                       f"أجور العرض: {sum_ads:,.0f}$ | "
                       f"المجموع للقسم: {sum_combined:,.0f}$")
                p_fin.add_run(txt).bold = True
                _force_rtl_style(p_fin)

    doc.add_paragraph() 
    p_grand = doc.add_paragraph()
    run_g = p_grand.add_run(f"إجمالي القيمة المالية للعرض بالكامل: {grand_total:,.0f} $")
    run_g.bold = True; run_g.font.size = Pt(14); run_g.font.color.rgb = RGBColor(102, 0, 153)
    _force_rtl_style(p_grand)

    doc.add_paragraph()
    p_note = doc.add_paragraph()
    run_note = p_note.add_run("• ملاحظة: هذه المواقع متاحة لمدة 48 ساعة.")
    run_note.bold = True
    _force_rtl_style(p_note)
    
    target = io.BytesIO(); doc.save(target); target.seek(0)
    return target

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

# --- 3. Main App ---
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
        # --- Dashboard Page ---
        if page == "📊 Dashboard":
            st.title("📊 الخريطة التفاعلية وحالة الإشغال")
            current_year = datetime.now().year
            df_booked = pd.read_sql(f'SELECT DISTINCT "رقم اللوحة", "اسم الزبون" FROM "حجوزات1" WHERE "العام" = {current_year}', conn)
            df_all = pd.read_sql('SELECT * FROM "اعمدة انارة"', conn)
            df_map = pd.merge(df_all, df_booked, on='رقم اللوحة', how='left').drop_duplicates(subset=['رقم اللوحة'])
            c1, c2, c3 = st.columns(3)
            c1.metric("إجمالي اللوحات", len(df_map))
            c2.metric("محجوز حالياً", int(df_map['اسم الزبون'].notnull().sum()))
            c3.metric("متاح حالياً", int(df_map['اسم الزبون'].isnull().sum()))
            m = folium.Map(location=SYRIA_CITIES_COORDS["سوريا"], zoom_start=7)
            cluster = MarkerCluster().add_to(m)
            for _, r in df_map.iterrows():
                if pd.notnull(r.get('Latitude')):
                    is_booked = pd.notnull(r['اسم الزبون'])
                    color = 'red' if is_booked else 'purple'
                    popup_text = f"الموقع: {r['اسم العمود']}<br>الحالة: {'محجوز' if is_booked else 'متاح'}"
                    folium.Marker([r['Latitude'], r['Longitude']], popup=folium.Popup(popup_text, max_width=200), icon=folium.Icon(color=color)).add_to(cluster)
            st_folium(m, width="100%", height=600)

        # --- Quotation Page (with new features) ---
        # --- في صفحة Quotation ---
elif page == "📄 Quotation":
    st.title("📄 بناء عرض سعر وتثبيت حجز")
    try:
        with st.expander("🔔 إدارة العروض التي تجاوزت 48 ساعة"):
            manage_expired_offers(conn)

        st.subheader("📂 استرجاع عرض محفوظ")
        saved_off_df = pd.read_sql('SELECT id, client_name FROM "offers_history" WHERE status=\'Pending\' ORDER BY id DESC', conn)
        if not saved_off_df.empty:
            off_options = {r['client_name']: r['id'] for _, r in saved_off_df.iterrows()}
            sel_label = st.selectbox("اختر عرضاً لتعديله:", ["---"] + list(off_options.keys()))
            if sel_label != "---" and st.button("🔄 تحميل للسلة"):
                res = pd.read_sql(f'SELECT cart_json, client_name FROM "offers_history" WHERE id={off_options[sel_label]}', conn)
                if not res.empty:
                    data = json.loads(res['cart_json'].iloc[0])
                    if "data" in data:
                        data = data["data"]
                    st.session_state.cart = {c: {n: pd.DataFrame(d) for n, d in ns.items()} for c, ns in data.items()}
                    st.session_state.temp_cust = res['client_name'].iloc[0]
                    st.rerun()

        st.divider()
        draw_df = pd.read_sql('SELECT * FROM "اسماء الرسم"', conn)
        
        cust = st.text_input("اسم الزبون", value=st.session_state.get('temp_cust', ""))
        
        col1, col2, col3 = st.columns(3)
        with col1: sz = st.selectbox("المقاس:", draw_df['الحجم'].unique().tolist())
        with col2: pt = st.radio("الطباعة:", ["عادي", "سكوتش"], horizontal=True)
        with col3: yr = st.number_input("العام:", value=2026)
        
        # خيارات الحساب
        opt_col1, opt_col2 = st.columns(2)
        with opt_col1:
            is_foreign = st.checkbox("🏢 عميل أجنبي (يبحث عن أجور عرض خاصة)")
        with opt_col2:
            calc_method = st.radio("طريقة حساب الأجور:", ["حساب بالفترات", "حساب بالأيام"], horizontal=True)
        
        # --- حالة حساب بالأيام ---
        if calc_method == "حساب بالأيام":
            col_date1, col_date2 = st.columns(2)
            with col_date1:
                start_date = st.date_input("📅 تاريخ البداية", value=datetime(2026, 4, 1))
            with col_date2:
                end_date = st.date_input("📅 تاريخ النهاية", value=datetime(2026, 4, 10))
            
            if start_date > end_date:
                st.error("⚠️ تاريخ البداية يجب أن يكون قبل تاريخ النهاية")
                days_count = 0
            else:
                days_count = (end_date - start_date).days + 1
                st.info(f"📅 عدد الأيام: {days_count} يوم (الشهر = 28 يوم للحساب)")
        else:
            # حساب بالفترات (الكود القديم)
            df_p = pd.read_sql('SELECT * FROM "الفترة" ORDER BY "no"', conn)
            cp1, cp2 = st.columns(2)
            with cp1: start_p = st.selectbox("من فترة:", df_p['namee'].tolist())
            with cp2: end_p = st.selectbox("إلى فترة:", df_p['namee'].tolist(), index=len(df_p)-1)
            
            s_idx = int(df_p[df_p['namee']==start_p]['no'].iloc[0])
            e_idx = int(df_p[df_p['namee']==end_p]['no'].iloc[0])
            target_p_list = df_p[(df_p['no'] >= s_idx) & (df_p['no'] <= e_idx)]['namee'].tolist()
            p_str = ", ".join([f"'{p}'" for p in target_p_list])
            days_count = 0  # not used
        
        # --- جلب الأجور ---
        def get_fees_advanced(draw_df, size, print_type, is_foreign, calc_method):
            """جلب الأجور مع دعم الأيام"""
            subset = draw_df[draw_df['الحجم'] == size].copy()
            subset['search_name'] = subset['اسم الرسم'].str.strip().str.replace('أ', 'ا')
            target_pt = print_type.replace('أ', 'ا')
            
            # أجور الطباعة (ثابتة)
            f_pr_row = subset[subset['search_name'].str.contains("طباعة", na=False) & 
                              subset['search_name'].str.contains(target_pt, na=False)]
            if f_pr_row.empty and print_type == "عادي":
                f_pr_row = subset[subset['search_name'].str.contains("طباعة", na=False)]
            fee_print = float(f_pr_row['اجرة الرسم'].sum()) if not f_pr_row.empty else 0.0
            
            # أجور العرض - حسب طريقة الحساب
            if calc_method == "حساب بالأيام":
                # نبحث عن "عرض شهري" أو "أجنبي شهري"
                search_keyword = "اجنبي شهري" if is_foreign else "عرض شهري"
                f_ad_row = subset[subset['search_name'].str.contains(search_keyword, na=False)]
                
                if f_ad_row.empty and is_foreign:
                    f_ad_row = subset[subset['search_name'].str.contains("عرض شهري", na=False)]
                
                fee_ads_monthly = float(f_ad_row['اجرة الرسم'].sum()) if not f_ad_row.empty else 0.0
                return fee_print, fee_ads_monthly, "monthly"
            else:
                # حساب بالفترات (نصف شهري)
                search_keyword = "اجنبي" if is_foreign else "عرض"
                f_ad_row = subset[subset['search_name'].str.contains(search_keyword, na=False)]
                if is_foreign and f_ad_row.empty:
                    f_ad_row = subset[subset['search_name'].str.contains("عرض", na=False)]
                fee_ads = float(f_ad_row['اجرة الرسم'].sum()) if not f_ad_row.empty else 0.0
                return fee_print, fee_ads, "period"
        
        fee_print, fee_ads_value, fee_type = get_fees_advanced(draw_df, sz, pt, is_foreign, calc_method)
        
        if calc_method == "حساب بالأيام":
            st.info(f"💰 أجر الطباعة الثابت: {fee_print}$ | أجر العرض الشهري (28 يوم): {fee_ads_value}$")
            if days_count > 0:
                daily_ads = fee_ads_value / 28
                actual_ads = daily_ads * days_count
                st.info(f"📊 حسب الأيام {days_count}: أجر العرض الفعلي = {daily_ads:.2f} × {days_count} = {actual_ads:.2f}$ لكل عمود")
        else:
            st.info(f"💰 أجر الطباعة: {fee_print}$ | أجر العرض (نصف شهري): {fee_ads_value}$")
        
        # --- باقي الكود (فلترة المواقع، إضافة للسلة، الحسابات) ---
        # يجب تعديل حساب الإجمالي في السلة ليتناسب مع طريقة الأيام
        
        if st.session_state.cart:
            st.divider()
            g_total = 0.0
            
            for c, ns in list(st.session_state.cart.items()):
                for n, df_cart in list(ns.items()):
                    with st.expander(f"📍 {c} - {n}", expanded=True):
                        ed = st.data_editor(df_cart, key=f"ed_{c}_{n}", num_rows="dynamic")
                        st.session_state.cart[c][n] = ed
                        q = pd.to_numeric(ed['العدد']).sum()
                        f_p_v = float(ed['fee_print'].max()) if 'fee_print' in ed.columns else 0.0
                        f_a_v = float(ed['fee_ads'].max()) if 'fee_ads' in ed.columns else 0.0
                        
                        if calc_method == "حساب بالأيام" and days_count > 0:
                            # أجر العرض = (الأجر الشهري / 28) × عدد الأيام
                            daily_ads = f_a_v / 28
                            actual_ads_per_column = daily_ads * days_count
                            total_per_column = f_p_v + actual_ads_per_column
                            g_total += q * total_per_column
                        else:
                            # حساب بالفترات (نصف شهري)
                            g_total += q * (f_p_v + f_a_v)
                        
                        if st.button("حذف الشبكة", key=f"del_{c}_{n}"):
                            del st.session_state.cart[c][n]
                            st.rerun()
            
            st.info(f"### 💰 إجمالي العرض: {g_total:,.2f} $")
            # ... باقي الأزرار (حفظ، تثبيت، تصدير)
                    
                    b1, b2, b3, b4 = st.columns(4)
                    with b1:
                        if st.button("💾 حفظ مسودة"):
                            if not cust: st.error("أدخل اسم الزبون")
                            else:
                                cart_with_meta = {
                                    "data": {c: {n: df.to_dict() for n, df in ns.items()} for c, ns in st.session_state.cart.items()},
                                    "calc_method": calc_method,
                                    "is_foreign": is_foreign,
                                    "days": days_count if calc_method == "حساب بالأيام" else None
                                }
                                c_json = json.dumps(cart_with_meta, ensure_ascii=False)
                                cur = conn.cursor()
                                cur.execute('INSERT INTO "offers_history" (client_name, cart_json, status) VALUES (%s, %s, %s)', (cust, c_json, 'Pending'))
                                conn.commit(); st.success("تم الحفظ")
                    with b2:
                        if st.button("✅ تثبيت نهائي"):
                            if not cust: st.error("أدخل اسم الزبون")
                            else:
                                recs = [(str(r['رقم اللوحة']), str(cust), str(p), int(yr)) for _, ns in st.session_state.cart.items() for _, df in ns.items() for _, r in df.iterrows() for p in target_p_list]
                                cur = conn.cursor(); cur.executemany('INSERT INTO "حجوزات1" ("رقم اللوحة", "اسم الزبون", "فترة الحجز", "العام") VALUES (%s, %s, %s, %s)', recs)
                                conn.commit(); st.session_state.cart = {}; st.success("تم التثبيت نهائياً!"); st.rerun()
                    with b3:
                        if st.button("📝 تصدير Word"):
                            word_file = export_word(cust, st.session_state.cart, start_p, end_p, g_total, calc_method, days_count, is_foreign)
                            st.download_button("📥 تحميل العرض", word_file, f"Offer_{cust}.docx")
                    with b4:
                        if st.button("🔴 تفريغ السلة"): st.session_state.cart = {}; st.rerun()
            except Exception as e:
                st.error(f"❌ خطأ تقني: {e}")

        # --- Inventory Report Page ---
        elif page == "📋 تقرير الجرد":
            st.title("📋 تقرير الإشغال والجرد السحابي")
            try:
                df_p = pd.read_sql('SELECT "no", "namee" FROM "الفترة" ORDER BY "no"', conn)
                c1, c2, c3 = st.columns(3)
                with c1: s_p = st.selectbox("من فترة:", df_p['namee'].tolist(), key="inv_s")
                with c2: e_p = st.selectbox("إلى فترة:", df_p['namee'].tolist(), index=len(df_p)-1, key="inv_e")
                with c3: yr = st.number_input("العام:", value=2026, key="inv_y")
                
                s_idx = int(df_p[df_p['namee'] == s_p]['no'].iloc[0])
                e_idx = int(df_p[df_p['namee'] == e_p]['no'].iloc[0])
                target_p_names = df_p[(df_p['no'] >= s_idx) & (df_p['no'] <= e_idx)]['namee'].tolist()
                p_placeholders = ", ".join([f"'{p}'" for p in target_p_names])
                
                all_b = pd.read_sql('SELECT "رقم اللوحة", "المحافظة", "الحجم" FROM "اعمدة انارة"', conn)
                booked_query = f'SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" WHERE "العام"={yr} AND "فترة الحجز" IN ({p_placeholders})'
                booked_list = pd.read_sql(booked_query, conn)['رقم اللوحة'].tolist()
                all_b['الحالة'] = all_b['رقم اللوحة'].apply(lambda x: 'محجوز' if x in booked_list else 'متاح')
                
                t_all = len(all_b); t_booked = len(booked_list); t_avail = t_all - t_booked
                
                st.subheader("📥 روابط التحميل")
                m1, m2, m3 = st.columns(3)
                m1.metric("إجمالي اللوحات", t_all)
                m2.metric("المحجوز", t_booked)
                m3.metric("المتاح", t_avail)
                
                csv = all_b.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                st.download_button("📥 تصدير Excel", csv, f"Inventory_{yr}.csv", "text/csv")
                
                st.divider()
                for city in sorted(all_b['المحافظة'].unique()):
                    st.write(f"#### 📍 محافظة {city}")
                    c_df = all_b[all_b['المحافظة'] == city]
                    c_stats = c_df.groupby(['الحجم', 'الحالة']).size().unstack(fill_value=0)
                    if 'محجوز' not in c_stats.columns: c_stats['محجوز'] = 0
                    if 'متاح' not in c_stats.columns: c_stats['متاح'] = 0
                    st.table(c_stats)
            except Exception as e:
                st.error(f"⚠️ خطأ: {e}")

        # --- Settings Page ---
        elif page == "⚙️ الإعدادات":
            st.title("⚙️ إدارة البيانات الأساسية")
            st.info("💡 يمكنك تعديل البيانات مباشرة من الجداول")
            
            try:
                engine = get_engine()
                tab1, tab2, tab3 = st.tabs(["📍 اللوحات", "📅 الحجوزات", "💰 أجور الرسم"])
                
                with tab1:
                    st.subheader("أعمدة الإنارة")
                    df_boards = pd.read_sql('SELECT * FROM "اعمدة انارة"', conn)
                    new_boards = st.data_editor(df_boards, num_rows="dynamic", key="editor_boards")
                    if st.button("💾 حفظ اللوحات"):
                        with engine.begin() as cn:
                            cn.execute(text('DELETE FROM "اعمدة انارة"'))
                            new_boards.to_sql("اعمدة انارة", cn, if_exists="append", index=False)
                        st.success("✅ تم التحديث")
                
                with tab2:
                    st.subheader("سجل الحجوزات")
                    df_booking = pd.read_sql('SELECT * FROM "حجوزات1" LIMIT 500', conn)
                    new_booking = st.data_editor(df_booking, num_rows="dynamic", key="editor_bookings")
                    if st.button("💾 تحديث الحجوزات"):
                        with engine.begin() as cn:
                            cn.execute(text('DELETE FROM "حجوزات1"'))
                            new_booking.to_sql("حجوزات1", cn, if_exists="append", index=False)
                        st.success("✅ تم التحديث")
                
                with tab3:
                    st.subheader("أجور الرسم")
                    df_prices = pd.read_sql('SELECT * FROM "اسماء الرسم"', conn)
                    new_prices = st.data_editor(df_prices, num_rows="dynamic", key="editor_prices")
                    if st.button("💾 حفظ الأسعار"):
                        with engine.begin() as cn:
                            cn.execute(text('DELETE FROM "اسماء الرسم"'))
                            new_prices.to_sql("اسماء الرسم", cn, if_exists="append", index=False)
                        st.success("✅ تم التحديث")
            except Exception as e:
                st.error(f"⚠️ خطأ: {e}")

        conn.close()
