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
    if DATABASE_URL:
        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        return conn
    else:
        import sqlite3
        db_path = os.path.join(app.root_path, 'database.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    if DATABASE_URL:
        # Pilotlar Tablosu
        c.execute('''CREATE TABLE IF NOT EXISTS pilots 
                     (id SERIAL PRIMARY KEY, 
                      pilot_id VARCHAR(50) UNIQUE NOT NULL, 
                      name VARCHAR(100) NOT NULL, 
                      email VARCHAR(100), 
                      password VARCHAR(255) NOT NULL, 
                      flight_hours REAL DEFAULT 0.0,
                      rank VARCHAR(50) DEFAULT 'Captain',
                      is_admin BOOLEAN DEFAULT FALSE)''')
        
        # Rotalar Tablosu
        c.execute('''CREATE TABLE IF NOT EXISTS routes 
                     (id SERIAL PRIMARY KEY, 
                      flight_number VARCHAR(20) NOT NULL, 
                      departure VARCHAR(10) NOT NULL, 
                      arrival VARCHAR(10) NOT NULL, 
                      aircraft VARCHAR(50) NOT NULL, 
                      assigned_pilot_id VARCHAR(50))''')

        # Uçuş Raporları Tablosu
        c.execute('''CREATE TABLE IF NOT EXISTS flight_reports 
                     (id SERIAL PRIMARY KEY, 
                      pilot_id VARCHAR(50) NOT NULL, 
                      flight_number VARCHAR(20) NOT NULL, 
                      departure VARCHAR(10) NOT NULL, 
                      arrival VARCHAR(10) NOT NULL, 
                      flight_time REAL NOT NULL, 
                      status VARCHAR(20) DEFAULT 'Approved', 
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

        # Ödüller & Başarılar Tablosu
        c.execute('''CREATE TABLE IF NOT EXISTS achievements 
                     (id SERIAL PRIMARY KEY, 
                      pilot_id VARCHAR(50) NOT NULL, 
                      title VARCHAR(100) NOT NULL, 
                      description TEXT, 
                      badge_icon VARCHAR(50) DEFAULT '🏆')''')
        conn.commit()
    else:
        c.execute('''CREATE TABLE IF NOT EXISTS pilots 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, pilot_id TEXT UNIQUE, name TEXT, email TEXT, password TEXT, flight_hours REAL DEFAULT 0.0, rank TEXT DEFAULT 'Captain', is_admin BOOLEAN DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS routes 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, flight_number TEXT, departure TEXT, arrival TEXT, aircraft TEXT, assigned_pilot_id TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS flight_reports 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, pilot_id TEXT, flight_number TEXT, departure TEXT, arrival TEXT, flight_time REAL, status TEXT DEFAULT 'Approved', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        c.execute('''CREATE TABLE IF NOT EXISTS achievements 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, pilot_id TEXT, title TEXT, description TEXT, badge_icon TEXT DEFAULT '🏆')''')
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

# Oturum Kontrolü (FLYOUR001 Otomatik Admin Tanımlama)
@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    if 'pilot_id' in session:
        conn = get_db()
        c = conn.cursor()
        query = 'SELECT pilot_id, name, flight_hours, rank, is_admin FROM pilots WHERE pilot_id=%s' if DATABASE_URL else 'SELECT pilot_id, name, flight_hours, rank, is_admin FROM pilots WHERE pilot_id=?'
        c.execute(query, (session['pilot_id'],))
        user = c.fetchone()
        conn.close()
        
        if user:
            # FLYOUR001 özel kontrolü
            is_admin = True if user['pilot_id'] == 'FLYOUR001' else bool(user['is_admin'])
            return jsonify({
                'authenticated': True,
                'user': {
                    'pilot_id': user['pilot_id'],
                    'name': user['name'],
                    'flight_hours': user['flight_hours'],
                    'rank': user['rank'],
                    'is_admin': is_admin
                }
            })
    return jsonify({'authenticated': False})

# Kayıt API
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
        
        # Eğer kaydolmaya çalışan id FLYOUR001 ise doğrudan Admin yetkisi tanımla
        is_admin = True if pilot_id == 'FLYOUR001' else False

        query = 'INSERT INTO pilots (pilot_id, name, email, password, is_admin) VALUES (%s, %s, %s, %s, %s)' if DATABASE_URL else 'INSERT INTO pilots (pilot_id, name, email, password, is_admin) VALUES (?, ?, ?, ?, ?)'
        c.execute(query, (pilot_id, name, email, password, is_admin))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'message': 'Kayıt başarılı! Şimdi giriş yapabilirsiniz.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Bu Pilot ID zaten alınmış veya kayıt hatası oluştu.'})

