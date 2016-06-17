#! /usr/bin/env python
"""
echo_message.py
Bot that echoes messages back.
usage:
./echo_message.py
"""

from flow import Flow


flow = Flow()
# Start local account (by default the first one)
flow.start_up()

# Define a function to deal with 'message' notifications


@flow.message
def echo_message(notif_type, data):
    # There are two types of messages,
    # 'regularMessages' and 'channelMessages'.
    # We only care about 'regularMessages'
    # ('channelMessages' are used for other purposes)
    regular_messages = data["regularMessages"]
    for message in regular_messages:
        sender_id = message["senderAccountId"]
        # Just echo messages coming from other account
        if sender_id != flow.account_id():
            cid = message["channelId"]
            # Get the channel properties
            channel = flow.get_channel(cid)
            oid = channel["orgId"]
            msg = message["text"]
            # Echo the message back to the channel
            flow.send_message(oid, cid, "echo: %s" % msg)
            print("* msg '%s' echoed back to '%s'" % (
                msg,
                flow.get_peer_from_id(sender_id)["username"],
            ))

# Main loop to process notifications.
print("Listening for incoming messages... (press Ctrl-C to stop)")
flow.process_notifications()
