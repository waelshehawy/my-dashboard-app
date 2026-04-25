import streamlit as st
import sqlite3
import pandas as pd
# مكتبات الـ PDF كما ذكرنا سابقاً
from fpdf import FPDF 

st.set_page_config(page_title="Preview Quotation Generator", layout="wide")

# --- دالة جلب البيانات ---
def get_data(province, network_id):
    conn = sqlite3.connect('billboards_data.db')
    # استعلام لجلب اللوحات حسب المحافظة والشبكة (تأكد من مسميات الأعمدة في جدولك)
    query = f"SELECT [اسم العمود] AS الموقع, [العدد] FROM [اعمدة انارة] WHERE [المحافظة] = ? AND [الشبكة] = ?"
    df = pd.read_sql(query, conn, params=(province, network_id))
    conn.close()
    return df

st.title("📄 مصمم عروض أسعار بريفيو")

# --- خطوة 1: الاختيارات ---
col1, col2 = st.columns(2)
with col1:
    provinces = ["دمشق", "حلب", "حمص", "حماة", "اللاذقية", "طرطوس"] # أو اسحبها من جدول المحافظات
    selected_prov = st.selectbox("اختر المحافظة", provinces)
with col2:
    network = st.number_input("رقم الشبكة", min_value=1, value=4)

# --- خطوة 2: عرض وتعديل البيانات ---
st.subheader(f"مواقع الشبكة رقم {network} في {selected_prov}")
raw_data = get_data(selected_prov, network)

if not raw_data.empty:
    st.info("💡 يمكنك حذف أي سطر غير مرغوب فيه بالضغط عليه ثم زر Delete في لوحة المفاتيح، أو تعديل 'العدد'.")
    # محرر البيانات التفاعلي
    edited_df = st.data_editor(raw_data, num_rows="dynamic", use_container_width=True)
    
    # --- خطوة 3: التصدير ---
    customer_name = st.text_input("اسم الزبون المحترم", "شركة جود")
    
    if st.button("💾 توليد عرض السعر PDF مطابق للنموذج"):
        # هنا يتم استدعاء دالة FPDF التي صممناها سابقاً 
        # مع إضافة الترويسة البنفسجية وتنسيق الجداول المزدوجة
        st.success("تم تجهيز العرض بناءً على اختيارك للشبكة واللوحات المحددة.")
else:
    st.warning("لا توجد بيانات لهذه الشبكة في هذه المحافظة.")
