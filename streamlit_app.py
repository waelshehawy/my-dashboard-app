import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
import plotly.express as px

# 1. إعداد الواجهة
st.set_page_config(layout="wide", page_title="Billboard Management System")

# 2. مراكز المحافظات
city_centers = {
    '1': [33.5138, 36.2765],  # كود دمشق
    '2': [34.7324, 36.7137],  # كود حمص
    '3': [35.5312, 35.7921],  # كود اللاذقية
    '4': [34.8890, 35.8866],  # كود طرطوس
    '5': [35.3609, 35.9256]   # كود جبلة
}

# 3. إحداثيات المناطق
geo_map = {
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
    'طريق الشام ذهاب': [34.7042, 36.7095], 'شارع الميدان إياب': [34.7265, 36.7120],
    'شارع الدروبي': [34.7305, 36.7135], 'شارع الحمراء': [34.7220, 36.7050],
    'شارع الحضارة': [34.7150, 36.7110], 'دوار الجامعة': [34.7125, 36.7075],
    'مفرق الحواش طريق طرطوس الرئيسي': [34.7770, 36.3150],
    'ساحة عدن –كراجات البولمان': [35.5250, 35.8050], 'حديقة المنشية -8اذار': [35.5190, 35.7870],
    'المحكمة –الشيخ ضاهر': [35.5215, 35.7830], 'استراد الثورة فرن عكاشة1': [35.5350, 35.7950],
    'طريق الشاطئ الأزرق مفرق المدينة الرياضية1': [35.5810, 35.7480],
    'شارع المحكمة ذهاب': [34.8950, 35.8820], 'الكورنيش الشرقي ذهاب و إياب': [34.8900, 35.8950],
    'مدخل طرطوس مشفى الوطني 1': [34.8720, 35.8890], 'ساحة المصرف العقاري1': [34.8925, 35.8845],
    'كورنيش جبلة بوظة رومينزا 1': [35.3620, 35.9180], 'جبلة مفرق المشفى 1': [35.3580, 35.9320],
}

# 4. دالة معالجة البيانات السحابية
@st.cache_data(ttl=600)
def load_data():
    try:
        # الرابط المباشر لجوجل شيت بصيغة CSV
        url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTcXGzXOdLPritndflQQETl-Bdxn59S85YtaqnvXzs64ZDHo4wgYUiWPICiC2DPtZ9a3ID1EpH8psMT/pub?output=csv"
        
        # قراءة البيانات وتجاوز الأسطر المشوهة
        df = pd.read_csv(url, on_bad_lines='skip')
        
        # البحث عن رأس الجدول
        found_header = False
        for i in range(min(20, len(df))):
            if 'الموقع' in df.iloc[i].values:
                df.columns = df.iloc[i]
                df = df.iloc[i+1:].reset_index(drop=True)
                found_header = True
                break
        
        # تنظيف الأسماء وتعبئة الخلايا المدمجة
        df.columns = [str(c).strip() for c in df.columns]
               # أضف "كود المحافظة" لعملية التعبئة التلقائية
        for col in ['نوع اللوحات', 'كود المحافظة', 'الموقع']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip().replace(['nan', 'None', ''], pd.NA).ffill()

        
        # ربط المواقع بالإحداثيات
        def get_coords(loc):
            coords = geo_map.get(str(loc).strip(), [33.5138, 36.2765])
            return coords
            
        df['coords'] = df['الموقع'].apply(get_coords)
        df['lat'] = df['coords'].apply(lambda x: x[0])
        df['lon'] = df['coords'].apply(lambda x: x[1])
        return df
    except Exception as e:
        st.error(f"خطأ في تحميل البيانات: {e}")
        return pd.DataFrame()

df = load_data()

# 5. عرض الواجهة (نفس كودك الأصلي)

if not df.empty:
    # 1. القائمة الجانبية للاختيار بالكود
    unique_codes = df['كود المحافظة'].unique()
    selected_code = st.sidebar.selectbox("اختر كود المحافظة:", unique_codes)

    # 2. الفلترة باستخدام الكود المختار
    city_df = df[df['كود المحافظة'] == selected_code].copy()

    # 3. اختيار الفترة الزمنية
    date_cols = [c for c in df.columns if any(m in str(c) for m in ['اذار', 'نيسان', 'ايار', 'حزيران', 'تموز'])]
    selected_period = st.sidebar.selectbox("اختر الفترة:", date_cols)

    # 4. تحديد الحالة بناءً على الفترة المختارة
    city_df['الحالة'] = city_df[selected_period].apply(lambda x: 'متاح' if pd.isna(x) or str(x).strip() == "" or str(x).lower() == 'nan' else 'محجوز')
    city_df['is_vacant'] = city_df['الحالة'] == 'متاح'

    # 5. الحصول على اسم المحافظة لعرضه في العنوان (أول اسم موجود في الفلتر)
    city_name = city_df['محافظة'].iloc[0] if 'محافظة' in city_df.columns else selected_code
    st.title(f"📊 إدارة لوحات {city_name}")

    # 6. بناء الخريطة باستخدام إحداثيات الكود
    center = city_centers.get(selected_code, [33.5138, 36.2765])
    m = folium.Map(location=center, zoom_start=13, tiles="CartoDB positron")


    for _, row in city_df.iterrows():
        popup = f"الموقع: {row['الموقع']} | العدد: {row.get('العدد', '1')}"
        if row['is_vacant']:
            icon = '<div style="background:#00ff00;width:12px;height:12px;border-radius:50%;animation:blink 1s infinite;border:2px solid white;"></div><style>@keyframes blink{50%{opacity:0.2;}}</style>'
            folium.Marker([row['lat'], row['lon']], icon=folium.DivIcon(html=icon), popup=popup).add_to(m)
        else:
            folium.CircleMarker([row['lat'], row['lon']], radius=8, color='red', fill=True, popup=popup).add_to(m)
            label = f'<div style="background:rgba(255,255,255,0.8);border:1px solid red;padding:1px 4px;font-size:9pt;font-weight:bold;transform:translate(10px,-10px);">{row.get("العدد", "1")}</div>'
            folium.Marker([row['lat'], row['lon']], icon=folium.DivIcon(html=label)).add_to(m)

    c1, c2 = st.columns([3, 1])
    with c1:
        st_folium(m, center=center, width='stretch', height=550, key=f"map_{selected_code}")

    with c2:
        st.metric("المواقع المتاحة", (city_df['الحالة'] == 'متاح').sum())
        fig = px.pie(city_df, names='الحالة', color='الحالة', color_discrete_map={'متاح':'green', 'محجوز':'red'}, hole=.4)
        st.plotly_chart(fig, use_container_width=True)

    st.dataframe(city_df[['نوع اللوحات', 'الموقع', 'الحالة']], use_container_width=True)
