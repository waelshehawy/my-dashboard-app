# test_db.py
import psycopg2

def test_connection():
    try:
        conn = psycopg2.connect(
            host="aws-1-eu-north-1.pooler.supabase.com",
            port="6543",
            database="postgres",
            user="postgres.ncuofpvbaglwbdqnpman",
            password="W@elPreview2026",
            sslmode="require",
            connect_timeout=10
        )
        print("✅ الاتصال ناجح!")
        conn.close()
        return True
    except Exception as e:
        print(f"❌ فشل الاتصال: {e}")
        return False

if __name__ == "__main__":
    test_connection()
