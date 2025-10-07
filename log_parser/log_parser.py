import asyncio
import logging
import os
from collections.abc import Callable
from enum import Enum
from functools import wraps
from typing import Any

from anyio import AsyncFile, open_file

logger = logging.getLogger(__name__)


class _FileState(Enum):
    """
    Indicators for the state of a file.

    NOCHANGE  = the file has not changed or lines have been added to it
    TRUNCATED = the file has not changed and has been truncated
    DELETED   = the file has been deleted
    DIFFERENT = a file with the same name exists but it has a different file descriptor
    """

    NOCHANGE = 0
    TRUNCATED = 1
    DELETED = 2
    DIFFERENT = 3


async def _check_file_state(log_io: AsyncFile[str]) -> _FileState:
    """
    Check and return the state of the file currently opened as ``log_io``.

    :param log_io: file to check
    :return: state of the ``log_io`` file
    """
    try:
        same_name_file_stat = os.stat(log_io.name)
    except FileNotFoundError:
        return _FileState.DELETED
    file_stat = os.stat(log_io.fileno())
    if same_name_file_stat == file_stat:
        if not log_io.seekable():
            return _FileState.NOCHANGE
        if await log_io.tell() > file_stat.st_size:
            return _FileState.TRUNCATED
        else:
            return _FileState.NOCHANGE
    return _FileState.DIFFERENT


def _log_arguments(f: Callable) -> Callable:
    @wraps(f)
    def _(*args, **kwargs) -> Any:  # noqa: ANN401
        arg_string = ", ".join(str(a) for a in args)
        kwargs_string = ", ".join(f"{k}={v}" for k, v in kwargs.items())
        logger.debug(f"calling: {f.__name__}({arg_string}, {kwargs_string})")
        return f(*args, **kwargs)

    return _


@_log_arguments
async def track_file(
    log_file: str, line_parsers: list[Callable], poll_delay: int = 1, tail: bool = False, timeout: int | None = None
) -> None:
    """
    Read all lines from a file and apply each line parser to each line as it is read.

    If the end of the file is reached, this function will wait until more lines are added.

    :param log_file: path to a file to open for reading
    :param line_parsers: functions to apply to each line
    :param poll_delay: how long to wait (in seconds) before checking if additional lines have been written to the file
    :param tail: only process lines that have been added to the file *after* this function was initially called
    :param timeout: raise a ``TimeoutError`` after this many seconds have elapsed since this function was started, or run forever if ``None``
    :raises TimeoutError: see the ``timeout`` parameter
    """
    logger.info(f"tracking '{log_file}' starting from the {'end' if tail else 'beginning'}.")
    async with asyncio.timeout(timeout):
        log_io = await open_file(log_file)
        logger.debug(f"file '{log_file}' opened for reading")
        try:
            if tail and log_io.seekable():
                await log_io.seek(0, os.SEEK_END)
            while True:
                file_state = await _check_file_state(log_io)
                if file_state == _FileState.NOCHANGE:
                    async for line in log_io:
                        for line_parser in line_parsers:
                            if asyncio.iscoroutinefunction(line_parser):
                                await line_parser(line)
                            else:
                                line_parser(line)
                elif file_state == _FileState.TRUNCATED:
                    logger.info(
                        f"file '{log_file}' has been truncated. Tracking will resume from the beginning of the file."
                    )
                    await log_io.seek(0)
                elif file_state == _FileState.DIFFERENT:
                    logger.info(
                        f"file '{log_file}' has been replaced. Tracking will resume from the beginning of the file."
                    )
                    await log_io.aclose()
                    log_io = await open_file(log_file)
                elif file_state == _FileState.DELETED:
                    logger.info(
                        f"file '{log_file}' has been deleted. Tracking will resume if the file is created at a later time."
                    )
                # if file is deleted, do nothing and wait to see if it is recreated later on
                await asyncio.sleep(poll_delay)
        finally:
            await log_io.aclose()
            logger.debug(f"file '{log_file}' closed")


@_log_arguments
async def track_async(
    configs: dict[str, list[Callable]], poll_delay: int = 1, tail: bool = False, timeout: int | None = None
) -> None:
    """
    Asynchronously run the :func:`track_file` function for all files and line parsers in ``configs``.

    :param configs: dictionary where keys are ``log_file``s and values are ``line_parsers`` (see parameters for the :func:`track_file` function)
    :param poll_delay: how long to wait (in seconds) before checking if additional lines have been written to a file
    :param tail: only process lines that have been added to files *after* this function was initially called
    :param timeout: raise a ``TimeoutError`` after this many seconds have elapsed since this function was started, or run forever if ``None``
    :raises TimeoutError: see the ``timeout`` parameter
    """
    if timeout is not None:
        logger.info(f"timeout for tracking multiple files set to: {timeout} seconds")
    async with asyncio.timeout(timeout):
        async with asyncio.TaskGroup() as tg:
            for log_file, line_parsers in configs.items():
                # Note: timeout is explicitly set to None in favour of the timeout context manager in this function
                tg.create_task(track_file(log_file, line_parsers, poll_delay, tail, timeout=None))


@_log_arguments
def track(
    configs: dict[str, list[Callable]], poll_delay: int = 1, tail: bool = False, timeout: int | None = None
) -> None:
    """
    Run the :func:`track_file` function for all files and line parsers in ``configs``.

    :param configs: dictionary where keys are ``log_file``s and values are ``line_parsers`` (see parameters for the :func:`track_file` function)
    :param poll_delay: how long to wait (in seconds) before checking if additional lines have been written to a file
    :param tail: only process lines that have been added to files *after* this function was initially called
    :param timeout: raise a ``TimeoutError`` after this many seconds have elapsed since this function was started, or run forever if ``None``
    :raises TimeoutError: see the ``timeout`` parameter
    """
    asyncio.run(track_async(configs, poll_delay, tail, timeout))
