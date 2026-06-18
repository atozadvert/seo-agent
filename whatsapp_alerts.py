import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

def send_whatsapp_alert(message: str):
    """Send WhatsApp alert for critical SEO or Uptime events."""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token  = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
    to_number   = os.getenv("MY_WHATSAPP_NUMBER")
    
    if not all([account_sid, auth_token, to_number]):
        print("⚠️ WhatsApp configuration missing in .env")
        return False
    
    try:
        client = Client(account_sid, auth_token)
        client.messages.create(body=message, from_=from_number, to=to_number)
        return True
    except Exception as e:
        print(f"❌ WhatsApp alert failed: {e}")
        return False