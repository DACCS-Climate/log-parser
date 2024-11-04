import argparse
import glob
import importlib
import logging
import os
import sys
from collections import defaultdict
from collections.abc import Callable

from log_parser import track

logger = logging.getLogger(__name__)


def _load_parser_configs(parsers: list[str], config_variable: str) -> dict[str, list[Callable]]:
    """
    Import parser python files and extract the configuration settings from each.

    :param parsers: paths on disk that contain the the parser files
    :param config_variable: name of a constant that must exist in each parser file from which to load the configuration settings
    :return configs: dictionary where keys are ``log_file``s and values are ``line_parsers`` (see parameters for the :func:`log_parser.track_file` function)
    """
    configs = defaultdict(list)
    for parser in parsers:
        parser = os.path.realpath(parser)
        if os.path.isdir(parser):
            path_addition = parser
            parser_files = glob.glob(os.path.join(parser, "*.py"))
        else:
            path_addition = os.path.dirname(parser)
            parser_files = [parser]
        sys.path.append(path_addition)
        logger.debug(f"appended '{path_addition}' to sys.path")
        try:
            for file_path in parser_files:
                logger.info(f"loading parser from: {file_path}")
                parser_module = importlib.import_module(os.path.basename(os.path.splitext(file_path)[0]))
                for log_file, line_parsers in getattr(parser_module, config_variable).items():
                    configs[log_file].extend(line_parsers)
        finally:
            try:
                sys.path.pop(next(i for i in range(len(sys.path) - 1, -1, -1) if sys.path[i] == path_addition))
                logger.debug(f"removed '{path_addition}' from sys.path")
            except StopIteration:
                logger.debug(f"cannot remove '{path_addition}' from sys.path: it has already been removed")
    return dict(configs)


def run(
    parsers: list[str],
    config_variable: str,
    log_filename: str | None,
    log_level: int,
    poll_delay: int,
    tail: bool,
    timeout: int | None,
) -> None:
    """
    Load parser files and start tracking each log file identified within.

    :param parsers: paths on disk that contain the parser files
    :param poll_delay: how long to wait (in seconds) before checking if additional lines have been written to a file
    :param tail: only process lines that have been added to files *after* this function was initially called
    :param config_variable: name of a constant that must exist in each parser file from which to load the configuration settings
    :param timeout: returns after this many seconds have elapsed since this function was started, or run forever if ``None``

    .. note::
        Logging is configured here
    """
    logging.basicConfig(
        level=log_level, filename=log_filename, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    try:
        track(_load_parser_configs(parsers, config_variable), poll_delay, tail, timeout)
    except TimeoutError as e:
        logger.info(f"stopping execution because timeout was reached. Timeout message: '{e}'")


def _truthy(s: str | None) -> bool:
    """
    Return ``True`` iff ``s`` is a string that the argument parser should treat as a truthy value.

    :param s: string to evaluate for truthyness
    """
    return bool(s and s.lower().strip() in {"1", "true", "t"})


def add_parser_args(parser: argparse.ArgumentParser) -> None:
    """
    Add arguments to the argument parser used.

    :param parser: argument parser to add arguments to
    """
    log_level_mapping = logging.getLevelNamesMapping()
    parser.add_argument(
        "-p",
        "--parsers",
        default=[p for p in os.getenv("LOG_PARSER_PARSERS", "").split(":") if p],
        nargs="*",
        action="extend",
        help="path to parser files. Multiple file paths can be specified after this argument. "
        "If the path is a directory, all files in that directory ending with .py will be added.",
    )
    parser.add_argument(
        "--poll-delay",
        type=int,
        metavar="N",
        default=os.getenv("LOG_PARSER_POLL_DELAY", "1"),
        help="check if a log file has new lines every %(metavar)s seconds (default: 1)",
    )
    parser.add_argument(
        "--tail",
        action="store_true",
        default=_truthy(os.getenv("LOG_PARSER_TAIL")),
        help="only parse new lines added to log files in the future (default: False)",
    )
    parser.add_argument(
        "--config-variable",
        default=os.getenv("LOG_PARSER_CONFIG_VARIABLE", "LOG_PARSER_CONFIG"),
        help="the name of the variable in parser files that contains the configuration dictionary (default: LOG_PARSER_CONFIG)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=int(os.getenv("LOG_PARSER_TIMEOUT", 0)) or None,
        help="exit after this many seconds have elapsed (default: no timeout)",
    )
    parser.add_argument(
        "--log-filename",
        default=os.getenv("LOG_PARSER_LOG_FILENAME", None),
        help="write logs to this file (default: write to stdout)",
    )
    parser.add_argument(
        "--log-level",
        type=lambda level: log_level_mapping[level.upper()],
        choices=log_level_mapping.values(),
        default=os.getenv("LOG_PARSER_LOG_LEVEL", "INFO"),
        metavar=f"{{{','.join(log_level_mapping)}}}",
        help="log level (default: INFO)",
    )


def parse_args(args: list[str] | None = None) -> None:
    """
    Parse arguments from the command line.

    :param args: list of arguments to parse, if ``None`` then parse arguments from ``sys.argv``
    """
    parser = argparse.ArgumentParser()
    add_parser_args(parser)
    return parser.parse_args(args)


def main() -> None:
    """
    Run the CLI.

    This function is called when invoking the ``log-parser`` project script (see pyproject.toml)
    """
    run(**vars(parse_args()))


if __name__ == "__main__":
    main()
