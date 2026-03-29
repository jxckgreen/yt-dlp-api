import os
import tempfile
import yt_dlp
from flask import Flask, request, jsonify, Response, stream_with_context
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

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "video.%(ext)s")

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "best[ext=mp4]/best",
            "outtmpl": output_path,
            "noplaylist": True,
        }

        ig_cookies = os.environ.get("INSTAGRAM_COOKIES")
        if ig_cookies and "instagram.com" in url:
            ydl_opts["http_headers"] = {"Cookie": ig_cookies}

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except yt_dlp.utils.DownloadError as e:
            msg = str(e).replace("ERROR: ", "")
            return jsonify({"error": msg}), 502
        except Exception as e:
            return jsonify({"error": f"Unexpected error: {str(e)}"}), 500

        # Find the downloaded file
        files = os.listdir(tmpdir)
        if not files:
            return jsonify({"error": "Download produced no output file."}), 502

        filepath = os.path.join(tmpdir, files[0])
        ext = os.path.splitext(files[0])[1].lstrip(".")
        content_type = f"video/{ext}" if ext else "video/mp4"
        file_size = os.path.getsize(filepath)

        def generate():
            with open(filepath, "rb") as f:
                while chunk := f.read(1024 * 64):
                    yield chunk

        return Response(
            stream_with_context(generate()),
            status=200,
            headers={
                "Content-Type": content_type,
                "Content-Length": str(file_size),
                "Cache-Control": "no-store",
            },
        )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
