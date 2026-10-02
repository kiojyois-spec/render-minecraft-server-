FROM eclipse-temurin:21-jdk-alpine

# 必要なツール（Python3, pip, curl, bash, jq, procps）をインストール
RUN apk add --no-co-cache python3 py3-pip curl bash jq procps

WORKDIR /data

# Python 依存関係のインストール
COPY requirements.txt /data/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /data/requirements.txt

# 設定ファイル・スクリプトのコピー
COPY app.py /data/app.py
COPY start.sh /data/start.sh
COPY eula.txt /data/eula.txt
COPY plugins /data/plugins

RUN chmod +x /data/start.sh

# Web UI用 (10000), Java版用 (25565), Bedrock/統合版用 (19132/udp)
EXPOSE 10000 25565 19132/udp

# 管理用 Web UI (Python/Flask) を起動
CMD ["python3", "app.py"]
