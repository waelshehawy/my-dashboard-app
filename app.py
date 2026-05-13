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
def export_to_excel(df, filename):
import base64
from PIL import Image
import plotly.express as px
import plotly.graph_objects as go
    """تصدير DataFrame إلى Excel مع دعم اللغة العربية"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='تقرير', index=False)
        # ضبط اتجاه الكتابة لليمين
        workbook = writer.book
        worksheet = writer.sheets['تقرير']
        worksheet.right_to_left()
        
        # ضبط عرض الأعمدة
        for i, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
            worksheet.set_column(i, i, min(max_len, 30))
    
    output.seek(0)
    return output
def set_table_rtl(table):
    tblPr = table._element.xpath('w:tblPr')[0]
    bidi = OxmlElement('w:bidiVisual')
    tblPr.append(bidi)

def _force_rtl_style(p):
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
        rFonts = OxmlElement('w:rFonts')
        rFonts.set(qn('w:cs'), 'Arial')
        rPr.append(rFonts)
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
    """جلب أجور الطباعة والعرض من جدول اسماء الرسم"""
    subset = draw_df[draw_df['الحجم'] == size].copy()
    
    # 1. أجور الطباعة - ابحث عن "اجور الطباعة" أو "اجور الطباعة عادي"
    if print_type == "عادي":
        f_pr = subset[subset['اسم الرسم'].str.contains("اجور الطباعة عادي", na=False)]
        if f_pr.empty:
            f_pr = subset[subset['اسم الرسم'].str.contains("اجور الطباعة", na=False)]
    else:  # سكوتش
        f_pr = subset[subset['اسم الرسم'].str.contains("اجور الطباعة", na=False)]
        # استبعاد كلمة "عادي"
        f_pr = f_pr[~f_pr['اسم الرسم'].str.contains("عادي", na=False)]
    
    fee_print = float(f_pr['اجرة الرسم'].iloc[0]) if not f_pr.empty else 0.0
    
    # 2. أجور العرض - ابحث عن "اجور العرض" أو "اجور العرض اجنبي"
    if is_foreign:
        f_ad = subset[subset['اسم الرسم'].str.contains("اجور العرض اجنبي", na=False)]
        if f_ad.empty:
            f_ad = subset[subset['اسم الرسم'].str.contains("اجور العرض", na=False)]
    else:
        f_ad = subset[subset['اسم الرسم'].str.contains("اجور العرض", na=False)]
        # استبعاد كلمة "اجنبي"
        f_ad = f_ad[~f_ad['اسم الرسم'].str.contains("اجنبي", na=False)]
    
    fee_ads = float(f_ad['اجرة الرسم'].iloc[0]) if not f_ad.empty else 0.0
    
    # عرض للمستخدم لقيم DEBUG
    st.info(f"🔍 DEBUG: الحجم={size}, نوع الطباعة={print_type}, أجنبي={is_foreign}")
    st.info(f"💰 أجر الطباعة: {fee_print}$, أجر العرض (شهري): {fee_ads}$")
    
    return fee_print, fee_ads

# ============================================================
# 4. دالة تصدير Word (كاملة بالتنسيقات)
# ============================================================
def export_word_old(customer_name, cart_data, start_p, end_p, grand_total):
    doc = Document('template.docx') if os.path.exists('template.docx') else Document()
    PURPLE_COLOR = "660099" 
    doc.add_paragraph()
    today_date = datetime.now().strftime("%d / %m / %Y")
    p_date = doc.add_paragraph()
    p_date.add_run(f"التاريخ: {today_date}")
    _force_rtl_style(p_date)
    doc.add_paragraph()
    
    p_cust = doc.add_paragraph()
    if is_foreign:
        p_cust.add_run(f"السادة شركة {customer_name} المحترمين ").bold = True
    else:
        p_cust.add_run(f"السادة شركة {customer_name} المحترمين").bold = True
    _force_rtl_style(p_cust)

    p_stat = doc.add_paragraph()
    if is_foreign:
        p_stat.add_run(f"نقدم لكم المواقع المتاحة لعرض إعلانكم الأجنبي من فترة ({start_p}) ولغاية ({end_p})")
    else:
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
                sum_combined = sum_print + sum_ads
                
                p_fin = doc.add_paragraph()
                txt = (f"إجمالي العدد: {int(total_q)} | "
                       f"أجور الطباعة: {sum_print:,.0f}$ | "
                       f"أجور العرض: {sum_ads:,.0f}$ | "
                       f"المجموع للشبكة: {sum_combined:,.0f}$")
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
        page = st.radio("القائمة الرئيسية", ["📊 Dashboard", "📄 عرض سعر", "📋 تقرير الجرد", "📅 تقرير التوفر الشهري", "⚙️ الإعدادات"])
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
        st.title("📊 لوحة التحكم - الخريطة التفاعلية")
        
        current_year = datetime.now().year
        
        # إجمالي اللوحات الفعلية (مجموع العدد)
        total_boards = pd.read_sql('SELECT SUM("العدد") as total FROM "اعمدة انارة"', conn).iloc[0,0]
        
        # اللوحات المحجوزة (مجموع العدد للحجوزات النشطة)
        booked_boards = pd.read_sql(f'''
            SELECT COALESCE(SUM(b."العدد"), 0) as booked
            FROM "اعمدة انارة" b
            INNER JOIN (
                SELECT DISTINCT "رقم اللوحة" 
                FROM "حجوزات1" 
                WHERE "العام" = {current_year}
            ) h ON b."رقم اللوحة" = h."رقم اللوحة"
        ''', conn).iloc[0,0]
        
        available_boards = total_boards - booked_boards
        
        # عرض المؤشرات
        col1, col2, col3 = st.columns(3)
        col1.metric("🏢 إجمالي اللوحات", f"{int(total_boards):,}")
        col2.metric("🔴 محجوز حالياً", f"{int(booked_boards):,}")
        col3.metric("🟢 متاح حالياً", f"{int(available_boards):,}")
        
        st.progress(booked_boards / total_boards, text=f"📊 نسبة الإشغال: {(booked_boards/total_boards*100):.1f}%")
        
        st.divider()
        
        # جلب بيانات الخريطة
        all_columns = pd.read_sql('SELECT * FROM "اعمدة انارة"', conn)
        booked_numbers = pd.read_sql(f'''
            SELECT DISTINCT "رقم اللوحة" 
            FROM "حجوزات1" 
            WHERE "العام" = {current_year}
        ''', conn)['رقم اللوحة'].tolist()
        
        # تحديد الحالة لكل موقع
        all_columns['الحالة'] = all_columns['رقم اللوحة'].apply(
            lambda x: 'محجوز' if x in booked_numbers else 'متاح'
        )
        
        # الخريطة
        st.subheader("🗺️ توزع اللوحات على الخريطة")
        
        m = folium.Map(location=SYRIA_COORDS["سوريا"], zoom_start=7)
        marker_cluster = MarkerCluster().add_to(m)
        
        for _, row in all_columns.iterrows():
            if pd.notnull(row.get('Latitude')) and pd.notnull(row.get('Longitude')):
                color = 'red' if row['الحالة'] == 'محجوز' else 'purple'
                popup_html = f"""
                <div dir="rtl" style="font-family: Arial; text-align: right;">
                    <b>{row['اسم العمود']}</b><br>
                    المحافظة: {row['المحافظة']}<br>
                    الشبكة: {row['الشبكة']}<br>
                    الحجم: {row['الحجم']}<br>
                    العدد: {row['العدد']}<br>
                    الحالة: {row['الحالة']}
                </div>
                """
                
                folium.Marker(
                    [row['Latitude'], row['Longitude']],
                    popup=folium.Popup(popup_html, max_width=250),
                    icon=folium.Icon(color=color)
                ).add_to(marker_cluster)
        
        st_folium(m, width="100%", height=600)
        
        # إحصائيات حسب المحافظة
        st.divider()
        st.subheader("📊 إحصائيات حسب المحافظة")
        
        # حساب الإجمالي والمحجوز لكل محافظة (بالأعداد الفعلية)
        city_stats = []
        for city in all_columns['المحافظة'].unique():
            city_data = all_columns[all_columns['المحافظة'] == city]
            total = city_data['العدد'].sum()
            booked = city_data[city_data['الحالة'] == 'محجوز']['العدد'].sum()
            city_stats.append({
                'المحافظة': city,
                'الإجمالي': int(total),
                'المحجوز': int(booked),
                'المتاح': int(total - booked)
            })
        
        stats_df = pd.DataFrame(city_stats)
        st.dataframe(stats_df, use_container_width=True)
    

    # ============================================================
    # صفحة عرض سعر
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
                def safe_offer_date(date_val):
                    if date_val is None:
                        return "بدون تاريخ"
                    if hasattr(date_val, 'date'):
                        return date_val.date().strftime('%Y-%m-%d')
                    if hasattr(date_val, 'strftime'):
                        return date_val.strftime('%Y-%m-%d')
                    return str(date_val)[:10]
                
                offer_options = {}
                for _, row in saved_offers.iterrows():
                    date_str = safe_offer_date(row['offer_date'])
                    offer_options[f"{row['client_name']} ({date_str})"] = row['id']
                
                selected_offer = st.selectbox("اختر عرضاً محفوظاً:", ["---"] + list(offer_options.keys()), key="load_offer_select")
                
                if selected_offer != "---" and st.button("🔄 تحميل للسلة", key="load_offer_button"):
                    try:
                        offer_id = offer_options[selected_offer]
                        result = pd.read_sql(f'SELECT cart_json, client_name, start_p, end_p, year FROM "offers_history" WHERE id = {offer_id}', conn)
                        
                        if not result.empty:
                            row = result.iloc[0]
                            data = json.loads(row['cart_json'])
                            
                            cart_raw = data.get("data", data)
                            st.session_state.cart = {}
                            for city, networks in cart_raw.items():
                                st.session_state.cart[city] = {}
                                for net, df_dict in networks.items():
                                    st.session_state.cart[city][net] = pd.DataFrame(df_dict)
                            
                            st.session_state.temp_cust = row['client_name']
                            st.session_state.current_offer_id = offer_id
                            
                            st.success("تم تحميل العرض بنجاح")
                            st.rerun()
                    except Exception as e:
                        st.error(f"خطأ في تحميل العرض: {str(e)}")
            
            st.divider()
            
            # تحميل البيانات الأساسية
            draw_df = pd.read_sql('SELECT * FROM "اسماء الرسم"', conn)
            
            customer_name = st.text_input("🏢 اسم الزبون", value=st.session_state.get('temp_cust', ""))
            st.session_state.temp_cust = customer_name
            
            col1, col2, col3 = st.columns(3)
            with col1:
                selected_size = st.selectbox("📏 قياس اللوحة:", draw_df['الحجم'].unique().tolist())
            with col2:
                print_type = st.radio("🖨️ نوع الطباعة:", ["عادي", "سكوتش"], horizontal=True)
            with col3:
                default_year = st.session_state.get('loaded_year', 2026)
                year = st.number_input("📅 العام:", min_value=2024, max_value=2030, value=default_year)
            
            col_opt1, col_opt2 = st.columns(2)
            with col_opt1:
                is_foreign = st.checkbox("🌍 منتج أجنبي")
            with col_opt2:
                st.write("")
            
            calc_method = st.radio("طريقة الحساب:", ["حساب بالأيام", "حساب بالفترات"], horizontal=True)
            
            days_count = 14
            start_date = None
            end_date = None
            start_p = ""
            end_p = ""
            selected_periods = []
            
            if calc_method == "حساب بالأيام":
                import datetime as dt
                col_date1, col_date2 = st.columns(2)
                with col_date1:
                    start_date_str = st.text_input("📅 تاريخ البداية (YYYY-MM-DD)", f"{year}-04-01")
                with col_date2:
                    end_date_str = st.text_input("📅 تاريخ النهاية (YYYY-MM-DD)", f"{year}-04-10")
                
                try:
                    dt.datetime.strptime(start_date_str, '%Y-%m-%d')
                    dt.datetime.strptime(end_date_str, '%Y-%m-%d')
                    start_date = start_date_str
                    end_date = end_date_str
                    d1 = dt.datetime.strptime(start_date_str, '%Y-%m-%d').date()
                    d2 = dt.datetime.strptime(end_date_str, '%Y-%m-%d').date()
                    days_count = (d2 - d1).days + 1
                    start_p = start_date_str
                    end_p = end_date_str
                    st.info(f"📅 عدد الأيام: {days_count} يوم")
                except ValueError:
                    st.error("❌ صيغة التاريخ غير صحيحة. استخدم YYYY-MM-DD")
                    st.stop()
            
            else:
                periods_df = pd.read_sql('SELECT namee, no FROM "الفترة" ORDER BY no', conn)
                period_names = periods_df['namee'].tolist()
                if not period_names:
                    st.error("❌ لا توجد فترات في جدول الفترة")
                    st.stop()
                
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    start_p = st.selectbox("📅 من فترة:", period_names, key="start_period")
                with col_p2:
                    end_p = st.selectbox("📅 إلى فترة:", period_names, index=len(period_names)-1, key="end_period")
                
                start_idx = period_names.index(start_p)
                end_idx = period_names.index(end_p)
                periods_count = abs(end_idx - start_idx) + 1
                days_count = periods_count * 15
                selected_periods = period_names[start_idx:end_idx+1]
                st.info(f"📅 عدد الفترات: {periods_count} | عدد الأيام التقريبي: {days_count} يوم")
            
            fee_print, fee_ads = get_fees(draw_df, selected_size, print_type, is_foreign)
            per_column_price = fee_print + (fee_ads / 28 * days_count)
            
            st.success(f"""
            💰 **تفاصيل الأسعار:**
            - أجر الطباعة الثابت: **{fee_print}$**
            - أجر العرض الشهري: **{fee_ads}$**
            - **الإجمالي لكل عمود: {per_column_price:.2f}$**
            """)
            
            st.divider()
            st.subheader("📍 اختيار المواقع")
            
            cities = pd.read_sql('SELECT DISTINCT "المحافظة" FROM "اعمدة انارة"', conn)['المحافظة'].tolist()
            selected_city = st.selectbox("اختر المحافظة:", cities)
            
            available_columns = pd.read_sql(f'''
                SELECT "رقم اللوحة", "اسم العمود" as "الموقع", "العدد", "الشبكة", "الحجم" 
                FROM "اعمدة انارة" 
                WHERE "المحافظة" = '{selected_city}' AND "الحجم" = '{selected_size}'
            ''', conn)
            
            # جلب المواقع المحجوزة
            booked_boards = []
            if calc_method == "حساب بالأيام" and start_date and end_date:
                booked_query = f'''
                    SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" 
                    WHERE "العام" = {year} 
                    AND "تاريخ البداية" <= '{end_date}' 
                    AND "تاريخ النهاية" >= '{start_date}'
                '''
                booked_df = pd.read_sql(booked_query, conn)
                booked_boards = booked_df['رقم اللوحة'].tolist() if not booked_df.empty else []
            else:
                period_placeholders = ', '.join([f"'{p}'" for p in selected_periods])
                booked_query = f'''
                    SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" 
                    WHERE "العام" = {year} 
                    AND "فترة الحجز" IN ({period_placeholders})
                '''
                booked_df = pd.read_sql(booked_query, conn)
                booked_boards = booked_df['رقم اللوحة'].tolist() if not booked_df.empty else []
            
            available_columns = available_columns[~available_columns['رقم اللوحة'].isin(booked_boards)]
            
            if not available_columns.empty:
                networks = st.multiselect("اختر الشبكات:", available_columns['الشبكة'].unique().tolist())
                if st.button("➕ إضافة إلى السلة", type="primary", use_container_width=True):
                    if selected_city not in st.session_state.cart:
                        st.session_state.cart[selected_city] = {}
                    for net in networks:
                        net_data = available_columns[available_columns['الشبكة'] == net].copy()
                        net_data['fee_print'] = fee_print
                        net_data['fee_ads'] = fee_ads
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
                            fam = float(edited_df['fee_ads'].iloc[0]) if 'fee_ads' in edited_df.columns else fee_ads
                            
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
                            save_data = {"data": {c: {n: df.to_dict() for n, df in ns.items()} for c, ns in st.session_state.cart.items()}}
                            cur = conn.cursor()
                            cur.execute('''
                                INSERT INTO "offers_history" (client_name, cart_json, status, start_p, end_p, year) 
                                VALUES (%s, %s, %s, %s, %s, %s)
                            ''', (customer_name, json.dumps(save_data, ensure_ascii=False), 'Pending', start_p, end_p, year))
                            conn.commit()
                            st.success("تم الحفظ")
                
                with col_btn2:
                    if st.button("✅ تثبيت نهائي", use_container_width=True, key="confirm_booking"):
                        if not customer_name:
                            st.error("الرجاء إدخال اسم الزبون")
                        else:
                            try:
                                cur = conn.cursor()
                                conn.rollback()
                                for city, networks in st.session_state.cart.items():
                                    for net, df in networks.items():
                                        for _, row in df.iterrows():
                                            if calc_method == "حساب بالأيام":
                                                cur.execute('''
                                                    INSERT INTO "حجوزات1" ("رقم اللوحة", "اسم الزبون", "العام", "فترة الحجز") 
                                                    VALUES (%s, %s, %s, %s)
                                                ''', (str(row['رقم اللوحة']), customer_name, year, f"{start_date}_to_{end_date}"))
                                            else:
                                                for period in selected_periods:
                                                    cur.execute('''
                                                        INSERT INTO "حجوزات1" ("رقم اللوحة", "اسم الزبون", "العام", "فترة الحجز") 
                                                        VALUES (%s, %s, %s, %s)
                                                    ''', (str(row['رقم اللوحة']), customer_name, year, period))
                                
                                if 'current_offer_id' in st.session_state:
                                    cur.execute('''
                                        UPDATE "offers_history" SET status = 'Accepted' WHERE id = %s
                                    ''', (st.session_state.current_offer_id,))
                                    del st.session_state.current_offer_id
                                
                                conn.commit()
                                st.session_state.cart = {}
                                st.success("تم التثبيت")
                                st.rerun()
                            except Exception as e:
                                conn.rollback()
                                st.error(f"حدث خطأ: {str(e)}")
                
                with col_btn3:
                    if st.button("📝 تصدير Word", use_container_width=True):
                        word_file = export_word_old(customer_name, st.session_state.cart, start_p, end_p, grand_total)
                        st.download_button("📥 تحميل العرض", word_file, f"Offer_{customer_name}.docx")
                
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
            # التحقق من وجود فترات
            periods_df = pd.read_sql('SELECT "no", "namee" FROM "الفترة" ORDER BY "no"', conn)
            
            if periods_df.empty:
                st.error("❌ لا توجد فترات في جدول الفترة")
                st.stop()
            
            period_names = periods_df['namee'].tolist()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                from_period = st.selectbox("من فترة:", period_names, key="from_period")
            with col2:
                to_period = st.selectbox("إلى فترة:", period_names, index=len(period_names)-1, key="to_period")
            with col3:
                report_year = st.number_input("العام:", value=datetime.now().year, key="report_year")
            
            # حساب نطاق الفترات
            from_idx = int(periods_df[periods_df['namee'] == from_period]['no'].iloc[0])
            to_idx = int(periods_df[periods_df['namee'] == to_period]['no'].iloc[0])
            target_periods = periods_df[(periods_df['no'] >= from_idx) & (periods_df['no'] <= to_idx)]['namee'].tolist()
            
            if not target_periods:
                st.warning("⚠️ لا توجد فترات في النطاق المحدد")
                st.stop()
            
            # جلب بيانات المواقع والأعمدة
            all_boards = pd.read_sql('SELECT "رقم اللوحة", "المحافظة", "الحجم", "العدد" FROM "اعمدة انارة"', conn)
            
            if all_boards.empty:
                st.warning("⚠️ لا توجد بيانات في جدول الأعمدة")
                st.stop()
            
            # جلب الحجوزات في الفترة المحددة
            period_placeholders = ", ".join([f"'{p}'" for p in target_periods])
            booked_query = f'''
                SELECT DISTINCT "رقم اللوحة" 
                FROM "حجوزات1" 
                WHERE "العام" = {report_year} 
                AND "فترة الحجز" IN ({period_placeholders})
            '''
            booked_in_period = pd.read_sql(booked_query, conn)['رقم اللوحة'].tolist()
            
            # تحديد الحالة لكل موقع
            all_boards['الحالة'] = all_boards['رقم اللوحة'].apply(lambda x: 'محجوز' if x in booked_in_period else 'متاح')
            
            # حساب الإحصائيات للمواقع (عدد السجلات)
            total_sites = len(all_boards)
            booked_sites = len(booked_in_period)
            available_sites = total_sites - booked_sites
            
            # حساب الإحصائيات للأعمدة (مجموع العدد)
            total_boards = all_boards['العدد'].sum()
            booked_boards = all_boards[all_boards['الحالة'] == 'محجوز']['العدد'].sum()
            available_boards = all_boards[all_boards['الحالة'] == 'متاح']['العدد'].sum()
            
            # عرض المؤشرات
            st.subheader("📊 إحصائيات عامة")
            
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.metric("🏢 المواقع الكلية", total_sites)
                st.metric("📌 الأعمدة الكلية", int(total_boards))
            with col_b:
                st.metric("🔴 المواقع المحجوزة", booked_sites)
                st.metric("🔴 الأعمدة المحجوزة", int(booked_boards))
            with col_c:
                st.metric("🟢 المواقع المتاحة", available_sites)
                st.metric("🟢 الأعمدة المتاحة", int(available_boards))
            
            st.divider()
            
            # عرض التفاصيل حسب المحافظة
            st.subheader("📋 تفاصيل حسب المحافظة")
            
            for city in sorted(all_boards['المحافظة'].unique()):
                city_data = all_boards[all_boards['المحافظة'] == city]
                
                if city_data.empty:
                    continue
                
                # إحصائيات المحافظة
                city_sites = len(city_data)
                city_boards = city_data['العدد'].sum()
                city_booked_sites = city_data[city_data['الحالة'] == 'محجوز'].shape[0]
                city_booked_boards = city_data[city_data['الحالة'] == 'محجوز']['العدد'].sum()
                city_available_sites = city_sites - city_booked_sites
                city_available_boards = city_boards - city_booked_boards
                
                st.write(f"### 📍 محافظة {city}")
                
                col_s1, col_s2, col_s3 = st.columns(3)
                with col_s1:
                    st.metric("المواقع", f"{city_available_sites} / {city_sites}")
                with col_s2:
                    st.metric("الأعمدة", f"{int(city_available_boards)} / {int(city_boards)}")
                with col_s3:
                    st.metric("نسبة الإشغال", f"{(city_booked_boards/city_boards*100):.1f}%" if city_boards > 0 else "0%")
                
                # جدول تفصيلي حسب الحجم
                table_data = []
                for size in city_data['الحجم'].unique():
                    size_data = city_data[city_data['الحجم'] == size]
                    size_sites = len(size_data)
                    size_boards = size_data['العدد'].sum()
                    size_booked = size_data[size_data['الحالة'] == 'محجوز']['العدد'].sum()
                    table_data.append({
                        'الحجم': size,
                        'عدد المواقع': size_sites,
                        'عدد الأعمدة': int(size_boards),
                        'محجوز': int(size_booked),
                        'متاح': int(size_boards - size_booked)
                    })
                
                st.dataframe(pd.DataFrame(table_data), use_container_width=True)
            
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
            
            with col_exp2:
                # تصدير Word (نسخة مبسطة)
                from docx import Document
                
                doc = Document()
                h = doc.add_heading(f"تقرير حالة الإشغال لعام {report_year}", 0)
                h.alignment = WD_ALIGN_PARAGRAPH.CENTER
                
                p_period = doc.add_paragraph()
                p_period.add_run(f"الفترة من: {from_period} لغاية: {to_period}").bold = True
                
                doc.add_paragraph()
                p_summary = doc.add_paragraph()
                p_summary.add_run(f"المواقع الكلية: {total_sites} | الأعمدة الكلية: {int(total_boards)}")
                p_summary.add_run(f"\nالمواقع المحجوزة: {booked_sites} | الأعمدة المحجوزة: {int(booked_boards)}")
                p_summary.add_run(f"\nالمواقع المتاحة: {available_sites} | الأعمدة المتاحة: {int(available_boards)}")
                
                word_out = io.BytesIO()
                doc.save(word_out)
                st.download_button(
                    "📝 تصدير إلى Word",
                    word_out.getvalue(),
                    f"Inventory_Report_{report_year}.docx",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )
                
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
    # ============================================================
    # صفحة تقرير المتاح حالياً (مع فلتر التاريخ وملاحظات)
    # ============================================================
    elif page == "📅 تقرير التوفر الشهري":
        st.title("📋 تقرير الأعمدة المتاحة")
        st.info("يعرض هذا التقرير الأعمدة المتاحة حالياً أو التي ستصبح متاحة بعد تاريخ محدد")
        
        from docx import Document
        from docx.shared import Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
        import io
        from datetime import date, timedelta
        
        # دالة RTL
        def force_rtl_word(paragraph):
            paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            pPr = paragraph._element.get_or_add_pPr()
            bidi = OxmlElement('w:bidi')
            bidi.set(qn('w:val'), '1')
            pPr.append(bidi)
            for run in paragraph.runs:
                rPr = run._element.get_or_add_rPr()
                rtl = OxmlElement('w:rtl')
                rtl.set(qn('w:val'), '1')
                rPr.append(rtl)
        
        def set_table_rtl(table):
            tblPr = table._element.xpath('w:tblPr')[0]
            bidi = OxmlElement('w:bidiVisual')
            tblPr.append(bidi)
        
        # دالة تصدير Word
        def export_available_word(df, total_count, notes):
            doc = Document()
            
            # عنوان
            title = doc.add_heading("تقرير الأعمدة المتاحة", 0)
            title.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            # تاريخ
            p = doc.add_paragraph()
            p.add_run(f"التاريخ: {date.today().strftime('%d/%m/%Y')}")
            force_rtl_word(p)
            doc.add_paragraph()
            
            # إجمالي عام
            p = doc.add_paragraph()
            p.add_run(f"إجمالي الأعمدة المتاحة: {total_count} عمود").bold = True
            force_rtl_word(p)
            doc.add_paragraph()
            
            # تفصيل حسب المحافظة
            for city in sorted(df['المحافظة'].unique()):
                city_df = df[df['المحافظة'] == city]
                city_count = len(city_df)
                city_total_boards = city_df['العدد'].sum() if 'العدد' in city_df.columns else city_count
                
                # عنوان المحافظة
                p = doc.add_paragraph()
                p.add_run(f"■ محافظة {city}").bold = True
                p.runs[0].font.size = Pt(14)
                force_rtl_word(p)
                
                # جدول الأعمدة (3 أعمدة: رقم اللوحة، اسم العمود، العدد)
                table = doc.add_table(rows=1, cols=3)
                table.style = 'Table Grid'
                set_table_rtl(table)
                
                # رأس الجدول
                hdr = table.rows[0].cells
                hdr[0].text = "رقم اللوحة"
                hdr[1].text = "اسم العمود"
                hdr[2].text = "العدد"
                for cell in hdr:
                    for para in cell.paragraphs:
                        force_rtl_word(para)
                    tc_pr = cell._element.get_or_add_tcPr()
                    shd = OxmlElement('w:shd')
                    shd.set(qn('w:fill'), '660099')
                    tc_pr.append(shd)
                    if cell.paragraphs[0].runs:
                        cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
                
                # بيانات الأعمدة
                for _, row in city_df.iterrows():
                    cells = table.add_row().cells
                    cells[0].text = str(row['رقم اللوحة'])
                    cells[1].text = str(row['اسم العمود'])
                    cells[2].text = str(row['العدد']) if 'العدد' in row else "1"
                    for cell in cells:
                        for para in cell.paragraphs:
                            force_rtl_word(para)
                
                doc.add_paragraph()
                
                # إجمالي المحافظة
                p = doc.add_paragraph()
                p.add_run(f"إجمالي محافظة {city}: {city_total_boards} لوحة").bold = True
                force_rtl_word(p)
                doc.add_paragraph()
                doc.add_paragraph()
            
            # الملاحظات اليدوية
            if notes:
                doc.add_paragraph()
                p = doc.add_paragraph()
                p.add_run("═══════════════ ملاحظات ═══════════════").bold = True
                force_rtl_word(p)
                
                p = doc.add_paragraph()
                p.add_run(notes)
                force_rtl_word(p)
            
            # المجموع الكلي
            doc.add_paragraph()
            p = doc.add_paragraph()
            p.add_run("═" * 40).bold = True
            force_rtl_word(p)
            
            p = doc.add_paragraph()
            p.add_run(f"المجموع الكلي للأعمدة المتاحة: {total_count} لوحة").bold = True
            p.runs[0].font.size = Pt(14)
            force_rtl_word(p)
            
            output = io.BytesIO()
            doc.save(output)
            output.seek(0)
            return output
        
        # ========== واجهة المستخدم ==========
        
        # خيارات الفلتر
        col_filter1, col_filter2 = st.columns(2)
        with col_filter1:
            show_all = st.checkbox("📅 عرض جميع الأعمدة المتاحة حالياً", value=True)
        with col_filter2:
            future_date = st.date_input("🗓️ عرض الأعمدة التي ستصبح متاحة بعد تاريخ", value=date.today() + timedelta(days=7))
        
        # ملاحظات يدوية
        notes = st.text_area("📝 ملاحظات (تظهر في نهاية التقرير)", placeholder="أضف ملاحظاتك هنا...", height=100)
        
        if st.button("🚀 تشغيل التقرير", use_container_width=True, type="primary"):
            
            with st.spinner("جاري إنشاء التقرير..."):
                
                current_year = date.today().year
                today = date.today()
                
                # جلب جميع الأعمدة
                all_columns = pd.read_sql('SELECT "رقم اللوحة", "اسم العمود", "المحافظة", "الشبكة", "الحجم", "العدد" FROM "اعمدة انارة"', conn)
                
                # جلب الحجوزات النشطة
                if show_all:
                    # الحجوزات النشطة حالياً
                    bookings_query = f'''
                        SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" 
                        WHERE "العام" = {current_year}
                    '''
                else:
                    # الحجوزات التي تنتهي بعد التاريخ المحدد
                    bookings_query = f'''
                        SELECT DISTINCT "رقم اللوحة" FROM "حجوزات1" 
                        WHERE "العام" = {current_year}
                        AND ("تاريخ النهاية" >= '{future_date}' OR "فترة الحجز" IS NOT NULL)
                    '''
                
                booked_df = pd.read_sql(bookings_query, conn)
                booked_boards = booked_df['رقم اللوحة'].tolist() if not booked_df.empty else []
                
                # تصفية الأعمدة المتاحة
                available_df = all_columns[~all_columns['رقم اللوحة'].isin(booked_boards)]
                total_available = len(available_df)
                total_boards_count = available_df['العدد'].sum() if 'العدد' in available_df.columns else total_available
                
                st.success(f"✅ {total_available} موقعاً ({int(total_boards_count)} لوحة) متاحة")
                
                # عرض الملخص
                st.subheader("📊 ملخص حسب المحافظة")
                summary = available_df.groupby('المحافظة').agg({
                    'رقم اللوحة': 'count',
                    'العدد': 'sum'
                }).rename(columns={'رقم اللوحة': 'عدد المواقع', 'العدد': 'عدد اللوحات'})
                st.dataframe(summary, use_container_width=True)
                
                # عرض التفاصيل
                st.subheader("📋 قائمة الأعمدة المتاحة")
                st.dataframe(available_df[['رقم اللوحة', 'اسم العمود', 'المحافظة', 'الشبكة', 'الحجم', 'العدد']], use_container_width=True, height=400)
                
                # تصدير Word
                word_file = export_available_word(available_df, int(total_boards_count), notes)
                st.download_button(
                    "📝 تحميل التقرير (Word)",
                    word_file,
                    f"available_columns_{date.today().strftime('%Y%m%d')}.docx",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )
        
        else:
            st.info("👆 اضغط على زر 'تشغيل التقرير'")
