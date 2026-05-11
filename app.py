# --- 5. DASHBOARD LOGIC ---
def show_dashboard(conn):
    st.title("📊 لوحة التحكم والمراقبة اللحظية")
    
    with st.spinner("جاري تحديث بيانات الخريطة..."):
        # جلب البيانات بكفاءة: فقط الأعمدة المطلوبة
        current_year = datetime.now().year
        
        # استعلام الحجوزات: جلب اللوحات المحجوزة فقط للعام الحالي لتقليل حجم البيانات
        query_booked = f'SELECT DISTINCT "رقم اللوحة", "اسم الزبون" FROM "حجوزات1" WHERE "العام" = {current_year}'
        df_booked = pd.read_sql(query_booked, conn)
        
        # استعلام الأعمدة
        df_all = pd.read_sql('SELECT "رقم اللوحة", "اسم العمود", "المحافظة", "الشبكة", "Latitude", "Longitude" FROM "اعمدة انارة"', conn)
        
        # دمج البيانات (Left Join) لمعرفة المحجوز والمتاح
        df_map = pd.merge(df_all, df_booked, on='رقم اللوحة', how='left')
        df_map['status'] = df_map['اسم الزبون'].apply(lambda x: 'محجوز' if pd.notnull(x) else 'متاح')

    # --- Metrics (المؤشرات العلوية) ---
    m1, m2, m3, m4 = st.columns(4)
    total_spots = len(df_map)
    booked_spots = df_map['اسم الزبون'].notnull().sum()
    available_spots = total_spots - booked_spots
    occupancy_rate = (booked_spots / total_spots) * 100 if total_spots > 0 else 0

    m1.metric("إجمالي المواقع", total_spots)
    m2.metric("المحجوز", booked_spots, delta=f"{occupancy_rate:.1f}% إشغال")
    m3.metric("المتاح", available_spots, delta=f"-{100-occupancy_rate:.1f}%", delta_color="normal")
    m4.metric("عدد المحافظات", df_map['المحافظة'].nunique())

    # --- Interactive Map ---
    st.subheader("📍 التوزع الجغرافي وحالة الإشغال")
    
    # اختيار المحافظة للتركيز (Zoom)
    SYRIA_CITIES = {
        "الكل": [34.80, 38.99, 7],
        "دمشق": [33.51, 36.27, 12],
        "حلب": [36.20, 37.13, 11],
        "حمص": [34.73, 36.71, 11],
        "اللاذقية": [35.53, 35.79, 11]
    }
    
    selected_city = st.selectbox("التركيز على محافظة:", list(SYRIA_CITIES.keys()))
    city_coords = SYRIA_CITIES[selected_city]

    # إنشاء الخريطة
    m = folium.Map(location=[city_coords[0], city_coords[1]], zoom_start=city_coords[2], tiles="CartoDB positron")
    marker_cluster = MarkerCluster(name="لوحات الإعلانات").add_to(m)

    for _, row in df_map.iterrows():
        if pd.notnull(row['Latitude']) and pd.notnull(row['Longitude']):
            is_booked = row['status'] == 'محجوز'
            color = 'red' if is_booked else 'purple'
            icon_type = 'info-sign' if is_booked else 'ok-sign'
            
            # محتوى النافذة المنبثقة بتنسيق HTML أنيق
            popup_html = f"""
            <div style="direction: rtl; font-family: tahoma; font-size: 12px;">
                <b>الموقع:</b> {row['اسم العمود']}<br>
                <b>الشبكة:</b> {row['الشبكة']}<br>
                <b>الحالة:</b> <span style="color:{color};">{'● ' + row['status']}</span><br>
                {"<b>الزبون:</b> " + row['اسم الزبون'] if is_booked else ""}
            </div>
            """
            
            folium.Marker(
                location=[row['Latitude'], row['Longitude']],
                popup=folium.Popup(popup_html, max_width=250),
                icon=folium.Icon(color=color, icon=icon_type)
            ).add_to(marker_cluster)

    st_folium(m, width="100%", height=500, returned_objects=[])

    # --- التحليل حسب المحافظات ---
    st.divider()
    st.subheader("📊 تحليل الإشغال حسب المحافظة")
    city_stats = df_map.groupby(['المحافظة', 'status']).size().unstack(fill_value=0)
    st.bar_chart(city_stats)
