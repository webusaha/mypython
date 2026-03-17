import os
import json
import zipfile
import time
import sqlite3
from io import BytesIO
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_file
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from jinja2 import Template
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'rahasia-banget-ini-ganti-ya-12345'
CORS(app)

# ========== KONFIGURASI SESSION UNTUK MULTI IP ==========
app.config['SESSION_COOKIE_DOMAIN'] = None  # Cookie berlaku untuk semua domain
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Izinkan cookie dari domain berbeda
app.config['REMEMBER_COOKIE_DOMAIN'] = None

CONFIG_FILE = 'sections.json'

# ========== SETUP FLASK-LOGIN ==========
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "Silakan login dulu untuk mengakses halaman ini."

# ========== DATABASE SETUP ==========
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS pending_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS calculations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tipe TEXT,
            input_data TEXT,
            hasil TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# ========== USER MODEL ==========
class User(UserMixin):
    def __init__(self, id, username, role='user'):
        self.id = id
        self.username = username
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT id, username, role FROM users WHERE id = ?", (user_id,))
    user_data = c.fetchone()
    conn.close()
    
    if user_data:
        return User(user_data[0], user_data[1], user_data[2])
    return None

# ========== FUNGSI BACA/TULIS CONFIG ==========
def read_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)

            # 🔧 AUTO FIX: Hero section
            if "hero" in config:
                hero = config["hero"]
                if "button1" in hero and isinstance(hero["button1"], dict):
                    if "text" in hero["button1"]:
                        hero["button1_text"] = hero["button1"]["text"]
                    if "link" in hero["button1"]:
                        hero["button1_link"] = hero["button1"]["link"]
                    del hero["button1"]
                if "button2" in hero and isinstance(hero["button2"], dict):
                    if "text" in hero["button2"]:
                        hero["button2_text"] = hero["button2"]["text"]
                    if "link" in hero["button2"]:
                        hero["button2_link"] = hero["button2"]["link"]
                    del hero["button2"]
                if "background" in hero:
                    if isinstance(hero["background"], dict) and "image" in hero["background"]:
                        if "background_image" not in hero:
                            hero["background_image"] = hero["background"]["image"]
                    else:
                        if "background_image" not in hero:
                            hero["background_image"] = hero["background"]
                    del hero["background"]
                if "bg" in hero:
                    if "background_image" not in hero:
                        hero["background_image"] = hero["bg"]
                    del hero["bg"]
                for key in list(hero.keys()):
                    if key.startswith('background_') and key != 'background_image':
                        del hero[key]
                if "background_image" not in hero:
                    hero["background_image"] = "/images/home-bg.jpg"
                config["hero"] = hero

            # 🔧 AUTO FIX: Tentang section
            if "tentang" in config:
                tentang = config["tentang"]
                if "judul" in tentang:
                    if isinstance(tentang["judul"], dict) and "utama" in tentang["judul"]:
                        if "judul_utama" not in tentang or not tentang["judul_utama"]:
                            tentang["judul_utama"] = tentang["judul"]["utama"]
                    del tentang["judul"]
                if "section" in tentang:
                    if isinstance(tentang["section"], dict) and "number" in tentang["section"]:
                        if "section_number" not in tentang or not tentang["section_number"]:
                            tentang["section_number"] = tentang["section"]["number"]
                    del tentang["section"]
                if "tab" in tentang:
                    del tentang["tab"]
                config["tentang"] = tentang

            # 🔧 AUTO FIX: Kontak section
            if "kontak" in config:
                kontak = config["kontak"]
                if "section" in kontak:
                    del kontak["section"]
                config["kontak"] = kontak

            return config

    except FileNotFoundError:
        return {
            "header": {"brand": "WEB USAHA", "menu": []},
            "hero": {
                "subtitle": "PEMBUATAN WEB / OPTIMASI WEB / SOCIAL MEDIA",
                "title": "WEB USAHA",
                "button1_text": "Layanan Kami",
                "button1_link": "#work",
                "button2_text": "Hubungi Kami",
                "button2_link": "#contact",
                "background_image": "/images/home-bg.jpg"
            },
            "layanan": [],
            "tentang": {},
            "tim": [],
            "portfolio": [],
            "harga": [],
            "kontak": {},
            "footer": {}
        }
    except Exception as e:
        print(f"Error membaca config: {e}")
        return {}

