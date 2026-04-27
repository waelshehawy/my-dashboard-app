import streamlit as st
import pandas as pd
import sqlite3
import os
import io
import plotly.express as px
import folium
from streamlit_folium import st_folium
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from arabic_reshaper import reshape
from bidi.algorithm import get_display

# --- إعدادات الصفحة ---
st.set_page_config(page_title="PreView ERP - Smart Edition", layout="wide")

# --- نظام الأمان ---
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("🔒 تسجيل الدخول - نظام بريفيو")
        
        # إضافة حقل لاسم المستخدم
        user_input = st.text_input("اسم المستخدم:")
        password_input = st.text_input("كلمة المرور:", type="password")
        
        # قائمة المستخدمين (يمكنك إضافة أي عدد هنا)
        users = {
            "admin": "preview2026",
            "wael": "wael123",
            "manager": "preview_boss"
        }

        if st.button("دخول"):
            if user_input in users and users[user_input] == password_input:
                st.session_state.authenticated = True
                st.session_state.username = user_input # حفظ اسم المستخدم للجلسة
                st.rerun()
            else:
                st.error("❌ خطأ في اسم المستخدم أو كلمة المرور")
        return False
    return True


if check_password():
    def get_connection():
        return sqlite3.connect('billboards_data.db')

    def ar(text):
        if not text: return ""
        return get_display(reshape(str(text)))

    # --- دالة إضافة الخلفية العائمة للوورد ---
    def add_float_picture(doc, image_path, width, height):
        header = doc.sections[0].header
        if not header.paragraphs: header.add_paragraph()
        run = header.paragraphs[0].add_run()
        shape = run.add_picture(image_path, width=width, height=height)
        inline = shape._inline
        extent, doc_pr = inline.extent, inline.docPr
        anchor_xml = f"""
        <wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0" relativeHeight="0" behindDoc="1" locked="0" layoutInCell="1" allowOverlap="1" xmlns:wp="http://openxmlformats.org">
            <wp:simplePos x="0" y="0"/><wp:positionH relativeFrom="page"><wp:posOffset>0</wp:posOffset></wp:positionH>
            <wp:positionV relativeFrom="page"><wp:posOffset>0</wp:posOffset></wp:positionV>
            <wp:extent cx="{extent.cx}" cy="{extent.cy}"/><wp:wrapNone/><wp:docPr id="{doc_pr.id}" name="{doc_pr.name}"/>
        </wp:anchor>"""
        anchor = OxmlElement(anchor_xml)
        anchor.append(inline.graphic)
        inline.getparent().replace(inline, anchor)

    def export_final_quotation(customer_name, cart_data, dates):
        doc = Document()
        doc.sections[0].right_to_left = True
        if os.path.exists('logo.png'):
            add_float_picture(doc, 'logo.png', width=Inches(8.27), height=Inches(11.69))
        for _ in range(5): doc.add_paragraph()
        p_cust = doc.add_paragraph()
        p_cust.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p_cust.add_run(ar(f"السادة شركة .. {customer_name} المحترمين")).bold = True
        for city, networks in cart_data.items():
            p_city = doc.add_paragraph()
            p_city.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            run_city = p_city.add_run(ar(f"محافظة {city}"))
            run_city.font.color.rgb = RGBColor(102, 0, 153)
            for net, df in networks.items():
                doc.add_paragraph(ar(f"شبكات {net}")).alignment = WD_ALIGN_PARAGRAPH.RIGHT
                table = doc.add_table(rows=1, cols=4); table.style = 'Table Grid'
                hdr = table.rows[0].cells
                hdr[0].text, hdr[1].text, hdr[2].text, hdr[3].text = ar("العدد"), ar("الموقع"), ar("العدد"), ar("الموقع")
                clean_df = df.iloc[:, :2].reset_index(drop=True)
                for i in range(len(clean_df)):
                    row_idx, col_off = (i // 2) + 1, (0 if i % 2 == 0 else 2)
                    if row_idx >= len(table.rows): table.add_row()
                    table.cell(row_idx, col_off).text = str(clean_df.iloc[i, 1])
                    table.cell(row_idx, col_off + 1).text = ar(clean_df.iloc[i, 0])
        target = io.BytesIO(); doc.save(target); target.seek(0)
        return target

    # --- واجهة التطبيق ---
    if 'cart' not in st.session_state: st.session_state.cart = {}
    st.sidebar.title("💎 PreView Ads ERP")
    page = st.sidebar.radio("القائمة:", ["🏠 الخريطة والداشبورد", "📄 العروض والعقود"])

    if st.sidebar.button("🚪 خروج"):
        st.session_state.authenticated = False
        st.rerun()

    conn = get_connection()

    if page == "🏠 الخريطة والداشبورد":
        st.title("🏠 لوحة التحكم الذكية")
        df_all = pd.read_sql("SELECT * FROM [اعمدة انارة]", conn)
        
        # إحصائيات
        c1, c2, c3 = st.columns(3)
        c1.metric("إجمالي المواقع", len(df_all))
        c2.metric("المحافظات", df_all['المحافظة'].nunique())
        c3.metric("عدد الأعمدة", df_all['العدد'].sum())

        # خريطة افتراضية (توزع حسب المحافظة)
        st.subheader("📍 التوزع الجغرافي للمواقع")
        m = folium.Map(location=[34.8, 38.5], zoom_start=7) # مركز سوريا
        # هنا يمكن إضافة نقاط (Markers) إذا توفرت خطوط الطول والعرض في جدولك
        st_folium(m, width=1200, height=400)

        # رسوم بيانية
        st.subheader("📊 إحصائيات الشبكات")
        fig = px.bar(df_all, x="المحافظة", color="الشبكة", barmode="group")
        st.plotly_chart(fig, use_container_width=True)

    elif page == "📄 العروض والعقود":
        st.title("📄 نظام بناء العروض وتثبيت الحجز")
        col_in, col_view = st.columns([1, 2])
        
        with col_in:
            cust = st.text_input("اسم الزبون")
            cities = pd.read_sql("SELECT المحافظة FROM المحافظات", conn)['المحافظة'].tolist()
            sel_city = st.selectbox("المحافظة", cities)
            raw_df = pd.read_sql(f"SELECT [اسم العمود] as الموقع, [العدد], [الشبكة] FROM [اعمدة انارة] WHERE المحافظة = '{sel_city}'", conn)
            sel_nets = st.multiselect("الشبكات المتاحة:", raw_df['الشبكة'].unique().tolist())
            if st.button("➕ إضافة للعربة"):
                st.session_state.cart[sel_city] = {n: raw_df[raw_df['الشبكة'] == n][['الموقع', 'العدد']] for n in sel_nets}
                st.success("تمت الإضافة")

        with col_view:
            if st.session_state.cart:
                for city_n, nets in st.session_state.cart.items():
                    with st.expander(f"📍 {city_n}"):
                        for net_n, df in nets.items():
                            st.session_state.cart[city_n][net_n] = st.data_editor(df, key=f"ed_{city_n}_{net_n}")
                
                b1, b2, b3 = st.columns(3)
                with b1:
                    if st.button("🚀 تصدير Word"):
                        out = export_final_quotation(cust, st.session_state.cart, {'start': "2026/05/01", 'end': "2026/05/28"})
                        st.download_button("📥 تحميل العرض", out, f"Quotation_{cust}.docx")
                with b2:
                    if st.button("✅ تثبيت عقد"):
                        st.balloons(); st.success("تم الحجز بنجاح!")
                with b3:
                    if st.button("🗑️ تفريغ"):
                        st.session_state.cart = {}; st.rerun()
