import asyncio
import time
import os
import logging
from collections import Counter
from datetime import datetime
from dotenv import load_dotenv

import aiohttp
import motor.motor_asyncio 
from pymongo.errors import ConnectionFailure

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# --- 🧠 ADVANCED DATA SCIENCE & ML LIBRARIES ---
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
import warnings
warnings.filterwarnings("ignore")

# ==========================================
# ⚙️ MODULE 1: CONFIGURATION & LOGGING
# ==========================================
load_dotenv()

# Logging စနစ်ကို ဖွင့်ခြင်း (Print အစား အဆင့်မြင့်စနစ်)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("UltimateAIBot")

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    CHANNEL_ID = os.getenv("CHANNEL_ID")
    MONGO_URI = os.getenv("MONGO_URI")
    
    WIN_STICKER = ""  # ဥပမာ: "CAACAgUAAxkBAAE..."
    LOSE_STICKER = "" 
    
    # Custom Multiplier Strategy
    MULTIPLIERS = [1, 2, 3, 5, 8, 15, 30, 50]
    
    # API Headers
    API_URL = 'https://6lotteryapi.com/api/webapi/GetNoaverageEmerdList'
    HEADERS = {
        'authority': '6lotteryapi.com', 'accept': 'application/json, text/plain, */*',
        'content-type': 'application/json;charset=UTF-8', 'origin': 'https://www.6win566.com',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

# ==========================================
# 🗄️ MODULE 2: DATABASE MANAGER
# ==========================================
class DatabaseManager:
    """ MongoDB သို့ ချိတ်ဆက်ခြင်းနှင့် မှတ်တမ်းများကို စီမံခန့်ခွဲခြင်း """
    def __init__(self, uri: str):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
        self.db = self.client['sixlottery_ultimate']
        self.history = self.db['game_history']
        self.predictions = self.db['predictions']

    async def initialize(self):
        try:
            await self.history.create_index("issue_number", unique=True)
            await self.predictions.create_index("issue_number", unique=True)
            logger.info("✅ Database Initialized Successfully.")
        except Exception as e:
            logger.error(f"❌ Database Error: {e}")

    async def save_history(self, issue: str, number: int, size: str, parity: str):
        await self.history.update_one(
            {"issue_number": issue}, 
            {"$setOnInsert": {"number": number, "size": size, "parity": parity, "timestamp": datetime.now()}}, 
            upsert=True
        )

    async def save_prediction(self, issue: str, pred_size: str, confidence: float):
        await self.predictions.update_one(
            {"issue_number": issue},
            {"$set": {"predicted_size": pred_size, "confidence": confidence, "timestamp": datetime.now()}},
            upsert=True
        )

    async def update_result(self, issue: str, actual_size: str, actual_number: int, win_lose: str):
        await self.predictions.update_one(
            {"issue_number": issue},
            {"$set": {"actual_size": actual_size, "actual_number": actual_number, "win_lose": win_lose}}
        )

    async def get_history(self, limit: int = 500) -> list:
        return await self.history.find().sort("issue_number", -1).limit(limit).to_list(length=limit)

    async def get_recent_predictions(self, limit: int = 10) -> list:
        return await self.predictions.find({"win_lose": {"$ne": None}}).sort("issue_number", -1).limit(limit).to_list(length=limit)

# ==========================================
# 🧠 MODULE 3: AI SUB-MODELS
# ==========================================
class PatternRecognizer:
    """ သမိုင်းကြောင်းမှ Pattern များကို ရှာဖွေစစ်ဆေးသော အပိုင်း """
    @staticmethod
    def get_streak(sizes_list: list) -> int:
        if not sizes_list: return 0
        count = 1
        for i in range(len(sizes_list)-2, -1, -1):
            if sizes_list[i] == sizes_list[-1]: count += 1
            else: break
        return count

    @staticmethod
    def analyze_ngrams(sizes: list, n: int = 3) -> tuple:
        if len(sizes) < n + 1: return 0.5, 0.5
        current_pattern = tuple(sizes[-n:])
        matches = {'BIG': 0, 'SMALL': 0}
        
        for i in range(len(sizes) - n):
            if tuple(sizes[i:i+n]) == current_pattern:
                next_size = sizes[i+n]
                matches[next_size] += 1
                
        total = sum(matches.values())
        if total == 0: return 0.5, 0.5
        return matches['BIG'] / total, matches['SMALL'] / total

class MarkovChainModel:
    """ ပြီးခဲ့သော ဂဏန်းအရ နောက်ထွက်မည့် ဂဏန်း၏ ရာခိုင်နှုန်းကို တွက်ချက်ခြင်း """
    @staticmethod
    def calculate_transitions(sizes: list) -> tuple:
        if len(sizes) < 2: return 0.5, 0.5
        transitions = {'BIG': {'BIG': 0, 'SMALL': 0}, 'SMALL': {'BIG': 0, 'SMALL': 0}}
        for i in range(len(sizes)-1): 
            transitions[sizes[i]][sizes[i+1]] += 1
            
        curr = sizes[-1]
        tot = transitions[curr]['BIG'] + transitions[curr]['SMALL']
        if tot == 0: return 0.5, 0.5
        return transitions[curr]['BIG'] / tot, transitions[curr]['SMALL'] / tot

class MLPredictor:
    """ Random Forest နှင့် Gradient Boosting ကို ပေါင်းစပ်ထားသော Machine Learning အပိုင်း """
    def __init__(self):
        self.rf = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42, n_jobs=-1)
        self.gb = GradientBoostingClassifier(n_estimators=100, learning_rate=0.05, max_depth=3, random_state=42)
        self.window = 5

    def predict(self, sizes: list, numbers: list, parities: list) -> tuple:
        if len(sizes) < self.window * 4: return 0.5, 0.5
        
        X, y = [], []
        for i in range(len(sizes) - self.window):
            row = []
            for j in range(self.window): 
                val = 1 if sizes[i+j] == 'BIG' else 0
                row.extend([val, numbers[i+j], parities[i+j]])
            X.append(row)
            y.append(1 if sizes[i+self.window] == 'BIG' else 0)
            
        try:
            self.rf.fit(X, y)
            self.gb.fit(X, y)
            
            curr_feats = []
            for j in range(1, self.window + 1): 
                val = 1 if sizes[-j] == 'BIG' else 0
                curr_feats.extend([val, numbers[-j], parities[-j]])
                
            rf_probs = self.rf.predict_proba([curr_feats])[0]
            gb_probs = self.gb.predict_proba([curr_feats])[0]
            
            rf_b = rf_probs[list(self.rf.classes_).index(1)] if 1 in self.rf.classes_ else 0.0
            gb_b = gb_probs[list(self.gb.classes_).index(1)] if 1 in self.gb.classes_ else 0.0
            
            return rf_b, gb_b
        except Exception as e:
            logger.warning(f"ML Prediction Error: {e}")
            return 0.5, 0.5

