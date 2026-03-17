from flask import Flask, request, jsonify, render_template
import sqlite3, json, os

app = Flask(__name__)
DB = 'calcpro.db'

# ── Database setup ─────────────────────────────────────────────────────────────
def get_db():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.execute('''CREATE TABLE IF NOT EXISTS settings (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS history (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        expr       TEXT,
        result     TEXT,
        time       TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Default settings — ensure PIN is a string
    defaults = {
        'pin': '1234',
        'appName': 'CalcPro',
        'features': json.dumps({'showHistory': True,'showMemory': True,'showScientific': True,'showPercent': True,'showPlusMinus': True}),
        'lockedButtons': json.dumps({}),
        'adminOverrides': json.dumps({}),
    }

    for k, v in defaults.items():
        # Use INSERT OR REPLACE to ensure defaults are applied correctly
        db.execute('INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)', (k, json.dumps(str(v)) if k=='pin' else v))

    db.commit()
    db.close()

def get_setting(key):
    db = get_db()
    row = db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
    db.close()
    if not row:
        return None
    val = json.loads(row['value'])
    # Ensure PIN is always string
    if key == 'pin':
        val = str(val)
    return val

def set_setting(key, value):
    db = get_db()
    # Always store PIN as string
    if key == 'pin':
        value = str(value)
    db.execute('INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)', (key, json.dumps(value)))
    db.commit()
    db.close()

# ── Serve frontend ─────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

# ── API: Get all admin-controlled settings ─────────────────────────────────────
@app.route('/api/settings', methods=['GET'])
def api_get_settings():
    return jsonify({
        'appName': get_setting('appName'),
        'features': get_setting('features'),
        'lockedButtons': get_setting('lockedButtons'),
        'adminOverrides': get_setting('adminOverrides'),
    })

# ── API: Update settings (admin only — PIN required) ──────────────────────────
@app.route('/api/settings', methods=['POST'])
def api_update_settings():
    data = request.get_json()
    pin = str(data.get('pin',''))  # ensure PIN is string
    if pin != get_setting('pin'):
        return jsonify({'ok': False, 'error': 'Wrong PIN'}), 403
    allowed = ['appName','features','lockedButtons','adminOverrides']
    for key in allowed:
        if key in data:
            set_setting(key, data[key])
    return jsonify({'ok': True})

# ── API: Verify admin PIN ──────────────────────────────────────────────────────
@app.route('/api/verify-pin', methods=['POST'])
def api_verify_pin():
    data = request.get_json()
    pin = str(data.get('pin',''))
    ok = pin == get_setting('pin')
    return jsonify({'ok': ok})

# ── API: Change PIN ────────────────────────────────────────────────────────────
@app.route('/api/change-pin', methods=['POST'])
def api_change_pin():
    data = request.get_json()
    current_pin = str(data.get('currentPin',''))
    if current_pin != get_setting('pin'):
        return jsonify({'ok': False, 'error': 'Wrong current PIN'}), 403
    new_pin = str(data.get('newPin',''))
    if len(new_pin) != 4 or not new_pin.isdigit():
        return jsonify({'ok': False, 'error': 'PIN must be exactly 4 digits'}), 400
    set_setting('pin', new_pin)
    return jsonify({'ok': True})

# ── API: History ───────────────────────────────────────────────────────────────
@app.route('/api/history', methods=['GET'])
def api_get_history():
    db = get_db()
    rows = db.execute('SELECT expr,result,time FROM history ORDER BY id DESC LIMIT 50').fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/history', methods=['POST'])
def api_add_history():
    data = request.get_json()
    db = get_db()
    db.execute('INSERT INTO history (expr,result,time) VALUES (?,?,?)',
               (data.get('expr',''), data.get('result',''), data.get('time','')))
    db.commit()
    db.close()
    return jsonify({'ok': True})

@app.route('/api/history', methods=['DELETE'])
def api_clear_history():
    db = get_db()
    db.execute('DELETE FROM history')
    db.commit()
    db.close()
    return jsonify({'ok': True})

# ── API: Stats ─────────────────────────────────────────────────────────────────
@app.route('/api/stats', methods=['GET'])
def api_get_stats():
    db = get_db()
    total = db.execute('SELECT COUNT(*) as c FROM history').fetchone()['c']
    db.close()
    return jsonify({'total': total})

# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)  # debug=True for easier testing
