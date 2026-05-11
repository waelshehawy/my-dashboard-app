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
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from sqlalchemy import create_engine, text
from datetime import datetime

# ==================== اتصالات قاعدة البيانات ====================
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
        st.error(f"⚠️ فشل الاتصال: {e}")
        return None

def get_engine():
    url_obj = URL.create(
        drivername="postgresql+psycopg2",
        username="postgres.ncuofpvbaglwbdqnpman",
        password="WaelPreview2026",
        host="aws-1-eu-north-1.pooler.supabase.com",
        port="6543",
        database="postgres",
    )
    return create_engine(url_obj, connect_args={'sslmode': 'require'})

# ==================== دوال مساعدة ====================
def set_table_rtl(table):
    tblPr = table._element.xpath('w:tblPr')[0]
    bidi = OxmlElement('w:bidiVisual')
    tblPr.append(bidi)

def force_rtl(p):
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

def get_fees(draw_df, size, print_type, is_foreign):
    """جلب أجور الطباعة والعرض"""
    subset = draw_df[draw_df['الحجم'] == size].copy()
    subset['search_name'] = subset['اسم الرسم'].str.strip().str.replace('أ', 'ا')
    target_pt = print_type.replace('أ', 'ا')
    
    # أجور الطباعة
    f_pr = subset[subset['search_name'].str.contains("طباعة", na=False) & 
                  subset['search_name'].str.contains(target_pt, na=False)]
    if f_pr.empty and print_type == "عادي":
        f_pr = subset[subset['search_name'].str.contains("طباعة", na=False)]
    fee_print = float(f_pr['اجرة الرسم'].sum()) if not f_pr.empty else 0.0
    
    # أجور العرض (شهري 28 يوم)
    search = "اجنبي شهري" if is_foreign else "عرض شهري"
    f_ad = subset[subset['search_name'].str.contains(search, na=False)]
    if is_foreign and f_ad.empty:
        f_ad = subset[subset['search_name'].str.contains("عرض شهري", na=False)]
    fee_ads_monthly = float(f_ad['اجرة الرسم'].sum()) if not f_ad.empty else 0.0
    
    return fee_print, fee_ads_monthly

def export_word(cust, cart, start_date, end_date, total, days, is_foreign, fee_print_val, fee_ads_monthly):
    """تصدير عرض السعر"""
    doc = Document()
    
    # التاريخ
    p = doc.add_paragraph()
    p.add_run(f"التاريخ: {datetime.now().strftime('%d/%m/%Y')}")
    force_rtl(p)
    
    # العميل
    p = doc.add_paragraph()
    p.add_run(f"السادة شركة {cust} المحترمين{' (عميل أجنبي)' if is_foreign else ''}").bold = True
    force_rtl(p)
    
    # فترة العرض
    p = doc.add_paragraph()
    p.add_run(f"عرض إعلان من تاريخ {start_date.strftime('%Y/%m/%d')} لغاية {end_date.strftime('%Y/%m/%d')}")
    force_rtl(p)
    
    # طريقة الحساب
    p = doc.add_paragraph()
    p.add_run(f"طريقة الحساب: بالأيام ({days} يوم) | الشهر = 28 يوم")
    force_rtl(p)
    p = doc.add_paragraph()
    p.add_run(f"أجر الطباعة الثابت: {fee_print_val}$ | أجر العرض الشهري: {fee_ads_monthly}$")
    force_rtl(p)
    
    # المحافظات والشبكات
    for city, nets in cart.items():
        p = doc.add_paragraph()
        p.add_run(f"■ محافظة {city}").bold = True
        force_rtl(p)
        
        for net, df in nets.items():
            if df.empty:
                continue
            p = doc.add_paragraph()
            p.add_run(f"الشبكة: {net} | القياس: {df['الحجم'].iloc[0]}").bold = True
            force_rtl(p)
            
            # جدول المواقع
            table = doc.add_table(rows=1, cols=2)
            table.style = 'Table Grid'
            set_table_rtl(table)
            hdr = table.rows[0].cells
            hdr[0].text = "اسم الموقع"
            hdr[1].text = "العدد"
            
            for _, row in df.iterrows():
                cells = table.add_row().cells
                cells[0].text = str(row['الموقع'])
                cells[1].text = str(int(row['العدد']))
            
            # حساب المجموع
            qty = int(df['العدد'].sum())
            daily_ads = fee_ads_monthly / 28
            actual_ads = daily_ads * days
            per_col = fee_print_val + actual_ads
            section_total = qty * per_col
            
            p = doc.add_paragraph()
            p.add_run(f"العدد: {qty} | لكل عمود: {per_col:.2f}$ | إجمالي القسم: {section_total:.2f}$").bold = True
            force_rtl(p)
    
    # المجموع الكلي
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.add_run(f"الإجمالي النهائي: {total:,.2f} $").bold = True
    p.runs[0].font.size = Pt(14)
    force_rtl(p)
    
    # ملاحظة
    p = doc.add_paragraph()
    p.add_run("ملاحظة: هذه المواقع متاحة لمدة 48 ساعة").bold = True
    force_rtl(p)
    
    out = io.BytesIO()
    doc.save(out)
    out.seek(0)
    return out

