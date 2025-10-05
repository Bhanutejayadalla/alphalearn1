import sqlite3
import json
from flask import current_app, g

def get_db():
    """Connects to the application's configured database."""
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    """Closes the database connection."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Initializes the database from the schema file."""
    db = get_db()
    with current_app.open_resource('schema.sql') as f:
        db.executescript(f.read().decode('utf8'))

def init_app(app):
    """Register database functions with the Flask app."""
    app.teardown_appcontext(close_db)
    # Check if DB needs to be initialized
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute("SELECT 1 FROM user LIMIT 1")
        except sqlite3.OperationalError:
            # Table doesn't exist, initialize
            init_db()

# --- Data Access Functions ---

def save_session_data(user_id, session_data):
    """Saves a learning session to the database."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        'INSERT INTO session (user_id, mode, score_percent, date) VALUES (?, ?, ?, CURRENT_TIMESTAMP)',
        (user_id, session_data['mode'], session_data['scorePercent'])
    )
    session_id = cursor.lastrowid
    
    # Save words
    words_to_insert = [
        (session_id, w['letter'], w['word'], w['meaning'], w['example'])
        for w in session_data['words']
    ]
    cursor.executemany(
        'INSERT INTO word (session_id, letter, word_text, meaning, example) VALUES (?, ?, ?, ?, ?)',
        words_to_insert
    )

    # Save quiz
    # Convert quiz data to JSON string for storage
    quiz_json = json.dumps(session_data['quiz'])
    cursor.execute(
        'INSERT INTO quiz (session_id, quiz_data) VALUES (?, ?)',
        (session_id, quiz_json)
    )
    
    db.commit()

def get_user_sessions(user_id):
    """Retrieves all sessions for a specific user."""
    db = get_db()
    sessions = db.execute(
        'SELECT id, mode, score_percent, strftime("%Y-%m-%d %H:%M", date) as date_formatted FROM session WHERE user_id = ? ORDER BY date DESC',
        (user_id,)
    ).fetchall()
    return [dict(row) for row in sessions]

def get_session_details(user_id, session_id):
    """Retrieves words and quiz for a specific session, ensuring user owns it."""
    db = get_db()
    # First, verify ownership
    session = db.execute(
        'SELECT * FROM session WHERE id = ? AND user_id = ?', (session_id, user_id)
    ).fetchone()

    if not session:
        return None

    words = db.execute(
        'SELECT letter, word_text, meaning, example FROM word WHERE session_id = ?', (session_id,)
    ).fetchall()
    
    quiz_data = db.execute(
        'SELECT quiz_data FROM quiz WHERE session_id = ?', (session_id,)
    ).fetchone()

    return {
        'id': session['id'],
        'mode': session['mode'],
        'scorePercent': session['score_percent'],
        'dateISO': session['date'],
        'words': [dict(row) for row in words],
        'quiz': json.loads(quiz_data['quiz_data']) if quiz_data else []
    }

def get_tracking_stats(user_id):
    """Calculates average scores and test counts for each level."""
    db = get_db()
    stats = {}
    levels = ['beginner', 'intermediate', 'proficient']
    for level in levels:
        result = db.execute(
            'SELECT AVG(score_percent) as average, COUNT(id) as count FROM session WHERE user_id = ? AND mode = ?',
            (user_id, level)
        ).fetchone()
        
        stats[level] = {
            'average': round(result['average']) if result['average'] is not None else 0,
            'count': result['count'] if result['count'] is not None else 0
        }
    return stats
