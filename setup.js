// Downloads the yt-dlp binary for the current platform
const YTDlpWrap = require("yt-dlp-wrap").default;
const path = require("path");

const binaryPath = path.join(__dirname, process.platform === "win32" ? "yt-dlp-binary.exe" : "yt-dlp-binary");

(async () => {
  console.log("Downloading yt-dlp binary...");
  await YTDlpWrap.downloadFromGithub(binaryPath);
  console.log("Done! Binary saved to:", binaryPath);
})();
