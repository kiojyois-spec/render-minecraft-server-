import os
import subprocess
import time
import psutil
from flask import Flask, render_template_string, request, jsonify
from mcrcon import MCRcon, MCRconException

app = Flask(__name__)

# RCON 設定 (start.sh と共通)
RCON_HOST = "127.0.0.1"
RCON_PORT = 25575
RCON_PASS = "render_mc_secret_123"

GEYSER_CONFIG_FILE = "/data/geyser_enabled.txt"
LOG_FILE = "/data/logs/latest.log"

def is_mc_running():
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd = proc.info['cmdline']
            if cmd and any('paper.jar' in arg for arg in cmd):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False

def set_geyser_status(enabled):
    with open(GEYSER_CONFIG_FILE, "w") as f:
        f.write("true" if enabled else "false")

def get_geyser_status():
    if os.path.exists(GEYSER_CONFIG_FILE):
        with open(GEYSER_CONFIG_FILE, "r") as f:
            return f.read().strip() == "true"
    return False

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Minecraft Server Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 text-white min-h-screen p-4 sm:p-8">
    <div class="max-w-4xl mx-auto space-y-6">
        <!-- ヘッダー -->
        <div class="flex justify-between items-center bg-slate-800 p-6 rounded-xl border border-slate-700 shadow-lg">
            <div>
                <h1 class="text-2xl font-bold flex items-center gap-2">
                    ⛏️ Minecraft Web Controller
                </h1>
                <p class="text-slate-400 text-sm mt-1">Render.com 統合ダッシュボード</p>
            </div>
            <div id="status-badge" class="px-4 py-2 rounded-full font-bold text-sm bg-gray-600 text-gray-200">
                確認中...
            </div>
        </div>

        <!-- コントロールボタン -->
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <button onclick="controlServer('start')" class="bg-emerald-600 hover:bg-emerald-500 font-bold py-3 px-4 rounded-lg transition shadow-md">
                ▶️ サーバー起動
            </button>
            <button onclick="controlServer('stop')" class="bg-rose-600 hover:bg-rose-500 font-bold py-3 px-4 rounded-lg transition shadow-md">
                ⏹️ サーバー停止
            </button>
            <button onclick="controlServer('restart')" class="bg-amber-600 hover:bg-amber-500 font-bold py-3 px-4 rounded-lg transition shadow-md">
                🔄 再起動
            </button>
        </div>

        <!-- GeyserMC (統合版対応) スイッチ -->
        <div class="bg-slate-800 p-6 rounded-xl border border-slate-700 shadow-lg space-y-4">
            <h2 class="text-lg font-bold flex items-center gap-2">🎮 クロスプレイ設定 (GeyserMC)</h2>
            <div class="flex items-center justify-between bg-slate-900 p-4 rounded-lg">
                <div>
                    <span class="font-bold">GeyserMC (Switch / スマホ / PS / Xbox 参加対応)</span>
                    <p class="text-xs text-slate-400 mt-1">有効にして「再起動」すると、統合版接続プラグインを自動設定します。</p>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" id="geyser-toggle" onchange="toggleGeyser(this.checked)" class="sr-only peer">
                    <div class="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-500"></div>
                </label>
            </div>
        </div>

        <!-- コマンド送信フォーム -->
        <div class="bg-slate-800 p-6 rounded-xl border border-slate-700 shadow-lg space-y-4">
            <h2 class="text-lg font-bold">💬 コマンド実行 (RCON)</h2>
            <form onsubmit="sendCommand(event)" class="flex gap-2">
                <input type="text" id="command-input" placeholder="例: op YourName, tp Player 0 100 0, gamemode creative YourName" class="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 focus:outline-none focus:border-emerald-500 text-white">
                <button type="submit" class="bg-indigo-600 hover:bg-indigo-500 font-bold px-6 py-2 rounded-lg transition">送信</button>
            </form>
            <div id="command-response" class="text-xs font-mono bg-slate-950 p-3 rounded border border-slate-800 text-emerald-400 hidden"></div>
        </div>

        <!-- コンソールログ表示 -->
        <div class="bg-slate-800 p-6 rounded-xl border border-slate-700 shadow-lg space-y-2">
            <div class="flex justify-between items-center">
                <h2 class="text-lg font-bold">📜 コンソールログ (playit.ggのURLもここに表示)</h2>
                <button onclick="fetchStatus()" class="text-xs bg-slate-700 hover:bg-slate-600 px-3 py-1 rounded">手動更新</button>
            </div>
            <pre id="logs" class="bg-slate-950 p-4 rounded-lg font-mono text-xs text-slate-300 h-64 overflow-y-auto whitespace-pre-wrap leading-relaxed border border-slate-800">ログを読み込んでいます...</pre>
        </div>
    </div>

    <script>
        async function fetchStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                
                const badge = document.getElementById('status-badge');
                if (data.online) {
                    badge.textContent = '🟢 オンライン';
                    badge.className = 'px-4 py-2 rounded-full font-bold text-sm bg-emerald-500/20 text-emerald-400 border border-emerald-500/30';
                } else {
                    badge.textContent = '🔴 オフライン';
                    badge.className = 'px-4 py-2 rounded-full font-bold text-sm bg-rose-500/20 text-rose-400 border border-rose-500/30';
                }

                document.getElementById('geyser-toggle').checked = data.geyser_enabled;
                document.getElementById('logs').textContent = data.logs || 'ログがありません。';
            } catch (e) {
                console.error(e);
            }
        }

        async function controlServer(action) {
            if(!confirm(`サーバーを ${action} しますか？`)) return;
            await fetch(`/api/${action}`, { method: 'POST' });
            setTimeout(fetchStatus, 2000);
        }

        async function toggleGeyser(enabled) {
            await fetch('/api/toggle-geyser', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ enabled })
            });
            alert('GeyserMC の設定を切り替えました。反映するにはサーバーを「再起動」してください。');
        }

        async function sendCommand(e) {
            e.preventDefault();
            const input = document.getElementById('command-input');
            const responseDiv = document.getElementById('command-response');
            const cmd = input.value.trim();
            if (!cmd) return;

            const res = await fetch('/api/command', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ command: cmd })
            });
            const data = await res.json();
            responseDiv.classList.remove('hidden');
            responseDiv.textContent = data.result;
            input.value = '';
        }

        setInterval(fetchStatus, 5000);
        fetchStatus();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/status')
