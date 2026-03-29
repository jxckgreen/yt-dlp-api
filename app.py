import os
import tempfile
import yt_dlp
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS


def write_netscape_cookies(cookie_string: str, filepath: str):
    """Write cookies to a Netscape cookie file for yt-dlp.
    Accepts either a full Netscape cookie file or a browser cookie string (name=value; ...).
    """
    cookie_string = cookie_string.strip()
    if "# Netscape HTTP Cookie File" in cookie_string:
        # Already in Netscape format — write as-is
        with open(filepath, "w") as f:
            f.write(cookie_string)
    else:
        # Browser cookie string format: name=value; name2=value2
        lines = ["# Netscape HTTP Cookie File\n"]
        for part in cookie_string.split(";"):
            part = part.strip()
            if "=" not in part:
                continue
            name, _, value = part.partition("=")
            lines.append(f".instagram.com\tTRUE\t/\tTRUE\t2147483647\t{name.strip()}\t{value.strip()}\n")
        with open(filepath, "w") as f:
            f.writelines(lines)

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

    tmpdir = tempfile.mkdtemp()
    try:
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
            cookie_file = os.path.join(tmpdir, "ig_cookies.txt")
            write_netscape_cookies(ig_cookies, cookie_file)
            ydl_opts["cookiefile"] = cookie_file

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except yt_dlp.utils.DownloadError as e:
            msg = str(e).replace("ERROR: ", "")
            return jsonify({"error": msg}), 502
        except Exception as e:
            return jsonify({"error": f"Unexpected error: {str(e)}"}), 500

        # Find the downloaded video file (exclude cookie files)
        files = [f for f in os.listdir(tmpdir) if not f.endswith(".txt")]
        if not files:
            return jsonify({"error": "Download produced no output file."}), 502

        filepath = os.path.join(tmpdir, files[0])
        ext = os.path.splitext(files[0])[1].lstrip(".")
        content_type = f"video/{ext}" if ext else "video/mp4"
        file_size = os.path.getsize(filepath)

        def generate():
            try:
                with open(filepath, "rb") as f:
                    while chunk := f.read(1024 * 64):
                        yield chunk
            finally:
                import shutil
                shutil.rmtree(tmpdir, ignore_errors=True)

        return Response(
            stream_with_context(generate()),
            status=200,
            headers={
                "Content-Type": content_type,
                "Content-Length": str(file_size),
                "Cache-Control": "no-store",
            },
        )
    except Exception:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
