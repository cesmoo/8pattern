# Python 3.11 image ကိုသုံးတယ် (ပိုမြန်ပြီး stable)
FROM python:3.11-slim

# Working directory သတ်မှတ်တယ်
WORKDIR /app

# System dependencies တွေထည့်တယ် (matplotlib, numpy အတွက်)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libfreetype6-dev \
    libpng-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# requirements.txt ကို အရင်ကူးတယ် (caching ကောင်းအောင်)
COPY requirements.txt .

# Python packages တွေ install လုပ်တယ်
RUN pip install --no-cache-dir -r requirements.txt

# Source code အားလုံးကို ကူးတယ်
COPY . .

# Bot ကို run တယ်
CMD ["python", "bot.py"]