# ==========================================
# ⚙️ MODULE 4: ACCURACY OPTIMIZER & MASTER AI
# ==========================================
class MetaOptimizer:
    """ အခြေအနေပေါ်မူတည်၍ Algorithm များ၏ အလေးချိန် (Weights) ကို အလိုအလျောက် ပြင်ဆင်ခြင်း """
    def __init__(self):
        self.weights = {'rf': 0.30, 'gb': 0.25, 'markov': 0.20, 'pattern': 0.25}

    def learn_from_result(self, actual: str, past_preds: dict):
        total_w = 0.0
        for model, pred in past_preds.items():
            if pred == actual:
                self.weights[model] += 0.05
            else:
                self.weights[model] = max(0.05, self.weights[model] - 0.03)
            total_w += self.weights[model]
            
        for k in self.weights:
            self.weights[k] /= total_w

class UltimateAIEngine:
    """ AI Core အားလုံးကို ထိန်းချုပ်မောင်းနှင်သော အဓိက အင်ဂျင်ကြီး """
    def __init__(self):
        self.optimizer = MetaOptimizer()
        self.ml_core = MLPredictor()
        self.last_predictions = {} 

    def analyze_and_predict(self, docs: list, recent_preds: list) -> tuple:
        if len(docs) < 30: return "BIG", 55.0
        
        sizes = [d.get('size', 'BIG') for d in reversed(docs)]
        numbers = [int(d.get('number', 0)) for d in reversed(docs)]
        parities = [1 if d.get('parity', 'EVEN') == 'EVEN' else 0 for d in reversed(docs)]
        
        # 1. Pattern & Markov
        pat_b, pat_s = PatternRecognizer.analyze_ngrams(sizes, n=3)
        mar_b, mar_s = MarkovChainModel.calculate_transitions(sizes)
        
        self.last_predictions['pattern'] = 'BIG' if pat_b > pat_s else 'SMALL'
        self.last_predictions['markov'] = 'BIG' if mar_b > mar_s else 'SMALL'
        
        # 2. Machine Learning
        rf_b, gb_b = self.ml_core.predict(sizes, numbers, parities)
        self.last_predictions['rf'] = 'BIG' if rf_b > 0.5 else 'SMALL'
        self.last_predictions['gb'] = 'BIG' if gb_b > 0.5 else 'SMALL'
        
        # 3. Ensemble Voting with Weights
        w = self.optimizer.weights
        score_b = (rf_b * w['rf']) + (gb_b * w['gb']) + (mar_b * w['markov']) + (pat_b * w['pattern'])
        score_s = ((1-rf_b) * w['rf']) + ((1-gb_b) * w['gb']) + (mar_s * w['markov']) + (pat_s * w['pattern'])
        
        # 4. Smart Streak Override (အတန်းရှည်နေပါက ချိုးမည့်အစား ဆက်လိုက်မည်)
        current_streak = PatternRecognizer.get_streak(sizes)
        if current_streak >= 4:
            if sizes[-1] == 'BIG': score_b += 0.35
            else: score_s += 0.35
            
        # 5. Calculate Final Result
        final_pred = "BIG" if score_b > score_s else "SMALL"
        raw_conf = (max(score_b, score_s) / (score_b + score_s)) * 100
        confidence = min(max(raw_conf, 51.0), 99.0)
        
        return final_pred, round(confidence, 1)

