# Python Flow Module

## Description

flow-python is a module to interact with the Flow stack using python.

## Install
```bash
$ git clone https://github.com/SpiderOak/flow-python.git
$ cd flow-python
$ sudo python setup.py install
```
## Simple Usage

Here's a simple script to list a user's Organizations/Teams:

```python
# !/usr/bin/env python
from flow import Flow

# Create flow intance and start using the API
flow = Flow('your-flow-username')

# Print user's organizations
print(flow.enumerate_orgs())

# Your application must make sure to call terminate when done with the flow object
flow.terminate()
```

## Listen for notifications

Here's a script that listens for messages and prints them to stdout:

```python
# !/usr/bin/env python
from flow import Flow

flow = Flow('your-flow-username')

def print_message(data):
    regular_messages = data["RegularMessages"]
    for message in regular_messages:
        print("Got message '%s' from ChannelID='%s'" %
              (message["Text"], message["ChannelID"]))

# Here we register our callback to be executed when we receive a message
flow.register_callback(Flow.MESSAGE_NOTIFICATION, print_message)

try:
	# Once you registered all your callbacks, all you have to do is loop.
    flow.process_notifications()
except:
    flow.terminate()
```

## TODO

- Implement remaining Flow API methods (e.g. enumerate_peer_verifications, create_device, etc.).
- Document all arguments of the Flow API. 
- Document Flow dict objects that are returned on many of the methods.
- Unit Testing the flow module.
- See TODOs in source code.
