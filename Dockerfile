# Playwright ကို အထောက်အပံ့ပေးသည့် Official Python Image ကို အသုံးပြုပါမည် (Ubuntu Jammy အခြေခံ)
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# လုပ်ငန်းဆောင်ရွက်မည့် Directory ကို သတ်မှတ်ခြင်း
WORKDIR /app

# Requirements ဖိုင်ကို အရင် copy ကူးပြီး install လုပ်ခြင်း (Cache ကို ပိုမိုကောင်းမွန်စွာ အသုံးချရန်)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright အတွက် Chromium browser ကို install လုပ်ခြင်း
RUN playwright install chromium

# Code ဖိုင်အားလုံးကို Docker Container ထဲသို့ Copy ကူးခြင်း
COPY . .

# Bot ကို စတင် Run ရန် Command
CMD ["python", "app.py"]