# --- 6. QUOTATION & SALES LOGIC ---
def show_quotation(conn):
    st.title("📄 محرك العروض وتثبيت الحجوزات")
    
    # 1. إدارة العروض المنتهية (تلقائي)
    with st.expander("🔔 تنبيهات العروض (48 ساعة)"):
        manage_expired_offers(conn)

    # 2. نظام استعادة المسودات
    st.subheader("📂 استرجاع مسودة")
    saved_df = pd.read_sql('SELECT id, client_name FROM "offers_history" WHERE status=\'Pending\' ORDER BY id DESC', conn)
    if not saved_df.empty:
        selected_offer = st.selectbox("اختر عرضاً محفوظاً:", ["---"] + saved_df['client_name'].tolist())
        if selected_offer != "---" and st.button("🔄 استعادة البيانات للسلة"):
            res = pd.read_sql(f"SELECT cart_json, client_name FROM \"offers_history\" WHERE client_name='{selected_offer}' AND status='Pending' LIMIT 1", conn)
            st.session_state.cart = json.loads(res['cart_json'].iloc[0])
            st.session_state.temp_cust = res['client_name'].iloc[0]
            st.rerun()

    st.divider()

    # 3. إعدادات العرض الجديد
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1: customer = st.text_input("اسم الزبون (المؤسسة):", value=st.session_state.get('temp_cust', ""))
    with col2: year = st.number_input("العام الإعلاني:", value=datetime.now().year + 1)
    with col3: print_type = st.radio("نوع الطباعة:", ["عادي", "سكوتش"], horizontal=True)

    # جلب بيانات المراجع (الفترات والأسعار)
    periods_df = pd.read_sql('SELECT * FROM "الفترة" ORDER BY "no"', conn)
    prices_df = pd.read_sql('SELECT * FROM "اسماء الرسم"', conn)

    c_p1, c_p2, c_p3, c_p4 = st.columns(4)
    with c_p1: start_p = st.selectbox("من فترة:", periods_df['namee'].tolist())
    with c_p2: end_p = st.selectbox("إلى فترة:", periods_df['namee'].tolist(), index=len(periods_df)-1)
    
    # --- المحرك المالي الجديد (أجنبي + أيام) ---
    with c_p3: is_foreign = st.checkbox("🚩 إعلان أجنبي")
    with c_p4: calc_method = st.radio("طريقة الحساب:", ["فترة كاملة", "بالأيام"], horizontal=True)

    days_count = 15 # القيمة الافتراضية
    if calc_method == "بالأيام":
        days_count = st.number_input("عدد الأيام الفعلي:", min_value=1, max_value=365, value=15)

    # 4. فلترة واختيار المواقع
    st.subheader("📍 اختيار المواقع والشبكات")
    cities = pd.read_sql('SELECT DISTINCT "المحافظة" FROM "اعمدة انارة"', conn)['المحافظة'].tolist()
    sel_city = st.selectbox("المحافظة المستهدفة:", cities)
    
    # جلب الأحجام المتاحة في هذه المحافظة
    sizes = pd.read_sql(f"SELECT DISTINCT \"الحجم\" FROM \"اعمدة انارة\" WHERE \"المحافظة\"='{sel_city}'", conn)['الحجم'].tolist()
    sel_size = st.selectbox("مقاس اللوحة:", sizes)

    # البحث الذكي عن السعر
    subset = prices_df[prices_df['الحجم'] == sel_size].copy()
    subset['clean_name'] = subset['اسم الرسم'].str.strip().str.replace('أ', 'ا')
    t_pt = print_type.replace('أ', 'ا')

    # سعر الطباعة
    f_print = subset[subset['clean_name'].str.contains(f"طباعة.*{t_pt}", na=False)]['اجرة الرسم'].sum()
    
    # سعر العرض (البحث عن أجنبي أو محلي)
    if is_foreign:
        f_ads_base = subset[subset['clean_name'].str.contains("عرض", na=False) & subset['clean_name'].str.contains("اجنبي", na=False)]['اجرة الرسم'].sum()
    else:
        f_ads_base = subset[subset['clean_name'].str.contains("عرض", na=False) & ~subset['clean_name'].str.contains("اجنبي", na=False)]['اجرة الرسم'].sum()

    # تطبيق معادلة الأيام
    f_ads_final = (f_ads_base / 15) * days_count if calc_method == "بالأيام" else f_ads_base

    # استعلام المواقع المتاحة (استبعاد المحجوز)
    s_idx = periods_df[periods_df['namee'] == start_p]['no'].iloc[0]
    e_idx = periods_df[periods_df['namee'] == end_p]['no'].iloc[0]
    target_periods = periods_df[(periods_df['no'] >= s_idx) & (periods_df['no'] <= e_idx)]['namee'].tolist()
    
    booked_ids = pd.read_sql(f"SELECT \"رقم اللوحة\" FROM \"حجوزات1\" WHERE \"العام\"={year} AND \"فترة الحجز\" IN ({str(target_periods)[1:-1]})", conn)['رقم اللوحة'].tolist()
    
    available_raw = pd.read_sql(f"SELECT \"رقم اللوحة\", \"اسم العمود\" as \"الموقع\", \"العدد\", \"الشبكة\" FROM \"اعمدة انارة\" WHERE \"المحافظة\"='{sel_city}' AND \"الحجم\"='{sel_size}'", conn)
    available_raw = available_raw[~available_raw['رقم اللوحة'].isin(booked_ids)]

    if not available_raw.empty:
        sel_nets = st.multiselect("الشبكات المتاحة:", sorted(available_raw['الشبكة'].unique().tolist()))
        if st.button("➕ إضافة الشبكات المختارة للسلة"):
            for net in sel_nets:
                net_data = available_raw[available_raw['الشبكة'] == net].copy()
                net_data['fee_print'] = f_print
                net_data['fee_ads'] = f_ads_final
                net_data['الحجم'] = sel_size
                net_data['is_foreign'] = is_foreign
                
                if sel_city not in st.session_state.cart: st.session_state.cart[sel_city] = {}
                st.session_state.cart[sel_city][net] = net_data.to_dict('records')
            st.success("تم التحديث!")
            st.rerun()

    # 5. عرض السلة والعمليات المالية
    if st.session_state.cart:
        render_cart_section(customer, start_p, end_p, year, target_periods, conn, is_foreign)
