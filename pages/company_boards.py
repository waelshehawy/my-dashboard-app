# pages/company_boards.py
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from utils.database import run_query
from utils.helpers import badge_animated

def get_company_bookings():
    """استرجاع بيانات الشركات المحجوزة"""
    query = """
    SELECT 
        "اسم الزبون" as company_name,
        COUNT(DISTINCT "رقم اللوحة") as total_boards,
        COUNT(DISTINCT "فترة الحجز") as total_periods,
        MAX("العام") as last_year,
        MAX("فترة الحجز") as last_period
    FROM "حجوزات1"
    GROUP BY "اسم الزبون"
    ORDER BY "اسم الزبون"
    """
    df = run_query(query)
    
    if df.empty:
        return df
    
    df['end_date'] = df.apply(
        lambda x: f"{x['last_period']} / {x['last_year']}" if x['last_period'] else "غير محدد",
        axis=1
    )
    return df

def get_company_locations_with_map(company_name):
    """استرجاع مواقع شركة معينة مع الإحداثيات"""
    query = f"""
    SELECT DISTINCT 
        b."رقم اللوحة",
        b."اسم العمود",
        b."المحافظة",
        b."الشبكة",
        b."الحجم",
        b."العدد",
        b."Latitude",
        b."Longitude"
    FROM "اعمدة انارة" b
    INNER JOIN "حجوزات1" h ON CAST(b."رقم اللوحة" AS TEXT) = CAST(h."رقم اللوحة" AS TEXT)
    WHERE h."اسم الزبون" = '{company_name}'
    """
    return run_query(query)

def show():
    """عرض صفحة لوحات الشركات"""
    st.title("🏢 لوحات الشركات المعلنة")
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    
    companies = get_company_bookings()
    
    if companies is None or companies.empty:
        st.warning("⚠️ لا توجد شركات معلنة حالياً")
        return
    
    for idx, company in companies.iterrows():
        with st.container():
            st.markdown(f"""
            <div class="neumorphic-card" style="margin-bottom: 20px;">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                    <div><h2 style="margin: 0 0 10px 0;">🏢 {company['company_name']}</h2></div>
                    <div>
                        {badge_animated(f"📊 {company['total_boards']} لوحة", "info")}
                        {badge_animated(f"🗓️ {company['total_periods']} فترة", "success")}
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            col1, col2 = st.columns([3, 1])
            with col2:
                if st.button("🗺️ عرض الخريطة", key=f"map_{idx}", use_container_width=True):
                    st.session_state['selected_company'] = company['company_name']
                    st.session_state['show_company_map'] = True
            
            st.markdown("<hr>", unsafe_allow_html=True)
    
    # عرض الخريطة للشركة المختارة
    if st.session_state.get('show_company_map', False):
        st.subheader(f"🗺️ مواقع شركة {st.session_state['selected_company']}")
        
        locations = get_company_locations_with_map(st.session_state['selected_company'])
        
        if locations is not None and not locations.empty:
            locations['Latitude'] = pd.to_numeric(locations['Latitude'], errors='coerce')
            locations['Longitude'] = pd.to_numeric(locations['Longitude'], errors='coerce')
            
            has_coords = locations[
                (locations['Latitude'].notna()) & 
                (locations['Latitude'] != 0) &
                (locations['Longitude'].notna()) & 
                (locations['Longitude'] != 0)
            ].copy()
            
            if not has_coords.empty:
                m = folium.Map(location=[34.8, 38.9], zoom_start=7)
                
                for _, row in has_coords.iterrows():
                    folium.CircleMarker(
                        location=[row['Latitude'], row['Longitude']],
                        radius=8,
                        popup=f"""
                        <div dir="rtl" style="text-align:right; min-width:180px;">
                            <b>{row['اسم العمود']}</b><br>
                            📍 {row['المحافظة']}<br>
                            📏 {row['الحجم']}
                        </div>
                        """,
                        color='#22c55e',
                        fill=True,
                        fill_color='#22c55e',
                        fill_opacity=0.7,
                        weight=2
                    ).add_to(m)
                
                st_folium(m, width="100%", height=500)
            else:
                st.info("📍 لا توجد إحداثيات لعرضها على الخريطة")
        else:
            st.warning("⚠️ لا توجد مواقع لهذه الشركة")
        
        if st.button("🔙 إغلاق الخريطة"):
            st.session_state['show_company_map'] = False
            st.rerun()
