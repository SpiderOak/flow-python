# Python Flow Module

## Description

flow-python is a module to interact with the Flow stack using python.

## Install
```
$ git clone https://github.com/SpiderOak/flow-python.git
$ cd flow-python
$ python setup.py install
```
## Basic Usage

Here's a simple script to list a user's Organizations/Teams:
```python
#!/usr/bin/env python
from flow import Flow

# Create flow intance and start using the API
flow = Flow('your-flow-username')

# Print user's organizations
print(flow.enumerate_orgs())
```

Here's a script that listens for messages and prints them to stdout:
```python
#!/usr/bin/env python
from flow import Flow

flow = Flow('your-flow-username')

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

## Comments

- Tested support on Linux, Windows and MacOS.
- Supports Python2.7 and Python3.3-3.5
- If you intend to use one of the examples above, 'your-flow-username' should already be logged-in in your device.
- See [samples](samples/) directory for examples on how to use the module.
- An application should use a single instance of `flow.Flow` per account.
- Use `logging.getLogger("flow")` to configure the log level for the module.
- By default, local databases and `semaphor-backend` output are located under `~/.config/flow-python`, you can override this on `Flow` init (`db_dir`). The config directory prior to 0.3 was `~/.config/semaphor`, see [here](CHANGELOG.md#03).
- `Flow` init starts the `semaphor-backend` as a subprocess.
- To start using `Flow` with an account you must use only one of these three API: (the three methods start the notification loop that listens from incoming events from the server)
  - `Flow.start_up  # This starts an already logged-in account`
  - `Flow.create_account  # This creates a new account`
  - `Flow.create_device  # This creates a new device for an existing account`
- `Flow` methods raise `Flow.FlowError` if something went wrong. 

## Changelog

See [CHANGELOG.md](CHANGELOG.md)

## TODO

- Implement remaining Flow API methods.
- Document all arguments of the Flow API. 
- Document Flow dict objects that are returned on many of the methods. Or find a better way to return these (objects vs dicts?).
- Unit Testing the flow module.
- It has support for multiple sessions but this hasn't been tested yet.
- Auto-generate API methods from the `flowapp` API.
- See other TODOs in source code.
