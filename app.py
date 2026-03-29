import os
import yt_dlp
from flask import Flask, request, jsonify
from flask_cors import CORS

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
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        video_url = info.get("url")

        # For formats with separate video+audio, grab the best single-file URL
        if not video_url and info.get("formats"):
            for fmt in reversed(info["formats"]):
                if fmt.get("url") and fmt.get("ext") == "mp4":
                    video_url = fmt["url"]
                    break
            if not video_url:
                video_url = info["formats"][-1].get("url")

        if not video_url:
            return jsonify({"error": "Could not extract a direct video URL."}), 502

        return jsonify({"video_url": video_url})

    except yt_dlp.utils.DownloadError as e:
        msg = str(e).replace("ERROR: ", "")
        return jsonify({"error": msg}), 502
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
