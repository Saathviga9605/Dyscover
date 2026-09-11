import argparse
import json

from .datasets import subject_level_split


def main() -> None:
    parser = argparse.ArgumentParser(description="Dyscover research ML utilities")
    parser.add_argument("command", choices=["split-info"], help="Run a safe dataset utility")
    args = parser.parse_args()
    if args.command == "split-info":
        print(json.dumps({"strategy": "subject_level_random_split", "status": "ready"}))


if __name__ == "__main__":
    main()
