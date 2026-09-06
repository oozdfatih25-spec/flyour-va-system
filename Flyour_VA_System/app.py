from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import requests

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///flyour_va.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- VERİTABANI MODELLERİ ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    callsign = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='PILOT')  # PILOT veya DISPATCHER
    flight_hours = db.Column(db.Float, default=0.0)

class Pirep(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pilot_callsign = db.Column(db.String(20), nullable=False)
    departure = db.Column(db.String(4), nullable=False)
    arrival = db.Column(db.String(4), nullable=False)
    aircraft = db.Column(db.String(20), nullable=False)
    flight_time = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='PENDING')  # PENDING, APPROVED, REJECTED

# --- ROTALAR / SAYFALAR ---

@app.route('/')
def home():
    return '''
    <div style="font-family: Arial; text-align: center; margin-top: 50px;">
        <h1>Flyover Virtual Airlines</h1>
        <p>Sistem Aktif!</p>
        <hr style="width: 50%;">
        <a href="/dispatcher/dashboard"><button style="padding: 10px 20px; margin: 5px;">Dispatcher Paneli</button></a>
        <a href="/dispatcher/ofp-calculator"><button style="padding: 10px 20px; margin: 5px;">OFP & Yakıt Hesabı</button></a>
    </div>
    '''

@app.route('/init-db')
def init_db():
    db.drop_all()
    db.create_all()
    
    # Varsayılan Hesaplar
    admin = User(callsign='DISP001', name='Fatih Ozdemir', role='DISPATCHER', flight_hours=150.0)
    pilot = User(callsign='FLY001', name='Ahmet Yilmaz', role='PILOT', flight_hours=25.5)
    
    db.session.add(admin)
    db.session.add(pilot)
    db.session.commit()
    
    return "<h1>Veritabanı Başarıyla Sıfırlandı ve Varsayılan Veriler Yüklendi!</h1><a href='/'>Anasayfaya Dön</a>"

# --- DISPATCHER MODÜLLERİ ---

@app.route('/dispatcher/dashboard')
def dispatcher_dashboard():
    pilots = User.query.all()
    pireps = Pirep.query.filter_eq(status='PENDING').all() if hasattr(Pirep.query, 'filter_eq') else Pirep.query.filter_by(status='PENDING').all()
    return render_template('dispatcher_dashboard.html', pilots=pilots, pireps=pireps)

@app.route('/dispatcher/ofp-calculator', methods=['GET', 'POST'])
def ofp_calculator():
    ofp_data = None
    metar_data = None
    
    if request.method == 'POST':
        dep = request.form.get('dep', '').upper()
        arr = request.form.get('arr', '').upper()
        aircraft = request.form.get('aircraft', 'A320')
        distance = float(request.form.get('distance', 300))
        
        # Basit Yakıt Hesabı (A320 için yakl. 2400 kg/saat)
        flight_time_hours = distance / 440.0
        trip_fuel = flight_time_hours * 2400
        contingency_fuel = trip_fuel * 0.05
        alternate_fuel = 1200.0
        final_reserve = 1000.0
        block_fuel = trip_fuel + contingency_fuel + alternate_fuel + final_reserve
        
        ofp_data = {
            'dep': dep,
            'arr': arr,
            'aircraft': aircraft,
            'distance': distance,
            'flight_time': round(flight_time_hours, 2),
            'trip_fuel': round(trip_fuel),
            'block_fuel': round(block_fuel)
        }
        
        # METAR Çekme
        if dep:
            try:
                res = requests.get(f"https://metar.vatsim.net/{dep}")
                if res.status_code == 200 and res.text:
                    metar_data = res.text
            except:
                metar_data = "METAR verisi alınamadı."
                
    return render_template('ofp_calculator.html', ofp=ofp_data, metar=metar_data)

if __name__ == '__main__':
    app.run(debug=True)
