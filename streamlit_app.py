import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
import plotly.express as px

# 1. إعداد الواجهة
st.set_page_config(layout="wide", page_title="Billboard Management System")

# 2. مراكز المحافظات للتحكم بانتقال الخريطة
city_centers = {
    'دمشق': [33.5138, 36.2765], 
    'حمص': [34.7324, 36.7137],
    'اللاذقية': [35.5312, 35.7921], 
    'طرطوس': [34.8890, 35.8866], 
    'جبلة': [35.3609, 35.9256]
}

# 3. أضف قاموس إحداثيات المناطق الخاص بك هنا
geo_map = {
# دمشق
    'طريق يعفور ذهاب': [33.5100, 36.1200],
    'من ساحة الامويين حتى السفارة الاماراتية': [33.5135, 36.2765],
    'كورنيش الميدان': [33.4912, 36.2970],
    'من المحافظة حتى فكتوريا': [33.5120, 36.2930],
    'مدخل باب توما حديقة الصوفانية': [33.5150, 36.3130],
    'شام سنتر من دوار الجوزة الى دوار الكارلتون': [33.4860, 36.2550],
    'الزاهرة الجديدة مقابل بوظة امية': [33.4835, 36.3015],
    'طريق يعفور إياب': [33.5105, 36.1210],
    'مشروع دمر مقابل الاب تاون': [33.5414, 36.2425],
    'شارع المجتهد إياب': [33.4980, 36.2870],
    'شام سنتر من دوار الكارلتون الى دوار الجوزة': [33.4855, 36.2545],
    # حمص
    'طريق الشام ذهاب': [34.7042, 36.7095], 'شارع الميدان إياب': [34.7265, 36.7120],
    'شارع الدروبي': [34.7305, 36.7135], 'شارع الحمراء': [34.7220, 36.7050],
    'شارع الحضارة': [34.7150, 36.7110], 'دوار الجامعة': [34.7125, 36.7075],
    'مفرق الحواش طريق طرطوس الرئيسي': [34.7770, 36.3150],
    # اللاذقية
    'ساحة عدن –كراجات البولمان': [35.5250, 35.8050], 'حديقة المنشية -8اذار': [35.5190, 35.7870],
    'المحكمة –الشيخ ضاهر': [35.5215, 35.7830], 'استراد الثورة فرن عكاشة1': [35.5350, 35.7950],
    'طريق الشاطئ الأزرق مفرق المدينة الرياضية1': [35.5810, 35.7480],
    # طرطوس
    'شارع المحكمة ذهاب': [34.8950, 35.8820], 'الكورنيش الشرقي ذهاب و إياب': [34.8900, 35.8950],
    'مدخل طرطوس مشفى الوطني 1': [34.8720, 35.8890], 'ساحة المصرف العقاري1': [34.8925, 35.8845],
    # جبلة
    'كورنيش جبلة بوظة رومينزا 1': [35.3620, 35.9180], 'جبلة مفرق المشفى 1': [35.3580, 35.9320],
}

# 4. دالة معالجة البيانات من الإكسل
@st.cache_data
def load_data():
    try:
        df = pd.read_excel('ads_data.xls', engine='xlrd')
        # البحث عن رأس الجدول
        for i in range(min(15, len(df))):
            if 'الموقع' in df.iloc[i].values:
                df.columns = df.iloc[i]; df = df.iloc[i+1:].reset_index(drop=True); break
        
        df.columns = [str(c).strip() for c in df.columns]
        # تعبئة الخلايا المدمجة
        for col in ['نوع اللوحات', 'محافظة', 'الموقع']:
            if col in df.columns: df[col] = df[col].ffill()
        
        # ربط المواقع بالإحداثيات
        def get_coords(loc):
            return geo_map.get(str(loc).strip(), [33.5138, 36.2765])
            
        df['coords'] = df['الموقع'].apply(get_coords)
        df['lat'] = df['coords'].apply(lambda x: x[0])
        df['lon'] = df['coords'].apply(lambda x: x[1])
        return df
    except Exception as e:
        st.error(f"Error loading Excel: {e}")
        return pd.DataFrame()

df = load_data()

if not df.empty:
    # --- Sidebar ---
    selected_city = st.sidebar.selectbox("اختر المحافظة:", df['محافظة'].unique())
    date_cols = [c for c in df.columns if any(m in str(c) for m in ['اذار', 'نيسان', 'ايار', 'حزيران'])]
    selected_period = st.sidebar.selectbox("اختر الفترة:", date_cols)

    # معالجة بيانات المحافظة المختارة
    city_df = df[df['محافظة'] == selected_city].copy()
    city_df['الحالة'] = city_df[selected_period].apply(lambda x: 'متاح' if pd.isna(x) else 'محجوز')
    city_df['is_vacant'] = city_df[selected_period].isna()

    st.title(f"📊 إدارة لوحات {selected_city}")

    # --- بناء الخريطة ---
    center = city_centers.get(selected_city, [33.5138, 36.2765])
    m = folium.Map(location=center, zoom_start=13, tiles="CartoDB positron")

    # إضافة النقاط
    for _, row in city_df.iterrows():
        popup = f"الموقع: {row['الموقع']} | العدد: {row['العدد']}"
        if row['is_vacant']:
            # وميض أخضر
            icon = '<div style="background:#00ff00;width:12px;height:12px;border-radius:50%;animation:blink 1s infinite;border:2px solid white;"></div><style>@keyframes blink{50%{opacity:0.2;}}</style>'
            folium.Marker([row['lat'], row['lon']], icon=folium.DivIcon(html=icon), popup=popup).add_to(m)
        else:
            # نقطة حمراء مع عدد
            folium.CircleMarker([row['lat'], row['lon']], radius=8, color='red', fill=True, popup=popup).add_to(m)
            label = f'<div style="background:rgba(255,255,255,0.8);border:1px solid red;padding:1px 4px;font-size:9pt;font-weight:bold;transform:translate(10px,-10px);">{row["العدد"]}</div>'
            folium.Marker([row['lat'], row['lon']], icon=folium.DivIcon(html=label)).add_to(m)

    # --- عرض الخريطة والإحصائيات ---
    c1, c2 = st.columns([3, 1])
    with c1:
        # السر في تحديث الخريطة هو الـ key الذي يتغير بتغير المدينة
        st_folium(m, center=center, width='stretch', height=550, key=f"map_{selected_city}")

    with c2:
        st.metric("المواقع المتاحة", (city_df['الحالة'] == 'متاح').sum())
        fig = px.pie(city_df, names='الحالة', color='الحالة', color_discrete_map={'متاح':'green', 'محجوز':'red'}, hole=.4)
        st.plotly_chart(fig, use_container_width=True)

    st.dataframe(city_df[['نوع اللوحات', 'الموقع', 'العدد', 'الحالة']], width='stretch')