def status():
    online = is_mc_running()
    logs = ""
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                logs = "".join(f.readlines()[-60:])
        except Exception as e:
            logs = f"ログ読み込みエラー: {str(e)}"
    
    return jsonify({
        "online": online,
        "geyser_enabled": get_geyser_status(),
        "logs": logs
    })

@app.route('/api/start', methods=['POST'])
def start_server():
    if not is_mc_running():
        subprocess.Popen(["/data/start.sh"], cwd="/data")
        return jsonify({"result": "起動処理を開始しました"})
    return jsonify({"result": "既に起動しています"})

@app.route('/api/stop', methods=['POST'])
def stop_server():
    if is_mc_running():
        try:
            with MCRcon(RCON_HOST, RCON_PASS, port=RCON_PORT, timeout=5) as mcr:
                mcr.command("stop")
            return jsonify({"result": "安全な停止コマンド (stop) を送信しました"})
        except Exception:
            subprocess.run(["pkill", "-f", "paper.jar"])
            return jsonify({"result": "プロセスを強制終了しました"})
    return jsonify({"result": "サーバーは起動していません"})

@app.route('/api/restart', methods=['POST'])
def restart_server():
    stop_server()
    time.sleep(5)
    return start_server()

@app.route('/api/command', methods=['POST'])
def run_command():
    data = request.get_json()
    cmd = data.get('command', '')
    if not is_mc_running():
        return jsonify({"result": "エラー: サーバーがオフラインです"})
    try:
        with MCRcon(RCON_HOST, RCON_PASS, port=RCON_PORT, timeout=5) as mcr:
            res = mcr.command(cmd)
            return jsonify({"result": res or "コマンドを正常に送信しました"})
    except Exception as e:
        return jsonify({"result": f"RCON実行失敗: {str(e)}"})

@app.route('/api/toggle-geyser', methods=['POST'])
def toggle_geyser():
    data = request.get_json()
    set_geyser_status(data.get('enabled', False))
    return jsonify({"status": "success"})

if __name__ == '__main__':
    # コンテナ起動時に自動でマイクラサーバーの起動を開始
    subprocess.Popen(["/data/start.sh"], cwd="/data")
    app.run(host='0.0.0.0', port=10000)
