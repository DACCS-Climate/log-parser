# Log Parser

Monitor log files and execute custom code whenever a new line is added to the logs.

## Installation

```shell
pip install git+https://github.com/DACCS-Climate/log-parser.git
```

## Usage

The Log Parser code can either be used as a python package or run directly from the command line

### Package

#### `track` and `track_async`

The `log_parser` package has two main public functions: `track` and `track_async`.

Both do the same thing, they start tracking log files and apply [line parser](#what-is-a-line-parser) functions 
to each line in the files as they are read.

Both functions accept the same parameters and do the exact same thing. The only real difference is that `track`
is a normal function and `track_async` is an 
[asynchronous coroutine](https://docs.python.org/3/library/asyncio-task.html). This means that they must be invoked
differently:

```python
import log_parser

log_parser.track(*args, **kwargs)

# this does the same thing as
import asyncio

asyncio.run(log_parser.track_async(*args, **kwargs))
```

In all of the usage examples below, we will use the `track(*args, **kwargs)` version for demonstration purposes
but know that either version is possible.

Both functions have the following parameters:<a id="track-parameters"></a>

- `configs`: dictionary where keys are paths to log files and values are a list of [line parsers](#what-is-a-line-parser)
- `poll_delay`: number indicating how long to wait (in seconds) before checking if additional lines have been written to a file
- `tail`: if true, only process lines that have been added to files *after* this function was initially called
- `timeout`: raise a `TimeoutError` after this many seconds have elapsed since this function was started, or run forever if `None`

#### `track_file`

The `log_parser` package also contains another asynchronous coroutine `track_file` which can be used to track
a single file at a time. This can be useful if you want to track different files with different configuration
options. For example to track two different files with different `timeout` options, you could do something like:

```python
import asyncio
from log_parser import track_file

async def catch_timeout(coroutine):
    try:
        await coroutine
    except TimeoutError:
        return

async def my_coroutine():
    async with asyncio.TaskGroup() as tg:
        tg.create_task(catch_timeout(track_file("file.log", [line_parser, other_line_parser], timeout=10)))
        tg.create_task(catch_timeout(track_file("other_file.log", [line_parser, other_line_parser], timeout=20)))

asyncio.run(my_coroutine())
```

`track_file` has the following parameters:

- `log_file`: path to a log file to track 
- `line_parsers` a list of [line parsers](#what-is-a-line-parser)
- `poll_delay`: (see [parameters](#track-parameters) for `track` and `track_async`)
- `tail`: (see [parameters](#track-parameters) for `track` and `track_async`)
- `timeout`: (see [parameters](#track-parameters) for `track` and `track_async`)

#### Usage Examples

Track a single log file named `example.log` with a [line parser](#what-is-a-line-parser) that simply prints each line to stdout:

```python
import log_parser

log_parser.track({"example.log": [print]})
```

By default, the example above will run forever, waiting until new lines are added to the file. To set a timeout so that
a `TimeoutError` is raised after a specified number of seconds have elapsed:

```python
import log_parser

log_parser.track({"example.log": [print]}, timeout=10) # raises a TimeoutError after 10 seconds
```

By default, the examples above will read as many lines from `example.log` as possible and then wait until
there are more lines to read. It will check for new lines every second by default. To change how often it will check
for new lines:

```python
import log_parser

log_parser.track({"example.log": [print]}, poll_delay=3) # checks every 3 seconds
```

By default, the examples above will read all lines in the files specified in [`config`](#track-parameters). To only
read new lines, not ones that are already present in the file:

```python
import log_parser

log_parser.track({"example.log": [print]}, tail=True) # waits until new lines are added to the file
```

This can be useful if you do not want to reparse all existing lines in a file if you restart tracking later on.

You can specify multiple files and multiple [line parsers](#what-is-a-line-parser) in the [`config`](#track-parameters)
argument. For example:

```python
import log_parser

log_parser.track({"example.log": [print, other_function], "example2.log": [other_function, and_another_function]})
```

### Command Line Interface (CLI)

The log parser can also be invoked from the command line using the `log-parser` executable.

`log-parser` must be called with at least one `--parsers` option. These are paths to python files that contain a configuration
variable named `LOG_PARSER_CONFIG` by default (this can be changed with the `--config-variable` option).

This variable contains a python dictionary where keys are paths to log files and values are a list of 
[line parsers](#what-is-a-line-parser).

Multiple python files can be specified using the `--parsers` option.

For an explanation of the rest of the command line options, call `log-parser` with the `--help` flag.

#### Environment Variables

All command line options can also be specified using an environment variable with the prefix `LOG_PARSER`.

For example, the `--config-variable` option can also be specified by setting `LOG_PARSER_CONFIG_VARIABLE`.

In general, the accepted values for environment variables are the same as the command line option it is 
replacing. However, not the following exceptions:

- to specify multiple parser files using `LOG_PARSER_PARSERS`, ensure that the files are `:` delimited
- when setting the `LOG_PARSER_TAIL` variable, values such as `t`, `true` and `1` will set the `tail` option.

Options passed on the command line will override environment variables with the exception of `--parsers` which
will extend the list of parsers passed as an environment variable. For example:

```sh
LOG_PARSER_CONFIG_VARIABLE=some_var log-parser --config-variable other_var  # sets config_variable to 'other var'
LOG_PARSER_PARSERS="test.py:others/" log-parser --parsers another.py # sets parsers to ["test.py", "others/", "another.py"]
```

#### Usage Examples

Load configuration options from one file located at `examples/example.py` and run the log parser:

```sh
mkdir examples/
echo "LOG_PARSER_CONFIG={'example.log': [print]}" > example.py
log-parser --parsers examples/example.py
```

The example above is roughly equivalent to executing in python:

```python
import log_parser

log_parser.track({"example.log": [print]})
```

Load configuration options from multiple python files located in the `examples/` directory and run the log parser:

```sh
mkdir examples/
echo "LOG_PARSER_CONFIG={'example.log': [print]}" > example1.py
echo "LOG_PARSER_CONFIG={'other.log': [print]}" > example2.py
echo "import json; LOG_PARSER_CONFIG={'other.log': [json.loads]}" > some_other_name.py
log-parser --parsers examples/
```

The example above is roughly equivalent to executing in python:

```python
import json
import log_parser

log_parser.track({"example.log": [print], "other.log": [print, json.loads]})
```

## FAQ

#### What is a line parser

A line parser is any function that takes a string as a single argument (a single line from a log file).
What it does with that string is up to you!

Line parsers will be called with a single string as an argument so its signature must correspond to:

```python
from typing import Any

def line_parser(line: str, **kwargs) -> Any:
    ...
```

Line parsers may also be coroutine functions. For example:

```python
from typing import Any

async def line_parser(line: str, **kwargs) -> Any:
    ...
```

#### How does Log Parser handle log rotation or file deletion?

While Log Parser is tracking a file, the file may be deleted, truncated, or replaced. Log Parser handles each of 
these scenarios in the following ways:

- Deleted: Log Parser checks every [`poll_delay`](#track-parameters) seconds if a new file has been created at the
           same path. If it has, it treats that file as having been replaced (see below).
- Truncated: Log Parser continues reading lines from the beginning of the file (regardless of the value of 
             [`tail`](#track-parameters)).
- Replaced: The new file located at given path will be opened for reading and Log Parser will continue tracking that file.

#### How do I track logs that haven't been written to a file?

Log Parser currently only supports reading logs from files. We'd like to support other log sources in the future though.
Feel free to [contribute](#development) to this project if you want to speed up support for this feature.

## Extensions

Extensions written for Log Parser can be found in the [extensions](./extensions/) directory. These contain python code
that extend the Log Parser in some way. For example, the [prometheus extension](./extensions/prometheus/) starts up a 
prometheus client before starting to track files so that parsers can export log information as 
[prometheus metrics](https://prometheus.github.io/client_python/instrumenting/).

All extensions must contain two files:

- `cli.py` the command line interface for this extension
- `requirements.txt` a [pip formatted](https://pip.pypa.io/en/stable/reference/requirements-file-format/) requirements file
 (can be empty).

The name of the extension is the name of the directory located directly under the the [extensions](./extensions/) directory
where the code for this extension is located.

## Docker

Docker images for this project can be found at https://hub.docker.com/r/marbleclimate/log-parser

To run the log parser with Docker:

```sh
docker run -it --rm marbleclimate/log-parser:latest --help
```

This is the equivalent of installing the Log Parser locally and running:

```sh
log-parser --help
```

The docker images also contain all extensions by default and they can be run by changing the entrypoint. For example,
if you'd like to run the `prometheus` extension:

```sh
docker run -it --rm --entrypoint log-parser-prometheus marbleclimate/log-parser:latest --help
```

The entrypoint for all extensions is `log-parser-<name>` where `<name>` is the name of the extension.

All parsers and logs must be visible to the docker container. This can be accomplished by mounting them as volumes.
For example, if you have some parsers in a directory named `./my-parsers` and logs being written to a directory named
`./my-logs` you can run:

```sh
docker run -it --rm -v './my-parsers:/parsers:ro' -v './my-logs:/logs:ro' marbleclimate/log-parser:latest --parsers /parsers 
```

Note that in the example above, the parsers refer to the location of the log files in the container (`/logs`), not on the
host (`./my-logs`).

## Development

To contribute to this project please fork [this repository](https://github.com/DACCS-Climate/log-parser) on GitHub, make 
changes as necessary and then submit a pull request to this repository.

We recommend installing a local copy of this package into a virtual environment while you develop:

```shell
git clone https://github.com/<location-of-your-fork>/log-parser
cd log-parser
python3 -m venv venv
. ./venv/bin/activate
pip install -e .[dev,test]
```

### Formatting and Linting

This project uses the [`ruff`](https://docs.astral.sh/ruff/) formatter and linter to enforce rules (defined in 
[`pyproject.toml`](./pyproject.toml)).

To manually run [`ruff`](https://docs.astral.sh/ruff/) to check your code:

```shell
ruff check # linter
ruff format # formatter
```

You can also install the [`pre-commit`](https://pre-commit.com/) hooks that come with this project

```shell
pre-commit install
```

and now the linter and formatter will be run every time you create a commit.

### Testing

This project uses [`pytest`](https://docs.pytest.org/) to run tests and all test code is in the [`test/`](./test/) directory:

```shell
pytest test/
```