# --- 7. RENDERING THE CART & FINANCIALS ---
def render_cart_section(customer, start_p, end_p, year, target_periods, conn, is_foreign):
    st.divider()
    st.subheader("🛒 سلة الحجز والمراجعة المالية")
    grand_total = 0.0
    
    for city, networks in list(st.session_state.cart.items()):
        for net, data in list(networks.items()):
            df = pd.DataFrame(data)
            with st.expander(f"📍 {city} | شبكة: {net}", expanded=True):
                # عرض البيانات مع إمكانية تعديل العدد يدوياً
                edited_df = st.data_editor(df, key=f"editor_{city}_{net}")
                st.session_state.cart[city][net] = edited_df.to_dict('records')
                
                # الحساب المالي للقسم
                q = pd.to_numeric(edited_df['العدد']).sum()
                p_fee = float(edited_df['fee_print'].iloc[0])
                a_fee = float(edited_df['fee_ads'].iloc[0])
                subtotal = q * (p_fee + a_fee)
                grand_total += subtotal
                
                st.write(f"إجمالي القسم: **{subtotal:,.0f} $**")
                if st.button(f"🗑️ حذف {net}", key=f"del_{city}_{net}"):
                    del st.session_state.cart[city][net]
                    if not st.session_state.cart[city]: del st.session_state.cart[city]
                    st.rerun()

    st.info(f"### 💰 إجمالي القيمة المالية للعرض: {grand_total:,.0f} $")

    col_b1, col_b2, col_b3, col_b4 = st.columns(4)
    with col_b1:
        if st.button("💾 حفظ كمنافسة/مسودة"):
            save_offer(customer, st.session_state.cart, 'Pending', conn)
    with col_b2:
        if st.button("✅ تثبيت حجز نهائي"):
            confirm_booking(customer, st.session_state.cart, year, target_periods, conn)
    with col_b3:
        word_file = export_word_pro(customer, st.session_state.cart, start_p, end_p, grand_total, is_foreign)
        st.download_button("📥 تحميل عرض السعر (Word)", word_file, f"Offer_{customer}.docx")
    with col_b4:
        if st.button("🔴 تفريغ السلة"):
            st.session_state.cart = {}; st.rerun()

