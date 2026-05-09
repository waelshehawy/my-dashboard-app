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

# --- 1. Database Connection ---
def get_connection():
    try:
        return psycopg2.connect(
            host="://supabase.com", 
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
    uri = "postgresql://postgres.ncuofpvbaglwbdqnpman:WaelPreview2026@://supabase.com:6543/postgres"
    return create_engine(uri)

# --- 2. Word RTL & Formatting Helpers ---
def _force_rtl_style(p):
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT # اليسار هنا يعني اليمين بسبب bidi
    pPr = p._element.get_or_add_pPr()
    bidi = OxmlElement('w:bidi'); bidi.set(qn('w:val'), '1'); pPr.append(bidi)
    for run in p.runs:
        rPr = run._element.get_or_add_rPr()
        rtl = OxmlElement('w:rtl'); rtl.set(qn('w:val'), '1'); rPr.append(rtl)
        rFonts = OxmlElement('w:rFonts'); rFonts.set(qn('w:cs'), 'Arial'); rPr.append(rFonts)

def set_table_rtl(table):
    tblPr = table._element.xpath('w:tblPr')[0]
    bidi = OxmlElement('w:bidiVisual'); tblPr.append(bidi)

def export_word(customer_name, cart_data, start_p, end_p, grand_total):
    doc = Document('template.docx') if os.path.exists('template.docx') else Document()
    PURPLE_COLOR = "660099" 
    
    # إضافة التاريخ في أعلى اليمين
    today_date = datetime.now().strftime("%d / %m / %Y")
    p_date = doc.add_paragraph(); p_date.add_run(f"التاريخ: {today_date}"); _force_rtl_style(p_date)

    p_cust = doc.add_paragraph(); p_cust.add_run(f"السادة شركة {customer_name} المحترمين").bold = True
    _force_rtl_style(p_cust)
    
    p_stat = doc.add_paragraph()
    p_stat.add_run(f"موضوع العرض: حجز مواقع إعلانية للفترة من ({start_p}) ولغاية ({end_p})")
    _force_rtl_style(p_stat)

    doc.add_paragraph(); doc.add_paragraph() # مسافة سطرين

    for city, networks in cart_data.items():
        p_city = doc.add_paragraph(); p_city.add_run(f"■ محافظة {city}").bold = True
        _force_rtl_style(p_city)
        for net, df in networks.items():
            if df.empty: continue
            for size_info, group_df in df.groupby(['الحجم']):
                p_size = doc.add_paragraph(); p_size.add_run(f"الشبكة: {net} | القياس: {size_info}").bold = True
                _force_rtl_style(p_size)
                
                table = doc.add_table(rows=1, cols=2); table.style = 'Table Grid'; set_table_rtl(table)
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
                f_p, f_a = float(group_df['fee_print'].max()), float(group_df['fee_ads'].max())
                sum_combined = total_q * (f_p + f_a)
                
                p_fin = doc.add_paragraph()
                txt = (f"إجمالي العدد: {int(total_q)} | أجور الطباعة: {total_q*f_p:,.0f}$ | "
                       f"أجور العرض: {total_q*f_a:,.0f}$ | المجموع للقسم: {sum_combined:,.0f}$")
                p_fin.add_run(txt).bold = True; _force_rtl_style(p_fin)

    p_grand = doc.add_paragraph()
    run_g = p_grand.add_run(f"إجمالي القيمة المالية للعرض بالكامل: {grand_total:,.0f} $")
    run_g.bold = True; run_g.font.size = Pt(14); run_g.font.color.rgb = RGBColor(102, 0, 153)
    _force_rtl_style(p_grand)

    doc.add_paragraph()
    p_note = doc.add_paragraph(); p_note.add_run("• ملاحظة: هذه المواقع متاحة لمدة 48 ساعة.").bold = True
    _force_rtl_style(p_note)

    target = io.BytesIO(); doc.save(target); target.seek(0)
    return target

# --- 3. Manage Expired Offers ---
def manage_expired_offers(conn):
    query = 'SELECT id, client_name, offer_date FROM "offers_history" WHERE status = \'Pending\' AND offer_date < NOW() - INTERVAL \'48 hours\''
    expired_df = pd.read_sql(query, conn)
    if not expired_df.empty:
        st.warning(f"يوجد {len(expired_df)} عروض متجاوزة للمدة.")
        for _, row in expired_df.iterrows():
            col1, col2, col3 = st.columns([2,1,1])
            col1.write(f"الزبون: {row['client_name']} ({row['offer_date']})")
            if col2.button("✅ تمديد", key=f"ext_{row['id']}"):
                cur = conn.cursor(); cur.execute('UPDATE "offers_history" SET offer_date = NOW() WHERE id = %s', (row['id'],)); conn.commit(); st.rerun()
            if col3.button("❌ إلغاء", key=f"can_{row['id']}"):
                cur = conn.cursor(); cur.execute("UPDATE \"offers_history\" SET status = 'Cancelled' WHERE id = %s", (row['id'],)); conn.commit(); st.rerun()
# --- 4. Main App Setup ---
st.set_page_config(page_title="PreView Ads ERP", layout="wide")
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
        # --- Page 1: Dashboard ---
        if page == "📊 Dashboard":
            st.title("📊 الحالة الحالية للخريطة")
            try:
                curr_yr = datetime.now().year
                df_b = pd.read_sql(f'SELECT DISTINCT "رقم اللوحة", "اسم الزبون" FROM "حجوزات1" WHERE "العام"={curr_yr}', conn)
                df_all = pd.read_sql('SELECT * FROM "اعمدة انارة"', conn)
                df_map = pd.merge(df_all, df_b, on='رقم اللوحة', how='left').drop_duplicates(subset=['رقم اللوحة'])
                
                c1, c2, c3 = st.columns(3)
                c1.metric("إجمالي اللوحات", len(df_map))
                c2.metric("محجوز حالياً", int(df_map['اسم الزبون'].notnull().sum()))
                c3.metric("متاح حالياً", int(df_map['اسم الزبون'].isnull().sum()))

                m = folium.Map(location=SYRIA_CITIES_COORDS["سوريا"], zoom_start=7)
                cluster = MarkerCluster().add_to(m)
                for _, r in df_map.iterrows():
                    if pd.notnull(r.get('Latitude')):
                        is_b = pd.notnull(r['اسم الزبون'])
                        folium.Marker([r['Latitude'], r['Longitude']], 
                                      popup=f"{r['اسم العمود']} - {'محجوز' if is_b else 'متاح'}", 
                                      icon=folium.Icon(color='red' if is_b else 'purple')).add_to(cluster)
                st_folium(m, width="100%", height=500)
            except Exception as e: st.error(f"خطأ في الداشبورد: {e}")

        # --- Page 2: Quotation ---
        elif page == "📄 Quotation":
            st.title("📄 عروض الأسعار")
            try:
                with st.expander("🔔 إدارة العروض المنتهية"): manage_expired_offers(conn)
                
                # استعادة المسودة
                saved_df = pd.read_sql('SELECT id, client_name FROM "offers_history" WHERE status=\'Pending\'', conn)
                if not saved_df.empty:
                    sel_id = st.selectbox("استعادة مسودة:", ["---"] + saved_df['client_name'].tolist())
                    if sel_id != "---" and st.button("🔄 تحميل"):
                        res = pd.read_sql(f"SELECT cart_json FROM \"offers_history\" WHERE client_name='{sel_id}' LIMIT 1", conn)
                        data = json.loads(res['cart_json'].iloc[0])
                        st.session_state.cart = {c: {n: pd.DataFrame(d) for n, d in ns.items()} for c, ns in data.items()}
                        st.rerun()

                st.divider()
                draw_df = pd.read_sql('SELECT * FROM "اسماء الرسم"', conn)
                df_p = pd.read_sql('SELECT * FROM "الفترة" ORDER BY "no"', conn)
                cust = st.text_input("اسم الزبون", value=st.session_state.get('temp_cust', ""))
                
                c1, c2, c3 = st.columns(3)
                with c1: sz = st.selectbox("المقاس:", draw_df['الحجم'].unique().tolist())
                with c2: pt = st.radio("الطباعة:", ["عادي", "سكوتش"])
                with c3: yr = st.number_input("العام:", value=2026)

                # حساب الأجور والفلترة
                subset = draw_df[draw_df['الحجم'] == sz]
                f_pr = float(subset[subset['اسم الرسم'].str.contains(f"طباعة.*{pt}", na=False)]['اجرة الرسم'].sum())
                f_ad = float(subset[subset['اسم الرسم'].str.contains(f"عرض.*{pt}", na=False)]['اجرة الرسم'].sum())
                
                city_l = pd.read_sql('SELECT DISTINCT "المحافظة" FROM "اعمدة انارة"', conn)['المحافظة'].tolist()
                sel_c = st.selectbox("المحافظة:", city_l)
                
                raw = pd.read_sql(f"SELECT * FROM \"اعمدة انارة\" WHERE \"المحافظة\"='{sel_c}' AND \"الحجم\"='{sz}'", conn)
                if not raw.empty:
                    raw['الشبكة'] = raw['الشبكة'].astype(str)
                    nets = st.multiselect("الشبكات المتاحة:", sorted(raw['الشبكة'].unique().tolist()))
                    if st.button("➕ إضافة"):
                        if sel_c not in st.session_state.cart: st.session_state.cart[sel_c] = {}
                        for n in nets: st.session_state.cart[sel_c][n] = raw[raw['الشبكة']==n].assign(fee_print=f_pr, fee_ads=f_ad, الموقع=raw['اسم العمود'])
                        st.rerun()

                if st.session_state.cart:
                    st.divider(); g_total = 0.0
                    for c, ns in list(st.session_state.cart.items()):
                        for n, df in list(ns.items()):
                            with st.expander(f"📍 {c} - {n}"):
                                ed = st.data_editor(df, key=f"e_{c}_{n}")
                                st.session_state.cart[c][n] = ed
                                q = pd.to_numeric(ed['العدد']).sum()
                                g_total += q * (f_pr + f_ad)
                    st.info(f"المجموع: {g_total:,.0f} $")
                    if st.button("📝 تصدير Word"):
                        st.download_button("تحميل", export_word(cust, st.session_state.cart, "فترة", "فترة", g_total), f"{cust}.docx")
            except Exception as e: st.error(f"خطأ في العرض: {e}")

        # --- Page 3: Inventory ---
        elif page == "📋 تقرير الجرد":
            st.title("📋 تقرير الجرد")
            try:
                all_b = pd.read_sql('SELECT "رقم اللوحة", "المحافظة", "الحجم" FROM "اعمدة انارة"', conn)
                booked = pd.read_sql('SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1"', conn)['رقم اللوحة'].tolist()
                all_b['الحالة'] = all_b['رقم اللوحة'].apply(lambda x: 'محجوز' if x in booked else 'متاح')
                for city in sorted(all_b['المحافظة'].unique()):
                    st.write(f"### {city}")
                    st.table(all_b[all_b['المحافظة']==city].groupby(['الحجم', 'الحالة']).size().unstack(fill_value=0))
            except Exception as e: st.error(f"خطأ في الجرد: {e}")

        # --- Page 4: Settings ---
        elif page == "⚙️ الإعدادات":
            st.title("⚙️ إدارة البيانات")
            engine = get_engine()
            tab1, tab2 = st.tabs(["📍 اللوحات", "📅 الحجوزات"])
            with tab1:
                df = pd.read_sql('SELECT * FROM "اعمدة انارة"', conn)
                new_df = st.data_editor(df, num_rows="dynamic")
                if st.button("حفظ اللوحات"):
                    with engine.begin() as cn:
                        cn.execute(text('DELETE FROM "اعمدة انارة"'))
                        new_df.to_sql("اعمدة انارة", cn, if_exists="append", index=False)
                    st.success("تم التحديث")
            with tab2:
                df_h = pd.read_sql('SELECT * FROM "حجوزات1" LIMIT 100', conn)
                new_h = st.data_editor(df_h, num_rows="dynamic")
                if st.button("تحديث الحجوزات"):
                    with engine.begin() as cn:
                        cn.execute(text('DELETE FROM "حجوزات1"'))
                        new_h.to_sql("حجوزات1", cn, if_exists="append", index=False)
                    st.success("تمت المزامنة")
        
        if conn: conn.close()
