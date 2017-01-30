FROM python:2.7

MAINTAINER Lucas Manuel Rodriguez <lucas@spideroak-inc.com>

# Update pip
RUN pip install --upgrade \
    pip

# Download Semaphor
RUN wget https://spideroak.com/releases/semaphor/debian \
    && dpkg -i debian \
    && rm -rf debian

# Install flow-python
RUN git clone https://github.com/SpiderOak/flow-python.git
WORKDIR flow-python
RUN pip install .
