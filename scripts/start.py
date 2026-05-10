import os
import subprocess
import sys


def run_fastapi():
    port = os.getenv("PORT", "8000")
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        port,
    ]
    return subprocess.call(command)


def run_streamlit():
    port = os.getenv("PORT", "8501")
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "streamlit_app.py",
        "--server.port",
        port,
        "--server.address",
        "0.0.0.0",
        "--server.headless",
        "true",
    ]
    return subprocess.call(command)


def main():
    mode = os.getenv("APP_MODE", "bot").strip().lower()

    if mode == "streamlit":
        raise SystemExit(run_streamlit())

    raise SystemExit(run_fastapi())


if __name__ == "__main__":
    main()
