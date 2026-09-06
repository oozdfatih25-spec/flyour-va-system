from flask import Flask, render_template, request, jsonify, session
import datetime

app = Flask(__name__)
app.secret_key = 'flyour-secret-key-change-this'

# ---------------------------------------------------------
# SİMÜLE EDİLEN VERİTABANI (MEMORY DATA)
# ---------------------------------------------------------

users = [
    {
        "id": 1,
        "pilot_id": "FLYOUR001",
        "name": "Fatih Özdemir",
        "email": "fatih@flyour.com",
        "password": "123",
        "flight_hours": 12.5,
        "rank": "Kaptan Pilot",
        "is_admin": True  # Sadece FLYOUR001 Admin!
    },
    {
        "id": 2,
        "pilot_id": "FLYOUR002",
        "name": "Ahmet Yılmaz",
        "email": "ahmet@flyour.com",
        "password": "123",
        "flight_hours": 5.0,
        "rank": "İkinci Pilot",
        "is_admin": False  # Normal Pilot
    }
]

routes = [
    {
        "id": 101,
        "assigned_pilot_id": "FLYOUR002",
        "flight_number": "FO102",
        "departure": "LTFM",
        "arrival": "LTAI",
        "aircraft": "A320"
    }
]

flight_reports = []

achievements = [
    {
        "pilot_id": "FLYOUR001",
        "badge_icon": "✈️",
        "title": "İlk Kanat",
        "description": "Flyour VA ailesine katıldı."
    }
]

announcements = [
    {
        "id": 1,
        "title": "Flyour VA Paneline Hoş Geldiniz!",
        "content": "Yeni uçuş raporlama ve duyuru sistemimiz aktif edilmiştir. Keyifli uçuşlar dileriz.",
        "date": "2026-09-06"
    }
]

# ---------------------------------------------------------
# SAYFA VE KULLANICI (AUTH) ROTALARI
# ---------------------------------------------------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    user_id = session.get('user_id')
    if user_id:
        user = next((u for u in users if u['id'] == user_id), None)
        if user:
            return jsonify({
                'authenticated': True,
                'user': {
                    'id': user['id'],
                    'pilot_id': user['pilot_id'],
                    'name': user['name'],
                    'flight_hours': user['flight_hours'],
                    'rank': user['rank'],
                    'is_admin': user.get('is_admin', False)
                }
            })
    return jsonify({'authenticated': False})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    pilot_id = data.get('pilot_id')
    password = data.get('password')

    user = next((u for u in users if u['pilot_id'].upper() == pilot_id.upper() and u['password'] == password), None)
    if user:
        session['user_id'] = user['id']
        return jsonify({'status': 'success', 'message': 'Giriş başarılı!'})
    
    return jsonify({'status': 'error', 'message': 'Hatalı Pilot ID veya Şifre!'}), 401

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    pilot_id = data.get('pilot_id').upper()
    
    if any(u['pilot_id'] == pilot_id for u in users):
        return jsonify({'status': 'error', 'message': 'Bu Pilot ID zaten kullanılıyor!'}), 400

    new_user = {
        "id": len(users) + 1,
        "pilot_id": pilot_id,
        "name": data.get('name'),
        "email": data.get('email'),
        "password": data.get('password'),
        "flight_hours": 0.0,
        "rank": "Öğrenci Pilot",
        "is_admin": False  # Yeni kayıt olanlar ASLA admin olamaz
    }
    users.append(new_user)
    return jsonify({'status': 'success', 'message': 'Kayıt başarıyla oluşturuldu! Giriş yapabilirsiniz.'})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'status': 'success'})

# ---------------------------------------------------------
# DUYURU ROTALARI
# ---------------------------------------------------------

@app.route('/api/announcements', methods=['GET'])
def get_announcements():
    return jsonify(announcements)

@app.route('/api/admin/add-announcement', methods=['POST'])
def add_announcement():
    user_id = session.get('user_id')
    user = next((u for u in users if u['id'] == user_id), None)
    
    if not user or not user.get('is_admin'):
        return jsonify({'status': 'error', 'message': 'Yetkisiz erişim!'}), 403
        
    data = request.json
    title = data.get('title')
    content = data.get('content')
    
    if not title or not content:
        return jsonify({'status': 'error', 'message': 'Lütfen tüm alanları doldurun!'}), 400
        
    new_ann = {
        "id": len(announcements) + 1,
        "title": title,
        "content": content,
        "date": datetime.date.today().strftime("%Y-%m-%d")
    }
    announcements.insert(0, new_ann)
    return jsonify({'status': 'success', 'message': 'Duyuru başarıyla yayınlandı!'})

