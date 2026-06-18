# utils/helpers.py
import pandas as pd

def safe_split(value):
    """تقسيم آمن للنصوص"""
    if value is None or pd.isna(value):
        return []
    if isinstance(value, float):
        return []
    value_str = str(value)
    if value_str in ['', 'nan', 'None', 'NaN']:
        return []
    return [v.strip() for v in value_str.split(',') if v.strip()]

def badge_animated(text, badge_type="info"):
    """إنشاء شارة متحركة"""
    colors = {
        "info": "linear-gradient(135deg, #667eea, #764ba2)",
        "success": "linear-gradient(135deg, #11998e, #38ef7d)",
        "warning": "linear-gradient(135deg, #fa709a, #fee140)",
        "danger": "linear-gradient(135deg, #f093fb, #f5576c)"
    }
    color = colors.get(badge_type, colors["info"])
    return f'<span style="display:inline-block;padding:4px 12px;border-radius:20px;background:{color};color:white;font-size:12px;font-weight:bold;margin:2px;">{text}</span>'

def create_metric_card_3d(title, value, icon, color_gradient="primary"):
    """بطاقة إحصائية ثلاثية الأبعاد"""
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
