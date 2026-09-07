import os

from uvicorn import run

from app.main import app

if __name__ == "__main__":
    run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
