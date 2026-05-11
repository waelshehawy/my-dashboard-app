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
from datetime import date
# للتحقق
def safe_date(date_input):
    """تحويل أي مدخل تاريخ إلى كائن date بشكل آمن"""
    if date_input is None:
        return date.today()
    if isinstance(date_input, (tuple, list)):
        date_input = date_input[0]
    if hasattr(date_input, 'date'):
        return date_input.date()
    if isinstance(date_input, datetime):
        return date_input.date()
    return date_input
# ============================================================
# 1. اتصالات قاعدة البيانات
# ============================================================
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
    url_obj = URL.create(
        drivername="postgresql+psycopg2",
        username="postgres.ncuofpvbaglwbdqnpman",
        password="WaelPreview2026",
        host="aws-1-eu-north-1.pooler.supabase.com",
        port="6543",
        database="postgres",
    )
    return create_engine(url_obj, connect_args={'sslmode': 'require'})

# ============================================================
# 2. دوال التنسيق الخاصة بـ Word (RTL والجداول)
# ============================================================
def set_table_rtl(table):
    """تحويل اتجاه الجدول إلى RTL"""
    tblPr = table._element.xpath('w:tblPr')[0]
    bidi = OxmlElement('w:bidiVisual')
    tblPr.append(bidi)

def force_rtl_paragraph(p):
    """تطبيق الكتابة من اليمين لليسار على الفقرة"""
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    pPr = p._element.get_or_add_pPr()
    bidi = OxmlElement('w:bidi')
    bidi.set(qn('w:val'), '1')
    pPr.append(bidi)
    for run in p.runs:
        rPr = run._element.get_or_add_rPr()
        rtl = OxmlElement('w:rtl')
        rtl.set(qn('w:val'), '1')
        rPr.append(rtl)
        rFonts = OxmlElement('w:rFonts')
        rFonts.set(qn('w:cs'), 'Arial')
        rPr.append(rFonts)

# ============================================================
# 3. دوال حساب الأجور (مع دعم الأجنبي والأيام)
# ============================================================
def get_fees(draw_df, size, print_type, is_foreign):
    """
    جلب أجور الطباعة (ثابتة) وأجور العرض (شهرية 28 يوم)
    """
    subset = draw_df[draw_df['الحجم'] == size].copy()
    subset['search_name'] = subset['اسم الرسم'].str.strip().str.replace('أ', 'ا')
    target_pt = print_type.replace('أ', 'ا')
    
    # أجور الطباعة (ثابتة - لا تتغير بالأيام)
    f_pr_row = subset[subset['search_name'].str.contains("طباعة", na=False) & 
                      subset['search_name'].str.contains(target_pt, na=False)]
    if f_pr_row.empty and print_type == "عادي":
        f_pr_row = subset[subset['search_name'].str.contains("طباعة", na=False)]
    fee_print = float(f_pr_row['اجرة الرسم'].sum()) if not f_pr_row.empty else 0.0
    
    # أجور العرض (شهرية - تقسم على 28)
    search_keyword = "اجنبي شهري" if is_foreign else "عرض شهري"
    f_ad_row = subset[subset['search_name'].str.contains(search_keyword, na=False)]
    
    if is_foreign and f_ad_row.empty:
        f_ad_row = subset[subset['search_name'].str.contains("عرض شهري", na=False)]
    
    fee_ads_monthly = float(f_ad_row['اجرة الرسم'].sum()) if not f_ad_row.empty else 0.0
    
    return fee_print, fee_ads_monthly

def calculate_price_per_column(fee_print, fee_ads_monthly, days):
    """
    حساب سعر العمود الواحد:
    - أجر الطباعة: ثابت
    - أجر العرض: (أجر شهري / 28) × عدد الأيام
    """
    daily_ads = fee_ads_monthly / 28
    actual_ads = daily_ads * days
    return fee_print + actual_ads, actual_ads

