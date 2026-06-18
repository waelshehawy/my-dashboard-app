# utils/helpers.py
import pandas as pd

# ============================================================
# دوال الفترات (من الكود الأساسي)
# ============================================================

MONTHS_AR = {
    1: "كانون ثاني", 2: "شباط", 3: "اذار", 4: "نيسان",
    5: "ايار", 6: "حزيران", 7: "تموز", 8: "اب",
    9: "ايلول", 10: "تشرين اول", 11: "تشرين ثاني", 12: "كانون اول"
}

def convert_date_to_period_name(date_obj):
    """تحويل التاريخ إلى اسم الفترة (مثل 'حزيران 30-15')"""
    month_name = MONTHS_AR[date_obj.month]
    if date_obj.day <= 15:
        return f"{month_name} 15-1"
    else:
        return f"{month_name} 30-15"

PERIOD_ORDER = {
    'كانون الثاني 15-1': 1, 'كانون الثاني 31-16': 2,
    'شباط 15-1': 3, 'شباط 28-16': 4,
    'آذار 15-1': 5, 'آذار 31-16': 6,
    'نيسان 15-1': 7, 'نيسان 30-16': 8,
    'أيار 15-1': 9, 'أيار 31-16': 10,
    'حزيران 15-1': 11, 'حزيران 30-16': 12,
    'تموز 15-1': 13, 'تموز 31-16': 14,
    'آب 15-1': 15, 'آب 31-16': 16,
    'أيلول 15-1': 17, 'أيلول 30-16': 18,
    'تشرين الأول 15-1': 19, 'تشرين الأول 31-16': 20,
    'تشرين الثاني 15-1': 21, 'تشرين الثاني 30-16': 22,
    'كانون الأول 15-1': 23, 'كانون الأول 31-16': 24
}

def get_period_number(period_name):
    if period_name is None:
        return 99
    return PERIOD_ORDER.get(period_name, 99)

def get_period_from_date(date_obj):
    day = date_obj.day
    month = date_obj.month
    
    month_names = {
        1: 'كانون الثاني', 2: 'شباط', 3: 'آذار', 4: 'نيسان',
        5: 'أيار', 6: 'حزيران', 7: 'تموز', 8: 'آب',
        9: 'أيلول', 10: 'تشرين الأول', 11: 'تشرين الثاني', 12: 'كانون الأول'
    }
    
    month_name = month_names[month]
    
    if day <= 15:
        period_name = f"{month_name} 15-1"
    else:
        if month == 2:
            last_day = 28
        elif month in [4, 6, 9, 11]:
            last_day = 30
        else:
            last_day = 31
        period_name = f"{month_name} {last_day}-16"
    
    return PERIOD_ORDER.get(period_name, 99)

# ============================================================
# باقي الدوال المساعدة
# ============================================================

def safe_split(value):
    if value is None or pd.isna(value):
        return []
    if isinstance(value, float):
        return []
    value_str = str(value)
    if value_str in ['', 'nan', 'None', 'NaN']:
        return []
    return [v.strip() for v in value_str.split(',') if v.strip()]

def badge_animated(text, badge_type="info"):
    colors = {
        "info": "linear-gradient(135deg, #667eea, #764ba2)",
        "success": "linear-gradient(135deg, #11998e, #38ef7d)",
        "warning": "linear-gradient(135deg, #fa709a, #fee140)",
        "danger": "linear-gradient(135deg, #f093fb, #f5576c)"
    }
    color = colors.get(badge_type, colors["info"])
    return f'<span style="display:inline-block;padding:4px 12px;border-radius:20px;background:{color};color:white;font-size:12px;font-weight:bold;margin:2px;">{text}</span>'

def create_metric_card_3d(title, value, icon, color_gradient="primary"):
    gradients = {
        "primary": "linear-gradient(135deg, #667eea, #764ba2)",
        "success": "linear-gradient(135deg, #11998e, #38ef7d)",
        "danger": "linear-gradient(135deg, #f093fb, #f5576c)",
        "warning": "linear-gradient(135deg, #fa709a, #fee140)"
    }
    
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            formatted_value = f"{value:,}"
        else:
            formatted_value = str(value)
    except:
        formatted_value = str(value)
    
    return f"""
    <div style="background:{gradients.get(color_gradient, gradients['primary'])};border-radius:16px;padding:16px;text-align:center;color:white;box-shadow:0 4px 12px rgba(0,0,0,0.15);">
        <div style="font-size:32px;opacity:0.9;">{icon}</div>
        <div style="font-size:28px;font-weight:bold;">{formatted_value}</div>
        <div style="font-size:14px;opacity:0.9;">{title}</div>
    </div>
    """
