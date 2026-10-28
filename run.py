from __future__ import annotations

import argparse

from server.app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Carbon City server.")
    parser.add_argument("--host", default="127.0.0.1", help="interface to bind")
    parser.add_argument("--port", type=int, default=8000, help="port to listen on")
    args = parser.parse_args()

    app = create_app()
    app.run(host=args.host, port=args.port, threaded=True, debug=False)


if __name__ == "__main__":
    main()
