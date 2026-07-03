import os
import sqlite3
import json
import logging
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton, KeyboardButtonPollType, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, ConversationHandler, CallbackQueryHandler, PollAnswerHandler
)

# Enable Logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID")) if os.getenv("OWNER_ID") else None

DB_FILE = "quiz_bot.db"

# Global dictionary for active group games memory
GROUP_GAMES = {}

# Conversation flow states
TITLE, DESCRIPTION, QUESTIONS, PRE_MESSAGE, TIMER = range(5)
EDIT_TITLE, EDIT_DESC, EDIT_TIMER = range(5, 8)
EDIT_QUESTION_TEXT, EDIT_QUESTION_OPTIONS, EDIT_QUESTION_CORRECT, EDIT_QUESTION_EXPLANATION, EDIT_QUESTION_PRE_MESSAGE = range(8, 13)

def escape_markdown(text):
    """Escape special characters for Telegram Markdown"""
    if not text:
        return text
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

def format_time(seconds):
    """Convert seconds to min:sec format (e.g., 1m 45s)"""
    if seconds < 60:
        return f"{int(seconds)}s"
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{minutes}m {secs}s"

def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quizzes (
                quiz_id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id INTEGER,
                title TEXT,
                description TEXT,
                timer INTEGER DEFAULT 30
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id INTEGER,
                question_text TEXT,
                options TEXT,
                correct_answer TEXT,
                explanation TEXT,
                pre_message TEXT,
                FOREIGN KEY(quiz_id) REFERENCES quizzes(quiz_id)
            )
        """)
        conn.commit()
        conn.close()
        logging.info("Database initialized successfully")
    except Exception as e:
        logging.error(f"Error initializing database: {e}")

init_db()

def check_active_quiz_creation(user_id, context):
    """Check if user has an active quiz creation in progress"""
    return "quiz_build" in context.user_data and context.user_data["quiz_build"].get("title")

# Helper to create/replace group game when allowed
def add_or_replace_group_game(chat_id, quiz_id, setup_message_id=None, setup_panel_text=None, is_private=False):
    """
    Create or replace GROUP_GAMES[chat_id] when it's safe to start a new quiz.
    If an active (started and not paused) game exists, return the existing one and do not overwrite.
    """
    existing = GROUP_GAMES.get(chat_id)
    if existing and existing.get("quiz_started") and not existing.get("quiz_paused"):
        return existing

    game = {
        "quiz_id": int(quiz_id),
        "joined_users": {},
        "current_q": 0,
        "scores": {},
        "poll_map": {},
        "start_time": None,
        "user_answers": {},
        "question_start_times": {},
        "ready_users": set(),
        "quiz_started": False,
        "poll_message_ids": {},
        "setup_message_id": setup_message_id,
        "setup_panel_text": setup_panel_text,
        "is_private": is_private,
        "quiz_paused": False,
        "consecutive_no_answers": 0
    }
    GROUP_GAMES[chat_id] = game
    return game

# rest of file unchanged (kept original content)