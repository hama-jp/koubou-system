# backend/app.py

from flask import Flask, request, jsonify, g
from flask_cors import CORS
import sqlite3
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Path to the SQLite database file
DATABASE = os.path.join(app.root_path, 'notes.db')


def get_db():
    """
    Returns a database connection for the current request context.
    """
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row  # Return rows as dictionaries
    return db


def init_db():
    """
    Creates the notes table if it does not exist.
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )
    db.commit()


@app.teardown_appcontext
def close_connection(exception):
    """
    Closes the database connection after each request.
    """
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


@app.before_first_request
def before_first_request():
    """
    Initialize the database before handling the first request.
    """
    init_db()


# ---------- API Endpoints ----------

@app.route('/api/notes', methods=['GET'])
def get_notes():
    """
    Retrieve all notes, ordered by last updated time.
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM notes ORDER BY updated_at DESC')
    rows = cursor.fetchall()
    notes = [dict(row) for row in rows]
    return jsonify(notes), 200


@app.route('/api/notes', methods=['POST'])
def create_note():
    """
    Create a new note.
    Expected JSON body: { "title": "string", "content": "string" }
    """
    data = request.get_json()
    if not data or 'title' not in data:
        return jsonify({'error': 'Title is required'}), 400

    title = data['title']
    content = data.get('content', '')

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        'INSERT INTO notes (title, content) VALUES (?, ?)',
        (title, content)
    )
    db.commit()
    note_id = cursor.lastrowid

    cursor.execute('SELECT * FROM notes WHERE id = ?', (note_id,))
    row = cursor.fetchone()
    return jsonify(dict(row)), 201


@app.route('/api/notes/<int:note_id>', methods=['PUT'])
def update_note(note_id):
    """
    Update an existing note.
    Expected JSON body can contain "title" and/or "content".
    """
    data = request.get_json()
    if not data or ('title' not in data and 'content' not in data):
        return jsonify({'error': 'Nothing to update'}), 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM notes WHERE id = ?', (note_id,))
    row = cursor.fetchone()
    if row is None:
        return jsonify({'error': 'Note not found'}), 404

    new_title = data.get('title', row['title'])
    new_content = data.get('content', row['content'])

    cursor.execute(
        '''
        UPDATE notes
        SET title = ?, content = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        ''',
        (new_title, new_content, note_id)
    )
    db.commit()

    cursor.execute('SELECT * FROM notes WHERE id = ?', (note_id,))
    updated_row = cursor.fetchone()
    return jsonify(dict(updated_row)), 200


@app.route('/api/notes/<int:note_id>', methods=['DELETE'])
def delete_note(note_id):
    """
    Delete a note by ID.
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM notes WHERE id = ?', (note_id,))
    row = cursor.fetchone()
    if row is None:
        return jsonify({'error': 'Note not found'}), 404

    cursor.execute('DELETE FROM notes WHERE id = ?', (note_id,))
    db.commit()
    return jsonify({'message': f'Note {note_id} deleted'}), 200


# ---------- Run the App ----------

if __name__ == '__main__':
    # For development only. In production, use a WSGI server.
    app.run(debug=True)