# ---------------------------------------------------------
# UÇUŞ VE GÖREV (PIREP & ROUTE) ROTALARI
# ---------------------------------------------------------

@app.route('/api/my-routes', methods=['GET'])
def get_my_routes():
    user_id = session.get('user_id')
    user = next((u for u in users if u['id'] == user_id), None)
    if not user:
        return jsonify([])
    
    user_routes = [r for r in routes if r['assigned_pilot_id'] == user['pilot_id']]
    return jsonify(user_routes)

@app.route('/api/submit-flight', methods=['POST'])
def submit_flight():
    user_id = session.get('user_id')
    user = next((u for u in users if u['id'] == user_id), None)
    if not user:
        return jsonify({'status': 'error', 'message': 'Oturum açmanız gerekiyor!'}), 401

    data = request.json
    flight_time = float(data.get('flight_time', 0))
    
    # Pilotun uçuş saatini güncelle
    user['flight_hours'] += flight_time

    # Rapor veritabanına ekle
    report = {
        "id": len(flight_reports) + 1,
        "pilot_id": user['pilot_id'],
        "pilot_name": user['name'],
        "flight_number": data.get('flight_number'),
        "departure": data.get('departure'),
        "arrival": data.get('arrival'),
        "flight_time": flight_time
    }
    flight_reports.insert(0, report)

    # Eğer atanmış bir rotadan yapıldıysa listeden sil
    route_id = data.get('route_id')
    if route_id:
        global routes
        routes = [r for r in routes if str(r['id']) != str(route_id)]

    return jsonify({'status': 'success', 'message': 'Uçuş raporu başarıyla kaydedildi ve saatinize işlendi!'})

@app.route('/api/my-achievements', methods=['GET'])
def get_my_achievements():
    user_id = session.get('user_id')
    user = next((u for u in users if u['id'] == user_id), None)
    if not user:
        return jsonify([])
    
    user_ach = [a for a in achievements if a['pilot_id'] == user['pilot_id']]
    return jsonify(user_ach)

# ---------------------------------------------------------
# YÖNETİCİ (ADMIN) ROTALARI
# ---------------------------------------------------------

@app.route('/api/admin/reports', methods=['GET'])
def get_admin_reports():
    user_id = session.get('user_id')
    user = next((u for u in users if u['id'] == user_id), None)
    if not user or not user.get('is_admin'):
        return jsonify([]), 403
    return jsonify(flight_reports)

@app.route('/api/admin/assign-route', methods=['POST'])
def assign_route():
    user_id = session.get('user_id')
    user = next((u for u in users if u['id'] == user_id), None)
    if not user or not user.get('is_admin'):
        return jsonify({'status': 'error', 'message': 'Yetkisiz erişim!'}), 403

    data = request.json
    new_route = {
        "id": len(routes) + 101,
        "assigned_pilot_id": data.get('pilot_id').upper(),
        "flight_number": data.get('flight_number'),
        "departure": data.get('departure'),
        "arrival": data.get('arrival'),
        "aircraft": data.get('aircraft')
    }
    routes.append(new_route)
    return jsonify({'status': 'success', 'message': 'Rota pilotun paneline başarıyla atandı!'})

@app.route('/api/admin/give-award', methods=['POST'])
def give_award():
    user_id = session.get('user_id')
    user = next((u for u in users if u['id'] == user_id), None)
    if not user or not user.get('is_admin'):
        return jsonify({'status': 'error', 'message': 'Yetkisiz erişim!'}), 403

    data = request.json
    new_award = {
        "pilot_id": data.get('pilot_id').upper(),
        "badge_icon": "🏆",
        "title": data.get('title'),
        "description": data.get('description')
    }
    achievements.append(new_award)
    return jsonify({'status': 'success', 'message': 'Ödül pilota tanımlandı!'})

# ---------------------------------------------------------
# UYGULAMAYI BAŞLATMA
# ---------------------------------------------------------

if __name__ == '__main__':
    app.run(debug=True)
