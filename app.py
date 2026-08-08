from flask import Flask, request, render_template, send_file
import yt_dlp
import tempfile
import os
import re
import shutil

app = Flask(__name__)

# Helper: Get ALL available formats (video + audio) for a URL
def get_available_formats(url):
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        video_formats = []
        audio_formats = []

        for f in info.get("formats", []):
            # --- VIDEO FORMATS ---
            if f.get("vcodec") != "none" and f.get("height"):
                h = f["height"]
                try:
                    height_int = int(float(h))
                except (ValueError, TypeError):
                    continue
                video_formats.append({
                    "type": "video",
                    "format_id": f["format_id"],
                    "label": f"{height_int}p",
                    "ext": f["ext"],
                    "fps": f.get("fps", "N/A"),
                    "size_mb": round(f["filesize"] / (1024*1024), 2) if f.get("filesize") else "Unknown",
                    "note": f.get("format_note", ""),
                })
            # --- AUDIO FORMATS ---
            elif f.get("acodec") != "none" and f.get("vcodec") == "none":
                abr = f.get("abr", 0) or 0
                try:
                    abr_int = int(float(abr))
                except (ValueError, TypeError):
                    abr_int = 0
                audio_formats.append({
                    "type": "audio",
                    "format_id": f["format_id"],
                    "label": f"{abr_int}kbps",
                    "ext": f["ext"],
                    "size_mb": round(f["filesize"] / (1024*1024), 2) if f.get("filesize") else "Unknown",
                    "note": "Audio Only",
                })

        # Sort safely
        video_formats.sort(key=lambda x: int(x["label"].replace("p", "")), reverse=True)
        audio_formats.sort(key=lambda x: int(x["label"].replace("kbps", "")), reverse=True)
        seen = set()
        unique_audio = []
        for a in audio_formats:
            if a["label"] not in seen:
                unique_audio.append(a)
                seen.add(a["label"])

        return info["title"], video_formats, unique_audio

# Home page
@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

# Fetch qualities
@app.route("/fetch", methods=["POST"])
def fetch():
    url = request.form.get("url", "").strip()
    if not url:
        return render_template("index.html", error="Please enter a YouTube URL")
    try:
        title, video_formats, audio_formats = get_available_formats(url)
        return render_template(
            "index.html",
            url=url, title=title,
            video_formats=video_formats,
            audio_formats=audio_formats
        )
    except Exception as e:
        return render_template("index.html", error=f"Failed to load video: {str(e)}")

# Download selected format (video OR audio)
def sanitize_filename(name):
    """Remove unsafe characters for filenames"""
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip()

@app.route("/download", methods=["POST"])
def download():
    url = request.form.get("url")
    format_id = request.form.get("format_id")
    media_type = request.form.get("media_type", "video")
    if not url or not format_id:
        return render_template("index.html", error="Missing URL or quality selection")
    
    # ✅ FFmpeg path for Render (auto-installed via build.sh)
# Replace this line in your download() function:
    ffmpeg_path = os.path.join(os.path.dirname(__file__), "ffmpeg", "ffmpeg")
    
    temp_dir = tempfile.mkdtemp()
    try:
        ydl_opts = {
            "ffmpeg_location": ffmpeg_path,
            "quiet": False,
            "no_warnings": False,
            "outtmpl": os.path.join(temp_dir, "%(title)s.%(ext)s"),
        }

        if media_type == "audio":
            ydl_opts.update({
                "format": format_id,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
                "outtmpl": os.path.join(temp_dir, "%(title)s.mp3"),
            })
        else:
            # Video: merge selected video + best audio
            ydl_opts.update({
                "format": f"{format_id}+bestaudio[ext=m4a]/bestaudio",
                "merge_output_format": "mp4",
            })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            safe_title = sanitize_filename(info["title"])

            # Find the REAL final file in temp folder
            all_files = os.listdir(temp_dir)
            if media_type == "audio":
                final_files = [f for f in all_files if f.lower().endswith(".mp3")]
            else:
                final_files = [f for f in all_files if f.lower().endswith(".mp4")]

            if not final_files:
                raise Exception("Download completed but no output file found")
            
            actual_filename = final_files[0]
            actual_path = os.path.join(temp_dir, actual_filename)

        return send_file(
            actual_path,
            as_attachment=True,
            download_name=sanitize_filename(os.path.splitext(actual_filename)[0]) + (".mp3" if media_type == "audio" else ".mp4")
        )

    except Exception as e:
        return render_template("index.html", error=f"Download failed: {str(e)}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    app.run(debug=False)  # ⚠️ Debug turned OFF for Render
