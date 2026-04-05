"""
2DEXY Dashboard — Live API Server
Serves dashboard HTML + real API endpoints backed by SQLite.
Endpoints match what the dashboard expects.
2DEXY ColdPath can POST data here for live updates.
"""

import json
import time
import sqlite3
import hashlib
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

DB_PATH = '/data/2dexy.db'
STARTED_AT = time.time()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL,
            side TEXT NOT NULL CHECK(side IN ('buy','sell')),
            amount REAL NOT NULL DEFAULT 0,
            pnl REAL DEFAULT 0,
            outcome TEXT,
            timestamp TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL,
            action TEXT NOT NULL CHECK(action IN ('buy','sell')),
            confidence REAL DEFAULT 0,
            score REAL DEFAULT 0,
            features TEXT,
            timestamp TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS rug_stats (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            tokens_scanned INTEGER DEFAULT 0,
            rugs_caught INTEGER DEFAULT 0,
            safe_passed INTEGER DEFAULT 0,
            detection_rate REAL DEFAULT 0,
            false_alarm_rate REAL DEFAULT 0,
            last_updated TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT DEFAULT 'info',
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL DEFAULT (datetime('now'))
        );
        -- Initialize config defaults
        INSERT OR IGNORE INTO config (key, value) VALUES
            ('paper_mode', 'true'),
            ('execution_mode', 'paper'),
            ('hotpath_connected', 'false'),
            ('autotrader_enabled', 'true'),
            ('model_version', 'v12'),
            ('model_accuracy', '0.93'),
            ('precision', '0.84'),
            ('recall', '0.32'),
            ('f1_score', '0.47'),
            ('training_samples', '0'),
            ('observations_24h', '0'),
            ('win_rate', '0'),
            ('sharpe_ratio', '0'),
            ('sortino_ratio', '0'),
            ('profit_factor', '0'),
            ('max_drawdown', '0'),
            ('total_return', '0');
        INSERT OR IGNORE INTO rug_stats (id) VALUES (1);
    ''')
    conn.commit()
    conn.close()

init_db()

# ═══ Serve Dashboard ═══
@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/favicon.ico')
def favicon():
    return '', 204

# ═══ Health ═══
@app.route('/health')
def health():
    conn = get_db()
    try:
        cfg = {r['key']: r['value'] for r in conn.execute("SELECT key, value FROM config").fetchall()}
        rs = conn.execute("SELECT * FROM rug_stats WHERE id=1").fetchone()
        trade_count = conn.execute("SELECT COUNT(*) as c FROM trades").fetchone()['c']
        signal_count = conn.execute("SELECT COUNT(*) as c FROM signals").fetchone()['c']
    finally:
        conn.close()

    return jsonify({
        'ready': True,
        'hotpath_connected': cfg.get('hotpath_connected', 'false') == 'true',
        'paper_mode': cfg.get('paper_mode', 'true') == 'true',
        'execution_mode': cfg.get('execution_mode', 'paper'),
        'autotrader_enabled': cfg.get('autotrader_enabled', 'true') == 'true',
        'model_version': cfg.get('model_version', 'v12'),
        'uptime_seconds': int(time.time() - STARTED_AT),
        'total_trades': trade_count,
        'total_signals': signal_count,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

# ═══ Wallet ═══
@app.route('/wallet')
def wallet():
    conn = get_db()
    try:
        trades = conn.execute("SELECT * FROM trades ORDER BY id DESC LIMIT 200").fetchall()
    finally:
        conn.close()

    balance = 1.0  # Starting balance
    wins = 0
    losses = 0
    total_pnl = 0
    trade_list = []
    for t in trades:
        if t['side'] == 'sell' and t['pnl']:
            balance += t['pnl']
            total_pnl += t['pnl']
            if t['pnl'] >= 0:
                wins += 1
            else:
                losses += 1
        trade_list.append({
            'id': t['id'],
            'token': t['token'],
            'side': t['side'],
            'amount': t['amount'],
            'pnl': t['pnl'],
            'outcome': t['outcome'] or ('win' if (t['pnl'] or 0) >= 0 else 'loss'),
            'time': t['timestamp']
        })

    return jsonify({
        'balance': round(balance, 6),
        'total_pnl': round(total_pnl, 6),
        'paper_balance': round(balance, 6),
        'total_trades': len(trades),
        'wins': wins,
        'losses': losses,
        'start_balance': 1.0,
        'pnl_pct': round(total_pnl / 1.0 * 100, 2) if 1.0 > 0 else 0,
        'trades': trade_list
    })

# ═══ Telemetry ═══
@app.route('/telemetry/stats')
def telemetry():
    conn = get_db()
    try:
        cfg = {r['key']: r['value'] for r in conn.execute("SELECT key, value FROM config").fetchall()}
        trades = conn.execute("SELECT * FROM trades WHERE side='sell'").fetchall()
    finally:
        conn.close()

    wins = sum(1 for t in trades if (t['pnl'] or 0) >= 0)
    total_trades = len(trades)

    def g(key, default=0):
        v = cfg.get(key)
        try: return float(v) if v else default
        except: return default

    return jsonify({
        'model_version': cfg.get('model_version', 'v12'),
        'model_accuracy': g('model_accuracy'),
        'precision': g('precision'),
        'recall': g('recall'),
        'f1_score': g('f1_score'),
        'training_samples': int(g('training_samples')),
        'observations_24h': int(g('observations_24h')),
        'win_rate': wins / total_trades if total_trades > 0 else 0,
        'win_rate_traded': wins / total_trades if total_trades > 0 else 0,
        'win_rate_counterfactual': g('recall', 0.32),
        'sharpe_ratio': g('sharpe_ratio'),
        'sortino_ratio': g('sortino_ratio'),
        'profit_factor': g('profit_factor'),
        'max_drawdown': g('max_drawdown'),
        'total_return': g('total_return'),
        'total_trades': total_trades,
        'avg_win': float(sum(t['pnl'] for t in trades if (t['pnl'] or 0) > 0) / max(wins, 1)),
        'avg_loss': float(sum(t['pnl'] for t in trades if (t['pnl'] or 0) < 0) / max(total_trades - wins, 1)),
        'best_trade': float(max((t['pnl'] for t in trades), default=0)),
        'worst_trade': float(min((t['pnl'] for t in trades), default=0)),
    })

# ═══ Signals ═══
@app.route('/autotrader/recent-signals')
def recent_signals():
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM signals ORDER BY id DESC LIMIT 100").fetchall()
    finally:
        conn.close()
    return jsonify([{
        'id': r['id'],
        'token': r['token'],
        'action': r['action'],
        'confidence': r['confidence'],
        'score': r['score'],
        'features': json.loads(r['features']) if r['features'] else None,
        'time': r['timestamp']
    } for r in rows])

# ═══ Config ═══
@app.route('/autotrader/config')
def autotrader_config():
    conn = get_db()
    try:
        cfg = {r['key']: r['value'] for r in conn.execute("SELECT key, value FROM config").fetchall()}
    finally:
        conn.close()
    return jsonify({
        'config': cfg,
        'risk_limits': {
            'daily_loss_limit': float(cfg.get('daily_loss_limit', 0.5)),
            'daily_loss_used': float(cfg.get('daily_loss_used', 0)),
            'max_position_size': float(cfg.get('max_position_size', 0.1)),
        }
    })

@app.route('/autotrader/status')
def autotrader_status():
    return telemetry()

# ═══ Rug Detector ═══
@app.route('/rug/stats')
def rug_stats():
    conn = get_db()
    try:
        rs = conn.execute("SELECT * FROM rug_stats WHERE id=1").fetchone()
    finally:
        conn.close()
    return jsonify({
        'tokens_scanned': rs['tokens_scanned'],
        'rugs_caught': rs['rugs_caught'],
        'safe_passed': rs['safe_passed'],
        'total': rs['tokens_scanned'],
        'caught': rs['rugs_caught'],
        'safe': rs['safe_passed'],
        'detection_rate': rs['detection_rate'],
        'false_alarm_rate': rs['false_alarm_rate'],
        'last_updated': rs['last_updated']
    })

# ═══ Logs ═══
@app.route('/learning/metrics')
def learning_metrics():
    return telemetry()

# ═══════════════════════════════════════════════
# INGESTION ENDPOINTS — 2DEXY posts data here
# ═══════════════════════════════════════════════

@app.route('/api/v1/signal', methods=['POST'])
def ingest_signal():
    d = request.json or {}
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO signals (token, action, confidence, score, features) VALUES (?,?,?,?,?)",
            (d.get('token','?'), d.get('action','buy'), d.get('confidence',0), d.get('score',0),
             json.dumps(d.get('features')) if d.get('features') else None)
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({'ok': True}), 201

@app.route('/api/v1/trade', methods=['POST'])
def ingest_trade():
    d = request.json or {}
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO trades (token, side, amount, pnl, outcome) VALUES (?,?,?,?,?)",
            (d.get('token','?'), d.get('side','buy'), d.get('amount',0), d.get('pnl',0), d.get('outcome'))
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({'ok': True}), 201

@app.route('/api/v1/rug-stats', methods=['POST'])
def ingest_rug_stats():
    d = request.json or {}
    conn = get_db()
    try:
        conn.execute("""UPDATE rug_stats SET
            tokens_scanned=?, rugs_caught=?, safe_passed=?,
            detection_rate=?, false_alarm_rate=?, last_updated=datetime('now')
            WHERE id=1""",
            (d.get('tokens_scanned',0), d.get('rugs_caught',0), d.get('safe_passed',0),
             d.get('detection_rate',0), d.get('false_alarm_rate',0))
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({'ok': True}), 201

@app.route('/api/v1/telemetry', methods=['POST'])
def ingest_telemetry():
    """Bulk update config/telemetry values from 2DEXY."""
    d = request.json or {}
    conn = get_db()
    try:
        for k, v in d.items():
            conn.execute("INSERT OR REPLACE INTO config (key, value, updated_at) VALUES (?,?,datetime('now'))",
                        (k, str(v)))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'ok': True}), 201

@app.route('/api/v1/log', methods=['POST'])
def ingest_log():
    d = request.json or {}
    conn = get_db()
    try:
        conn.execute("INSERT INTO system_logs (level, message) VALUES (?,?)",
                    (d.get('level','info'), d.get('message','')))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'ok': True}), 201

@app.route('/api/v1/logs', methods=['GET'])
def get_logs():
    limit = min(int(request.args.get('limit', 100)), 500)
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM system_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    finally:
        conn.close()
    return jsonify([{'level': r['level'], 'message': r['message'], 'time': r['timestamp']} for r in rows])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
