import abc
import argparse
import inspect
import itertools
import logging
import sys
from unittest.mock import patch

import pytest

import log_parser.cli


class TestRun:
    @pytest.fixture(autouse=True)
    def mocked_parse(self, mocker):
        mocker.patch("log_parser.cli.track", spec=True)
        return log_parser.cli.track

    @pytest.fixture
    def parse_kwargs(self):
        return {
            k: p.default
            for k, p in inspect.signature(log_parser.track).parameters.items()
            if p.default is not inspect.Parameter.empty
        }

    @pytest.fixture
    def all_kwargs(self, tmp_path, parse_kwargs):
        return {
            "parsers": [str(tmp_path)],
            "config_variable": "LOG_PARSER_CONFIG",
            "log_filename": None,
            "log_level": logging.INFO,
            **parse_kwargs,
        }

    @pytest.fixture
    def parser_files(self, tmp_path):
        def _():
            for i in itertools.count(1):
                name = f"test_parser_{i}"
                sys.modules.pop(name, None)
                yield tmp_path / f"{name}.py"

        return _()

    def test_load_parser_from_dir_single_log_file(self, mocked_parse, parse_kwargs, all_kwargs, parser_files):
        parser = next(parser_files)
        config = {"example_file": [1]}
        parser.write_text(f"{all_kwargs["config_variable"]}={config}")
        log_parser.cli.run(**all_kwargs)
        mocked_parse.assert_called_once_with(config, **parse_kwargs)

    def test_load_parser_from_dir_multi_log_file(self, mocked_parse, parse_kwargs, all_kwargs, parser_files):
        parser = next(parser_files)
        config = {"example_file": [1], "example_file2": [1]}
        parser.write_text(f"{all_kwargs["config_variable"]}={config}")
        log_parser.cli.run(**all_kwargs)
        mocked_parse.assert_called_once_with(config, **parse_kwargs)

    def test_load_parsers_from_dir_single_log_file(self, mocked_parse, all_kwargs, parser_files):
        n_parsers = 10
        for i, parser in enumerate(itertools.islice(parser_files, n_parsers)):
            config = {"example_file": [i]}
            parser.write_text(f"{all_kwargs["config_variable"]}={config}")
        log_parser.cli.run(**all_kwargs)
        assert len(mocked_parse.call_args_list) == 1
        configs = mocked_parse.call_args.kwargs.get("configs", mocked_parse.call_args.args[0])
        assert set(configs["example_file"]) == set(range(n_parsers))

    def test_load_parsers_from_dir_multi_log_file(self, mocked_parse, all_kwargs, parser_files):
        n_parsers = 10
        expected = {}
        for i, parser in enumerate(itertools.islice(parser_files, n_parsers)):
            config = {f"example_file_{i}": [i]}
            expected.update(config)
            parser.write_text(f"{all_kwargs["config_variable"]}={config}")
        log_parser.cli.run(**all_kwargs)
        assert len(mocked_parse.call_args_list) == 1
        configs = mocked_parse.call_args.kwargs.get("configs", mocked_parse.call_args.args[0])
        assert configs == expected

    def test_load_parsers_from_files(self, mocked_parse, all_kwargs, parser_files):
        n_parsers = 10
        parsers = []
        for i, parser in enumerate(itertools.islice(parser_files, n_parsers)):
            config = {"example_file": [i]}
            parser.write_text(f"{all_kwargs["config_variable"]}={config}")
            parsers.append(parser)
        all_kwargs["parsers"] = parsers
        log_parser.cli.run(**all_kwargs)
        assert len(mocked_parse.call_args_list) == 1
        configs = mocked_parse.call_args.kwargs.get("configs", mocked_parse.call_args.args[0])
        assert set(configs["example_file"]) == set(range(n_parsers))

    def test_load_parser_no_config_constant(self, all_kwargs, parser_files):
        parser = next(parser_files)
        config = {"example_file": [1]}
        parser.write_text(f"OTHER_CONFIG_CONSTANT={config}")
        with pytest.raises(AttributeError) as e:
            log_parser.cli.run(**all_kwargs)
        assert all_kwargs["config_variable"] in str(e)

    def test_passes_poll_delay(self, mocked_parse, parse_kwargs, all_kwargs, parser_files):
        parser = next(parser_files)
        config = {}
        parser.write_text(f"{all_kwargs["config_variable"]}={config}")
        all_kwargs["poll_delay"] += 1
        parse_kwargs["poll_delay"] += 1
        log_parser.cli.run(**all_kwargs)
        mocked_parse.assert_called_once_with(config, **parse_kwargs)

    def test_passes_tail(self, mocked_parse, all_kwargs, parse_kwargs, parser_files):
        parser = next(parser_files)
        config = {}
        parser.write_text(f"{all_kwargs["config_variable"]}={config}")
        all_kwargs["tail"] = not all_kwargs["tail"]
        parse_kwargs["tail"] = not parse_kwargs["tail"]
        log_parser.cli.run(**all_kwargs)
        mocked_parse.assert_called_once_with(config, **parse_kwargs)

    def test_passes_timeout(self, mocked_parse, all_kwargs, parse_kwargs, parser_files):
        parser = next(parser_files)
        config = {}
        parser.write_text(f"{all_kwargs["config_variable"]}={config}")
        all_kwargs["timeout"] = 1
        parse_kwargs["timeout"] = 1
        log_parser.cli.run(**all_kwargs)
        mocked_parse.assert_called_once_with(config, **parse_kwargs)

    def test_catches_timeout(self, mocked_parse, all_kwargs, parse_kwargs, parser_files):
        parser = next(parser_files)
        config = {}
        parser.write_text(f"{all_kwargs["config_variable"]}={config}")
        mocked_parse.side_effect = TimeoutError("test")
        log_parser.cli.run(**all_kwargs)
        mocked_parse.assert_called_once_with(config, **parse_kwargs)


