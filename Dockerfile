ARG EXTENSIONS="prometheus" # space delimited string

FROM python:3.13-alpine

ARG EXTENSIONS

COPY . /log_parser/

RUN python -m pip install /log_parser $(for imp in ${EXTENSIONS}; do echo "-r /log_parser/extensions/${imp}/requirements.txt"; done)

RUN mkdir /log-parser-bin && \
    for imp in ${EXTENSIONS}; do \
        echo '#!/bin/sh' > "/log-parser-bin/log-parser-${imp}" && \
        echo "exec python /log_parser/extensions/${imp}/cli.py" '"$@"' >> "/log-parser-bin/log-parser-${imp}" && \
        chmod u+x "/log-parser-bin/log-parser-${imp}"; \
    done

ENV PATH="$PATH:/log-parser-bin"

ENTRYPOINT [ "log-parser" ]
