import asyncio
import time
import os
import logging
from collections import Counter
from datetime import datetime
from dotenv import load_dotenv

import aiohttp
import motor.motor_asyncio 

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# --- 🧠 ENTERPRISE MACHINE LEARNING LIBRARIES ---
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import warnings
warnings.filterwarnings("ignore")

# ==========================================
# ⚙️ MODULE 1: CONFIGURATION & GLOBALS
# ==========================================
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ProPredictor")

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    CHANNEL_ID = os.getenv("CHANNEL_ID")
    MONGO_URI = os.getenv("MONGO_URI")
    
    WIN_STICKER = "CAACAgUAAxkBAAEQwtVpt1_oWxyaQFmiy3O_1knZjN9yCwAC2hIAAikFkVX0qhu40v6REDoE"  
    LOSE_STICKER = "" 
    
    MULTIPLIERS = [1, 2, 3, 5, 8, 15, 30, 50]
    
    API_URL = 'https://6lotteryapi.com/api/webapi/GetNoaverageEmerdList'
    HEADERS = {
        'authority': '6lotteryapi.com', 'accept': 'application/json, text/plain, */*',
        'content-type': 'application/json;charset=UTF-8', 'origin': 'https://www.6win566.com',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

bot = Bot(token=Config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ==========================================
# 🗄️ MODULE 2: DATABASE MANAGER
# ==========================================
class DatabaseManager:
    """ MongoDB စီမံခန့်ခွဲရေး """
    def __init__(self, uri: str):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
        self.db = self.client['sixlottery_professional']
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

    async def save_prediction(self, issue: str, pred_size: str, confidence: float, details: dict):
        await self.predictions.update_one(
            {"issue_number": issue},
            {"$set": {"predicted_size": pred_size, "confidence": confidence, "model_votes": details, "timestamp": datetime.now()}},
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
# 🔬 MODULE 3: FEATURE ENGINEERING
# ==========================================
class FeatureEngineer:
    """ Raw Data များကို Machine Learning နားလည်သော သင်္ချာကိန်းဂဏန်းများအဖြစ် ပြောင်းလဲပေးခြင်း """
    def __init__(self, window_size=5):
        self.window = window_size
        self.scaler = StandardScaler()

    def prepare_data(self, sizes: list, numbers: list, parities: list):
        if len(sizes) < self.window * 4:
            return None, None, None
            
        X, y = [], []
        for i in range(len(sizes) - self.window):
            row = []
            for j in range(self.window): 
                size_val = 1 if sizes[i+j] == 'BIG' else 0
                par_val = 1 if parities[i+j] == 'EVEN' else 0
                num_val = numbers[i+j]
                row.extend([size_val, par_val, num_val])
            X.append(row)
            y.append(1 if sizes[i+self.window] == 'BIG' else 0)
            
        # လက်ရှိခန့်မှန်းရမည့် အခြေအနေ (Current Features)
        curr_feats = []
        for j in range(1, self.window + 1): 
            size_val = 1 if sizes[-j] == 'BIG' else 0
            par_val = 1 if parities[-j] == 'EVEN' else 0
            num_val = numbers[-j]
            curr_feats.extend([size_val, par_val, num_val])
            
        X_scaled = self.scaler.fit_transform(X)
        curr_scaled = self.scaler.transform([curr_feats])
        
        return X_scaled, y, curr_scaled

# ==========================================
# 🧠 MODULE 4: THE 6-CORE PREDICTOR MODELS
# ==========================================
class PatternEngine:
    @staticmethod
    def predict(sizes: list, n: int = 3) -> float:
        """ N-Gram Sequence မှတဆင့် နောက်ထွက်မည့် ရာခိုင်နှုန်းကို ရှာဖွေခြင်း """
        if len(sizes) < n + 1: return 0.5
        current_pattern = tuple(sizes[-n:])
        matches = {'BIG': 0, 'SMALL': 0}
        for i in range(len(sizes) - n):
            if tuple(sizes[i:i+n]) == current_pattern:
                matches[sizes[i+n]] += 1
        total = sum(matches.values())
        if total == 0: return 0.5
        return matches['BIG'] / total

class MarkovChain:
    @staticmethod
    def predict(sizes: list) -> float:
        """ လက်ရှိ State မှ နောက် State သို့ ကူးပြောင်းမည့် ရာခိုင်နှုန်းကို သင်္ချာနည်းဖြင့် တွက်ခြင်း """
        if len(sizes) < 2: return 0.5
        transitions = {'BIG': {'BIG': 0, 'SMALL': 0}, 'SMALL': {'BIG': 0, 'SMALL': 0}}
        for i in range(len(sizes)-1): 
            transitions[sizes[i]][sizes[i+1]] += 1
        curr = sizes[-1]
        tot = transitions[curr]['BIG'] + transitions[curr]['SMALL']
        if tot == 0: return 0.5
        return transitions[curr]['BIG'] / tot

class MachineLearningCore:
    """ ML Model ၄ မျိုးစလုံးကို တစ်ပြိုင်နက်တည်း အလုပ်လုပ်စေမည့် Class """
    def __init__(self):
        self.rf = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42, n_jobs=-1)
        self.gb = GradientBoostingClassifier(n_estimators=100, learning_rate=0.05, max_depth=3, random_state=42)
        self.xgb = xgb.XGBClassifier(n_estimators=100, learning_rate=0.05, max_depth=3, eval_metric='logloss', random_state=42)
        self.lr = LogisticRegression(max_iter=500, random_state=42)

    def train_and_predict(self, X, y, curr_X) -> dict:
        results = {'rf': 0.5, 'gb': 0.5, 'xgb': 0.5, 'lr': 0.5}
        try:
            # Random Forest
            self.rf.fit(X, y)
            if 1 in self.rf.classes_:
                results['rf'] = self.rf.predict_proba(curr_X)[0][list(self.rf.classes_).index(1)]
                
            # Gradient Boosting
            self.gb.fit(X, y)
            if 1 in self.gb.classes_:
                results['gb'] = self.gb.predict_proba(curr_X)[0][list(self.gb.classes_).index(1)]
                
            # XGBoost
            self.xgb.fit(np.array(X), np.array(y))
            if 1 in self.xgb.classes_:
                results['xgb'] = self.xgb.predict_proba(curr_X)[0][list(self.xgb.classes_).index(1)]
                
            # Logistic Regression
            self.lr.fit(X, y)
            if 1 in self.lr.classes_:
                results['lr'] = self.lr.predict_proba(curr_X)[0][list(self.lr.classes_).index(1)]
                
        except Exception as e:
            logger.warning(f"ML Core Error: {e}")
            
        return results

# ==========================================
# ⚙️ MODULE 5: META OPTIMIZER & ENSEMBLE
# ==========================================
class MetaOptimizer:
    """ အခြေအနေပေါ်မူတည်၍ Algorithm ၆ မျိုး၏ အလေးချိန် (Weights) ကို အလိုအလျောက် ပြင်ဆင်ခြင်း """
    def __init__(self):
        # ကနဦး အလေးချိန်များ
        self.weights = {
            'rf': 0.20, 'gb': 0.20, 'xgb': 0.20, 
            'lr': 0.10, 'markov': 0.15, 'pattern': 0.15
        }

    def learn_from_result(self, actual: str, past_model_preds: dict):
        if not past_model_preds: return

        total_w = 0.0
        actual_val = 1.0 if actual == 'BIG' else 0.0
        
        for model, prob_big in past_model_preds.items():
            # Error ကို တွက်ချက်ခြင်း (0.0 to 1.0)
            error = abs(actual_val - prob_big)
            
            # အမှားနည်းလျှင် အမှတ်တိုးမည်၊ အမှားများလျှင် အမှတ်လျှော့မည်
            if error < 0.5:
                self.weights[model] += 0.05
            else:
                self.weights[model] = max(0.01, self.weights[model] - 0.03)
                
            total_w += self.weights[model]
            
        # Normalize Back to 1.0
        if total_w > 0:
            for k in self.weights:
                self.weights[k] /= total_w

class UltimateAIEngine:
    def __init__(self):
        self.fe = FeatureEngineer(window_size=6)
        self.ml_core = MachineLearningCore()
        self.optimizer = MetaOptimizer()
        self.last_model_probs = {} 

    def analyze_and_predict(self, docs: list) -> tuple:
        if len(docs) < 40: 
            return "BIG", 55.0, {}
        
        sizes = [d.get('size', 'BIG') for d in reversed(docs)]
        numbers = [int(d.get('number', 0)) for d in reversed(docs)]
        parities = [d.get('parity', 'EVEN') for d in reversed(docs)]
        
        # 1. Statistical Models
        prob_b_pat = PatternEngine.predict(sizes, n=3)
        prob_b_mar = MarkovChain.predict(sizes)
        
        # 2. Machine Learning Models
        X, y, curr_X = self.fe.prepare_data(sizes, numbers, parities)
        if X is not None:
            ml_probs = self.ml_core.train_and_predict(X, y, curr_X)
        else:
            ml_probs = {'rf': 0.5, 'gb': 0.5, 'xgb': 0.5, 'lr': 0.5}
            
        # Save exact probabilities for the Optimizer to learn later
        self.last_model_probs = {
            'pattern': prob_b_pat, 'markov': prob_b_mar,
            'rf': ml_probs['rf'], 'gb': ml_probs['gb'], 
            'xgb': ml_probs['xgb'], 'lr': ml_probs['lr']
        }
        
        # 3. Apply Meta-Optimizer Weights
        w = self.optimizer.weights
        final_b_score = (
            (self.last_model_probs['pattern'] * w['pattern']) +
            (self.last_model_probs['markov'] * w['markov']) +
            (self.last_model_probs['rf'] * w['rf']) +
            (self.last_model_probs['gb'] * w['gb']) +
            (self.last_model_probs['xgb'] * w['xgb']) +
            (self.last_model_probs['lr'] * w['lr'])
        )
        
        final_pred = "BIG" if final_b_score > 0.5 else "SMALL"
        
        # Confidence Scaling (50.0 to 99.0)
        raw_conf = final_b_score if final_b_score > 0.5 else (1.0 - final_b_score)
        confidence = min(max(raw_conf * 100, 51.0), 99.0)
        
        return final_pred, round(confidence, 1), self.last_model_probs

# ==========================================
# 💰 MODULE 6: UI & BOT MANAGER
# ==========================================
class TelegramUI:
    def __init__(self, bot_instance: Bot):
        self.bot = bot_instance

    async def send_prediction(self, issue: str, pred: str, step: int, conf: float, top_model: str):
        msg = (
            f"<b>[PRO PREDICTOR V6]</b>\n"
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
            f"<b>SIX-LOTTERY</b>\n\n"
            f"⏰ Period: {issue}\n"
            f"🎯 Choice: {pred} {step}x\n"
            f"📊 Result: {icon} {win_str} | {res_letter} ({actual_num})"
        )
        
        try: 
            await self.bot.send_message(chat_id=Config.CHANNEL_ID, text=msg)
            
            if is_win and Config.WIN_STICKER:
                await self.bot.send_sticker(chat_id=Config.CHANNEL_ID, sticker=Config.WIN_STICKER)
            elif not is_win and Config.LOSE_STICKER:
                await self.bot.send_sticker(chat_id=Config.CHANNEL_ID, sticker=Config.LOSE_STICKER)
        except Exception as e: logger.error(f"TG Result Error: {e}")

# ==========================================
# 🚀 MODULE 7: MAIN CONTROLLER LOOP
# ==========================================
class GameController:
    def __init__(self):
        self.db = DatabaseManager(Config.MONGO_URI)
        self.ai = UltimateAIEngine()
        self.ui = TelegramUI(bot)
        self.last_issue = None
        self.lose_streak = 0

    async def fetch_lottery_data(self, session: aiohttp.ClientSession) -> dict:
        json_data = {
            'pageSize': 10, 'pageNo': 1, 'typeId': 1, 'language': 7, 
            'random': '736ea5fe7d1744008714320d2cfbbed4', 
            'signature': '9BE5D3A057D1938B8210BA32222A993C', 
            'timestamp': int(time.time())
        }
        for _ in range(3):
            try:
                async with session.post(Config.API_URL, headers=Config.HEADERS, json=json_data, timeout=3.0) as r:
                    if r.status == 200: return await r.json()
            except: await asyncio.sleep(0.5)
        return None

    async def run(self):
        await self.db.initialize()
        
        async with aiohttp.ClientSession() as session:
            logger.info("🔥 PRO Game Loop Started...")
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
                    
                    # 1. Initial Start
                    if not self.last_issue:
                        self.last_issue = issue
                        recent_preds = await self.db.get_recent_predictions(10)
                        
                        self.lose_streak = 0
                        for p in recent_preds:
                            if p.get("win_lose") == "LOSE": self.lose_streak += 1
                            else: break
                        if self.lose_streak >= len(Config.MULTIPLIERS): self.lose_streak = 0

                        next_issue = str(int(issue) + 1)
                        docs = await self.db.get_history(500)
                        pred, conf, details = self.ai.analyze_and_predict(docs)
                        
                        top_model = max(self.ai.optimizer.weights, key=self.ai.optimizer.weights.get)
                        current_step = self.lose_streak + 1
                        
                        await self.ui.send_prediction(next_issue, pred, current_step, conf, top_model)
                        await asyncio.sleep(1.0); continue

                    # 2. New Issue Detected
                    if int(issue) > int(self.last_issue):
                        await self.db.save_history(issue, number, size, parity)
                        
                        # Self Learning Update
                        self.ai.optimizer.learn_from_result(size, self.ai.last_model_probs)
                        
                        pred_doc = await self.db.predictions.find_one({"issue_number": issue})
                        
                        if pred_doc and pred_doc.get('predicted_size'):
                            predicted_size = pred_doc['predicted_size']
                            is_win = (predicted_size == size)
                            win_lose_db = "WIN" if is_win else "LOSE"
                            
                            await self.db.update_result(issue, size, number, win_lose_db)
                            
                            current_step = self.lose_streak + 1
                            await self.ui.send_result(issue, predicted_size, current_step, is_win, size, number)
                            
                            if is_win: self.lose_streak = 0
                            else: 
                                self.lose_streak += 1
                                if self.lose_streak >= len(Config.MULTIPLIERS): self.lose_streak = 0

                        self.last_issue = issue
                        
                        # 3. Next Prediction
                        next_issue = str(int(issue) + 1)
                        docs = await self.db.get_history(500)
                        
                        pred, conf, details = self.ai.analyze_and_predict(docs)
                        await self.db.save_prediction(next_issue, pred, conf, details)
                        
                        top_model = max(self.ai.optimizer.weights, key=self.ai.optimizer.weights.get)
                        current_step = self.lose_streak + 1
                        
                        await self.ui.send_prediction(next_issue, pred, current_step, conf, top_model)

                except Exception as e:
                    logger.error(f"Loop Exception: {e}")
                await asyncio.sleep(1.5)

# ==========================================
# 🚀 ENTRY POINT
# ==========================================
async def main():
    logger.info("Initializing 6-CORE PROFESSIONAL PREDICTOR...")
    await bot.delete_webhook(drop_pending_updates=True)
    
    controller = GameController()
    asyncio.create_task(controller.run())
    
    logger.info("Bot Polling Started...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try: asyncio.run(main())
    except KeyboardInterrupt: logger.info("Bot Stopped by User.")