# ==========================================
# 💰 MODULE 5: BETTING & UI MANAGER
# ==========================================
class BettingStrategy:
    @staticmethod
    def get_multiplier(lose_streak: int) -> int:
        if lose_streak >= len(Config.MULTIPLIERS):
            return Config.MULTIPLIERS[0]
        return Config.MULTIPLIERS[lose_streak]

class TelegramUI:
    """ Telegram သို့ မက်ဆေ့ချ်များ ပို့ခြင်းကို သီးသန့် စီမံခြင်း """
    def __init__(self, bot: Bot):
        self.bot = bot

    async def send_prediction(self, issue: str, pred: str, step: int, conf: float, top_model: str):
        msg = (
            f"<b>[ULTIMATE AI PRO V5]</b>\n"
            f"⏰ Period: {issue}\n"
            f"🎯 Prediction: {pred} {step}x\n"
            f"📊 Confidence: {conf}%\n"
            f"🧠 Top Core: {top_model.upper()}"
        )
        try: await self.bot.send_message(chat_id=Config.CHANNEL_ID, text=msg)
        except Exception as e: logger.error(f"TG Send Error: {e}")

    async def send_result(self, issue: str, pred: str, step: int, is_win: bool, actual_size: str, actual_num: int):
        win_str = "WIN" if is_win else "LOSE"
        icon = "🟢" if is_win else "🔴"
        res_letter = "B" if actual_size == "BIG" else "S"
        
        msg = (
            f"<b>☘️ 𝐒𝐈𝐗-𝐋𝐎𝐓𝐓𝐄𝐑𝐘 ☘️</b>\n\n"
            f"⏰ Period: {issue}\n"
            f"🎯 Choice: {pred} {step}x\n"
            f"📊 Result: {icon} {win_str} | {res_letter} ({actual_num})"
        )
        
        try: 
            await self.bot.send_message(chat_id=Config.CHANNEL_ID, text=msg)
            
            # Send Sticker
            if is_win and Config.WIN_STICKER:
                await self.bot.send_sticker(chat_id=Config.CHANNEL_ID, sticker=Config.WIN_STICKER)
            elif not is_win and Config.LOSE_STICKER:
                await self.bot.send_sticker(chat_id=Config.CHANNEL_ID, sticker=Config.LOSE_STICKER)
        except Exception as e: logger.error(f"TG Result Error: {e}")

