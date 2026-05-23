import os
from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "your_sid_here")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "your_token_here")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

def send_whatsapp_msg(to_number, message_body):
    """
    Sends a WhatsApp message using Twilio.
    If credentials aren't set, it will just print to console.
    """
    try:
        # Check if credentials exist, otherwise just mock it
        if not TWILIO_ACCOUNT_SID or TWILIO_ACCOUNT_SID == "your_sid_here":
            print(f"\n--- MOCK WHATSAPP SENT ---")
            print(f"To: {to_number}")
            print(f"Message: {message_body}")
            print(f"--------------------------\n")
            return
            
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            body=message_body,
            to=f"whatsapp:{to_number}"
        )
        return message.sid
    except Exception as e:
        print(f"Failed to send WhatsApp: {e}")
