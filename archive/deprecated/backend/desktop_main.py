import os

import uvicorn


def run() -> None:
    port = int(os.getenv("PSS_DESKTOP_BACKEND_PORT", "8877"))
    host = os.getenv("PSS_DESKTOP_BACKEND_HOST", "127.0.0.1")

    # Desktop mode defaults: local sqlite and permissive CORS for file:// origin.
    os.environ.setdefault("DATABASE_URL", "sqlite:///./pss_logger.db")
    os.environ.setdefault("ALLOWED_HOSTS", "*")

    uvicorn.run("app.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run()
