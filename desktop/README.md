# CLEAPYFLY — Install on this PC

Two ways to run CLEAPYFLY on a Windows PC. No Node.js is needed for either — the
web files ship prebuilt, video processing uses a bundled local FFmpeg.

## Option A — one-click launcher (recommended)

1. Install **Python 3.10+** from <https://www.python.org/downloads/> (tick *Add python.exe to PATH*).
2. Double-click `CLEAPYFLY.bat`.
   - First run: creates the environment and installs dependencies automatically (needs internet once).
   - Then it starts the app and opens `http://127.0.0.1:8734` in your browser.
3. Next runs need no internet and start in a second.

All data (projects, clips, renders) is stored in a `data` folder next to the app files.
Close the black console window to stop CLEAPYFLY.

## Option B — single-file `CLEAPYFLY.exe`

Want one `.exe` you can copy anywhere (USB stick, another PC)?

1. Make sure Python 3.10+ is installed.
2. Double-click `build_exe.bat`.
3. The finished app appears at `installer\CLEAPYFLY.exe`.

Double-click the exe — it starts a private local server (no other devices can reach it)
and opens the app in your browser.

## Notes

- Everything runs **locally**: no accounts, no paid AI APIs, no cloud processing.
- Local video upload is the always-works source. YouTube links are read for metadata
  via the official oEmbed API; CLEAPYFLY never bypasses YouTube authentication, DRM,
  or platform terms.
- Supported inputs: MP4, MOV, MKV, WebM, AVI and friends.
- Ports: the app serves on TCP 127.0.0.1:8734 only (localhost, private).
