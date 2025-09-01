# backend/app.py

from flask import Flask, request, jsonify, g
from flask_cors import CORS
import sqlite3
import os
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Path to the SQLite database file
DATABASE = os.path.join(app.root_path, 'stickies.db')


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
    Creates the stickies table if it does not exist.
    """
    with app.app_context():
        db = sqlite3.connect(DATABASE)
        cursor = db.cursor()
        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS stickies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT NOT NULL,
                color TEXT DEFAULT '#FFEB3B',
                position_x INTEGER DEFAULT 100,
                position_y INTEGER DEFAULT 100,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )
        db.commit()
        db.close()


@app.teardown_appcontext
def close_connection(exception):
    """
    Closes the database connection after each request.
    """
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


# ---------- API Endpoints ----------

@app.route('/api/stickies', methods=['GET'])
def get_stickies():
    """
    Retrieve all sticky notes.
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM stickies ORDER BY created_at DESC')
    rows = cursor.fetchall()
    stickies = []
    for row in rows:
        sticky = dict(row)
        sticky['position'] = {
            'x': sticky.pop('position_x', 100),
            'y': sticky.pop('position_y', 100)
        }
        stickies.append(sticky)
    return jsonify(stickies), 200


@app.route('/api/stickies', methods=['POST'])
def create_sticky():
    """
    Create a new sticky note.
    """
    data = request.get_json()
    if not data or 'content' not in data:
        return jsonify({'error': 'Content is required'}), 400

    title = data.get('title', '')
    content = data['content']
    color = data.get('color', '#FFEB3B')
    position = data.get('position', {'x': 100, 'y': 100})

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        '''INSERT INTO stickies (title, content, color, position_x, position_y) 
           VALUES (?, ?, ?, ?, ?)''',
        (title, content, color, position['x'], position['y'])
    )
    db.commit()
    sticky_id = cursor.lastrowid

    cursor.execute('SELECT * FROM stickies WHERE id = ?', (sticky_id,))
    row = cursor.fetchone()
    sticky = dict(row)
    sticky['position'] = {
        'x': sticky.pop('position_x', 100),
        'y': sticky.pop('position_y', 100)
    }
    return jsonify(sticky), 201


@app.route('/api/stickies/<int:sticky_id>', methods=['GET'])
def get_sticky(sticky_id):
    """
    Get a specific sticky note.
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM stickies WHERE id = ?', (sticky_id,))
    row = cursor.fetchone()
    
    if row is None:
        return jsonify({'error': 'Sticky not found'}), 404
    
    sticky = dict(row)
    sticky['position'] = {
        'x': sticky.pop('position_x', 100),
        'y': sticky.pop('position_y', 100)
    }
    return jsonify(sticky), 200


@app.route('/api/stickies/<int:sticky_id>', methods=['PUT'])
def update_sticky(sticky_id):
    """
    Update an existing sticky note.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM stickies WHERE id = ?', (sticky_id,))
    row = cursor.fetchone()
    
    if row is None:
        return jsonify({'error': 'Sticky not found'}), 404

    # Update fields if provided
    title = data.get('title', row['title'])
    content = data.get('content', row['content'])
    color = data.get('color', row['color'])
    position = data.get('position', {})
    position_x = position.get('x', row['position_x'])
    position_y = position.get('y', row['position_y'])

    cursor.execute(
        '''UPDATE stickies
           SET title = ?, content = ?, color = ?, position_x = ?, position_y = ?, 
               updated_at = CURRENT_TIMESTAMP
           WHERE id = ?''',
        (title, content, color, position_x, position_y, sticky_id)
    )
    db.commit()

    cursor.execute('SELECT * FROM stickies WHERE id = ?', (sticky_id,))
    updated_row = cursor.fetchone()
    sticky = dict(updated_row)
    sticky['position'] = {
        'x': sticky.pop('position_x', 100),
        'y': sticky.pop('position_y', 100)
    }
    return jsonify(sticky), 200


@app.route('/api/stickies/<int:sticky_id>', methods=['PATCH'])
def patch_sticky(sticky_id):
    """
    Partially update a sticky note (e.g., position only).
    """
    return update_sticky(sticky_id)  # Same logic as PUT for now


@app.route('/api/stickies/<int:sticky_id>', methods=['DELETE'])
def delete_sticky(sticky_id):
    """
    Delete a sticky note.
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM stickies WHERE id = ?', (sticky_id,))
    row = cursor.fetchone()
    
    if row is None:
        return jsonify({'error': 'Sticky not found'}), 404

    cursor.execute('DELETE FROM stickies WHERE id = ?', (sticky_id,))
    db.commit()
    return '', 204


@app.route('/api/stickies/export', methods=['GET'])
def export_stickies():
    """
    Export all sticky notes as JSON.
    """
    stickies, _ = get_stickies()
    stickies_data = json.loads(stickies.data)
    return jsonify({'stickies': stickies_data}), 200


@app.route('/api/stickies/import', methods=['POST'])
def import_stickies():
    """
    Import sticky notes from JSON.
    """
    data = request.get_json()
    if not data or 'stickies' not in data:
        return jsonify({'error': 'Invalid import data'}), 400

    db = get_db()
    cursor = db.cursor()
    
    imported_count = 0
    for sticky_data in data['stickies']:
        if 'content' in sticky_data:
            position = sticky_data.get('position', {'x': 100, 'y': 100})
            cursor.execute(
                '''INSERT INTO stickies (title, content, color, position_x, position_y) 
                   VALUES (?, ?, ?, ?, ?)''',
                (sticky_data.get('title', ''),
                 sticky_data['content'],
                 sticky_data.get('color', '#FFEB3B'),
                 position['x'],
                 position['y'])
            )
            imported_count += 1
    
    db.commit()
    return jsonify({'message': f'Imported {imported_count} sticky notes'}), 201


# ---------- Health Check ----------

@app.route('/health', methods=['GET'])
def health_check():
    """
    Simple health check endpoint.
    """
    return jsonify({'status': 'healthy', 'service': 'StickyBoard API'}), 200


# ---------- Run the App ----------

if __name__ == '__main__':
    # Initialize database
    init_db()
    # For development only. In production, use a WSGI server.
    app.run(debug=True, port=5000)