#!/bin/bash
set -e
pip install -r requirements.txt

# Download & install FFmpeg static build
cd /app
curl -O https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
tar xf ffmpeg-release-amd64-static.tar.xz
mv ffmpeg-*-amd64-static ffmpeg
