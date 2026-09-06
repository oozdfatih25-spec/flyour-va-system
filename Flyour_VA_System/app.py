import os
import json
import urllib.request
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = 'flyour-va-secret-key-2026'

# Render ortamında varsayılan SQLite veritabanı yolu
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'flyour_va.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==========================================
# VERİTABANI MODELLERİ (DATABASE MODELS)
# ==========================================

class Pilot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    callsign = db.Column(db.String(20), unique=True, nullable=False) # Örn: FLY001
    name = db.Column(db.String(100), nullable=False)
    total_hours = db.Column(db.Float, default=0.0)
    pireps = db.relationship('Pirep', backref='pilot', lazy=True)

class Pirep(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pilot_id = db.Column(db.Integer, db.ForeignKey('pilot.id'), nullable=False)
    dep_icao = db.Column(db.String(4), nullable=False)
    arr_icao = db.Column(db.String(4), nullable=False)
    planned_flight_time = db.Column(db.Float, nullable=False) # Planlanan Süre (Saat)
    reported_flight_time = db.Column(db.Float, nullable=False) # Pilotun Bildirdiği Süre
    approved_flight_time = db.Column(db.Float, nullable=True)  # Dispatcher'ın Onayladığı Süre
    status = db.Column(db.String(20), default='PENDING')       # PENDING, APPROVED, REJECTED
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ==========================================
# YARDIMCI FONKSİYONLAR
# ==========================================

def get_metar(icao_code):
    """Aviation Weather API üzerinden canlı METAR verisi çeker."""
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
# ROTALAR VE PANEL FONKSİYONLARI
# ==========================================

# Ana Sayfa
@app.route('/')
def home():
    return render_template('index.html')

# 1. API: CANLI METAR SORGULAMA
@app.route('/api/metar/<icao>')
def api_metar(icao):
    metar_text = get_metar(icao)
    return jsonify({"icao": icao.upper(), "metar": metar_text})

# 2. DISPATCHER OFP & YAKIT / AĞIRLIK HESAPLAYICI
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
        
        # A320 / B738 Tipi Dar Gövde Yakıt & Yük Hesabı:
        pax_weight = pax * 84.0 # Yolcu + Kabin Bagajı
        payload = pax_weight + cargo_kg
        
        trip_fuel = distance * 4.5
        alternate_fuel = 1200.0
        reserve_fuel = 1500.0
        taxi_fuel = 200.0
        
        block_fuel = trip_fuel + alternate_fuel + reserve_fuel + taxi_fuel
        
        # Canlı METAR Verileri
        dep_metar = get_metar(dep)
        arr_metar = get_metar(arr)
        alt_metar = get_metar(alt)
        
        result = {
            "dep": dep, "arr": arr, "alt": alt,
            "distance": distance, "pax": pax, "payload": payload,
            "trip_fuel": round(trip_fuel, 1),
            "alternate_fuel": round(alternate_fuel, 1),
            "reserve_fuel": round(reserve_fuel, 1),
            "block_fuel": round(block_fuel, 1),
            "dep_metar": dep_metar,
            "arr_metar": arr_metar,
            "alt_metar": alt_metar
        }
    return render_template('ofp_calculator.html', result=result)

# 3. DISPATCHER DASHBOARD (ONAY BEKLEYEN PIREP'LER)
@app.route('/dispatcher/dashboard')
def dispatcher_dashboard():
    pending_pireps = Pirep.query.filter_by(status='PENDING').all()
    return render_template('dispatcher_dashboard.html', pireps=pending_pireps)

# 4. DISPATCHER PIREP ONAY / REDDET / SÜRE DÜZELTME
@app.route('/dispatcher/review-pirep/<int:pirep_id>', methods=['POST'])
def review_pirep(pirep_id):
    pirep = Pirep.query.get_or_404(pirep_id)
    action = request.form.get('action') # 'approve' veya 'reject'
    custom_time = request.form.get('custom_flight_time') # Dispatcher'ın elle girdiği süre

    if action == 'approve':
        if custom_time and custom_time.strip() != "":
            final_hours = float(custom_time)
        else:
            final_hours = pirep.reported_flight_time

        pirep.approved_flight_time = final_hours
        pirep.status = 'APPROVED'

        # Pilotun toplam saatini güncelle
        pilot = Pilot.query.get(pirep.pilot_id)
        if pilot:
            pilot.total_hours = round(pilot.total_hours + final_hours, 2)

        flash(f"PIREP başarıyla onaylandı! Pilota {final_hours} saat eklendi.", "success")

    elif action == 'reject':
        pirep.status = 'REJECTED'
        flash("PIREP reddedildi.", "danger")

    db.session.commit()
    return redirect(url_for('dispatcher_dashboard'))

# TEST / İLK KURULUM ROTASI
@app.route('/init-db')
def init_db():
    db.create_all()
    if not Pilot.query.filter_by(callsign='FLY001').first():
        sample_pilot = Pilot(callsign='FLY001', name='Fatih Özdemir', total_hours=10.0)
        db.session.add(sample_pilot)
        db.session.commit()
        
        sample_pirep = Pirep(
            pilot_id=sample_pilot.id,
            dep_icao='LTFM',
            arr_icao='LTAI',
            planned_flight_time=1.2,
            reported_flight_time=2.8 # 1.6 saatlik aşım uyarısı için örnek
        )
        db.session.add(sample_pirep)
        db.session.commit()
        return "Veritabanı oluşturuldu ve test verileri yüklendi!"
    return "Veritabanı zaten hazır."

# TABLOLARI OTOMATİK OLUŞTURMA
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
