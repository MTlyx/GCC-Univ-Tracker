import sqlite3
from pathlib import Path

DB_PATH = Path("data/bot.db")

CREATE_USERS = '''
CREATE TABLE IF NOT EXISTS users (
    htb_id TEXT PRIMARY KEY,
    name TEXT
);
'''

CREATE_CHALLENGES = '''
CREATE TABLE IF NOT EXISTS challenges (
    htb_id TEXT PRIMARY KEY,
    name TEXT,
    difficulty TEXT,
    points INTEGER,
    category TEXT
);
'''

CREATE_MACHINES = '''
CREATE TABLE IF NOT EXISTS machines (
    htb_id TEXT PRIMARY KEY,
    name TEXT,
    difficulty TEXT,
    points INTEGER,
    os TEXT
);
'''

CREATE_FORTRESSES = '''
CREATE TABLE IF NOT EXISTS fortresses (
    htb_id TEXT PRIMARY KEY,
    name TEXT,
    points INTEGER,
    number_of_flags INTEGER
);
'''

CREATE_MACHINE_FLAGS = '''
CREATE TABLE IF NOT EXISTS machine_flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_htb_id TEXT,
    machine_htb_id TEXT,
    flag_type TEXT,
    UNIQUE(user_htb_id, machine_htb_id, flag_type)
);
'''

CREATE_FORTRESS_FLAGS = '''
CREATE TABLE IF NOT EXISTS fortress_flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_htb_id TEXT,
    fortress_htb_id TEXT,
    flag_type TEXT,
    UNIQUE(user_htb_id, fortress_htb_id, flag_type)
);
'''

CREATE_CHALLENGE_COMPLETIONS = '''
CREATE TABLE IF NOT EXISTS challenge_completions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_htb_id TEXT,
    challenge_htb_id TEXT,
    UNIQUE(user_htb_id, challenge_htb_id)
);
'''

CREATE_TODO = '''
CREATE TABLE IF NOT EXISTS todo (
    type TEXT,
    htb_id TEXT,
    name TEXT
);
'''

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(CREATE_USERS)
    c.execute(CREATE_CHALLENGES)
    c.execute(CREATE_MACHINES)
    c.execute(CREATE_FORTRESSES)
    c.execute(CREATE_MACHINE_FLAGS)
    c.execute(CREATE_FORTRESS_FLAGS)
    c.execute(CREATE_CHALLENGE_COMPLETIONS)
    c.execute(CREATE_TODO)
    conn.commit()
    conn.close()

def add_or_update_user(htb_id, name):
    if not htb_id or not name:
        print(f"[!] Données utilisateur invalides: htb_id={htb_id}, name={name}")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users (htb_id, name) VALUES (?, ?)", (htb_id, name))
    conn.commit()
    conn.close()

def add_or_update_challenge(htb_id, name, difficulty, points, category):
    if not htb_id or not name:
        print(f"[!] Données challenge invalides: htb_id={htb_id}, name={name}")
        return
    points = int(points) if points is not None else 0
    category = category or 'Inconnue'
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO challenges (htb_id, name, difficulty, points, category) VALUES (?, ?, ?, ?, ?)",
        (htb_id, name, difficulty, points, category)
    )
    conn.commit()
    conn.close()

def add_or_update_machine(htb_id, name, difficulty, points, os):
    if not htb_id or not name:
        print(f"[!] Données machine invalides: htb_id={htb_id}, name={name}")
        return
    points = int(points) if points is not None else 0
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO machines (htb_id, name, difficulty, points, os) VALUES (?, ?, ?, ?, ?)",
        (htb_id, name, difficulty, points, os or 'Inconnu')
    )
    conn.commit()
    conn.close()

def add_or_update_fortress(htb_id, name, points, number_of_flags):
    if not htb_id or htb_id == '0':
        print(f"[!] ID de forteresse invalide: {htb_id}")
        return
    if not name:
        name = 'Inconnu'
    points = int(points) if points is not None else (number_of_flags * 10 if number_of_flags else 0)
    number_of_flags = int(number_of_flags) if number_of_flags is not None else 0
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO fortresses (htb_id, name, points, number_of_flags) VALUES (?, ?, ?, ?)",
        (htb_id, name, points, number_of_flags)
    )
    conn.commit()
    conn.close()

def add_machine_flag(user_htb_id, machine_htb_id, flag_type):
    if not user_htb_id or not machine_htb_id or not flag_type:
        print(f"[!] Données machine flag invalides: user={user_htb_id}, machine={machine_htb_id}, flag_type={flag_type}")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO machine_flags (user_htb_id, machine_htb_id, flag_type) VALUES (?, ?, ?)",
        (user_htb_id, machine_htb_id, flag_type)
    )
    conn.commit()
    conn.close()

def add_fortress_flag(user_htb_id, fortress_htb_id, flag_type):
    if not user_htb_id or not fortress_htb_id or not flag_type:
        print(f"[!] Données forteresse flag invalides: user={user_htb_id}, fortress={fortress_htb_id}, flag_type={flag_type}")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO fortress_flags (user_htb_id, fortress_htb_id, flag_type) VALUES (?, ?, ?)",
        (user_htb_id, fortress_htb_id, flag_type)
    )
    conn.commit()
    conn.close()

def add_challenge_completion(user_htb_id, challenge_htb_id):
    if not user_htb_id or not challenge_htb_id:
        print(f"[!] Données challenge completion invalides: user={user_htb_id}, challenge={challenge_htb_id}")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO challenge_completions (user_htb_id, challenge_htb_id) VALUES (?, ?)",
        (user_htb_id, challenge_htb_id)
    )
    conn.commit()
    conn.close()

def get_fortress_flags(user_htb_id, fortress_htb_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT flag_type FROM fortress_flags WHERE user_htb_id = ? AND fortress_htb_id = ?",
        (user_htb_id, fortress_htb_id)
    )
    rows = c.fetchall()
    conn.close()
    return [row[0] for row in rows]

def get_machine_flags(user_htb_id, machine_htb_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT flag_type FROM machine_flags WHERE user_htb_id = ? AND machine_htb_id = ?",
        (user_htb_id, machine_htb_id)
    )
    rows = c.fetchall()
    conn.close()
    return [row[0] for row in rows]

def get_challenge_completions(user_htb_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT challenge_htb_id FROM challenge_completions WHERE user_htb_id = ?",
        (user_htb_id,)
    )
    rows = c.fetchall()
    conn.close()
    return [row[0] for row in rows]

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
    c.execute("SELECT htb_id, name, points, number_of_flags FROM fortresses")
    rows = c.fetchall()
    conn.close()
    return rows

def add_todo(type, htb_id, name):
    if not type or not htb_id or not name:
        print(f"[!] Données todo invalides: type={type}, htb_id={htb_id}, name={name}")
        return
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