"""Run the reel browser: `python -m reel_categorizer.web`."""
from __future__ import annotations

import uvicorn

from .server import FRONTEND_DIST, build_app

HOST = "127.0.0.1"
PORT = 8000


def main() -> None:
    if not FRONTEND_DIST.is_dir():
        print(f"! No built frontend at {FRONTEND_DIST}\n"
              "  Run `npm install && npm run build` in frontend/ first "
              "(the API still works meanwhile).\n")
    print(f"Reel browser on http://{HOST}:{PORT}")
    uvicorn.run(build_app(), host=HOST, port=PORT)


if __name__ == "__main__":
    main()