# ==========================================
# 🚀 MODULE 6: MAIN CONTROLLER LOOP
# ==========================================
class GameController:
    """ API မှ Data ယူခြင်းနှင့် AI, DB, UI တို့ကို ချိတ်ဆက်မောင်းနှင်သော အဓိက အပိုင်း """
    def __init__(self):
        self.db = DatabaseManager(Config.MONGO_URI)
        self.ai = UltimateAIEngine()
        self.ui = TelegramUI(bot)
        self.last_issue = None
        self.lose_streak = 0
        self.current_step = 1

    async def fetch_lottery_data(self, session: aiohttp.ClientSession) -> dict:
        json_data = {'pageSize': 1, 'pageNo': 1, 'typeId': 1, 'language': 7, 'random': '1234', 'signature': 'ABCD', 'timestamp': int(time.time())}
        for _ in range(3):
            try:
                async with session.post(Config.API_URL, headers=Config.HEADERS, json=json_data, timeout=3.0) as r:
                    if r.status == 200: return await r.json()
            except: await asyncio.sleep(0.5)
        return None

    async def run(self):
        await self.db.initialize()
        
        async with aiohttp.ClientSession() as session:
            logger.info("🔥 Main Game Loop Started...")
            while True:
                try:
                    data = await self.fetch_lottery_data(session)
                    if not data or data.get('code') != 0:
                        await asyncio.sleep(1.0); continue
                        
                    records = data.get("data", {}).get("list", [])
                    if not records: continue
                    
                    latest = records[0]
                    issue, number = str(latest["issueNumber"]), int(latest["number"])
                    size = "BIG" if number >= 5 else "SMALL"
                    parity = "EVEN" if number % 2 == 0 else "ODD"
                    
                    # 1. အစပြုချိန် (Initial Start)
                    if not self.last_issue:
                        self.last_issue = issue
                        recent_preds = await self.db.get_recent_predictions(10)
                        
                        # Streak ကို DB မှ ပြန်ယူခြင်း
                        self.lose_streak = 0
                        for p in recent_preds:
                            if p.get("win_lose") == "LOSE": self.lose_streak += 1
                            else: break
                        if self.lose_streak >= len(Config.MULTIPLIERS): self.lose_streak = 0

                        next_issue = str(int(issue) + 1)
                        docs = await self.db.get_history(500)
                        pred, conf = self.ai.analyze_and_predict(docs, recent_preds)
                        
                        top_model = max(self.ai.optimizer.weights, key=self.ai.optimizer.weights.get)
                        self.current_step = self.lose_streak + 1
                        
                        await self.ui.send_prediction(next_issue, pred, self.current_step, conf, top_model)
                        await asyncio.sleep(1.0); continue

                    # 2. ပွဲစဉ်အသစ် တွေ့ရှိသောအခါ (New Issue Detected)
                    if int(issue) > int(self.last_issue):
                        # Save History
                        await self.db.save_history(issue, number, size, parity)
                        
                        # Self-Learning Update
                        self.ai.optimizer.learn_from_result(size, self.ai.last_predictions)
                        
                        # Check Previous Prediction
                        recent_preds = await self.db.get_recent_predictions(1)
                        if recent_preds and recent_preds[0]['issue_number'] == issue:
                            pred_doc = recent_preds[0]
                            predicted_size = pred_doc['predicted_size']
                            is_win = (predicted_size == size)
                            win_lose_db = "WIN" if is_win else "LOSE"
                            
                            # Update DB Result
                            await self.db.update_result(issue, size, number, win_lose_db)
                            
                            # UI အား Result ပို့ခိုင်းခြင်း
                            await self.ui.send_result(issue, predicted_size, self.current_step, is_win, size, number)
                            
                            # Streak ပြင်ဆင်ခြင်း
                            if is_win: self.lose_streak = 0
                            else: 
                                self.lose_streak += 1
                                if self.lose_streak >= len(Config.MULTIPLIERS): self.lose_streak = 0

                        self.last_issue = issue
                        
                        # 🎯 3. နောက်ပွဲစဉ်အတွက် ချက်ချင်း ခန့်မှန်းခြင်း
                        next_issue = str(int(issue) + 1)
                        docs = await self.db.get_history(500)
                        recent_preds = await self.db.get_recent_predictions(10)
                        
                        pred, conf = self.ai.analyze_and_predict(docs, recent_preds)
                        await self.db.save_prediction(next_issue, pred, conf)
                        
                        top_model = max(self.ai.optimizer.weights, key=self.ai.optimizer.weights.get)
                        self.current_step = self.lose_streak + 1
                        
                        await self.ui.send_prediction(next_issue, pred, self.current_step, conf, top_model)

                except Exception as e:
                    logger.error(f"Loop Exception: {e}")
                await asyncio.sleep(1.5)

# ==========================================
# 🚀 ENTRY POINT
# ==========================================
async def main():
    logger.info("Initializing Ultimate System Components...")
    await bot.delete_webhook(drop_pending_updates=True)
    
    controller = GameController()
    asyncio.create_task(controller.run())
    
    logger.info("Bot Polling Started...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try: asyncio.run(main())
    except KeyboardInterrupt: logger.info("Bot Stopped by User.")
