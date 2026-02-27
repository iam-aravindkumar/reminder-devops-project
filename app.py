from flask import Flask, request, jsonify, g
import sqlite3
from datetime import datetime
import threading
import time
import os

app = Flask(__name__)

# ==============================
# Configuration
# ==============================
DB_NAME = os.getenv("DB_NAME", "reminders.db")
APP_VERSION = os.getenv("APP_VERSION", "1.0")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


# ==============================
# Database Helper
# ==============================
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_NAME, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT NOT NULL,
            remind_time TEXT NOT NULL,
            triggered INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()


# ==============================
# API Endpoints
# ==============================

@app.route("/")
def home():
    return jsonify({
        "service": "Reminder API",
        "version": APP_VERSION,
        "environment": ENVIRONMENT,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })


@app.route("/health")
def health():
    return jsonify({"status": "healthy"})


@app.route("/add", methods=["POST"])
def add_reminder():
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "Invalid JSON"}), 400

        message = data.get("message")
        remind_time = data.get("remind_time")

        if not message or not remind_time:
            return jsonify({"error": "Missing required fields"}), 400

        # Validate time format
        datetime.strptime(remind_time, "%Y-%m-%d %H:%M")

        db = get_db()
        db.execute(
            "INSERT INTO reminders (message, remind_time) VALUES (?, ?)",
            (message, remind_time)
        )
        db.commit()

        return jsonify({"message": "Reminder added successfully"}), 201

    except ValueError:
        return jsonify({"error": "Invalid datetime format. Use YYYY-MM-DD HH:MM"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/reminders", methods=["GET"])
def list_reminders():
    db = get_db()
    reminders = db.execute(
        "SELECT id, message, remind_time, triggered FROM reminders"
    ).fetchall()

    return jsonify([dict(row) for row in reminders])


# ==============================
# Background Scheduler
# ==============================

def check_reminders():
    while True:
        try:
            db = sqlite3.connect(DB_NAME)
            cursor = db.cursor()

            now = datetime.now().strftime("%Y-%m-%d %H:%M")

            cursor.execute("""
                SELECT id, message FROM reminders
                WHERE remind_time = ? AND triggered = 0
            """, (now,))

            reminders = cursor.fetchall()

            for reminder in reminders:
                print(f"🔔 Reminder Triggered: {reminder[1]}")

                cursor.execute(
                    "UPDATE reminders SET triggered = 1 WHERE id = ?",
                    (reminder[0],)
                )
                db.commit()

            db.close()
            time.sleep(60)

        except Exception as e:
            print("Scheduler error:", e)
            time.sleep(60)


def start_scheduler():
    thread = threading.Thread(target=check_reminders, daemon=True)
    thread.start()


# ==============================
# Application Entry Point
# ==============================

if __name__ == "__main__":
    with app.app_context():
        init_db()
    start_scheduler()
    app.run(host="0.0.0.0", port=5000)
