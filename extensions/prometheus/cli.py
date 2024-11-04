import argparse
import os

import prometheus_client

from log_parser.cli import add_parser_args, run


def main(args: argparse.Namespace) -> None:
    """
    Invoke this to run the CLI.

    :param args: namespace containing command line arguments
    """
    prometheus_client.start_http_server(args.port)
    run(**{k: v for k, v in vars(args).items() if k != "port"})


def parse_args() -> None:
    """Parse arguments from the command line."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=int(os.getenv("PROMETHEUS_LOG_PARSER_CLIENT_PORT", 8000)))
    add_parser_args(parser)
    return parser.parse_args()


if __name__ == "__main__":
    main(parse_args())