def manage_expired_offers(conn):
    st.subheader("⚠️ العروض المنتهية")
    q = 'SELECT id, client_name, offer_date FROM "offers_history" WHERE status=\'Pending\' AND offer_date < NOW() - INTERVAL \'48 hours\''
    df = pd.read_sql(q, conn)
    if df.empty:
        st.success("لا توجد عروض منتهية")
    else:
        for _, r in df.iterrows():
            c1, c2, c3 = st.columns([3,1,1])
            c1.write(f"{r['client_name']} - {r['offer_date']}")
            if c2.button("تمديد", key=f"ext_{r['id']}"):
                cur = conn.cursor()
                cur.execute('UPDATE "offers_history" SET offer_date = NOW() WHERE id = %s', (r['id'],))
                conn.commit()
                st.rerun()
            if c3.button("إلغاء", key=f"del_{r['id']}"):
                cur = conn.cursor()
                cur.execute('UPDATE "offers_history" SET status = \'Cancelled\' WHERE id = %s', (r['id'],))
                conn.commit()
                st.rerun()

# ==================== التطبيق الرئيسي ====================
st.set_page_config(page_title="ERP إعلانات", layout="wide")

SYRIA_COORDS = {"دمشق": [33.51, 36.27], "حلب": [36.20, 37.13], "حمص": [34.73, 36.71], "اللاذقية": [35.53, 35.79], "سوريا": [34.80, 38.99]}

if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 تسجيل الدخول")
    u = st.text_input("User")
    p = st.text_input("Pass", type="password")
    if st.button("دخول"):
        if u == "a" and p == "3900":
            st.session_state.auth = True
            st.rerun()