# Giriş API (FLYOUR001 Yetki Doğrulama)
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    pilot_id = data.get('pilot_id', '').upper().strip()
    password = data.get('password')
    
    conn = get_db()
    c = conn.cursor()
    query = 'SELECT pilot_id, name, flight_hours, rank, is_admin FROM pilots WHERE pilot_id=%s AND password=%s' if DATABASE_URL else 'SELECT pilot_id, name, flight_hours, rank, is_admin FROM pilots WHERE pilot_id=? AND password=?'
    c.execute(query, (pilot_id, password))
    user = c.fetchone()
    conn.close()
    
    if user:
        session.permanent = True
        session['pilot_id'] = user['pilot_id']
        
        # FLYOUR001 girişi yapıldığında oturuma admin yetkisini sabitle
        is_admin_user = True if user['pilot_id'] == 'FLYOUR001' else bool(user['is_admin'])
        session['is_admin'] = is_admin_user
        
        return jsonify({
            'status': 'success',
            'user': {
                'pilot_id': user['pilot_id'],
                'name': user['name'],
                'flight_hours': user['flight_hours'],
                'rank': user['rank'],
                'is_admin': is_admin_user
            }
        })
    else:
        return jsonify({'status': 'error', 'message': 'Hatalı Pilot ID veya Şifre!'})

# Çıkış API
@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'status': 'success'})

# --- PİLOT KİŞİSEL İŞLEMLERİ ---

# Uçuş Raporu Kaydetme (Saat Ekleme)
@app.route('/api/submit-flight', methods=['POST'])
def submit_flight():
    if 'pilot_id' not in session:
        return jsonify({'status': 'error', 'message': 'Oturum açmanız gerekiyor.'})
    
    data = request.json
    flight_number = data.get('flight_number')
    departure = data.get('departure', '').upper().strip()
    arrival = data.get('arrival', '').upper().strip()
    flight_time = float(data.get('flight_time', 0))

    conn = get_db()
    c = conn.cursor()
    
    query_report = 'INSERT INTO flight_reports (pilot_id, flight_number, departure, arrival, flight_time) VALUES (%s, %s, %s, %s, %s)' if DATABASE_URL else 'INSERT INTO flight_reports (pilot_id, flight_number, departure, arrival, flight_time) VALUES (?, ?, ?, ?, ?)'
    c.execute(query_report, (session['pilot_id'], flight_number, departure, arrival, flight_time))
    
    query_update = 'UPDATE pilots SET flight_hours = flight_hours + %s WHERE pilot_id = %s' if DATABASE_URL else 'UPDATE pilots SET flight_hours = flight_hours + ? WHERE pilot_id = ?'
    c.execute(query_update, (flight_time, session['pilot_id']))
    
    conn.commit()
    conn.close()
    return jsonify({'status': 'success', 'message': 'Uçuş raporu kaydedildi ve uçuş saatinize eklendi!'})

