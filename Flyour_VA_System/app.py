import os
import json
import urllib.request
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = 'flyour-va-secret-key-2026'

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'flyour_va.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==========================================
# VERİTABANI MODELLERİ
# ==========================================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    callsign = db.Column(db.String(20), unique=True, nullable=False) # Örn: FLY001 veya DISP001
    name = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='PILOT') # 'PILOT' veya 'DISPATCHER'
    total_hours = db.Column(db.Float, default=0.0)
    pireps = db.relationship('Pirep', backref='user', lazy=True)

class Pirep(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    dep_icao = db.Column(db.String(4), nullable=False)
    arr_icao = db.Column(db.String(4), nullable=False)
    planned_flight_time = db.Column(db.Float, nullable=False)
    reported_flight_time = db.Column(db.Float, nullable=False)
    approved_flight_time = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), default='PENDING')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def get_metar(icao_code):
    if not icao_code:
        return "Meydan girilmedi."
    icao_code = icao_code.strip().upper()
    url = f"https://aviationweather.gov/api/data/metar?ids={icao_code}&format=json"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            if data and len(data) > 0:
                return data[0].get("rawOb", "METAR verisi bulunamadı.")
            return "METAR verisi bulunamadı."
    except Exception as e:
        return f"Hava durumu verisi alınamadı: {str(e)}"

# ==========================================
# GİRİŞ, KAYIT VE ÇIKIŞ ROTALARI
# ==========================================

@app.route('/')
def home():
    user = User.query.get(session.get('user_id')) if 'user_id' in session else None
    return render_template('index.html', user=user)

# KAYIT OLMA (REGISTER)
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        callsign = request.form.get('callsign', '').upper()
        name = request.form.get('name')
        password = request.form.get('password')
        role = request.form.get('role', 'PILOT') # PILOT veya DISPATCHER

        existing_user = User.query.filter_by(callsign=callsign).first()
        if existing_user:
            flash('Bu Callsign zaten kullanımda!', 'danger')
            return redirect(url_for('register'))

        new_user = User(callsign=callsign, name=name, password=password, role=role)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Kayıt başarılı! Şimdi giriş yapabilirsiniz.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

# GİRİŞ YAPMA (LOGIN)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        callsign = request.form.get('callsign', '').upper()
        password = request.form.get('password')

        user = User.query.filter_by(callsign=callsign, password=password).first()
        if user:
            session['user_id'] = user.id
            session['callsign'] = user.callsign
            session['role'] = user.role
            flash(f'Hoş geldin {user.name}!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Callsign veya şifre hatalı!', 'danger')

    return render_template('login.html')

# ÇIKIŞ YAPMA (LOGOUT)
@app.route('/logout')
def logout():
    session.clear()
    flash('Çıkış yapıldı.', 'info')
    return redirect(url_for('login'))

# ==========================================
# DISPATCHER VE SİSTEM ROTALARI
# ==========================================

@app.route('/dispatcher/ofp-calculator', methods=['GET', 'POST'])
def ofp_calculator():
    result = None
    if request.method == 'POST':
        dep = request.form.get('dep_icao', '').upper()
        arr = request.form.get('arr_icao', '').upper()
        alt = request.form.get('alt_icao', '').upper()
        distance = float(request.form.get('distance_nm', 0))
        pax = int(request.form.get('pax_count', 0))
        cargo_kg = float(request.form.get('cargo_kg', 0))
        
        pax_weight = pax * 84.0
        payload = pax_weight + cargo_kg
        
        trip_fuel = distance * 4.5
        alternate_fuel = 1200.0
        reserve_fuel = 1500.0
        taxi_fuel = 200.0
        block_fuel = trip_fuel + alternate_fuel + reserve_fuel + taxi_fuel
        
        result = {
            "dep": dep, "arr": arr, "alt": alt,
            "distance": distance, "pax": pax, "payload": payload,
            "trip_fuel": round(trip_fuel, 1),
            "alternate_fuel": round(alternate_fuel, 1),
            "reserve_fuel": round(reserve_fuel, 1),
            "block_fuel": round(block_fuel, 1),
            "dep_metar": get_metar(dep),
            "arr_metar": get_metar(arr),
            "alt_metar": get_metar(alt)
        }
    return render_template('ofp_calculator.html', result=result)

@app.route('/dispatcher/dashboard')
def dispatcher_dashboard():
    if session.get('role') != 'DISPATCHER':
        flash('Bu alana sadece Dispatcher erişebilir!', 'danger')
        return redirect(url_for('home'))
    pending_pireps = Pirep.query.filter_by(status='PENDING').all()
    return render_template('dispatcher_dashboard.html', pireps=pending_pireps)

@app.route('/init-db')
def init_db():
    db.drop_all() # Eski hatalı tabloları temizler
    db.create_all()
    
    # Otomatik Senin Adına Hesap Oluşturur:
    admin_user = User(callsign='DISP001', name='Fatih Özdemir', password='123', role='DISPATCHER')
    pilot_user = User(callsign='FLY001', name='Fatih Özdemir', password='123', role='PILOT')
    
    db.session.add(admin_user)
    db.session.add(pilot_user)
    db.session.commit()
    return "Sistem ve Veritabanı Sıfırlandı! Yeni hesaplar tanımlandı."

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
