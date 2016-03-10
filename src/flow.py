"""
Flow Synchronous API Python Module.
All Flow API responses are represented with Python dicts.
"""

import sys
import subprocess
import json
import requests
import threading
import Queue
import definitions
import os


class Flow(object):
    """Class to interact with the Flow API.
    Request/Responses are synchronous.
    """

    # Notification Types
    ORG_NOTIFICATION = "org"
    CHANNEL_NOTIFICATION = "channel"
    MESSAGE_NOTIFICATION = "message"
    CHANNEL_MEMBER_NOTIFICATION = "channel-member-event"

    class _Session(object):
        """Internal class to hold session data."""

        _MAX_QUEUE_SIZE = 128

        def __init__(self, flow, sid):
            """Arguments:
            flow : Flow instance
            sid : int, SessionID
            """
            self.sid = sid
            self.flow = flow
            self.callbacks = {}  # Notification Name -> Function Object
            self.notification_queue = Queue.Queue()
            self.listen_notifications = threading.Event()
            self.notification_thread = threading.Thread(
                target=self._notification_loop,
                args=())
            self.callback_lock = threading.Lock()

        def start_notification_loop(self):
            """Starts the thread that polls for notifications."""
            self.listen_notifications.set()
            self.notification_thread.start()

        def unregister_callback(self, notification_name):
            """Unregisters a callback for this session.
            Arguments:
            notification_name : string, type of the notification.
            """
            self.callback_lock.acquire()
            del self.callbacks[notification_name]
            self.callback_lock.release()

        def register_callback(self, notification_name, callback):
            """Registers a callback for a notification type.
            Arguments:
            notification_name : string, type of the notification
            callback : function object that receives a string as argument.
            """
            self.callback_lock.acquire()
            self.callbacks[notification_name] = callback
            self.callback_lock.release()

        def _queue_changes(self, changes):
            """Queues the changes of registered change types.
            Arguments:
            changes : Change dict/s returned by wait_for_notification.
            """
            # If single notification, then make a one-elem list
            if not isinstance(changes, list):
                changes = [changes]
            for change in changes:
                if change and "type" in change \
                   and change["type"] in self.callbacks:
                    # This check should leave the queue with
                    # an approximate size of _MAX_QUEUE_SIZE
                    if self.notification_queue.qsize() > self._MAX_QUEUE_SIZE:
                        notification = self.notification_queue.get()
                        self.flow._print_debug(
                            "Queue is full: ignoring notification '%s'" %
                            notification["data"])
                    self.notification_queue.put(change)

        def _notification_loop(self):
            """Loops calling WaitForNotification on this session."""
            while self.listen_notifications.is_set():
                try:
                    changes = self.flow.wait_for_notification(self.sid)
                    self.callback_lock.acquire()
                    self._queue_changes(changes)
                    self.callback_lock.release()
                except Flow.FlowError:
                    pass

        def consume_notification(self, timeout_secs):
            """Consumes the notification queue for this session
            and execute the callbacks. This call blocks until there is
            a notification ready to be processed or if timeouts
            after 'timeout_secs'.
            Arguments:
            timeouts_secs : float, seconds to block waiting for notifications.
            """
            notification_consumed = False
            try:
                notification = \
                    self.notification_queue.get(
                        block=True, timeout=timeout_secs)
                try:
                    self.callback_lock.acquire()
                    self.callbacks[notification["type"]](
                        notification["data"])
                except KeyError:
                    self.flow._print_debug(
                        "Notification of type '%s' not supported." %
                        notification["type"])
                except Exception as exception:
                    self.flow._print_debug(
                        "Error: %s" % str(exception))
                finally:
                    self.callback_lock.release()
                notification_consumed = True
            except Queue.Empty:
                notification_consumed = False
            return notification_consumed

        def close(self):
            """Closes the session by terminating the listener thread."""
            self.listen_notifications.clear()
            if self.notification_thread.is_alive():
                self.notification_thread.join()

    class FlowError(Exception):
        """Exception class for Flow related errors"""
        pass

    def __init__(self,
                 username="",
                 server_uri="",
                 flowappglue="",
                 debug=False,
                 host="",
                 port="",
                 db_dir="",
                 schema_dir="",
                 attachment_dir="",
                 use_tls="true"):
        """Initializes the Flow object. It starts and configures
        flowappglue local server as a subprocess.
        It also starts a new session so that you can start using
        the Flow API. You should be good by calling this function
        with no arguments.
        It will call start_up() if a username is provided.
        Arguments:
        flowappglue : string, path to the flowappglue binary,
        if empty, then it tries to determine the location.
        debug : boolean.
        """
        self.debug = debug
        if not flowappglue:
            flowappglue = definitions.get_default_flowappglue_path()
        self._check_file_exists(flowappglue)
        self._flowappglue = subprocess.Popen(
            [flowappglue, "0"], stdout=subprocess.PIPE)
        token_port_line = json.loads(self._flowappglue.stdout.readline())
        self._token = token_port_line["token"]
        self._port = token_port_line["port"]
        self.sessions = {}  # SessionID -> _Session
        # Configure flowappglue and create the session
        self._config(host, port, db_dir, schema_dir, attachment_dir, use_tls)
        self._current_session = self.new_session()
        self._loop_process_notifications = False
        # If username available then start the session
        if username:
            self.start_up(username, server_uri)

    def terminate(self):
        """Shuts down the flowappglue local server.
        It must be called when you are done using the Flow API.
        """
        # Terminate the flowappglue process
        if self._flowappglue:
            self._flowappglue.terminate()
        # Close all sessions
        sids = list(self.sessions.keys())
        for sid in sids:
            self.close(sid)

    def _print_debug(self, msg):
        """Prints msg debug strings to stdout (if self.debug is True)"""
        if self.debug:
            print(msg.encode('utf-8'))
            sys.stdout.flush()

    def _run(self, method, **params):
        """Performs the HTTP JSON POST against
        the flowappglue server on localhost.
        Arguments:
        method : string, API method name.
        params : kwargs, request parameters.
        Returns a dict with the response received from the flowappglue,
        it returns the 'result' part of the response.
        """
        request_str = json.dumps(
            dict(
                method=method,
                params=[params],
                token=self._token))
        self._print_debug("request: %s" % request_str)
        try:
            response = requests.post(
                "http://localhost:%s/rpc" %
                self._port,
                headers={'Content-type': 'application/json'},
                data=request_str)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as flow_err:
            raise Flow.FlowError(str(flow_err))
        response_data = json.loads(response.text, encoding='utf-8')
        self._print_debug(
            "response: HTTP %s : %s" %
            (response.status_code, response.text))
        if "error" in response_data.keys() and len(response_data["error"]) > 0:
            raise Flow.FlowError(response_data["error"])
        if "result" in response_data.keys():
            return response_data["result"]
        else:
            return response_data

    @staticmethod
    def _check_file_exists(path, create_if_non_existent=False):
        """Internal check for path existence.
        Arguments:
        path : string, path to check for existence.
        Raises a Flow.FlowError exception if the path does not exist.
        """
        if not os.path.exists(path):
            if not create_if_non_existent:
                raise Flow.FlowError(
                    "Cannot access '%s', no such file or directory." % path)
            os.makedirs(path, 0o700)

    def _config(
            self,
            host="",
            port="",
            db_dir="",
            schema_dir="",
            attachment_dir="",
            use_tls="true"):
        """Sets up the basic configuration parameters for FlowApp
        to talk FlowServ and create local accounts.
        If arguments are empty, then it will try to determine the
        configuration.
        """
        # try to determine defaults if not specified
        if not host:
            host = definitions.DEFAULT_SERVER
        if not port:
            port = definitions.DEFAULT_PORT
        if not db_dir:
            db_dir = definitions.get_default_db_path()
        if not schema_dir:
            schema_dir = definitions.get_default_schema_path()
        if not attachment_dir:
            attachment_dir = definitions.get_default_attachment_path()
        self._check_file_exists(schema_dir)
        self._check_file_exists(db_dir, True)
        self._check_file_exists(attachment_dir, True)
        self._run(method="Config",
                  FlowServHost=host,
                  FlowServPort=port,
                  FlowLocalDatabaseDir=db_dir,
                  FlowLocalSchemaDir=schema_dir,
                  FlowLocalAttachmentDir=attachment_dir,
                  FlowUseTLS=use_tls,
                  )

    def register_callback(self, notification_name, callback, sid=0):
        """Registers a callback to be executed for
        a specific notification type.
        Arguments:
        sid : int, SessionID
        notification_name : string, type of the notification.
        callback : function object that receives a string as argument.
        Upon callback execution, the string argument of the callback
        will contain the "data" section of the notification.
        """
        if not sid:
            sid = self._current_session
        self.sessions[sid].register_callback(notification_name, callback)

    def unregister_callback(self, notification_name, sid=0):
        """Unregisters a callback, this makes the Flow module
        to ignore notifications of this type.
        Arguments:
        sid : int, SessionID
        notification_name : string, type of the notification.
        """
        if not sid:
            sid = self._current_session
        self.sessions[sid].unregister_callback(notification_name)

    def process_one_notification(self, timeout_secs=0.05, sid=0):
        """Processes a single notification.
        Returns 'True' if a notification was processed, 'False'
        meaning no notification was available for processing.
        This is to be used on a loop using the return value.
        Arguments:
        timeout_secs : float, seconds to block on the notification queue.
        sid : int, SessionI.
        """
        if not sid:
            sid = self._current_session
        return self.sessions[sid].consume_notification(timeout_secs)

    def set_processing_notifications(self, value=True):
        """Sets whether to continue processing the notifications.
        Use w/ value=False if you don't want to process more notifications.
        It will make the app quit the 'process_notification()' loop.
        """
        self._loop_process_notifications = value

    def process_notifications(self, timeout_secs=0.05, sid=0):
        """Loop to processes notifications.
        This is to be called by your app if you just want to listen to
        notifications.
        Arguments:
        timeout_secs : float, seconds to block on the notification queue.
        sid : int, SessionID
        """
        if not sid:
            sid = self._current_session
        self._loop_process_notifications = True
        while self._loop_process_notifications:
            self.sessions[sid].consume_notification(timeout_secs)

    def new_session(self):
        """Creates a new session.
        Returns an integer representing a SessionID.
        """
        response = self._run(method="NewSession")
        sid = response["SessionID"]
        self.sessions[sid] = self._Session(self, sid)
        return sid

    def set_current_session(self, sid):
        """Sets the current session.
        All API calls after this will use 'sid' SessionID.
        Arguments:
        sid : int, SessionID
        """
        self._current_session = sid

    def get_current_session(self):
        """Returns an int representing the current session
        used by API calls."""
        return self._current_session

    def start_up(self, username, server_uri="", sid=0):
        """Starts the flowapp instance (notification internal loop, etc)
        for an account that is already created and has a device already
        configured in the current device. Returns 'null'.
        Internally, it starts a thread that calls WaitForNotifications
        and stores the notifications on a event queue.
        """
        if not server_uri:
            server_uri = definitions.DEFAULT_URI
        if not sid:
            sid = self._current_session
        self._run(method="StartUp",
                  SessionID=sid,
                  EmailAddress=username,
                  ServerURI=server_uri,
                  )
        self.sessions[sid].start_notification_loop()

    def create_account(
            self,
            phone_number,
            device_name,
            username,
            server_uri,
            password,
            totpverifier="",
            sid=0):
        """Creates an account with the specified data.
        'phone_number', along with 'username' and 'server_uri'
        (these last two provided at 'start_up') must be unique.
        This call also starts the notification
        loop for this session.
        Returns 'null'.
        """
        if not sid:
            sid = self._current_session
        response = self._run(method="CreateAccount",
                             SessionID=sid,
                             PhoneNumber=phone_number,
                             DeviceName=device_name,
                             EmailAddress=username,
                             ServerURI=server_uri,
                             Password=password,
                             TotpVerifier=totpverifier,
                             )
        self.sessions[sid].start_notification_loop()
        return response

    def create_device(self,
                      username,
                      server_uri,
                      device_name,
                      password,
                      platform,
                      os_release,
                      sid=0):
        """CreateDevice creates a new device for an existing account,
        similar to CreateAccount in terms of parameters.
        It also starts the notification loop (like create_account).
        Returns a 'Device' dict.
        """
        if not sid:
            sid = self._current_session
        response = self._run(method="CreateDevice",
                             SessionID=sid,
                             EmailAddress=username,
                             ServerURI=server_uri,
                             DeviceName=device_name,
                             Password=password,
                             Platform=platform,
                             OSRelease=os_release,
                             )
        self.sessions[sid].start_notification_loop()
        return response

    def new_org(self, name, discoverable, sid=0):
        """Creates a new organization. Returns an 'Org' dict."""
        if not sid:
            sid = self._current_session
        return self._run(method="NewOrg",
                         SessionID=sid,
                         Name=name,
                         Discoverable=discoverable,
                         )

    def new_channel(self, oid, name, sid=0):
        """Creates a new channel in a specific 'OrgID'.
        Returns a string that represents the `ChannelID` created.
        """
        if not sid:
            sid = self._current_session
        return self._run(method="NewChannel",
                         SessionID=sid,
                         OrgID=oid,
                         Name=name,
                         )

    def enumerate_orgs(self, sid=0):
        """Lists all the orgs the caller is a member of.
        Returns array of 'Org' dicts.
        """
        if not sid:
            sid = self._current_session
        return self._run(method="EnumerateOrgs",
                         SessionID=sid,
                         )

    def enumerate_org_members(self, oid, sid=0):
        """Lists all members for an org and their state."""
        if not sid:
            sid = self._current_session
        return self._run(method="EnumerateOrgMembers",
                         SessionID=sid,
                         OrgID=oid,
                         )

    def enumerate_channels(self, oid, sid=0):
        """Lists the channels available for an 'OrgID'.
        Returns an array of 'Channel' dicts.
        """
        if not sid:
            sid = self._current_session
        return self._run(method="EnumerateChannels",
                         SessionID=sid,
                         OrgID=oid,
                         )

    def enumerate_channel_members(self, cid, sid=0):
        """Lists the channel members for a given 'ChannelID'.
        Returns an array of 'ChannelMember' dicts.
        """
        if not sid:
            sid = self._current_session
        return self._run(method="EnumerateChannelMembers",
                         SessionID=sid,
                         ChannelID=cid,
                         )

    def send_message(self, oid, cid, msg, other_data=None, sid=0):
        """Sends a message to a channel this user is a member of.
        Returns a string that represents the 'MessageID'
        that has just been sent.
        """
        if not sid:
            sid = self._current_session
        return self._run(method="SendMessage",
                         SessionID=sid,
                         OrgID=oid,
                         ChannelID=cid,
                         Text=msg,
                         OtherData=other_data,
                         )

    def wait_for_notification(self, sid=0):
        """Returns the oldest unseen notification
        in the queue for this device.
        WARNING: it will block until there's a new notification
        if there isn't any at the time it is called.
        It's advised to call this method in a thread outside of
        the main one. Returns a 'Change' dict.
        """
        if not sid:
            sid = self._current_session
        return self._run(method="WaitForNotification",
                         SessionID=sid,
                         )

    def enumerate_messages(self, oid, cid, filters={}, sid=0):
        """Lists all the messages for a channel.
        Returns an array of 'Message' dicts.
        """
        if not sid:
            sid = self._current_session
        return self._run(method="EnumerateMessages",
                         SessionID=sid,
                         OrgID=oid,
                         ChannelID=cid,
                         Filters=filters,
                         )

    def get_channel(self, cid, sid=0):
        """Returns all the metadata for a channel the user is a member of.
        Returns a 'Channel' dict.
        """
        if not sid:
            sid = self._current_session
        return self._run(method="GetChannel",
                         SessionID=sid,
                         ChannelID=cid,
                         )

    def new_org_join_request(self, oid, sid=0):
        """Creates a new request to join an existing organization.
        Returns 'null'.
        """
        if not sid:
            sid = self._current_session
        return self._run(method="NewOrgJoinRequest",
                         SessionID=sid,
                         OrgID=oid,
                         )

    def enumerate_org_join_requests(self, oid, sid=0):
        """Lists all the join requests for an 'OrgID'.
        Returns an array of 'OrgJoinRequest' dicts.
        """
        if not sid:
            sid = self._current_session
        return self._run(method="EnumerateOrgJoinRequests",
                         SessionID=sid,
                         OrgID=oid,
                         )

    def org_add_member(self, oid, account_id, member_state, sid=0):
        """Adds a member to an organization, assuming the user has
        the proper permissions. Returns 'null'.
        'member_state' argument valid values are
        'm' (member), 'a' (admin), 'o' (owner), 'b' blocked.
        """
        if not sid:
            sid = self._current_session
        return self._run(method="OrgAddMember",
                         SessionID=sid,
                         OrgID=oid,
                         MemberAccountID=account_id,
                         MemberState=member_state,
                         )

    def channel_add_member(self, oid, cid, account_id, member_state, sid=0):
        """Adds the specified member to the channel as long as
        the requestor has the right permissions. Returns 'null'.
        """
        if not sid:
            sid = self._current_session
        return self._run(method="ChannelAddMember",
                         SessionID=sid,
                         OrgID=oid,
                         ChannelID=cid,
                         MemberAccountID=account_id,
                         MemberState=member_state,
                         )

    def new_direct_conversation(self, oid, account_id, sid=0):
        """Creates a new channel to initiate a
        direct conversation with another user.
        Returns a 'ChannelID'.
        """
        if not sid:
            sid = self._current_session
        return self._run(method="NewDirectConversation",
                         SessionID=sid,
                         OrgID=oid,
                         MemberID=account_id,
                         )

    def get_peer(self, username, sid=0):
        """Returns all the metadata of a peer for this user.
        Returns a 'Peer' dict.
        """
        if not sid:
            sid = self._current_session
        return self._run(method="GetPeer",
                         SessionID=sid,
                         PeerEmailAddress=username,
                         )

    def enumerate_local_accounts(self):
        """Lists all the accounts configured locally (not the peers).
        Returns an array of 'AccountIdentifier' dicts.
        """
        return self._run(method="EnumerateLocalAccounts",
                         )

    def new_org_member_state(self,
                             oid,
                             member_account_id,
                             member_state,
                             sid=0):
        """Sets the Org member state for a given account.
        'member_state' can be one of the following:
        'a' (admin), 'm' (member), 'o' (owner), 'b' (blocked).
        """
        if not sid:
            sid = self._current_session
        return self._run(method="NewOrgMemberState",
                         SessionID=sid,
                         OrgID=oid,
                         MemberAccountID=member_account_id,
                         MemberState=member_state,
                         )

    def new_channel_member_state(self,
                                 oid,
                                 cid,
                                 member_account_id,
                                 member_state,
                                 sid=0):
        """Sets the Channel member state for a given account.
        'member_state' can be one of the following:
        'a' (admin), 'm' (member), 'o' (owner), 'b' (blocked).
        """
        if not sid:
            sid = self._current_session
        return self._run(method="NewChannelMemberState",
                         SessionID=sid,
                         OrgID=oid,
                         ChannelID=cid,
                         MemberAccountID=member_account_id,
                         MemberState=member_state,
                         )

    def close(self, sid=0):
        """Closes a session and cleanly finishes any long running operations.
        It could be seen as a logout. Returns 'null'.
        """
        if not sid:
            sid = self._current_session
        self.sessions[sid].close()
        del self.sessions[sid]
        # TODO: 'Close' fails with error
        # "Caused by <class 'socket.error'>:
        # [Errno 104] Connection reset by peer"
        # because of two possible scenarios:
        # loop thread is blocked in a wait_for_notification call
        # or flowappglue is not running anymore.
        try:
            response = self._run(method="Close",
                                 SessionID=sid,
                                 )
        except Exception as exception:
            self._print_debug("%s" % str(exception))
            response = "null"
        return response
