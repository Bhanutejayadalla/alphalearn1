import os
from flask import Flask, jsonify, render_template, request, session, g
from werkzeug.security import check_password_hash, generate_password_hash
import requests
import random
import string
import database

# App configuration
app = Flask(__name__)
app.config.from_mapping(
    SECRET_KEY='dev',  # Replace with a real secret key in production
    DATABASE=os.path.join(app.instance_path, 'alpha_learn.sqlite'),
)

# Ensure the instance folder exists
try:
    os.makedirs(app.instance_path)
except OSError:
    pass

# Initialize database
database.init_app(app)

# --- Dictionary API Helper ---
def get_word_details(word):
    """Fetches meaning and an example sentence for a word."""
    try:
        # Using a free dictionary API
        response = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}")
        response.raise_for_status()
        data = response.json()[0]
        meaning = data['meanings'][0]['definitions'][0]['definition']
        
        # Find an example, fallback if none exists
        example = "No example sentence found."
        for meaning_data in data['meanings']:
            for definition in meaning_data['definitions']:
                if 'example' in definition:
                    example = definition['example']
                    break
            if example != "No example sentence found.":
                break

        return {'word': word.capitalize(), 'meaning': meaning, 'example': example}
    except requests.exceptions.RequestException as e:
        print(f"API Error for word '{word}': {e}")
        return None
    except (KeyError, IndexError):
        print(f"Could not parse data for word: {word}")
        return None

# --- Routes ---

@app.route('/')
def index():
    """Serves the main HTML file."""
    return render_template('alpha.html')

# --- API Routes for Authentication ---

@app.route('/api/register', methods=['POST'])
def register():
    """Registers a new user."""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    db = database.get_db()

    if not username or not password:
        return jsonify({'error': 'Username and password are required.'}), 400

    if db.execute('SELECT id FROM user WHERE username = ?', (username,)).fetchone() is not None:
        return jsonify({'error': f"User {username} is already registered."}), 409

    db.execute(
        'INSERT INTO user (username, password) VALUES (?, ?)',
        (username, generate_password_hash(password))
    )
    db.commit()
    return jsonify({'message': 'Registration successful!'}), 201

@app.route('/api/login', methods=['POST'])
def login():
    """Logs in a user."""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    db = database.get_db()
    error = None

    user = db.execute('SELECT * FROM user WHERE username = ?', (username,)).fetchone()

    if user is None:
        error = 'Incorrect username.'
    elif not check_password_hash(user['password'], password):
        error = 'Incorrect password.'

    if error is None:
        session.clear()
        session['user_id'] = user['id']
        session['username'] = user['username']
        return jsonify({'message': f"Welcome back, {user['username']}!", 'username': user['username']}), 200
    
    return jsonify({'error': error}), 401
    
@app.route('/api/logout', methods=['POST'])
def logout():
    """Logs out the current user."""
    session.clear()
    return jsonify({'message': 'Logged out successfully.'}), 200

@app.route('/api/check_auth', methods=['GET'])
def check_auth():
    """Checks if a user is currently logged in."""
    if 'user_id' in session:
        return jsonify({'isAuthenticated': True, 'username': session['username']})
    return jsonify({'isAuthenticated': False})

# --- API Routes for App Features ---

@app.route('/api/words/<level>', methods=['GET'])
def get_words(level):
    """Generates 26 words (A-Z) for a given level."""
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required.'}), 401

    words_list = []
    
    # Define difficulty constraints for Datamuse API
    # 'rel_trg' = words triggered by the query word
    # 'sp' = spelling pattern
    difficulty_params = {
        'beginner': {'md': 'f', 'max': 1000},      # More frequent words
        'intermediate': {'md': 'f', 'max': 500}, # Less frequent
        'proficient': {'md': 'f', 'max': 100}      # Rare words
    }
    params = difficulty_params.get(level, difficulty_params['beginner'])
    
    # Fallback list in case API fails
    fallback_words = {
        'A': 'Apple', 'B': 'Brave', 'C': 'Clever', 'D': 'Dream', 'E': 'Energy', 'F': 'Future', 
        'G': 'Grace', 'H': 'Happy', 'I': 'Imagine', 'J': 'Journey', 'K': 'Kind', 'L': 'Laugh', 
        'M': 'Magic', 'N': 'Noble', 'O': 'Open', 'P': 'Peace', 'Q': 'Quest', 'R': 'Rise', 
        'S': 'Smile', 'T': 'Trust', 'U': 'Unity', 'V': 'Value', 'W': 'Wish', 'X': 'Xenial', 
        'Y': 'Youth', 'Z': 'Zeal'
    }

    for letter in string.ascii_uppercase:
        word_found = False
        try:
            # Query Datamuse API for a word starting with the letter
            api_params = {'sp': f'{letter.lower()}*', **params}
            response = requests.get("https://api.datamuse.com/words", params=api_params)
            response.raise_for_status()
            potential_words = response.json()
            
            if potential_words:
                # Try to get details for a few words until one succeeds
                for word_data in potential_words[:5]:
                    details = get_word_details(word_data['word'])
                    if details:
                        details['letter'] = letter
                        words_list.append(details)
                        word_found = True
                        break
        except requests.exceptions.RequestException as e:
            print(f"Datamuse API error: {e}")

        if not word_found:
            # Use fallback if API fails or no valid word is found
            details = get_word_details(fallback_words[letter])
            if details:
                details['letter'] = letter
                words_list.append(details)

    return jsonify(words_list)

@app.route('/api/sessions', methods=['POST'])
def save_session():
    """Saves a completed learning session and quiz result."""
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required.'}), 401
        
    data = request.get_json()
    user_id = session['user_id']
    
    database.save_session_data(user_id, data)
    
    return jsonify({'message': 'Session saved successfully.'}), 201

@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    """Gets all past sessions for the logged-in user."""
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required.'}), 401
    
    user_id = session['user_id']
    sessions = database.get_user_sessions(user_id)
    return jsonify(sessions)

@app.route('/api/sessions/<int:session_id>', methods=['GET'])
def get_session_detail(session_id):
    """Gets the detailed view of a single past session."""
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required.'}), 401
    
    user_id = session['user_id']
    session_details = database.get_session_details(user_id, session_id)
    if session_details:
        return jsonify(session_details)
    return jsonify({'error': 'Session not found or access denied.'}), 404

@app.route('/api/track', methods=['GET'])
def get_tracking_data():
    """Gets the average scores for each difficulty level."""
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required.'}), 401
    
    user_id = session['user_id']
    tracking_data = database.get_tracking_stats(user_id)
    return jsonify(tracking_data)

if __name__ == '__main__':
    app.run(debug=True)
