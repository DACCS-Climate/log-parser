import abc
import asyncio
import inspect
import itertools
import os
from contextlib import asynccontextmanager

import anyio
import pytest

import log_parser.log_parser

pytestmark = [pytest.mark.anyio("asyncio"), pytest.mark.timeout(2)]


@asynccontextmanager
async def silent_timeout(*args, **kwargs):
    try:
        async with asyncio.timeout(*args, **kwargs) as cm:
            yield cm
    except TimeoutError:
        return


class TestTrackFile:
    @pytest.fixture
    async def tmp_log(self, tmp_path):
        log_file = anyio.Path(tmp_path / "test.log")
        await log_file.touch()
        return log_file

    @pytest.fixture
    async def tmp_log_pipe(self, tmp_path):
        log_file = anyio.Path(tmp_path / "test.log")
        os.mkfifo(log_file)
        return log_file

    @staticmethod
    async def delayed_write(file, text, delay, mode="w"):
        await asyncio.sleep(delay)
        async with await anyio.open_file(str(file), mode) as f:
            await f.write(text)

    @staticmethod
    def basic_line_parser(container):
        return lambda line, c=container: c.append(line.strip())

    @staticmethod
    def basic_line_parser_async(container):
        async def _(line, c=container):
            c.append(line.strip())

        return _

    async def test_file_contains_line(self, tmp_log):
        text = ["test 123"]
        await tmp_log.write_text("\n".join(text))
        output = []
        async with silent_timeout(0.1):
            await log_parser.track_file(str(tmp_log), [self.basic_line_parser(output)])
        assert output == text

    async def test_file_contains_lines(self, tmp_log):
        text = ["test 123", "test456"]
        await tmp_log.write_text("\n".join(text))
        output = []
        async with silent_timeout(0.1):
            await log_parser.track_file(str(tmp_log), [self.basic_line_parser(output)])
        assert output == text

    async def test_file_adds_line(self, tmp_log):
        text = ["test 123"]
        output = []
        async with silent_timeout(1.1), asyncio.TaskGroup() as tg:
            tg.create_task(log_parser.track_file(str(tmp_log), [self.basic_line_parser(output)]))
            tg.create_task(self.delayed_write(tmp_log, "\n".join(text), 0.1))
        assert output == text

    async def test_file_adds_lines(self, tmp_log):
        text = ["test 123", "test456"]
        output = []
        async with silent_timeout(1.1), asyncio.TaskGroup() as tg:
            tg.create_task(log_parser.track_file(str(tmp_log), [self.basic_line_parser(output)]))
            tg.create_task(self.delayed_write(tmp_log, "\n".join(text), 0.1))
        assert output == text

    async def test_file_appends_line(self, tmp_log):
        text = ["test 123", "test456"]
        await tmp_log.write_text(f"{text[0]}\n")
        output = []
        async with silent_timeout(1.1), asyncio.TaskGroup() as tg:
            tg.create_task(log_parser.track_file(str(tmp_log), [self.basic_line_parser(output)]))
            tg.create_task(self.delayed_write(tmp_log, text[1], 0.1, "a"))
        assert output == text

    async def test_file_multiple_line_parsers(self, tmp_log):
        text = ["test 123", "test456"]
        await tmp_log.write_text("\n".join(text))
        output = []
        n_parsers = 10
        async with silent_timeout(0.1):
            await log_parser.track_file(str(tmp_log), [self.basic_line_parser(output)] * n_parsers)
        assert output == list(itertools.chain.from_iterable(zip(*[text] * n_parsers)))

    async def test_file_adds_lines_poll_delay_less_than_timeout(self, tmp_log):
        text = ["test 123", "test456"]
        output = []
        async with silent_timeout(0.6), asyncio.TaskGroup() as tg:
            tg.create_task(log_parser.track_file(str(tmp_log), [self.basic_line_parser(output)], poll_delay=0.5))
            tg.create_task(self.delayed_write(tmp_log, "\n".join(text), 0.1))
        assert output == text

    async def test_file_adds_lines_poll_delay_more_than_timeout(self, tmp_log):
        text = ["test 123", "test456"]
        output = []
        async with silent_timeout(0.5), asyncio.TaskGroup() as tg:
            tg.create_task(log_parser.track_file(str(tmp_log), [self.basic_line_parser(output)], poll_delay=0.6))
            tg.create_task(self.delayed_write(tmp_log, "\n".join(text), 0.1))
        assert output == []

    async def test_file_contains_lines_tail(self, tmp_log):
        text = ["test 123", "test456"]
        await tmp_log.write_text("\n".join(text))
        output = []
        async with silent_timeout(0.1):
            await log_parser.track_file(str(tmp_log), [self.basic_line_parser(output)], tail=True)
        assert output == []

    async def test_file_adds_lines_tail(self, tmp_log):
        text = ["test 123", "test456"]
        output = []
        async with silent_timeout(1.1), asyncio.TaskGroup() as tg:
            tg.create_task(log_parser.track_file(str(tmp_log), [self.basic_line_parser(output)], tail=True))
            tg.create_task(self.delayed_write(tmp_log, "\n".join(text), 0.1))
        assert output == text

    async def test_file_appends_line_tail(self, tmp_log):
        text = ["test 123", "test456"]
        await tmp_log.write_text(f"{text[0]}\n")
        output = []
        async with silent_timeout(1.1), asyncio.TaskGroup() as tg:
            tg.create_task(log_parser.track_file(str(tmp_log), [self.basic_line_parser(output)], tail=True))
            tg.create_task(self.delayed_write(tmp_log, text[1], 0.1, "a"))
        assert output == text[1:]

    async def test_file_contains_lines_timeout_early(self, tmp_log):
        text = ["test 123", "test456"]
        await tmp_log.write_text("\n".join(text))
        output = []
        async with silent_timeout(1):
            with pytest.raises(TimeoutError):
                await log_parser.track_file(str(tmp_log), [self.basic_line_parser(output)], timeout=0.1)

    async def test_file_contains_line_async_line_parser(self, tmp_log):
        text = ["test 123"]
        await tmp_log.write_text("\n".join(text))
        output = []
        async with silent_timeout(0.1):
            await log_parser.track_file(str(tmp_log), [self.basic_line_parser_async(output)])
        assert output == text

    async def test_file_contains_line_mixed_line_parsers(self, tmp_log):
        text = ["test 123"]
        await tmp_log.write_text("\n".join(text))
        output = []
        async with silent_timeout(0.1):
            await log_parser.track_file(
                str(tmp_log), [self.basic_line_parser_async(output), self.basic_line_parser(output)]
            )
        assert output == text * 2

    async def test_pipe_contains_line(self, tmp_log_pipe):
        text = ["test 123"]
        output = []
        async with silent_timeout(1.1), asyncio.TaskGroup() as tg:
            tg.create_task(log_parser.track_file(str(tmp_log_pipe), [self.basic_line_parser(output)]))
            tg.create_task(self.delayed_write(tmp_log_pipe, "\n".join(text), 0.1))
        assert output == text

    async def test_pipe_contains_lines(self, tmp_log_pipe):
        text = ["test 123", "test 456"]
        output = []
        async with silent_timeout(1.1), asyncio.TaskGroup() as tg:
            tg.create_task(log_parser.track_file(str(tmp_log_pipe), [self.basic_line_parser(output)]))
            tg.create_task(self.delayed_write(tmp_log_pipe, "\n".join(text), 0.1))
        assert output == text


