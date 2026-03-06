import sqlite3
import json
from datetime import datetime

def init_database(db_path='database.db'):
    """データベースを初期化"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # カードテーブル作成
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT NOT NULL,
            category TEXT NOT NULL,
            raw_input TEXT NOT NULL,
            generated_html TEXT,
            anki_note_id INTEGER,
            deck_name TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 生成履歴テーブル
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS generation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id INTEGER,
            prompt_used TEXT,
            llm_response TEXT,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (card_id) REFERENCES cards(id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"✅ データベース初期化完了: {db_path}")

if __name__ == "__main__":
    init_database()