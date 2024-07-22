FROM registry.fedoraproject.org/fedora:40

ADD . /llm-load-test/

WORKDIR /llm-load-test/

ARG GIT_BRANCH=main

ENV LLM_LOAD_TEST_CONFIG=config.yaml
ENV LLM_LOAD_TEST_LOG_LEVEL=warning

RUN dnf -y update \
 && dnf -y install git python3-pip

RUN git switch $GIT_BRANCH
RUN pip3 install -r requirements.txt

CMD python3 load_test.py -c $LLM_LOAD_TEST_CONFIG -log $LLM_LOAD_TEST_LOG_LEVEL