# Kendisine Atanan Rotalar
@app.route('/api/my-routes', methods=['GET'])
def get_my_routes():
    if 'pilot_id' not in session:
        return jsonify([])
    
    conn = get_db()
    c = conn.cursor()
    query = 'SELECT flight_number, departure, arrival, aircraft FROM routes WHERE assigned_pilot_id = %s' if DATABASE_URL else 'SELECT flight_number, departure, arrival, aircraft FROM routes WHERE assigned_pilot_id = ?'
    c.execute(query, (session['pilot_id'],))
    routes = c.fetchall()
    conn.close()
    
    return jsonify([{'flight_number': r['flight_number'], 'departure': r['departure'], 'arrival': r['arrival'], 'aircraft': r['aircraft']} for r in routes])

# Kendisine Verilen Ödüller
@app.route('/api/my-achievements', methods=['GET'])
def get_my_achievements():
    if 'pilot_id' not in session:
        return jsonify([])
    
    conn = get_db()
    c = conn.cursor()
    query = 'SELECT title, description, badge_icon FROM achievements WHERE pilot_id = %s' if DATABASE_URL else 'SELECT title, description, badge_icon FROM achievements WHERE pilot_id = ?'
    c.execute(query, (session['pilot_id'],))
    achievements = c.fetchall()
    conn.close()
    
    return jsonify([{'title': a['title'], 'description': a['description'], 'badge_icon': a['badge_icon']} for a in achievements])

# --- FLYOUR001 ÖZEL YÖNETİCİ (ADMIN) API'LERİ ---

# Tüm Pilotları ve Şifreleri Görme (Sadece FLYOUR001 Görür)
@app.route('/api/admin/pilots', methods=['GET'])
def admin_get_pilots():
    if session.get('pilot_id') != 'FLYOUR001' and not session.get('is_admin'):
        return jsonify({'status': 'error', 'message': 'Bu alana sadece Yönetici (FLYOUR001) erişebilir!'}), 403
    
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id, pilot_id, name, email, password, flight_hours, rank, is_admin FROM pilots')
    pilots = c.fetchall()
    conn.close()
    return jsonify([dict(p) for p in pilots])

# Özel Rota Atama (Sadece FLYOUR001)
@app.route('/api/admin/assign-route', methods=['POST'])
def assign_route():
    if session.get('pilot_id') != 'FLYOUR001' and not session.get('is_admin'):
        return jsonify({'status': 'error', 'message': 'Yetkisiz erişim!'}), 403

    data = request.json
    flight_number = data.get('flight_number')
    departure = data.get('departure', '').upper()
    arrival = data.get('arrival', '').upper()
    aircraft = data.get('aircraft')
    assigned_pilot_id = data.get('pilot_id', '').upper()

    conn = get_db()
    c = conn.cursor()
    query = 'INSERT INTO routes (flight_number, departure, arrival, aircraft, assigned_pilot_id) VALUES (%s, %s, %s, %s, %s)' if DATABASE_URL else 'INSERT INTO routes (flight_number, departure, arrival, aircraft, assigned_pilot_id) VALUES (?, ?, ?, ?, ?)'
    c.execute(query, (flight_number, departure, arrival, aircraft, assigned_pilot_id))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success', 'message': f'{assigned_pilot_id} idli pilota rota tanımlandı!'})

# Ödül / Rozet Tanımlama (Sadece FLYOUR001)
@app.route('/api/admin/give-award', methods=['POST'])
def give_award():
    if session.get('pilot_id') != 'FLYOUR001' and not session.get('is_admin'):
        return jsonify({'status': 'error', 'message': 'Yetkisiz erişim!'}), 403

    data = request.json
    pilot_id = data.get('pilot_id', '').upper()
    title = data.get('title')
    description = data.get('description')
    badge_icon = data.get('badge_icon', '🏆')

    conn = get_db()
    c = conn.cursor()
    query = 'INSERT INTO achievements (pilot_id, title, description, badge_icon) VALUES (%s, %s, %s, %s)' if DATABASE_URL else 'INSERT INTO achievements (pilot_id, title, description, badge_icon) VALUES (?, ?, ?, ?)'
    c.execute(query, (pilot_id, title, description, badge_icon))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success', 'message': f'{pilot_id} idli pilota ödül tanımlandı!'})

if __name__ == '__main__':
    app.run(debug=True)
