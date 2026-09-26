from flask import Flask, request, jsonify, render_template, send_file
import yt_dlp
import os
import threading
import uuid
import mimetypes

app = Flask(__name__)

DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "/tmp/downhub")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
jobs = {}

def get_info(url):
    opts = {"quiet": True, "no_warnings": True, "noplaylist": True}
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(url, download=False)
    heights = sorted({
        f.get("height") for f in info.get("formats", [])
        if f.get("height") and f.get("vcodec") != "none"
    }, reverse=True)
    return info, [{"height": h} for h in heights if h]

def hook(job_id):
    def progress(d):
        job = jobs.get(job_id)
        if not job:
            return
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            job["percent"] = (done / total * 100) if total else 0
            job["speed"] = d.get("_speed_str") or ""
            job["eta"] = d.get("_eta_str") or ""
            job["status"] = "Downloading..."
        elif d["status"] == "finished":
            job["percent"] = 100
            job["status"] = "Merging video + audio..."
    return progress

@app.get("/")
def home():
    return render_template("index.html")

@app.get("/health")
def health():
    return jsonify(status="ok")

@app.post("/info")
def info():
    try:
        url = (request.json or {}).get("url", "").strip()
        if not url:
            raise ValueError("Please enter a YouTube URL.")
        i, formats = get_info(url)
        if not formats:
            raise ValueError("No video formats found.")
        return jsonify(
            title=i.get("title", "Video"),
            thumbnail=i.get("thumbnail", ""),
            uploader=i.get("uploader", ""),
            duration=i.get("duration_string") or "",
            formats=formats,
        )
    except Exception as e:
        return jsonify(error=str(e)), 400

@app.post("/download")
def download():
    try:
        data = request.json or {}
        url = data.get("url", "").strip()
        height = int(data.get("height", 720))
        if not url:
            raise ValueError("Please enter a URL.")

        job_id = uuid.uuid4().hex
        jobs[job_id] = {
            "percent": 0, "speed": "", "eta": "",
            "status": "Starting...", "done": False,
            "error": None, "filename": "", "path": ""
        }

        def worker():
            try:
                fmt = (
                    f"bestvideo[height<={height}][ext=mp4][vcodec^=avc1]+"
                    f"bestaudio[ext=m4a]/"
                    f"bestvideo[height<={height}]+bestaudio/"
                    f"best[height<={height}]"
                )
                opts = {
                    "format": fmt,
                    "merge_output_format": "mp4",
                    "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s [%(id)s].%(ext)s"),
                    "noplaylist": True,
                    "quiet": True,
                    "progress_hooks": [hook(job_id)],
                }
                with yt_dlp.YoutubeDL(opts) as y:
                    result = y.extract_info(url, download=True)

                title = result.get("title", "video")
                video_id = result.get("id", "")
                candidates = [
                    os.path.join(DOWNLOAD_DIR, f"{title} [{video_id}].mp4"),
                ]
                path = next((p for p in candidates if os.path.isfile(p)), "")
                if not path:
                    # Find the newest MP4 if title characters were normalized by yt-dlp.
                    mp4s = [
                        os.path.join(DOWNLOAD_DIR, x)
                        for x in os.listdir(DOWNLOAD_DIR)
                        if x.lower().endswith(".mp4")
                    ]
                    if mp4s:
                        path = max(mp4s, key=os.path.getmtime)

                jobs[job_id]["filename"] = os.path.basename(path) if path else f"{title}.mp4"
                jobs[job_id]["path"] = path
                jobs[job_id]["percent"] = 100
                jobs[job_id]["status"] = "Download complete."
            except Exception as e:
                jobs[job_id]["error"] = str(e)
                jobs[job_id]["status"] = "Download failed."
            finally:
                jobs[job_id]["done"] = True

        threading.Thread(target=worker, daemon=True).start()
        return jsonify(job=job_id)
    except Exception as e:
        return jsonify(error=str(e)), 400

@app.get("/progress/<job_id>")
def progress(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify(error="Unknown job.", done=True), 404
    data = dict(job)
    if data.get("done") and data.get("path"):
        data["download_url"] = f"/file/{job_id}"
        data.pop("path", None)
    else:
        data.pop("path", None)
    return jsonify(data)

@app.get("/file/<job_id>")
def file_download(job_id):
    job = jobs.get(job_id)
    if not job or not job.get("done") or not job.get("path"):
        return "File is not ready.", 404
    path = job["path"]
    if not os.path.isfile(path):
        return "File is no longer available.", 404
    return send_file(
        path,
        as_attachment=True,
        download_name=job.get("filename") or "downhub.mp4",
        mimetype="video/mp4",
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
