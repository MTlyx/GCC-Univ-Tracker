import sqlite3
from pathlib import Path

DB_PATH = Path("data/bot.db")

CREATE_USERS = '''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    htb_id TEXT UNIQUE,
    name TEXT
);
'''

CREATE_CHALLENGES = '''
CREATE TABLE IF NOT EXISTS challenges (
    id INTEGER PRIMARY KEY,
    htb_id TEXT UNIQUE,
    name TEXT,
    difficulty TEXT,
    points INTEGER,
    category TEXT
);
'''

CREATE_MACHINES = '''
CREATE TABLE IF NOT EXISTS machines (
    id INTEGER PRIMARY KEY,
    htb_id TEXT UNIQUE,
    name TEXT,
    difficulty TEXT,
    points INTEGER,
    os TEXT
);
'''

CREATE_FORTRESSES = '''
CREATE TABLE IF NOT EXISTS fortresses (
    id INTEGER PRIMARY KEY,
    htb_id TEXT UNIQUE,
    name TEXT,
    points INTEGER,
    flags INTEGER
);
'''

CREATE_TODO = '''
CREATE TABLE IF NOT EXISTS todo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT, -- 'challenge', 'machine', 'fortress'
    htb_id TEXT,
    name TEXT
);
'''

def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(CREATE_USERS)
    c.execute(CREATE_CHALLENGES)
    c.execute(CREATE_MACHINES)
    c.execute(CREATE_FORTRESSES)
    c.execute(CREATE_TODO)
    conn.commit()
    conn.close()

def add_or_update_user(htb_id, name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users (htb_id, name) VALUES (?, ?)", (htb_id, name))
    conn.commit()
    conn.close()

def add_or_update_challenge(htb_id, name, difficulty, points, category):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO challenges (htb_id, name, difficulty, points, category) VALUES (?, ?, ?, ?, ?)", (htb_id, name, difficulty, points, category))
    conn.commit()
    conn.close()

def add_or_update_machine(htb_id, name, difficulty, points, os):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO machines (htb_id, name, difficulty, points, os) VALUES (?, ?, ?, ?, ?)", (htb_id, name, difficulty, points, os))
    conn.commit()
    conn.close()

def add_or_update_fortress(htb_id, name, points, flags):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO fortresses (htb_id, name, points, flags) VALUES (?, ?, ?, ?)", (htb_id, name, points, flags))
    conn.commit()
    conn.close()

def add_todo(item_type, htb_id, name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO todo (type, htb_id, name) VALUES (?, ?, ?)", (item_type, htb_id, name))
    conn.commit()
    conn.close()

def clear_todo():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM todo")
    conn.commit()
    conn.close()

def get_todo():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT type, htb_id, name FROM todo")
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT htb_id, name FROM users")
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_challenges():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT htb_id, name, difficulty, points, category FROM challenges")
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_machines():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT htb_id, name, difficulty, points, os FROM machines")
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_fortresses():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT htb_id, name, points, flags FROM fortresses")
    rows = c.fetchall()
    conn.close()
    return rows

def remove_todo(item_type, htb_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM todo WHERE type = ? AND htb_id = ?", (item_type, htb_id))
    conn.commit()
    conn.close()