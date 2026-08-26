FROM python:3.12-slim

# ffmpeg is required by yt-dlp to merge separate video/audio streams into mp4.
# curl + unzip are only needed to fetch the PO token provider below.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl unzip \
    && rm -rf /var/lib/apt/lists/*

# PO token provider: without it, YouTube's "Sign in to confirm you're not a
# bot" wall hits datacenter IPs (Render, AWS, etc.) on almost every request.
# This generates a real proof-of-origin token per request so yt-dlp's web
# client passes that check — no personal account/cookies involved.
# https://github.com/jim60105/bgutil-ytdlp-pot-provider-rs
RUN mkdir -p /root/yt-dlp-plugins/bgutil-ytdlp-pot-provider \
    && curl -sL -o /usr/local/bin/bgutil-pot \
       https://github.com/jim60105/bgutil-ytdlp-pot-provider-rs/releases/latest/download/bgutil-pot-linux-x86_64 \
    && chmod +x /usr/local/bin/bgutil-pot \
    && curl -sL -o /tmp/pot-plugin.zip \
       https://github.com/jim60105/bgutil-ytdlp-pot-provider-rs/releases/latest/download/bgutil-ytdlp-pot-provider-rs.zip \
    && unzip -oq /tmp/pot-plugin.zip -d /root/yt-dlp-plugins/bgutil-ytdlp-pot-provider \
    && rm /tmp/pot-plugin.zip

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Ephemeral scratch space only — wiped on every container restart, nothing persisted
RUN mkdir -p /tmp/yt-pull

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