# --- 8. PROFESSIONAL WORD EXPORT FUNCTION ---
def export_word_pro(customer, cart_data, start_p, end_p, total, is_foreign):
    doc = Document()
    set_rtl(doc) # ضبط المستند بالكامل RTL
    
    # رأس الصفحة (اللوغو والتاريخ)
    today = datetime.now().strftime("%Y/%m/%d")
    p_date = doc.add_paragraph()
    p_date.add_run(f"التاريخ: {today}").bold = True
    set_rtl(p_date)
    
    doc.add_paragraph("\n") # مسافات
    
    # العنوان الرئيسي
    title = doc.add_paragraph()
    adv_type = "الأجنبي" if is_foreign else "الوطني"
    title.add_run(f"السادة شركة {customer} المحترمين").bold = True
    title.runs[0].font.size = Pt(14)
    set_rtl(title)
    
    intro = doc.add_paragraph()
    intro.add_run(f"موضوع العرض: تقديم مواقع إعلانية - إعلان {adv_type}")
    set_rtl(intro)
    
    intro2 = doc.add_paragraph()
    intro2.add_run(f"يسرنا تقديم المواقع المتاحة للفترة من ({start_p}) ولغاية ({end_p}):")
    set_rtl(intro2)

    for city, nets in cart_data.items():
        city_head = doc.add_paragraph()
        city_head.add_run(f"■ محافظة {city}:").bold = True
        city_head.runs[0].font.color.rgb = RGBColor(102, 0, 153)
        set_rtl(city_head)
        
        for net, items in nets.items():
            df = pd.DataFrame(items)
            net_desc = doc.add_paragraph()
            net_desc.add_run(f"الشبكة: {net} | القياس: {df['الحجم'].iloc[0]}").bold = True
            set_rtl(net_desc)
            
            # إنشاء الجدول
            table = doc.add_table(rows=1, cols=2)
            apply_table_style(table)
            hdr_cells = table.rows[0].cells
            hdr_cells[0].text = "اسم الموقع (العمود)"
            hdr_cells[1].text = "العدد"
            
            # تنسيق الهيدر باللون البنفسجي
            for cell in hdr_cells:
                set_rtl(cell.paragraphs[0])
                tc_pr = cell._element.get_or_add_tcPr()
                shd = OxmlElement('w:shd'); shd.set(qn('w:fill'), "660099"); tc_pr.append(shd)
                cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)

            for _, row in df.iterrows():
                row_cells = table.add_row().cells
                row_cells[0].text = str(row['الموقع'])
                row_cells[1].text = str(row['العدد'])
                for cell in row_cells: set_rtl(cell.paragraphs[0])

    # الخاتمة المالية
    doc.add_paragraph("\n")
    final_p = doc.add_paragraph()
    final_run = final_p.add_run(f"إجمالي القيمة المالية للعرض: {total:,.0f} دولار أمريكي")
    final_run.bold = True; final_run.font.size = Pt(14)
    set_rtl(final_p)
    
    note = doc.add_paragraph()
    note.add_run("• ملاحظة: المواقع المذكورة أعلاه متاحة للحجز لمدة 48 ساعة من تاريخ العرض.").italic = True
    set_rtl(note)

    out = io.BytesIO()
    doc.save(out)
    out.seek(0)
    return out

# --- 9. INVENTORY & SETTINGS PAGES ---
def show_inventory(conn):
    st.title("📋 تقارير الجرد والحالة")
    # (هنا نستخدم نفس منطق التصفية الذي بنيناه في الجزء السابق مع تحسين عرض الجداول بصرياً)
    # إضافة زر تصدير Excel باستخدام xlsxwriter ليكون الملف مرتباً جداً.

def show_settings(conn):
    st.title("⚙️ الإعدادات المتقدمة")
    engine = get_engine()
    tabs = st.tabs(["بيانات اللوحات", "أسماء الرسم والأجور", "إدارة الحجوزات"])
    # (استخدام st.data_editor مع engine.begin() لضمان المزامنة الصحيحة مع Supabase)
