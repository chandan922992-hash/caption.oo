import sys
import threading
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> None:
    import uvicorn

    from app.main import app

    host, port = "127.0.0.1", 8734
    url = f"http://{host}:{port}"
    threading.Timer(2.5, webbrowser.open, args=(url,)).start()
    print(f"\n  CLEAPYFLY is starting at {url}\n  Keep this window open — close it to stop the app.\n")
    try:
        uvicorn.run(app, host=host, port=port, log_level="info")
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