class _ParseTests(abc.ABC):
    @pytest.fixture
    def parser_defaults(self):
        return {
            "config_variable": "LOG_PARSER_CONFIG",
            "parsers": [],
            "poll_delay": 1,
            "tail": False,
            "timeout": None,
            "log_filename": None,
            "log_level": logging.INFO,
        }

    @pytest.fixture
    def parser_non_defaults(self):
        return {
            "config_variable": "SOME_OTHER_CONFIG",
            "parsers": ["dir-dir-dir"],
            "poll_delay": 2,
            "tail": True,
            "timeout": 1,
            "log_filename": "test-log-output.log",
            "log_level": logging.CRITICAL,
        }

    @abc.abstractmethod
    def parse_args(self, args=[]):
        raise NotImplementedError

    def test_correct_args(self, parser_defaults):
        assert vars(self.parse_args()).keys() == parser_defaults.keys()

    def test_correct_defaults(self, parser_defaults):
        assert vars(self.parse_args()) == parser_defaults

    def test_all_settable(self, parser_non_defaults):
        args = []
        for key, val in parser_non_defaults.items():
            args.append(f"--{key.replace('_', '-')}")
            if key == "parsers":
                args.extend(val)
            elif key == "log_level":
                args.append(logging.getLevelName(val))
            elif key != "tail":
                args.append(str(val))
        assert vars(self.parse_args(args)) == parser_non_defaults

    def test_defaults_settable_with_env_vars(self, parser_non_defaults, monkeypatch):
        with monkeypatch.context() as m:
            for key, val in parser_non_defaults.items():
                if key == "parsers":
                    env_val = ":".join(val)
                elif key == "log_level":
                    env_val = logging.getLevelName(val)
                else:
                    env_val = str(val)
                m.setenv(f"LOG_PARSER_{key.upper()}", env_val)
            assert vars(self.parse_args()) == parser_non_defaults

    def test_tail_settable_with_truthy_env_var(self, monkeypatch):
        results = {}
        with monkeypatch.context() as m:
            for val in ["t", "T", "True", "true", "TRUE", "TrUe", "1"]:
                m.setenv("LOG_PARSER_TAIL", val)
                results[val] = self.parse_args().tail
        assert all(results.values())

    def test_tail_settable_with_falsy_env_var(self, monkeypatch):
        results = {}
        with monkeypatch.context() as m:
            for val in ["f", "F", "tru", "asdf", ":", "", "0", "false", "False"]:
                m.setenv("LOG_PARSER_TAIL", val)
                results[val] = self.parse_args().tail
        assert not any(results.values())


class TestAddParserArgs(_ParseTests):
    def parse_args(self, args=[]):
        parser = argparse.ArgumentParser()
        log_parser.cli.add_parser_args(parser)
        return parser.parse_args(args)


class TestParseArgs(_ParseTests):
    def parse_args(self, args=[]):
        return log_parser.cli.parse_args(args)


class TestMain(_ParseTests):
    @pytest.fixture(autouse=True)
    def mocked_run(self, mocker):
        mocker.patch("log_parser.cli.run", spec=True)

    def parse_args(self, args=[]):
        with patch.object(sys, "argv", sys.argv[:1] + args):
            log_parser.cli.main()
        return argparse.Namespace(**log_parser.cli.run.call_args.kwargs)
