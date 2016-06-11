#! /usr/bin/env python
"""
auto_join.py
Bot to accept all Team join requests from a certain team.
It will also add the requestor to all channels within the Team.
usage:
./auto_join.py <teamId>
"""

import os
import sys

from flow import Flow


if len(sys.argv) < 2:
    print("usage: %s <teamId>" % sys.argv[0])
    sys.exit(os.EX_USAGE)

team_id = sys.argv[1]

flow = Flow()
# Log in with the first local device found in the system
flow.start_up()

# Callback to automatically add users to the team and all its channels


def accept(notif_type, notif_data):
    for ojr in notif_data:
        if ojr["orgId"] == team_id:
            user_id = ojr["accountId"]
            username = flow.get_peer_from_id(user_id)["username"]
            # Add user to Team
            flow.org_add_member(team_id, user_id, "m")
            print("* user '%s' added to team." % username)
            # Add user to all Channels within Team
            for channel in flow.enumerate_channels(team_id):
                flow.channel_add_member(team_id, channel["id"], user_id, "m")
                print("  - also added to channel '%s'." % channel["name"])

# You can use 'register_callback' or just add the '@flow.org_join_request'
# decorator to 'accept'
flow.register_callback(Flow.ORG_JOIN_REQUEST_NOTIFICATION, accept)

# Main loop
print("Listening for incoming team join requests... (press Ctrl-C to stop)")
flow.process_notifications()
