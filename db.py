import sqlite3
from pathlib import Path

DB_PATH = Path("data/bot.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS challenges (
        id TEXT PRIMARY KEY,
        name TEXT,
        difficulty TEXT,
        points INTEGER,
        challenge_category TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS machines (
        id TEXT PRIMARY KEY,
        name TEXT,
        difficulty TEXT,
        points INTEGER,
        os TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS fortresses (
        id TEXT PRIMARY KEY,
        name TEXT,
        points INTEGER,
        number_of_flags INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS challenge_completions (
        user_id TEXT,
        challenge_id TEXT,
        PRIMARY KEY (user_id, challenge_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS machine_flags (
        user_id TEXT,
        machine_id TEXT,
        flag_type TEXT,
        PRIMARY KEY (user_id, machine_id, flag_type)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS fortress_flags (
        user_id TEXT,
        fortress_id TEXT,
        flag_title TEXT,
        PRIMARY KEY (user_id, fortress_id, flag_title)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS todo (
        type TEXT,
        htb_id TEXT,
        name TEXT
    )''')
    conn.commit()
    conn.close()

def add_or_update_user(user_id, name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users (id, name) VALUES (?, ?)", (user_id, name))
    conn.commit()
    conn.close()

def add_or_update_challenge(challenge_id, name, difficulty, points, category):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO challenges (id, name, difficulty, points, challenge_category) VALUES (?, ?, ?, ?, ?)",
              (challenge_id, name, difficulty, points, category))
    conn.commit()
    conn.close()

def add_or_update_machine(machine_id, name, difficulty, points, os):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO machines (id, name, difficulty, points, os) VALUES (?, ?, ?, ?, ?)",
              (machine_id, name, difficulty, points, os))
    conn.commit()
    conn.close()

def add_or_update_fortress(fortress_id, name, points, number_of_flags):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO fortresses (id, name, points, number_of_flags) VALUES (?, ?, ?, ?)",
              (fortress_id, name, points, number_of_flags))
    conn.commit()
    conn.close()

def add_challenge_completion(user_id, challenge_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO challenge_completions (user_id, challenge_id) VALUES (?, ?)", (user_id, challenge_id))
    conn.commit()
    conn.close()

def add_machine_flag(user_id, machine_id, flag_type):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO machine_flags (user_id, machine_id, flag_type) VALUES (?, ?, ?)", (user_id, machine_id, flag_type))
    conn.commit()
    conn.close()

def add_fortress_flag(user_id, fortress_id, flag_title):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO fortress_flags (user_id, fortress_id, flag_title) VALUES (?, ?, ?)", (user_id, fortress_id, flag_title))
    conn.commit()
    conn.close()

def get_challenge_completions(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT challenge_id FROM challenge_completions WHERE user_id = ?", (user_id,))
    completions = [row[0] for row in c.fetchall()]
    conn.close()
    return completions

def get_machine_flags(user_id, machine_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT flag_type FROM machine_flags WHERE user_id = ? AND machine_id = ?", (user_id, machine_id))
    flags = [row[0] for row in c.fetchall()]
    conn.close()
    return flags

def get_fortress_flags(user_id, fortress_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT flag_title FROM fortress_flags WHERE user_id = ? AND fortress_id = ?", (user_id, fortress_id))
    flags = [row[0] for row in c.fetchall()]
    conn.close()
    return flags

def get_all_challenges():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, difficulty, points, challenge_category FROM challenges")
    challenges = c.fetchall()
    conn.close()
    return challenges

def get_all_machines():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, difficulty, points, os FROM machines")
    machines = c.fetchall()
    conn.close()
    return machines

def get_all_fortresses():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, points, number_of_flags FROM fortresses")
    fortresses = c.fetchall()
    conn.close()
    return fortresses

def clear_todo():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM todo")
    conn.commit()
    conn.close()

def add_todo(type, htb_id, name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO todo (type, htb_id, name) VALUES (?, ?, ?)", (type, htb_id, name))
    conn.commit()
    conn.close()

def remove_todo(type, htb_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM todo WHERE type = ? AND htb_id = ?", (type, htb_id))
    conn.commit()
    conn.close()

def get_todo():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT type, htb_id, name FROM todo")
    todos = c.fetchall()
    conn.close()
    return todos