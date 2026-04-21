import argparse

import uvicorn


def parse_args():
    parser = argparse.ArgumentParser(description="Story graph web app")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    return parser.parse_args()


def main():
    args = parse_args()
    uvicorn.run(
        "story_graph.web:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
