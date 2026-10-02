#!/bin/bash

echo "=========================================="
echo "Minecraft サーバー起動処理の開始"
echo "=========================================="

# --- 1. ディレクトリと基本ファイルの確保 ---
mkdir -p /data/plugins /data/logs
echo "eula=true" > /data/eula.txt

# --- 2. server.properties と RCON の安全な自動作成・補正 ---
PROP_FILE="/data/server.properties"
if [ ! -f "$PROP_FILE" ]; then
    touch "$PROP_FILE"
fi

set_prop() {
    key=$1
    val=$2
    if grep -q "^${key}=" "$PROP_FILE"; then
        sed -i "s/^${key}=.*/${key}=${val}/" "$PROP_FILE"
    else
        echo "${key}=${val}" >> "$PROP_FILE"
    fi
}

# RCONを強制有効化（WebUIからのコマンド送信に必須）
set_prop "enable-rcon" "true"
set_prop "rcon.port" "25575"
set_prop "rcon.password" "render_mc_secret_123"
set_prop "online-mode" "true"

# --- 3. PaperMC (最新安定版 1.20.4) の自動ダウンローダー ---
PAPER_VERSION="1.20.4"
if [ ! -f "/data/paper.jar" ]; then
    echo "PaperMC ${PAPER_VERSION} を取得中..."
    BUILD_NUMBER=$(curl -s https://api.papermc.io/v2/projects/paper/versions/${PAPER_VERSION}/builds | jq '.builds[-1].build' 2>/dev/null)
    
    # 失敗時のフォールバック処理
    if [ -z "$BUILD_NUMBER" ] || [ "$BUILD_NUMBER" = "null" ]; then
        echo "ビルド番号の自動取得に失敗したため、バックアップビルドを使用します。"
        BUILD_NUMBER="496"
    fi

    PAPER_URL="https://api.papermc.io/v2/projects/paper/versions/${PAPER_VERSION}/builds/${BUILD_NUMBER}/downloads/paper-${PAPER_VERSION}-${BUILD_NUMBER}.jar"
    curl -sL -o /data/paper.jar "${PAPER_URL}"
fi

# --- 4. GeyserMC & Floodgate の自動ダウンロード判定 ---
GEYSER_FLAG="/data/geyser_enabled.txt"
if [ -f "$GEYSER_FLAG" ] && [ "$(cat $GEYSER_FLAG)" = "true" ]; then
    echo "[GeyserMC] クロスプレイ機能をダウンロード・セットアップ中..."
    
    if [ ! -f "/data/plugins/Geyser-Spigot.jar" ]; then
        curl -sL https://download.geysermc.org/v2/projects/geyser/versions/latest/builds/latest/downloads/spigot -o /data/plugins/Geyser-Spigot.jar
    fi

    if [ ! -f "/data/plugins/Floodgate-Spigot.jar" ]; then
        curl -sL https://download.geysermc.org/v2/projects/floodgate/versions/latest/builds/latest/downloads/spigot -o /data/plugins/Floodgate-Spigot.jar
    fi
else
    echo "[GeyserMC] クロスプレイ機能は無効に設定されています。"
fi

# --- 5. playit.gg トンネルの起動 ---
if [ ! -f "/data/playit" ]; then
    echo "playit.gg をダウンロード中..."
    curl -sSL https://github.com/playit-cloud/playit-agent/releases/latest/download/playit-linux-amd64 -o /data/playit
    chmod +x /data/playit
fi

if ! pgrep -x "playit" > /dev/null; then
    echo "playit.gg トンネルをバックグラウンド起動中..."
    /data/playit > /data/logs/playit.log 2>&1 &
fi

# --- 6. Java プロセス起動 ---
echo "PaperMC サーバーを起動します..."
exec java -Xms1024M -Xmx1536M \
    -XX:+UseG1GC \
    -XX:+ParallelRefProcEnabled \
    -XX:MaxGCPauseMillis=200 \
    -jar /data/paper.jar nogui
