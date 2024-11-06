#!/usr/bin/env python3

import argparse

from src.main import run


def parse_args():
    parser = argparse.ArgumentParser(
        prog="BGG - Which game today?",
        description="A board game recommendation assistant of your owned games.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-e",
        "--expansions",
        action="store_true",
        help="Include expansions in the recommendations.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output."
    )
    parser.add_argument(
        "-f",
        "--fast",
        action="store_true",
        help="Skip the detailed chat summary and provide quick game recommendations.",
    )
    parser.add_argument(
        "-s",
        "--skip",
        action="store_true",
        help="Skip already known BGG pages.",
    )
    parser.add_argument(
        "mode",
        choices=["db", "chat"],
        help="Mode to perform. db refreshes the database, chat starts the chatbot.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    config = {
        "verbose": args.verbose,
        "fast": args.fast,
        "skip": args.skip,
        "mode": args.mode,
        "expansions": args.expansions,
    }
    run(config)


if __name__ == "__main__":
    main()
