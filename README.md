[![Build Status](https://travis-ci.org/SpiderOak/flow-python.svg?branch=master)](https://travis-ci.org/SpiderOak/flow-python)

# Python Flow Module

## Description

flow-python is a module to interact with the Flow stack using python.

## Install

1. Download and install Semaphor: https://spideroak.com/opendownload.
2. Clone and install the flow-python repo:
```
$ git clone https://github.com/SpiderOak/flow-python.git
$ cd flow-python
$ python setup.py install
```

### Try it out with docker

```
$ docker build -t test/flow-python .
$ docker run -it test/flow-python
```

## Basic Usage

Here's a simple script to list a user's Organizations/Teams:
```python
#!/usr/bin/env python
from flow import Flow

# Create flow intance and start using the API
flow = Flow('flow-username')

# Print user's organizations
print(flow.enumerate_orgs())
```

Here's a script that listens for messages and prints them to stdout:
```python
#!/usr/bin/env python
from flow import Flow

flow = Flow('flow-username')

# Here we register our callback to be executed when we receive a message
@flow.message
def print_message(notif_type, notif_data):
    regular_messages = notif_data["regularMessages"]
    for message in regular_messages:
        print("Got message '%s' from ChannelID='%s'" %
              (message["text"], message["channelId"]))

# Once you registered all your callbacks, all you have to do is loop.
flow.process_notifications()
```

## How does flow-python work?

When a `Flow` object is created, flow-python spawns a `semaphor-backend` subprocess (this binary is packaged with [Semaphor](https://spideroak.com/opendownload)). Each flow-python API executed (e.g. `send_message()`, `new_channel()`, etc.) will perform a local HTTP request to the running semaphor-backend, which in turn will communicate securely with the Flow server.

```
Local                                       Cloud
+----------------------+                    +--------------------+
| +------------------+ |                    |                    |
| | semaphor-backend | |      TLS API       |  Flow Server       |
| | subprocess       <---------------------->  Encrypted Storage |
| +--+---------------+ |                    |                    |
|    |                 |                    +--------------------+
|    | HTTP API        |
|    |                 |
| +--+---------------+ |
| | Python app using | |
| | flow-python      | |
| +------------------+ |
+----------------------+
```

## Comments

- Tested support on Linux, Windows and MacOS.
- Supports Python2.7 and Python3.3-3.5
- If you intend to use one of the examples above, 'your-flow-username' should already be logged-in in your device.
- See [samples](samples/) directory for examples on how to use the module.
- An application should use a single instance of `flow.Flow` per account.
- Use `logging.getLogger("flow")` to configure the log level for the module.
- By default, local databases and `semaphor-backend` output are located under `~/.config/flow-python`, you can override this on `Flow` init (`db_dir`). The config directory prior to 0.3 was `~/.config/semaphor`, see [here](CHANGELOG.md#03).
- To start using `Flow` with an account you must use only one of these three API: (the three methods start the notification loop that listens from incoming events from the server)
  - `Flow.start_up  # This starts an already logged-in account`
  - `Flow.create_account  # This creates a new account`
  - `Flow.create_device  # This creates a new device for an existing account`
- `Flow` methods raise `Flow.FlowError` if something went wrong. 

## Auto-Updates

Since version 0.6, flow-python will, by default, auto-update the `semaphor-backend` binary. As soon as an update is available, it will automatically terminate the current `semaphor-backend` subprocess and start the new one.

Here's how you can turn off auto-updates (not recommended):
```python
account = Flow(extra_config={"FlowUpdateSignPublicKey": "off"})
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md)

## TODO

- Document all arguments of the Flow API methods.
- Document Flow dict objects that are returned on many of the methods. Or find a better way to return these (objects vs dicts?).
- Add support for multiple flowapp sessions.
