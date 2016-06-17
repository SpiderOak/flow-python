#! /usr/bin/env python
"""
install_bot.py
Installs a bot in the system.
usage:
./install_bot.py <username> <recoveryKey>
"""

import os
import sys
import time
import string
import random

from flow import Flow


if len(sys.argv) < 3:
    print("usage: %s <username> <recoveryKey>" % sys.argv[0])
    sys.exit(os.EX_USAGE)

username = sys.argv[1]
password = sys.argv[2]

flow = Flow()


print("* Checking if account is already installed...")
try:
    flow.start_up(
        username=username,
    )
    print("* Account already installed.")
    sys.exit(0)
except Flow.FlowError as flow_err:
    pass


print("* Account not installed, trying local device creation...")
try:
    flow.create_device(
        username=username,
        password=password,
        device_name="test-device",
    )
    time.sleep(2)
    print("* Account has been installed locally.")
except Flow.FlowError as flow_err:
    pass


print("* Account does not exist, creating account...")
try:
    flow.create_account(
        username=username,
        password=password,
        device_name="test_device",
        phone_number="".join(random.choice(string.digits) for _ in range(10)),
    )
    time.sleep(2)
    print("* Account has been successfully created and installed locally.")
    sys.exit(0)
except Flow.FlowError as flow_err:
    print("# Error: Account couldn't be installed.")
