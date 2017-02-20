FROM python:2.7

MAINTAINER Lucas Manuel Rodriguez <lucas@spideroak-inc.com>

# Update pip
RUN pip install --upgrade \
    pip

# Download and install Semaphor
RUN wget https://spideroak.com/releases/semaphor/debian \
    && dpkg -i debian \
    && rm -rf debian

# Install flow-python
RUN pip install git+https://github.com/SpiderOak/flow-python.git