def save_config(data):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ========== ROUTES UTAMA ==========
@app.route('/')
def index():
    """Halaman publik website"""
    config = read_config()
    return render_template('index.html', config=config)

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard berdasarkan role"""
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('user_dashboard'))

@app.route('/admin-dashboard')
@login_required
def admin_dashboard():
    """Dashboard khusus admin"""
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('user_dashboard'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT id, username, created_at FROM pending_users ORDER BY created_at DESC")
    pending = c.fetchall()
    
    # Stats
    c.execute("SELECT COUNT(*) FROM users WHERE role = 'user'")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM pending_users")
    pending_users = c.fetchone()[0]
    
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    c.execute('''
        SELECT COUNT(DISTINCT user_id) 
        FROM calculations 
        WHERE created_at > ?
    ''', (yesterday,))
    active_users = c.fetchone()[0]
    
    conn.close()
    
    return render_template('admin_dashboard.html', 
                         pending=pending,
                         total_users=total_users,
                         pending_users=pending_users,
                         active_users=active_users)

@app.route('/user-dashboard')
@login_required
def user_dashboard():
    """Dashboard untuk user biasa"""
    return render_template('user_dashboard.html', username=current_user.username)

# ========== ROUTE ADMIN UNTUK APPROVE/REJECT ==========
@app.route('/approve/<int:user_id>')
@login_required
def approve_user(user_id):
    if current_user.role != 'admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT username, password FROM pending_users WHERE id = ?", (user_id,))
    user_data = c.fetchone()
    
    if user_data:
        username, password = user_data
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                  (username, password, 'user'))
        c.execute("DELETE FROM pending_users WHERE id = ?", (user_id,))
        conn.commit()
        flash(f'User {username} telah di-approve!', 'success')
    else:
        flash('User tidak ditemukan!', 'danger')
    
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/reject/<int:user_id>')
@login_required
def reject_user(user_id):
    if current_user.role != 'admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT username FROM pending_users WHERE id = ?", (user_id,))
    user_data = c.fetchone()
    
    if user_data:
        username = user_data[0]
        c.execute("DELETE FROM pending_users WHERE id = ?", (user_id,))
        conn.commit()
        flash(f'User {username} telah ditolak.', 'warning')
    else:
        flash('User tidak ditemukan!', 'danger')
    
    conn.close()
    return redirect(url_for('admin_dashboard'))

# ========== LOGIN/REGISTER ==========
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT id, username, password, role FROM users WHERE username = ?", (username,))
        user_data = c.fetchone()
        conn.close()
        
        if user_data and check_password_hash(user_data[2], password):
            user = User(user_data[0], user_data[1], user_data[3])
            login_user(user)
            flash('Login berhasil! Selamat datang.', 'success')
            
            if user_data[3] == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('user_dashboard'))
        else:
            flash('Username atau password salah!', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')
        
        if password != confirm:
            flash('Password tidak sama!', 'danger')
            return redirect(url_for('register'))
        
        if len(password) < 6:
            flash('Password minimal 6 karakter!', 'danger')
            return redirect(url_for('register'))
        
        hashed = generate_password_hash(password)
        
        try:
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute("INSERT INTO pending_users (username, password) VALUES (?, ?)", 
                     (username, hashed))
            conn.commit()
            conn.close()
            
            flash('Registrasi berhasil! Akun Anda akan diaktifkan oleh admin setelah disetujui.', 'success')
            return redirect(url_for('login'))
            
        except sqlite3.IntegrityError:
            flash('Username sudah digunakan!', 'danger')
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Anda telah logout.', 'info')
    return redirect(url_for('login'))

# ========== CMS EDITOR (KHUSUS ADMIN) ==========
@app.route('/editor')
@login_required
def editor():
    """Halaman CMS Editor - hanya admin"""
    if current_user.role != 'admin':
        flash('Akses ditolak! Halaman ini khusus admin.', 'danger')
        return redirect(url_for('dashboard'))
    
    config = read_config()
    return render_template('editor.html', config=config)

# ========== API UNTUK CMS ==========
@app.route('/api/sections', methods=['GET'])
@login_required
def get_sections():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    return jsonify(read_config())

@app.route('/api/section/<section_name>', methods=['GET', 'PUT'])
@login_required
def manage_section(section_name):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    config = read_config()
    
    if request.method == 'GET':
        return jsonify(config.get(section_name, {}))
    
    elif request.method == 'PUT':
        data = request.get_json()
        config[section_name] = data
        save_config(config)
        return jsonify({"status": "success", "message": f"Section {section_name} diperbarui"})

@app.route('/api/section/<section_name>/<int:index>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def manage_list_item(section_name, index):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    config = read_config()
    
    if section_name not in config or not isinstance(config[section_name], list):
        return jsonify({"error": "Section not found or not a list"}), 404
    
    if request.method == 'GET':
        if index < len(config[section_name]):
            return jsonify(config[section_name][index])
        return jsonify({"error": "Index out of range"}), 404
    
    elif request.method == 'PUT':
        data = request.get_json()
        if index < len(config[section_name]):
            config[section_name][index] = data
            save_config(config)
            return jsonify({"status": "success"})
        return jsonify({"error": "Index out of range"}), 404
    
    elif request.method == 'DELETE':
        if index < len(config[section_name]):
            del config[section_name][index]
            save_config(config)
            return jsonify({"status": "success"})
        return jsonify({"error": "Index out of range"}), 404

@app.route('/api/section/<section_name>/add', methods=['POST'])
@login_required
def add_list_item(section_name):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    config = read_config()
    
    if section_name not in config or not isinstance(config[section_name], list):
        return jsonify({"error": "Section not found or not a list"}), 404
    
    data = request.get_json()
    config[section_name].append(data)
    save_config(config)
    return jsonify({"status": "success", "index": len(config[section_name]) - 1})

# ========== EXPORT WEBSITE (KHUSUS ADMIN) ==========
@app.route('/export-website')
@login_required
def export_website():
    """Export website - hanya admin"""
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        memory_file = BytesIO()
        timestr = time.strftime("%Y%m%d-%H%M%S")
        zip_filename = f"website_{timestr}.zip"
        
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            templates_dir = os.path.join(app.root_path, 'templates')
            html_files = ['index.html', 'login.html', 'register.html', 'user_dashboard.html', 'admin_dashboard.html']
            config = read_config()
            
            for html_file in html_files:
                file_path = os.path.join(templates_dir, html_file)
                if os.path.exists(file_path):
                    if html_file == 'index.html':
                        export_path = os.path.join(templates_dir, 'index_export.html')
                        if os.path.exists(export_path):
                            with open(export_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            try:
                                template = Template(content)
                                rendered = template.render(config=config)
                                zipf.writestr('index.html', rendered.encode('utf-8'))
                            except:
                                zipf.writestr('index.html', content.encode('utf-8'))
                        else:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            try:
                                template = Template(content)
                                rendered = template.render(config=config)
                                zipf.writestr('index.html', rendered.encode('utf-8'))
                            except:
                                zipf.writestr('index.html', content.encode('utf-8'))
                    else:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        zipf.writestr(html_file, content.encode('utf-8'))
            
            static_dir = os.path.join(app.root_path, 'static')
            if os.path.exists(static_dir):
                for root, dirs, files in os.walk(static_dir):
                    for file in files:
                        if file.endswith(('.py', '.pyc', '.gitignore')):
                            continue
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, static_dir)
                        zipf.write(file_path, arcname=f'static/{rel_path}')
            
            readme = f"Website export - {time.strftime('%d %B %Y')}"
            zipf.writestr('README.txt', readme)
        
        memory_file.seek(0)
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_filename
        )
        
    except Exception as e:
        return f"Error: {str(e)}", 500

# ========== API ADMIN STATS ==========
@app.route('/api/admin/stats')
@login_required
def admin_stats():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM users WHERE role = 'user'")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM pending_users")
    pending_users = c.fetchone()[0]
    
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    c.execute('''
        SELECT COUNT(DISTINCT user_id) 
        FROM calculations 
        WHERE created_at > ?
    ''', (yesterday,))
    active_users = c.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'total_users': total_users,
        'pending_users': pending_users,
        'active_users': active_users
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)