class _TrackTests(abc.ABC):
    @abc.abstractmethod
    @pytest.fixture
    def track_function(self):
        return log_parser.track

    @pytest.fixture
    def track_file_kwargs(self):
        return {
            k: p.default
            for k, p in inspect.signature(log_parser.log_parser.track_file).parameters.items()
            if p.default is not inspect.Parameter.empty
        }

    @pytest.fixture
    def mocked_track_file(
        self, mocker, track_file_kwargs
    ):  # this ensures track_file_kwargs are inspected before it is mocked
        mocker.patch("log_parser.log_parser.track_file", spec=True, new_callable=mocker.AsyncMock)
        return log_parser.log_parser.track_file

    def test_call_track_file_with_log_file(self, mocked_track_file, track_file_kwargs, track_function):
        track_function({"test_file": []})
        mocked_track_file.assert_called_once_with("test_file", [], **track_file_kwargs)

    def test_call_track_file_with_log_files(self, mocked_track_file, track_file_kwargs, mocker, track_function):
        config = {"test_file": [], "test_file2": []}
        track_function(config)
        mocked_track_file.assert_has_calls([mocker.call(f, p, **track_file_kwargs) for f, p in config.items()])

    def test_call_with_correct_parsers(self, mocked_track_file, track_file_kwargs, mocker, track_function):
        config = {"test_file": [1, 2], "test_file2": [4]}
        track_function(config)
        mocked_track_file.assert_has_calls([mocker.call(f, p, **track_file_kwargs) for f, p in config.items()])

    def test_call_track_file_with_tail(self, mocked_track_file, track_file_kwargs, track_function):
        track_function({"test_file": []}, tail=True)
        track_file_kwargs["tail"] = True
        mocked_track_file.assert_called_once_with("test_file", [], **track_file_kwargs)

    def test_call_track_files_with_tail(self, mocked_track_file, track_file_kwargs, mocker, track_function):
        config = {"test_file": [], "test_file2": []}
        track_function(config, tail=True)
        track_file_kwargs["tail"] = True
        mocked_track_file.assert_has_calls([mocker.call(f, p, **track_file_kwargs) for f, p in config.items()])

    def test_call_track_file_with_poll_delay(self, mocked_track_file, track_file_kwargs, track_function):
        track_function({"test_file": []}, poll_delay=0.5)
        track_file_kwargs["poll_delay"] = 0.5
        mocked_track_file.assert_called_once_with("test_file", [], **track_file_kwargs)

    def test_call_track_files_with_poll_delay(self, mocked_track_file, track_file_kwargs, mocker, track_function):
        config = {"test_file": [], "test_file2": []}
        track_function(config, poll_delay=0.5)
        track_file_kwargs["poll_delay"] = 0.5
        mocked_track_file.assert_has_calls([mocker.call(f, p, **track_file_kwargs) for f, p in config.items()])

    def test_call_track_file_with_timeout(self, mocked_track_file, track_file_kwargs, track_function):
        track_function({"test_file": []}, timeout=2)
        mocked_track_file.assert_called_once_with("test_file", [], **track_file_kwargs)

    def test_call_track_files_with_timeout(self, mocked_track_file, track_file_kwargs, mocker, track_function):
        config = {"test_file": [], "test_file2": []}
        track_function(config, timeout=2)
        mocked_track_file.assert_has_calls([mocker.call(f, p, **track_file_kwargs) for f, p in config.items()])


class TestTrack(_TrackTests):
    @pytest.fixture
    def track_function(self):
        return log_parser.track


class TestTrackAsync(_TrackTests):
    @pytest.fixture
    def track_function(self):
        return lambda *args, **kwargs: asyncio.run(log_parser.track_async(*args, **kwargs))
