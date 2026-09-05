from flask import Flask, render_template, request, jsonify, session, send_from_directory
import os
from datetime import timedelta
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'flyour_va_secret_key_2026_super_secure')
app.permanent_session_lifetime = timedelta(days=30)

# Veritabanı Adresi (Render'daki DATABASE_URL, yoksa fallback SQLite/Local)
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db():
    if DATABASE_URL:
        # Render PostgreSQL Bağlantısı
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        return conn
    else:
        # Yerel geliştirme için SQLite alternatifi
        import sqlite3
        db_path = os.path.join(app.root_path, 'database.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    if DATABASE_URL:
        c.execute('''CREATE TABLE IF NOT EXISTS pilots 
                     (id SERIAL PRIMARY KEY, 
                      pilot_id VARCHAR(50) UNIQUE NOT NULL, 
                      name VARCHAR(100) NOT NULL, 
                      email VARCHAR(100), 
                      password VARCHAR(255) NOT NULL, 
                      flight_hours REAL DEFAULT 0.0,
                      rank VARCHAR(50) DEFAULT 'First Officer')''')
    else:
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

try:
    init_db()
except Exception as e:
    print("DB Init Error:", e)

@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'manifest.json')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    if 'pilot_id' in session:
        conn = get_db()
        if DATABASE_URL:
            c = conn.cursor(cursor_factory=RealDictCursor)
        else:
            c = conn.cursor()
            
        c.execute('SELECT pilot_id, name, flight_hours, rank FROM pilots WHERE pilot_id=%s' if DATABASE_URL else 'SELECT pilot_id, name, flight_hours, rank FROM pilots WHERE pilot_id=?', (session['pilot_id'],))
        user = c.fetchone()
        conn.close()
        
        if user:
            return jsonify({
                'authenticated': True,
                'user': {
                    'pilot_id': user['pilot_id'],
                    'name': user['name'],
                    'flight_hours': user['flight_hours'],
                    'rank': user['rank']
                }
            })
    return jsonify({'authenticated': False})

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    pilot_id = data.get('pilot_id', '').upper().strip()
    
    if not pilot_id or not password or not name:
        return jsonify({'status': 'error', 'message': 'Lütfen tüm alanları doldurun!'})

    try:
        conn = get_db()
        c = conn.cursor()
        query = 'INSERT INTO pilots (pilot_id, name, email, password) VALUES (%s, %s, %s, %s)' if DATABASE_URL else 'INSERT INTO pilots (pilot_id, name, email, password) VALUES (?, ?, ?, ?)'
        c.execute(query, (pilot_id, name, email, password))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'message': 'Kayıt başarılı! Şimdi giriş yapabilirsiniz.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Bu Pilot ID zaten alınmış veya bir kayıt hatası oluştu.'})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    pilot_id = data.get('pilot_id', '').upper().strip()
    password = data.get('password')
    
    conn = get_db()
    if DATABASE_URL:
        c = conn.cursor(cursor_factory=RealDictCursor)
    else:
        c = conn.cursor()
        
    query = 'SELECT pilot_id, name, flight_hours, rank FROM pilots WHERE pilot_id=%s AND password=%s' if DATABASE_URL else 'SELECT pilot_id, name, flight_hours, rank FROM pilots WHERE pilot_id=? AND password=?'
    c.execute(query, (pilot_id, password))
    user = c.fetchone()
    conn.close()
    
    if user:
        session.permanent = True
        session['pilot_id'] = user['pilot_id']
        return jsonify({
            'status': 'success',
            'user': {
                'pilot_id': user['pilot_id'],
                'name': user['name'],
                'flight_hours': user['flight_hours'],
                'rank': user['rank']
            }
        })
    else:
        return jsonify({'status': 'error', 'message': 'Hatalı Pilot ID veya Şifre!'})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(debug=True)
