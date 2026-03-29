const express = require("express");
const YTDlpWrap = require("yt-dlp-wrap").default;
const path = require("path");
const fs = require("fs");
const os = require("os");
const { PassThrough } = require("stream");

const app = express();
app.use(express.json());

const PORT = process.env.PORT || 3001;
const API_KEY = process.env.API_KEY || null;
const BINARY_PATH = path.join(__dirname, process.platform === "win32" ? "yt-dlp-binary.exe" : "yt-dlp-binary");

// Write INSTAGRAM_COOKIES env var content to a temp file if provided
let COOKIES_FILE = process.env.COOKIES_FILE || null;
if (!COOKIES_FILE && process.env.INSTAGRAM_COOKIES) {
  COOKIES_FILE = path.join(os.tmpdir(), "instagram_cookies.txt");
  fs.writeFileSync(COOKIES_FILE, process.env.INSTAGRAM_COOKIES, "utf8");
  console.log("Wrote Instagram cookies to", COOKIES_FILE);
}

const ytDlp = new YTDlpWrap(BINARY_PATH);

// Optional bearer token auth
function checkAuth(req, res) {
  if (!API_KEY) return true;
  const header = req.headers["authorization"] || "";
  if (header === `Bearer ${API_KEY}`) return true;
  res.status(401).json({ error: "Unauthorized" });
  return false;
}

app.get("/health", (req, res) => {
  res.json({ status: "ok" });
});

app.post("/download", async (req, res) => {
  if (!checkAuth(req, res)) return;

  const { url } = req.body;
  if (!url || typeof url !== "string" || url.trim() === "") {
    return res.status(400).json({ error: "A URL is required." });
  }

  console.log("[download] URL:", url.trim());

  // Get video info first to determine format/filename
  const cookieArgs = COOKIES_FILE ? ["--cookies", COOKIES_FILE] : [];

  let info;
  try {
    info = await ytDlp.getVideoInfo([url.trim(), ...cookieArgs]);
  } catch (err) {
    console.error("[download] Info error:", err.message);
    return res.status(502).json({ error: "Could not fetch video info: " + err.message });
  }

  const ext = info.ext || "mp4";
  const title = (info.title || "video").replace(/[^\w\s-]/g, "").trim().replace(/\s+/g, "_");
  const filename = `${title}.${ext}`;

  res.setHeader("Content-Type", `video/${ext}`);
  res.setHeader("Content-Disposition", `attachment; filename="${filename}"`);

  console.log("[download] Streaming:", filename);

  const passThrough = new PassThrough();
  passThrough.pipe(res);

  try {
    await new Promise((resolve, reject) => {
      const stream = ytDlp.execStream([
        url.trim(),
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "-o", "-",
        "--no-playlist",
        ...cookieArgs,
      ]);

      stream.on("error", reject);
      stream.pipe(passThrough);
      stream.on("end", resolve);
      stream.on("close", resolve);
    });
  } catch (err) {
    console.error("[download] Stream error:", err.message);
    if (!res.headersSent) {
      res.status(502).json({ error: "Download failed: " + err.message });
    } else {
      res.end();
    }
  }
});

app.listen(PORT, () => {
  console.log(`yt-dlp API running on http://localhost:${PORT}`);
  if (API_KEY) console.log("API key protection enabled.");
});
