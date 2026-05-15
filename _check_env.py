import os
from dotenv import load_dotenv
load_dotenv(r'C:\Users\asus\Alpha-Omega-System\.env')
print('TOKEN:', os.getenv('TELEGRAM_TOKEN'))
print('CHAT:', os.getenv('TELEGRAM_PERSONAL_CHAT_ID'))
