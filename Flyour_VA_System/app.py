from flask import Flask, render_template, request, jsonify, send_from_directory
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'flyour_secret_key_2026'

def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS pilots 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  pilot_id TEXT UNIQUE, 
                  name TEXT, 
                  email TEXT, 
                  password TEXT, 
                  flight_hours REAL DEFAULT 0.0,
                  rank TEXT DEFAULT 'First Officer')''')
    conn.commit()
    conn.close()

init_db()

@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'manifest.json')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    pilot_id = data.get('pilot_id')
    
    try:
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('INSERT INTO pilots (pilot_id, name, email, password) VALUES (?, ?, ?, ?)',
                  (pilot_id, name, email, password))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'message': 'Kayıt başarılı! Giriş yapabilirsiniz.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Bu Pilot ID zaten kullanımda!'})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    pilot_id = data.get('pilot_id')
    password = data.get('password')
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT pilot_id, name, flight_hours, rank FROM pilots WHERE pilot_id=? AND password=?', (pilot_id, password))
    user = c.fetchone()
    conn.close()
    
    if user:
        return jsonify({
            'status': 'success',
            'user': {
                'pilot_id': user[0],
                'name': user[1],
                'flight_hours': user[2],
                'rank': user[3]
            }
        })
    else:
        return jsonify({'status': 'error', 'message': 'Hatalı Pilot ID veya Şifre!'})

if __name__ == '__main__':
    app.run(debug=True)