else:
    conn = get_connection()
    if "cart" not in st.session_state:
        st.session_state.cart = {}
    
    with st.sidebar:
        page = st.radio("القائمة", ["📊 Dashboard", "📄 عرض سعر", "📋 جرد", "⚙️ إعدادات"])
        if st.button("تسجيل خروج"):
            st.session_state.auth = False
            st.rerun()
    
    if conn:
        # ==================== Dashboard (مصحح) ====================
        if page == "📊 Dashboard":
            st.title("🗺️ الخريطة وحالة الإشغال")
            yr = datetime.now().year
            booked = pd.read_sql(f'SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" WHERE "العام"={yr}', conn)
            all_col = pd.read_sql('SELECT * FROM "اعمدة انارة"', conn)
            
            # دمج مع تحديد الأعمدة بوضوح
            df = pd.merge(all_col, booked, on="رقم اللوحة", how="left", suffixes=('', '_booked'))
            
            # التحقق من وجود العمود الناتج وتحديد الحالة
            if 'رقم اللوحة_booked' in df.columns:
                df['الحالة'] = df['رقم اللوحة_booked'].apply(lambda x: 'محجوز' if pd.notnull(x) else 'متاح')
            else:
                df['الحالة'] = 'متاح'
            
            c1, c2, c3 = st.columns(3)
            c1.metric("إجمالي اللوحات", len(df))
            c2.metric("محجوز", (df['الحالة'] == 'محجوز').sum())
            c3.metric("متاح", (df['الحالة'] == 'متاح').sum())
            
            m = folium.Map(location=SYRIA_COORDS["سوريا"], zoom_start=7)
            cluster = MarkerCluster().add_to(m)
            for _, r in df.iterrows():
                if pd.notnull(r.get('Latitude')):
                    color = 'red' if r['الحالة'] == 'محجوز' else 'green'
                    folium.Marker(
                        [r['Latitude'], r['Longitude']], 
                        popup=r['اسم العمود'], 
                        icon=folium.Icon(color=color)
                    ).add_to(cluster)
            st_folium(m, width="100%", height=500)
        
        # ==================== عرض سعر ====================
        elif page == "📄 عرض سعر":
            st.title("📄 إنشاء عرض سعر")
            try:
                with st.expander("إدارة العروض المنتهية"):
                    manage_expired_offers(conn)
                
                draw_df = pd.read_sql('SELECT * FROM "اسماء الرسم"', conn)
                
                cust = st.text_input("اسم الزبون")
                
                col1, col2 = st.columns(2)
                with col1:
                    sz = st.selectbox("المقاس", draw_df['الحجم'].unique())
                with col2:
                    pt = st.selectbox("نوع الطباعة", ["عادي", "سكوتش"])
                
                col3, col4 = st.columns(2)
                with col3:
                    is_foreign = st.checkbox("عميل أجنبي")
                with col4:
                    st.write("")
                
                col_date1, col_date2 = st.columns(2)
                with col_date1:
                    start_date = st.date_input("تاريخ البداية", datetime(2026, 4, 1))
                with col_date2:
                    end_date = st.date_input("تاريخ النهاية", datetime(2026, 4, 10))
                
                if start_date > end_date:
                    st.error("تاريخ البداية يجب أن يكون قبل تاريخ النهاية")
                    st.stop()
                
                days = (end_date - start_date).days + 1
                st.info(f"📅 عدد الأيام: {days} (الشهر = 28 يوم)")
                
                fee_print, fee_ads_monthly = get_fees(draw_df, sz, pt, is_foreign)
                daily_ads = fee_ads_monthly / 28
                actual_ads = daily_ads * days
                per_column_total = fee_print + actual_ads
                
                st.success(f"💰 أجر الطباعة الثابت: {fee_print}$ | أجر العرض الشهري: {fee_ads_monthly}$")
                st.info(f"📊 حسب الأيام {days}: أجر العرض الفعلي = {daily_ads:.2f} × {days} = {actual_ads:.2f}$ لكل عمود")
                st.info(f"💵 إجمالي لكل عمود = {per_column_total:.2f}$")
                
                cities = pd.read_sql('SELECT DISTINCT "المحافظة" FROM "اعمدة انارة"', conn)['المحافظة'].tolist()
                city = st.selectbox("المحافظة", cities)
                
                all_columns = pd.read_sql(f'SELECT "رقم اللوحة", "اسم العمود" as "الموقع", "العدد", "الشبكة", "الحجم" FROM "اعمدة انارة" WHERE "المحافظة"=\'{city}\' AND "الحجم"=\'{sz}\'', conn)
                
                yr = 2026
                booked_simple = pd.read_sql(f'SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" WHERE "العام"={yr}', conn)['رقم اللوحة'].tolist()
                
                available = all_columns[~all_columns['رقم اللوحة'].isin(booked_simple)]
                
                if not available.empty:
                    networks = st.multiselect("الشبكات", available['الشبكة'].unique())
                    if st.button("➕ إضافة للسلة"):
                        if city not in st.session_state.cart:
                            st.session_state.cart[city] = {}
                        for net in networks:
                            df_net = available[available['الشبكة'] == net].copy()
                            df_net['fee_print'] = fee_print
                            df_net['fee_ads_monthly'] = fee_ads_monthly
                            st.session_state.cart[city][net] = df_net
                        st.rerun()
                
                if st.session_state.cart:
                    st.divider()
                    st.subheader("🛒 سلة العروض")
                    grand_total = 0.0
                    
                    for city, nets in list(st.session_state.cart.items()):
                        for net, df_cart in list(nets.items()):
                            with st.expander(f"📍 {city} - {net}"):
                                edited = st.data_editor(df_cart, key=f"ed_{city}_{net}", num_rows="dynamic")
                                st.session_state.cart[city][net] = edited
                                
                                qty = int(edited['العدد'].sum())
                                fp = float(edited['fee_print'].iloc[0])
                                fam = float(edited['fee_ads_monthly'].iloc[0])
                                
                                daily = fam / 28
                                actual = daily * days
                                per_col = fp + actual
                                section_total = qty * per_col
                                grand_total += section_total
                                
                                st.write(f"العدد: {qty} | لكل عمود: {per_col:.2f}$ | إجمالي القسم: {section_total:.2f}$")
                                
                                if st.button("🗑️ حذف", key=f"del_{city}_{net}"):
                                    del st.session_state.cart[city][net]
                                    st.rerun()
                    
                    st.info(f"### 💰 الإجمالي العام: {grand_total:,.2f} $")
                    
                    col_b1, col_b2, col_b3, col_b4 = st.columns(4)
                    with col_b1:
                        if st.button("💾 حفظ مسودة"):
                            if not cust:
                                st.error("أدخل اسم الزبون")
                            else:
                                to_save = {
                                    "data": {c: {n: df.to_dict() for n, df in ns.items()} for c, ns in st.session_state.cart.items()},
                                    "cust": cust,
                                    "start": start_date.isoformat(),
                                    "end": end_date.isoformat(),
                                    "is_foreign": is_foreign,
                                    "fee_print": fee_print,
                                    "fee_ads_monthly": fee_ads_monthly,
                                    "days": days
                                }
                                cur = conn.cursor()
                                cur.execute('INSERT INTO "offers_history" (client_name, cart_json, status) VALUES (%s, %s, %s)',
                                           (cust, json.dumps(to_save, ensure_ascii=False), 'Pending'))
                                conn.commit()
                                st.success("تم الحفظ")
                    
                    with col_b2:
                        if st.button("✅ تثبيت نهائي"):
                            if not cust:
                                st.error("أدخل اسم الزبون")
                            else:
                                cur = conn.cursor()
                                for city, nets in st.session_state.cart.items():
                                    for net, df in nets.items():
                                        for _, row in df.iterrows():
                                            cur.execute('''
                                                INSERT INTO "حجوزات1" ("رقم اللوحة", "اسم الزبون", "العام", "تاريخ البداية", "تاريخ النهاية") 
                                                VALUES (%s, %s, %s, %s, %s)
                                            ''', (str(row['رقم اللوحة']), cust, yr, start_date, end_date))
                                conn.commit()
                                st.session_state.cart = {}
                                st.success("تم التثبيت!")
                                st.rerun()
                    
                    with col_b3:
                        if st.button("📝 Word"):
                            word_file = export_word(cust, st.session_state.cart, start_date, end_date, grand_total, days, is_foreign, fee_print, fee_ads_monthly)
                            st.download_button("تحميل", word_file, f"Offer_{cust}.docx")
                    
                    with col_b4:
                        if st.button("🔴 تفريغ"):
                            st.session_state.cart = {}
                            st.rerun()
            
            except Exception as e:
                st.error(f"خطأ: {e}")
        
        # ==================== جرد ====================
        elif page == "📋 جرد":
            st.title("📋 تقرير الجرد")
            try:
                yr = st.number_input("العام", value=2026)
                all_b = pd.read_sql('SELECT "رقم اللوحة", "المحافظة", "الحجم" FROM "اعمدة انارة"', conn)
                booked = pd.read_sql(f'SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" WHERE "العام"={yr}', conn)['رقم اللوحة'].tolist()
                all_b['الحالة'] = all_b['رقم اللوحة'].apply(lambda x: 'محجوز' if x in booked else 'متاح')
                
                st.metric("إجمالي اللوحات", len(all_b))
                st.metric("المحجوز", len(booked))
                st.metric("المتاح", len(all_b) - len(booked))
                
                csv = all_b.to_csv(index=False, encoding='utf-8-sig')
                st.download_button("📥 Excel", csv, f"inventory_{yr}.csv", "text/csv")
                
                for city in sorted(all_b['المحافظة'].unique()):
                    st.write(f"#### {city}")
                    d = all_b[all_b['المحافظة'] == city]
                    stats = d.groupby(['الحجم', 'الحالة']).size().unstack(fill_value=0)
                    st.table(stats)
            except Exception as e:
                st.error(f"خطأ: {e}")
        
        # ==================== إعدادات ====================
        elif page == "⚙️ إعدادات":
            st.title("⚙️ الإعدادات")
            try:
                engine = get_engine()
                tab1, tab2, tab3 = st.tabs(["اللوحات", "الحجوزات", "الأسعار"])
                
                with tab1:
                    df = pd.read_sql('SELECT * FROM "اعمدة انارة"', conn)
                    edited = st.data_editor(df, num_rows="dynamic")
                    if st.button("حفظ اللوحات"):
                        with engine.begin() as cn:
                            cn.execute(text('DELETE FROM "اعمدة انارة"'))
                            edited.to_sql("اعمدة انارة", cn, if_exists="append", index=False)
                        st.success("تم الحفظ")
                
                with tab2:
                    df = pd.read_sql('SELECT * FROM "حجوزات1" LIMIT 500', conn)
                    edited = st.data_editor(df, num_rows="dynamic")
                    if st.button("حفظ الحجوزات"):
                        with engine.begin() as cn:
                            cn.execute(text('DELETE FROM "حجوزات1"'))
                            edited.to_sql("حجوزات1", cn, if_exists="append", index=False)
                        st.success("تم الحفظ")
                
                with tab3:
                    st.info("أضف 'عرض شهري' أو 'اجنبي شهري' في اسم الرسم")
                    df = pd.read_sql('SELECT * FROM "اسماء الرسم"', conn)
                    edited = st.data_editor(df, num_rows="dynamic")
                    if st.button("حفظ الأسعار"):
                        with engine.begin() as cn:
                            cn.execute(text('DELETE FROM "اسماء الرسم"'))
                            edited.to_sql("اسماء الرسم", cn, if_exists="append", index=False)
                        st.success("تم الحفظ")
            except Exception as e:
                st.error(f"خطأ: {e}")
        
        conn.close()