# ============================================================
# 4. دالة تصدير Word (كاملة بالتنسيقات)
# ============================================================
def export_word_full(customer_name, cart_data, start_date, end_date, grand_total, days, is_foreign, fee_print, fee_ads_monthly):
    """تصدير عرض السعر إلى Word مع تنسيق RTL وجداول ملونة"""
    doc = Document()
    
    # العنوان الرئيسي
    title = doc.add_heading("عرض سعر", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # التاريخ
    p_date = doc.add_paragraph()
    p_date.add_run(f"التاريخ: {datetime.now().strftime('%d / %m / %Y')}")
    force_rtl_paragraph(p_date)
    
    doc.add_paragraph()
    
    # بيانات العميل
    p_cust = doc.add_paragraph()
    cust_type = " (عميل أجنبي)" if is_foreign else ""
    p_cust.add_run(f"السادة شركة {customer_name} المحترمين{cust_type}").bold = True
    force_rtl_paragraph(p_cust)
    
    # فترة العرض
    p_period = doc.add_paragraph()
    p_period.add_run(f"عرض إعلانكم الوطني من تاريخ {start_date.strftime('%Y/%m/%d')} لغاية {end_date.strftime('%Y/%m/%d')}")
    force_rtl_paragraph(p_period)
    
    # طريقة الحساب
    p_method = doc.add_paragraph()
    p_method.add_run(f"طريقة الحساب: بالأيام ({days} يوم) | الشهر = 28 يوم")
    force_rtl_paragraph(p_method)
    
    # الأسعار
    p_fees = doc.add_paragraph()
    p_fees.add_run(f"أجور الطباعة الثابتة: {fee_print}$ | أجور العرض الشهرية: {fee_ads_monthly}$")
    force_rtl_paragraph(p_fees)
    
    doc.add_paragraph()
    
    # عرض بيانات كل محافظة وشبكة
    for city, networks in cart_data.items():
        p_city = doc.add_paragraph()
        p_city.add_run(f"■ محافظة {city}").bold = True
        force_rtl_paragraph(p_city)
        
        for net, df in networks.items():
            if df.empty:
                continue
            
            # عنوان الشبكة
            p_net = doc.add_paragraph()
            p_net.add_run(f"الشبكة: {net} | القياس: {df['الحجم'].iloc[0]}").bold = True
            force_rtl_paragraph(p_net)
            
            # إنشاء الجدول
            table = doc.add_table(rows=1, cols=2)
            table.style = 'Table Grid'
            set_table_rtl(table)
            
            # رأس الجدول
            hdr_cells = table.rows[0].cells
            hdr_cells[0].text = "اسم الموقع (العمود)"
            hdr_cells[1].text = "العدد"
            
            for cell in hdr_cells:
                for p in cell.paragraphs:
                    force_rtl_paragraph(p)
                # تلوين رأس الجدول
                tc_pr = cell._element.get_or_add_tcPr()
                shd = OxmlElement('w:shd')
                shd.set(qn('w:fill'), '660099')
                tc_pr.append(shd)
                if cell.paragraphs[0].runs:
                    cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
            
            # بيانات الجدول
            for _, row in df.iterrows():
                row_cells = table.add_row().cells
                row_cells[0].text = str(row['الموقع'])
                row_cells[1].text = str(int(row['العدد']))
                for cell in row_cells:
                    for p in cell.paragraphs:
                        force_rtl_paragraph(p)
            
            # حساب المجموع لهذه الشبكة
            qty = int(df['العدد'].sum())
            per_col, actual_ads = calculate_price_per_column(fee_print, fee_ads_monthly, days)
            section_total = qty * per_col
            
            p_total = doc.add_paragraph()
            p_total.add_run(f"إجمالي العدد: {qty} | سعر العمود: {per_col:.2f}$ | إجمالي القسم: {section_total:,.2f}$").bold = True
            force_rtl_paragraph(p_total)
            
            doc.add_paragraph()
    
    # المجموع النهائي
    doc.add_paragraph()
    p_grand = doc.add_paragraph()
    p_grand.add_run(f"الإجمالي النهائي للعرض بالكامل: {grand_total:,.2f} $").bold = True
    p_grand.runs[0].font.size = Pt(14)
    p_grand.runs[0].font.color.rgb = RGBColor(102, 0, 153)
    force_rtl_paragraph(p_grand)
    
    # ملاحظة الـ 48 ساعة
    doc.add_paragraph()
    p_note = doc.add_paragraph()
    p_note.add_run("• ملاحظة: هذه المواقع متاحة لمدة 48 ساعة فقط.").bold = True
    force_rtl_paragraph(p_note)
    
    # حفظ الملف
    output = io.BytesIO()
    doc.save(output)
    output.seek(0)
    return output

# ============================================================
# 5. إدارة العروض المنتهية
# ============================================================
def manage_expired_offers(conn):
    st.subheader("⚠️ إدارة العروض التي تجاوزت 48 ساعة")
    
    query = '''
        SELECT id, client_name, offer_date 
        FROM "offers_history" 
        WHERE status = 'Pending' AND offer_date < NOW() - INTERVAL '48 hours'
    '''
    expired_df = pd.read_sql(query, conn)
    
    if expired_df.empty:
        st.success("✅ لا توجد عروض منتهية الصلاحية.")
        return
    
    for _, row in expired_df.iterrows():
        col1, col2, col3 = st.columns([3, 1, 1])
        col1.write(f"👤 الزبون: **{row['client_name']}** - تاريخ العرض: {row['offer_date']}")
        
        if col2.button("✅ تمديد 48 ساعة", key=f"ext_{row['id']}"):
            cur = conn.cursor()
            cur.execute('UPDATE "offers_history" SET offer_date = NOW() WHERE id = %s', (row['id'],))
            conn.commit()
            st.success("تم التمديد بنجاح")
            st.rerun()
        
        if col3.button("❌ إلغاء العرض", key=f"del_{row['id']}"):
            cur = conn.cursor()
            cur.execute('UPDATE "offers_history" SET status = \'Cancelled\' WHERE id = %s', (row['id'],))
            conn.commit()
            st.success("تم إلغاء العرض")
            st.rerun()

# ============================================================
# 6. التطبيق الرئيسي
# ============================================================
st.set_page_config(page_title="PreView Ads ERP - نظام إدارة الإعلانات", layout="wide")

# إحداثيات المدن السورية
SYRIA_COORDS = {
    "دمشق": [33.5138, 36.2765],
    "ريف دمشق": [33.45, 36.35],
    "حلب": [36.2028, 37.1343],
    "حمص": [34.7328, 36.7156],
    "حماة": [35.135, 36.748],
    "اللاذقية": [35.531, 35.79],
    "طرطوس": [34.883, 35.883],
    "سوريا": [34.802, 38.996]
}

# حالة تسجيل الدخول
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 نظام إدارة الإعلانات - تسجيل الدخول")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input("اسم المستخدم")
        password = st.text_input("كلمة المرور", type="password")
        if st.button("دخول", use_container_width=True):
            if username == "a" and password == "3900":
                st.session_state.auth = True
                st.rerun()
            else:
                st.error("اسم المستخدم أو كلمة المرور غير صحيحة")
else:
    conn = get_connection()
    
    if "cart" not in st.session_state:
        st.session_state.cart = {}
    if "temp_cust" not in st.session_state:
        st.session_state.temp_cust = ""
    
    # الشريط الجانبي
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/000000/advertising.png", width=80)
        st.title("القائمة الرئيسية")
        page = st.radio("", ["📊 Dashboard", "📄 عرض سعر", "📋 تقرير الجرد", "⚙️ الإعدادات"])
        st.divider()
        if st.button("🚪 تسجيل الخروج", use_container_width=True):
            st.session_state.auth = False
            st.session_state.cart = {}
            st.rerun()
    
    if not conn:
        st.error("❌ لا يمكن الاستمرار بدون اتصال بقاعدة البيانات")
        st.stop()
    
    # ============================================================
    # صفحة Dashboard
    # ============================================================
    if page == "📊 Dashboard":
        st.title("📊 لوحة التحكم - الخريطة التفاعلية وحالة الإشغال")
        
        current_year = datetime.now().year
        
        # جلب جميع اللوحات
        all_columns_df = pd.read_sql('SELECT * FROM "اعمدة انارة"', conn)
        
        # جلب الحجوزات - debug
        booked_df = pd.read_sql(f'SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" WHERE "العام" = {current_year}', conn)
        
        st.write(f"DEBUG: عدد الحجوزات في قاعدة البيانات: {len(booked_df)}")
        
        # دمج البيانات
        df_map = pd.merge(all_columns_df, booked_df, on="رقم اللوحة", how="left", suffixes=('', '_booked'))
        
        # حساب المحجوزات
        booked_count = df_map['رقم اللوحة_booked'].notna().sum() if 'رقم اللوحة_booked' in df_map.columns else 0
        total_boards = len(df_map)
        available_count = total_boards - booked_count
        
        # عرض المؤشرات
        col1, col2, col3 = st.columns(3)
        col1.metric("🏢 إجمالي اللوحات", total_boards)
        col2.metric("🔴 محجوز حالياً", booked_count)
        col3.metric("🟢 متاح حالياً", available_count)
        
        st.divider()
        
        # الخريطة
        st.subheader("🗺️ توزع اللوحات على الخريطة")
        
        m = folium.Map(location=SYRIA_COORDS["سوريا"], zoom_start=7)
        marker_cluster = MarkerCluster().add_to(m)
        
        for _, row in df_map.iterrows():
            if pd.notnull(row.get('Latitude')) and pd.notnull(row.get('Longitude')):
                is_booked = pd.notnull(row.get('رقم اللوحة_booked', None))
                color = 'red' if is_booked else 'purple'
                status_text = 'محجوز' if is_booked else 'متاح'
                
                popup_html = f"""
                <div dir="rtl" style="font-family: Arial; text-align: right;">
                    <b>{row['اسم العمود']}</b><br>
                    المحافظة: {row['المحافظة']}<br>
                    الشبكة: {row['الشبكة']}<br>
                    الحالة: {status_text}
                </div>
                """
                
                folium.Marker(
                    [row['Latitude'], row['Longitude']],
                    popup=folium.Popup(popup_html, max_width=250),
                    icon=folium.Icon(color=color)
                ).add_to(marker_cluster)
        
        st_folium(m, width="100%", height=500)
        
        # إحصائيات حسب المحافظة
        st.divider()
        st.subheader("📊 إحصائيات حسب المحافظة")
        
        df_map['الحالة'] = df_map['رقم اللوحة_booked'].apply(lambda x: 'محجوز' if pd.notnull(x) else 'متاح')
        stats_by_city = df_map.groupby('المحافظة')['الحالة'].value_counts().unstack(fill_value=0)
        st.dataframe(stats_by_city, use_container_width=True)
    
    # ============================================================
    # صفحة عرض سعر (النسخة النهائية المصححة)
    # ============================================================
    # ============================================================
    # صفحة عرض سعر (النسخة النهائية المصححة)
    # ============================================================
    elif page == "📄 عرض سعر":
        st.title("📄 بناء عرض سعر جديد")
        
        try:
            # إدارة العروض المنتهية
            with st.expander("🔔 العروض المنتهية (تحتاج إلى إجراء)", expanded=False):
                manage_expired_offers(conn)
            
            # استرجاع عرض محفوظ
            st.subheader("📂 استرجاع عرض محفوظ")
            saved_offers = pd.read_sql('SELECT id, client_name, offer_date, start_p, end_p, year, status FROM "offers_history" WHERE status = \'Pending\' ORDER BY id DESC', conn)
            
            if not saved_offers.empty:
                offer_options = {f"{row['client_name']} ({row['offer_date'][:10] if row['offer_date'] else 'بدون تاريخ'})": row['id'] for _, row in saved_offers.iterrows()}
                selected_offer = st.selectbox("اختر عرضاً محفوظاً:", ["---"] + list(offer_options.keys()))
                
                if selected_offer != "---" and st.button("🔄 تحميل للسلة"):
                    try:
                        offer_id = offer_options[selected_offer]
                        result = pd.read_sql(f'SELECT cart_json, client_name, start_p, end_p, year FROM "offers_history" WHERE id = {offer_id}', conn)
                        
                        if not result.empty:
                            row = result.iloc[0]
                            data = json.loads(row['cart_json'])
                            
                            # استعادة السلة
                            if "data" in data:
                                st.session_state.cart = data["data"]
                            else:
                                st.session_state.cart = data
                            
                            st.session_state.temp_cust = row['client_name']
                            
                            # استعادة التواريخ من الأعمدة
                            if row['start_p'] and row['end_p']:
                                st.session_state.loaded_start_p = row['start_p']
                                st.session_state.loaded_end_p = row['end_p']
                            if row['year']:
                                st.session_state.loaded_year = row['year']
                            
                            st.success("تم تحميل العرض بنجاح")
                            st.rerun()
                    except Exception as e:
                        st.error(f"خطأ في تحميل العرض: {str(e)}")
            
            st.divider()
            
            # تحميل البيانات الأساسية
            draw_df = pd.read_sql('SELECT * FROM "اسماء الرسم"', conn)
            
            # بيانات العميل
            customer_name = st.text_input("🏢 اسم الزبون", value=st.session_state.get('temp_cust', ""))
            st.session_state.temp_cust = customer_name
            
            # خيارات الإعلان
            col1, col2, col3 = st.columns(3)
            with col1:
                selected_size = st.selectbox("📏 قياس اللوحة:", draw_df['الحجم'].unique().tolist())
            with col2:
                print_type = st.radio("🖨️ نوع الطباعة:", ["عادي", "سكوتش"], horizontal=True)
            with col3:
                # استعادة العام المحفوظ
                default_year = st.session_state.get('loaded_year', 2026)
                year = st.number_input("📅 العام:", min_value=2024, max_value=2030, value=default_year)
            
            # خيارات الحساب
            col_opt1, col_opt2 = st.columns(2)
            with col_opt1:
                is_foreign = st.checkbox("🌍 عميل أجنبي (يبحث عن أجور عرض خاصة)")
            with col_opt2:
                st.write("")
            
            # اختيار التاريخ - مع دعم الفترات أو التواريخ
            calc_method = st.radio("طريقة الحساب:", ["حساب بالأيام", "حساب بالفترات"], horizontal=True)
            
            days_count = 14
            start_date = None
            end_date = None
            start_p = ""
            end_p = ""
            
            if calc_method == "حساب بالأيام":
                col_date1, col_date2 = st.columns(2)
                with col_date1:
                    start_date = st.date_input("📅 تاريخ بداية العرض", value=date(year, 4, 1))
                with col_date2:
                    end_date = st.date_input("📅 تاريخ نهاية العرض", value=date(year, 4, 10))
                
                if start_date > end_date:
                    st.error("❌ تاريخ البداية يجب أن يكون قبل تاريخ النهاية")
                    st.stop()
                
                days_count = (end_date - start_date).days + 1
                start_p = start_date.isoformat()
                end_p = end_date.isoformat()
                st.info(f"📅 عدد الأيام: {days_count} يوم")
            else:
                # حساب بالفترات (نصف شهر = 15 يوم)
                periods_df = pd.read_sql('SELECT * FROM "الفترة" ORDER BY "no"', conn)
                period_names = periods_df['namee'].tolist()
                
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    start_p = st.selectbox("من فترة:", period_names)
                with col_p2:
                    end_p = st.selectbox("إلى فترة:", period_names, index=len(period_names)-1)
                
                # حساب عدد الفترات
                start_idx = period_names.index(start_p)
                end_idx = period_names.index(end_p)
                periods_count = abs(end_idx - start_idx) + 1
                days_count = periods_count * 14  # كل فترة = 15 يوم
                
                st.info(f"📅 عدد الفترات: {periods_count} | عدد الأيام: {days_count} يوم")
            
            # جلب الأسعار
            fee_print, fee_ads_monthly = get_fees(draw_df, selected_size, print_type, is_foreign)
            per_column_price = fee_print + (fee_ads_monthly / 28 * days_count)
            
            st.success(f"""
            💰 **تفاصيل الأسعار:**
            - أجر الطباعة الثابت: **{fee_print}$**
            - أجر العرض الشهري: **{fee_ads_monthly}$**
            - **الإجمالي لكل عمود: {per_column_price:.2f}$**
            """)
            
            # اختيار المحافظة والشبكات
            st.divider()
            st.subheader("📍 اختيار المواقع")
            
            cities = pd.read_sql('SELECT DISTINCT "المحافظة" FROM "اعمدة انارة"', conn)['المحافظة'].tolist()
            selected_city = st.selectbox("اختر المحافظة:", cities)
            
            # جلب المواقع المتاحة
            available_columns = pd.read_sql(f'''
                SELECT "رقم اللوحة", "اسم العمود" as "الموقع", "العدد", "الشبكة", "الحجم" 
                FROM "اعمدة انارة" 
                WHERE "المحافظة" = '{selected_city}' AND "الحجم" = '{selected_size}'
            ''', conn)
            
            # جلب المواقع المحجوزة
            if calc_method == "حساب بالأيام" and start_date and end_date:
                booked_query = f'''
                    SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" 
                    WHERE "العام" = {year} 
                    AND "تاريخ البداية" <= '{end_date}' 
                    AND "تاريخ النهاية" >= '{start_date}'
                '''
            else:
                booked_query = f'''
                    SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" 
                    WHERE "العام" = {year} 
                    AND "فترة الحجز" IN ('{start_p}')
                '''
            
            try:
                booked_boards = pd.read_sql(booked_query, conn)['رقم اللوحة'].tolist()
            except:
                booked_boards = []
            
            available_columns = available_columns[~available_columns['رقم اللوحة'].isin(booked_boards)]
            
            if not available_columns.empty:
                networks = st.multiselect("اختر الشبكات:", available_columns['الشبكة'].unique().tolist())
                
                if st.button("➕ إضافة إلى السلة", type="primary", use_container_width=True):
                    if selected_city not in st.session_state.cart:
                        st.session_state.cart[selected_city] = {}
                    
                    for net in networks:
                        net_data = available_columns[available_columns['الشبكة'] == net].copy()
                        net_data['fee_print'] = fee_print
                        net_data['fee_ads_monthly'] = fee_ads_monthly
                        st.session_state.cart[selected_city][net] = net_data
                    
                    st.success(f"تمت الإضافة")
                    st.rerun()
            else:
                st.warning("⚠️ لا توجد مواقع متاحة")
            
            # عرض السلة
            if st.session_state.cart:
                st.divider()
                st.subheader("🛒 سلة العروض")
                
                grand_total = 0.0
                
                for city, networks in list(st.session_state.cart.items()):
                    for net, df_cart in list(networks.items()):
                        with st.expander(f"📍 {city} - {net}", expanded=True):
                            edited_df = st.data_editor(df_cart, key=f"edit_{city}_{net}", num_rows="dynamic")
                            st.session_state.cart[city][net] = edited_df
                            
                            qty = int(edited_df['العدد'].sum())
                            fp = float(edited_df['fee_print'].iloc[0]) if 'fee_print' in edited_df.columns else fee_print
                            fam = float(edited_df['fee_ads_monthly'].iloc[0]) if 'fee_ads_monthly' in edited_df.columns else fee_ads_monthly
                            
                            per_col = fp + (fam / 28 * days_count)
                            section_total = qty * per_col
                            grand_total += section_total
                            
                            st.info(f"العدد: {qty} | لكل عمود: {per_col:.2f}$ | الإجمالي: {section_total:.2f}$")
                            
                            if st.button("🗑️ حذف", key=f"delete_{city}_{net}"):
                                del st.session_state.cart[city][net]
                                st.rerun()
                
                st.markdown(f"## 💰 الإجمالي العام: {grand_total:,.2f} $")
                
                col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)
                
                with col_btn1:
                    if st.button("💾 حفظ كمسودة", use_container_width=True):
                        if not customer_name:
                            st.error("الرجاء إدخال اسم الزبون")
                        else:
                            save_data = {
                                "data": {c: {n: df.to_dict() for n, df in ns.items()} for c, ns in st.session_state.cart.items()}
                            }
                            cur = conn.cursor()
                            cur.execute('''
                                INSERT INTO "offers_history" (client_name, cart_json, status, start_p, end_p, year) 
                                VALUES (%s, %s, %s, %s, %s, %s)
                            ''', (customer_name, json.dumps(save_data, ensure_ascii=False), 'Pending', start_p, end_p, year))
                            conn.commit()
                            st.success("تم الحفظ")
                
                with col_btn2:
                    if st.button("✅ تثبيت نهائي", use_container_width=True):
                        if not customer_name:
                            st.error("الرجاء إدخال اسم الزبون")
                        else:
                            cur = conn.cursor()
                            for city, networks in st.session_state.cart.items():
                                for net, df in networks.items():
                                    for _, row in df.iterrows():
                                        if calc_method == "حساب بالأيام":
                                            cur.execute('''
                                                INSERT INTO "حجوزات1" ("رقم اللوحة", "اسم الزبون", "العام", "تاريخ البداية", "تاريخ النهاية") 
                                                VALUES (%s, %s, %s, %s, %s)
                                            ''', (str(row['رقم اللوحة']), customer_name, year, start_date, end_date))
                                        else:
                                            cur.execute('''
                                                INSERT INTO "حجوزات1" ("رقم اللوحة", "اسم الزبون", "العام", "فترة الحجز") 
                                                VALUES (%s, %s, %s, %s)
                                            ''', (str(row['رقم اللوحة']), customer_name, year, start_p))
                            conn.commit()
                            st.session_state.cart = {}
                            st.success("تم التثبيت")
                            st.rerun()
                
                with col_btn3:
                    if st.button("📝 تصدير Word", use_container_width=True):
                        from docx import Document
                        from docx.shared import Pt
                        doc = Document()
                        p = doc.add_paragraph()
                        p.add_run(f"عرض سعر لشركة {customer_name}")
                        word_bytes = io.BytesIO()
                        doc.save(word_bytes)
                        st.download_button("تحميل", word_bytes.getvalue(), f"offer_{customer_name}.docx")
                
                with col_btn4:
                    if st.button("🔴 تفريغ", use_container_width=True):
                        st.session_state.cart = {}
                        st.rerun()
        
        except Exception as e:
            st.error(f"حدث خطأ: {str(e)}")
    
    # ============================================================
    # صفحة تقرير الجرد
    # ============================================================
    elif page == "📋 تقرير الجرد":
        st.title("📋 التقرير التجميعي - جرد اللوحات")
        
        try:
            periods_df = pd.read_sql('SELECT "no", "namee" FROM "الفترة" ORDER BY "no"', conn)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                from_period = st.selectbox("من فترة:", periods_df['namee'].tolist(), key="from_period")
            with col2:
                to_period = st.selectbox("إلى فترة:", periods_df['namee'].tolist(), index=len(periods_df)-1, key="to_period")
            with col3:
                report_year = st.number_input("العام:", value=datetime.now().year, key="report_year")
            
            # حساب نطاق الفترات
            from_idx = int(periods_df[periods_df['namee'] == from_period]['no'].iloc[0])
            to_idx = int(periods_df[periods_df['namee'] == to_period]['no'].iloc[0])
            target_periods = periods_df[(periods_df['no'] >= from_idx) & (periods_df['no'] <= to_idx)]['namee'].tolist()
            
            # جلب بيانات اللوحات
            all_boards = pd.read_sql('SELECT "رقم اللوحة", "المحافظة", "الحجم" FROM "اعمدة انارة"', conn)
            
            # جلب الحجوزات في الفترة المحددة
            period_placeholders = ", ".join([f"'{p}'" for p in target_periods])
            booked_query = f'''
                SELECT DISTINCT "رقم اللوحة" 
                FROM "حجوزات1" 
                WHERE "العام" = {report_year} 
                AND "فترة الحجز" IN ({period_placeholders})
            '''
            booked_in_period = pd.read_sql(booked_query, conn)['رقم اللوحة'].tolist()
            
            # تحديد الحالة
            all_boards['الحالة'] = all_boards['رقم اللوحة'].apply(lambda x: 'محجوز' if x in booked_in_period else 'متاح')
            
            # الإحصائيات العامة
            total = len(all_boards)
            booked = len(booked_in_period)
            available = total - booked
            
            st.subheader("📊 إحصائيات عامة")
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("إجمالي اللوحات", total)
            col_b.metric("المحجوزة", booked)
            col_c.metric("المتاحة", available)
            
            # أزرار التصدير
            st.divider()
            col_exp1, col_exp2 = st.columns(2)
            
            with col_exp1:
                csv_data = all_boards.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    "📊 تصدير إلى Excel",
                    csv_data,
                    f"Inventory_Report_{report_year}.csv",
                    "text/csv",
                    use_container_width=True
                )
            
            # عرض التفاصيل حسب المحافظة
            st.divider()
            st.subheader("📋 تفاصيل حسب المحافظة")
            
            for city in sorted(all_boards['المحافظة'].unique()):
                city_data = all_boards[all_boards['المحافظة'] == city]
                city_stats = city_data.groupby(['الحجم', 'الحالة']).size().unstack(fill_value=0)
                
                st.write(f"### 📍 محافظة {city}")
                
                # إضافة الأعمدة المفقودة
                if 'محجوز' not in city_stats.columns:
                    city_stats['محجوز'] = 0
                if 'متاح' not in city_stats.columns:
                    city_stats['متاح'] = 0
                
                st.dataframe(city_stats, use_container_width=True)
                
        except Exception as e:
            st.error(f"حدث خطأ في التقرير: {str(e)}")
    
    # ============================================================
    # صفحة الإعدادات
    # ============================================================
    elif page == "⚙️ الإعدادات":
        st.title("⚙️ إعدادات النظام - إدارة الجداول الثابتة")
        st.warning("⚠️ تحذير: تعديل هذه الجداول يؤثر مباشرة على النظام. يرجى الحذر.")
        
        try:
            engine = get_engine()
            tab1, tab2, tab3 = st.tabs(["🗄️ أعمدة الإنارة", "📅 سجل الحجوزات", "💰 أجور الرسم"])
            
            with tab1:
                st.subheader("إدارة بيانات أعمدة الإنارة")
                df_boards = pd.read_sql('SELECT * FROM "اعمدة انارة" ORDER BY "المحافظة", "الشبكة"', conn)
                edited_boards = st.data_editor(df_boards, num_rows="dynamic", key="edit_boards")
                if st.button("💾 حفظ أعمدة الإنارة"):
                    with engine.begin() as cn:
                        cn.execute(text('DELETE FROM "اعمدة انارة"'))
                        edited_boards.to_sql("اعمدة انارة", cn, if_exists="append", index=False)
                    st.success("✅ تم تحديث أعمدة الإنارة")
            
            with tab2:
                st.subheader("إدارة سجل الحجوزات")
                df_bookings = pd.read_sql('SELECT * FROM "حجوزات1" LIMIT 500', conn)
                edited_bookings = st.data_editor(df_bookings, num_rows="dynamic", key="edit_bookings")
                if st.button("💾 حفظ سجل الحجوزات"):
                    with engine.begin() as cn:
                        cn.execute(text('DELETE FROM "حجوزات1"'))
                        edited_bookings.to_sql("حجوزات1", cn, if_exists="append", index=False)
                    st.success("✅ تم تحديث سجل الحجوزات")
            
            with tab3:
                st.subheader("إدارة أجور الرسم")
                st.info("💡 أضف 'عرض شهري' للعملاء العاديين أو 'اجنبي شهري' للعملاء الأجانب")
                df_fees = pd.read_sql('SELECT * FROM "اسماء الرسم"', conn)
                edited_fees = st.data_editor(df_fees, num_rows="dynamic", key="edit_fees")
                if st.button("💾 حفظ أجور الرسم"):
                    with engine.begin() as cn:
                        cn.execute(text('DELETE FROM "اسماء الرسم"'))
                        edited_fees.to_sql("اسماء الرسم", cn, if_exists="append", index=False)
                    st.success("✅ تم تحديث أجور الرسم")
        
        except Exception as e:
            st.error(f"⚠️ خطأ في صفحة الإعدادات: {e}")
