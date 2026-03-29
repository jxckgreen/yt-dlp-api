import os
import yt_dlp
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/download", methods=["POST"])
def download():
    data = request.get_json(silent=True)
    if not data or not data.get("url"):
        return jsonify({"error": "A 'url' field is required."}), 400

    url = data["url"].strip()

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "format": "best[ext=mp4]/best",
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        msg = str(e).replace("ERROR: ", "")
        return jsonify({"error": msg}), 502
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500

    # Pick best single-stream URL
    video_url = info.get("url")
    http_headers = info.get("http_headers", {})

    if not video_url and info.get("formats"):
        for fmt in reversed(info["formats"]):
            if fmt.get("url") and fmt.get("ext") == "mp4":
                video_url = fmt["url"]
                http_headers = fmt.get("http_headers", http_headers)
                break
        if not video_url:
            last = info["formats"][-1]
            video_url = last.get("url")
            http_headers = last.get("http_headers", http_headers)

    if not video_url:
        return jsonify({"error": "Could not extract a direct video URL."}), 502

    # Stream the video from the CDN using yt-dlp's own headers
    try:
        cdn_res = requests.get(video_url, headers=http_headers, stream=True, timeout=60)
        if not cdn_res.ok:
            return jsonify({"error": f"CDN returned {cdn_res.status_code}"}), 502

        content_type = cdn_res.headers.get("Content-Type", "video/mp4")
        content_length = cdn_res.headers.get("Content-Length")

        response_headers = {"Content-Type": content_type}
        if content_length:
            response_headers["Content-Length"] = content_length

        def generate():
            for chunk in cdn_res.iter_content(chunk_size=1024 * 64):
                if chunk:
                    yield chunk

        return Response(
            stream_with_context(generate()),
            status=200,
            headers=response_headers,
        )
    except Exception as e:
        return jsonify({"error": f"Failed to stream video: {str(e)}"}), 502


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
