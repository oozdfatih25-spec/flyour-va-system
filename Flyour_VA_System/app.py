from flask import Flask, render_template, request, jsonify, session, send_from_directory
import os
from datetime import datetime, timedelta
import zoneinfo
import psycopg
from psycopg.rows import dict_row

app = Flask(__name__)

# Güvenli Gizli Anahtar ve Kalıcı Oturum (30 Gün)
app.secret_key = os.environ.get('SECRET_KEY', 'flyour_va_secret_key_2026_super_secure')
app.permanent_session_lifetime = timedelta(days=30)

# Türkiye Saat Dilimi (TRT - UTC+3)
TURKEY_TZ = zoneinfo.ZoneInfo("Europe/Istanbul")

def get_turkey_time():
    return datetime.now(TURKEY_TZ)

# Render PostgreSQL Bağlantı Adresi
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db():
    """
    DATABASE_URL varsa Render PostgreSQL'e, 
    yoksa yerel SQLite veritabanına bağlanır.
    """
    if DATABASE_URL:
        # PostgreSQL (psycopg v3)
        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        return conn
    else:
        # Local SQLite Fallback
        import sqlite3
        db_path = os.path.join(app.root_path, 'database.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    """
    Sistem ilk çalıştığında veritabanı tablosunu oluşturur.
    """
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
        conn.commit()
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

# Veritabanını Başlat
try:
    init_db()
except Exception as e:
    print("DB Init Error:", e)

# PWA ve Web Manifest Servisi
@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'manifest.json')

# Ana Sayfa Rrotası
@app.route('/')
def index():
    return render_template('index.html')

# Oturum ve Kullanıcı Doğrulama Arayüzü (API)
@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    if 'pilot_id' in session:
        conn = get_db()
        c = conn.cursor()
        
        query = 'SELECT pilot_id, name, flight_hours, rank FROM pilots WHERE pilot_id=%s' if DATABASE_URL else 'SELECT pilot_id, name, flight_hours, rank FROM pilots WHERE pilot_id=?'
        c.execute(query, (session['pilot_id'],))
        user = c.fetchone()
        conn.close()
        
        if user:
            # Dict erişimi (PostgreSQL ve SQLite uyumlu)
            return jsonify({
                'authenticated': True,
                'user': {
                    'pilot_id': user['pilot_id'] if DATABASE_URL else user['pilot_id'],
                    'name': user['name'] if DATABASE_URL else user['name'],
                    'flight_hours': user['flight_hours'] if DATABASE_URL else user['flight_hours'],
                    'rank': user['rank'] if DATABASE_URL else user['rank']
                }
            })
    return jsonify({'authenticated': False})

# Pilot Kayıt API
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
        return jsonify({'status': 'error', 'message': 'Bu Pilot ID zaten alınmış veya kayıt hatası oluştu.'})

# Pilot Giriş API
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    pilot_id = data.get('pilot_id', '').upper().strip()
    password = data.get('password')
    
    conn = get_db()
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

# Çıkış Yap API
@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(debug=True)
