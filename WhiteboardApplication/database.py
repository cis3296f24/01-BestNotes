import sqlite3
from typing import List, Optional

class UserDatabase:
    def __init__(self, db_path: str = 'users_registry.db'):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    def add_user(self, username: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO users (username) VALUES (?)', (username,))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def user_exists(self, username: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT username FROM users WHERE username = ?', (username,))
            return cursor.fetchone() is not None