"""
Flow Synchronous API Python Module.
All Flow API responses are represented with Python dicts.
"""

import sys
import subprocess
import platform as platform_module
import json
import threading
import Queue
import os
import string
import random
import logging

import requests

from . import definitions

LOG = logging.getLogger("flow")


class Flow(object):
    """Class to interact with the Flow API.
    Request/Responses are synchronous.
    """

    # Notification Types
    ORG_NOTIFICATION = "org"
    CHANNEL_NOTIFICATION = "channel"
    MESSAGE_NOTIFICATION = "message"
    HWM_NOTIFICATION = "hwm"
    CHANNEL_MEMBER_NOTIFICATION = "channel-member-event"
    ORG_MEMBER_NOTIFICATION = "org-member-event"
    ORG_JOIN_REQUEST_NOTIFICATION = "org-join-request"
    PEER_VERIFICATION_NOTIFICATION = "peer-verification"
    PROFILE_NOTIFICATION = "profile"
    UPLOAD_START_NOTIFICATION = "upload-start-event"
    UPLOAD_PROGRESS_NOTIFICATION = "upload-progress-event"
    UPLOAD_COMPLETE_NOTIFICATION = "upload-complete-event"
    UPLOAD_ERROR_NOTIFICATION = "upload-error-event"
    DOWNLOAD_START_NOTIFICATION = "download-start-event"
    DOWNLOAD_PROGRESS_NOTIFICATION = "download-progress-event"
    DOWNLOAD_COMPLETE_NOTIFICATION = "download-complete-event"
    DOWNLOAD_ERROR_NOTIFICATION = "download-error-event"
    CHANNEL_SESSION_KEY_NOTIFICATION = "channel-session-key"
    CHANNEL_SESSION_KEY_SHARE_NOTIFICATION = "channel-session-key-share"

    def _make_notification_decorator(name):
        """Generates decorator functions for all notifications.
        E.g. the 'message' notification decorator usage:
        @flow.message
        def my_message_callback(notif_type, data):
            # do something...
        """

        def notification_decorator(self, func):
            """Decorator to register the event callback."""
            self.register_callback(name, func)
            return func
        notification_decorator.__doc__ = "Decorator to register a '%s' " \
            "notification callback." % name
        notification_decorator.__name__ = name
        return notification_decorator

    # Generate decorators for the notification callbacks
    message = _make_notification_decorator(MESSAGE_NOTIFICATION)
    org = _make_notification_decorator(ORG_NOTIFICATION)
    channel = _make_notification_decorator(CHANNEL_NOTIFICATION)
    message = _make_notification_decorator(MESSAGE_NOTIFICATION)
    hwm = _make_notification_decorator(HWM_NOTIFICATION)
    channel_member_event = _make_notification_decorator(
        CHANNEL_MEMBER_NOTIFICATION)
    org_member_event = _make_notification_decorator(ORG_MEMBER_NOTIFICATION)
    org_join_request = _make_notification_decorator(
        ORG_JOIN_REQUEST_NOTIFICATION)
    peer_verification = _make_notification_decorator(
        PEER_VERIFICATION_NOTIFICATION)
    profile = _make_notification_decorator(PROFILE_NOTIFICATION)
    upload_start_event = _make_notification_decorator(
        UPLOAD_START_NOTIFICATION)
    upload_progress_event = _make_notification_decorator(
        UPLOAD_PROGRESS_NOTIFICATION)
    upload_compete_event = _make_notification_decorator(
        UPLOAD_COMPLETE_NOTIFICATION)
    upload_error_event = _make_notification_decorator(
        UPLOAD_ERROR_NOTIFICATION)
    download_start_event = _make_notification_decorator(
        DOWNLOAD_START_NOTIFICATION)
    download_progress_event = _make_notification_decorator(
        DOWNLOAD_PROGRESS_NOTIFICATION)
    download_complete_event = _make_notification_decorator(
        DOWNLOAD_COMPLETE_NOTIFICATION)
    download_error_event = _make_notification_decorator(
        DOWNLOAD_ERROR_NOTIFICATION)
    channel_session_key = _make_notification_decorator(
        CHANNEL_SESSION_KEY_NOTIFICATION)
    channel_session_key_share = _make_notification_decorator(
        CHANNEL_SESSION_KEY_SHARE_NOTIFICATION)

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
            self.error_queue = Queue.Queue()
            self.listen_notifications = threading.Event()
            self.notification_thread = threading.Thread(
                target=self._notification_loop,
                args=())
            self.notification_thread.daemon = True
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

        def _queue_error(self, error):
            """Queues the notification error.
            Arguments:
            error : string.
            """
            # This check should leave the queue with
            # an approximate size of _MAX_QUEUE_SIZE
            if self.error_queue.qsize() > self._MAX_QUEUE_SIZE:
                ignored_error = self.error_queue.get()
                LOG.warn(
                    "Error queue is full: ignoring error '%s'",
                    ignored_error,
                )
            self.error_queue.put(error)

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
                        LOG.warn(
                            "Notification queue is full: "
                            "ignoring notification '%s'",
                            notification["data"])
                    self.notification_queue.put(change)

        def _notification_loop(self):
            """Loops calling WaitForNotification on this session."""
            while self.listen_notifications.is_set():
                try:
                    changes = self.flow.wait_for_notification(sid=self.sid)
                except Flow.FlowError as flow_err:
                    self._queue_error(str(flow_err))
                else:
                    self.callback_lock.acquire()
                    self._queue_changes(changes)
                    self.callback_lock.release()

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
                        notification["type"], notification["data"])
                except KeyError:
                    LOG.debug(
                        "Notification of type '%s' not supported.",
                        notification["type"])
                except Exception as exception:
                    LOG.debug("Error: %s", str(exception))
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
        """Exception class for Flow service related errors."""
        pass

    class FlowConnectionError(Exception):
        """Exception class for Flow connection related errors."""
        pass

    class FlowTimeoutError(Exception):
        """Exception class for Flow connection timeout related errors."""
        pass

    def __init__(
            self,
            username="",
            server_uri=definitions.DEFAULT_URI,
            flowappglue=definitions.get_default_flowappglue_path(),
            host=definitions.DEFAULT_SERVER,
            port=definitions.DEFAULT_PORT,
            db_dir=definitions.get_default_db_path(),
            schema_dir=definitions.get_default_schema_path(),
            attachment_dir=definitions.get_default_attachment_path(),
            use_tls=definitions.DEFAULT_USE_TLS,
            glue_out_filename=definitions.get_default_glue_out_filename()):
        """Initializes the Flow object. It starts and configures
        flowappglue local server as a subprocess.
        It also starts a new session so that you can start using
        the Flow API. You should be good by calling this function
        with no arguments.
        It will call start_up() if a username is provided.
        Arguments:
        flowappglue : string, path to the flowappglue binary,
        if empty, then it tries to determine the location.
        """
        self.server_uri = server_uri
        self._check_file_exists(flowappglue)
        self._check_file_exists(db_dir, True)
        with open(glue_out_filename, "w") as log_file:
            self._flowappglue = subprocess.Popen(
                [flowappglue, "0"],
                stdout=subprocess.PIPE,
                stderr=log_file)
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
            self.start_up(username)

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

    @staticmethod
    def gen_rand_req_id():
        """Generate a 10-byte random id for debugging."""
        return "".join(
            random.choice(string.ascii_uppercase + string.digits)
            for _ in range(10))

    def _get_session_id(self, sid):
        """Utility function to return the current
        session if sid is not provided.
        """
        return sid if sid else self._current_session

    def _run(self, method, timeout=None, **params):
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
                token=self._token),
            indent=2)
        rand_debug_req_id = self.gen_rand_req_id()
        LOG.debug(
            "request method=%s id=%s: %s",
            method, rand_debug_req_id, request_str)
        try:
            response = requests.post(
                "http://localhost:%s/rpc" %
                self._port,
                headers={'Content-type': 'application/json'},
                timeout=timeout,
                data=request_str)
        except requests.exceptions.ConnectionError as connection_err:
            raise Flow.FlowConnectionError(connection_err)
        except requests.exceptions.Timeout as timeout_err:
            raise Flow.FlowTimeoutError(timeout_err)
        response_data = json.loads(response.text, encoding='utf-8')
        LOG.debug(
            "response method=%s id=%s: HTTP %s, lat=%.2fs: %s",
            method, rand_debug_req_id, response.status_code,
            response.elapsed.total_seconds(), response.text)
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
            host,
            port,
            db_dir,
            schema_dir,
            attachment_dir,
            use_tls,
            timeout=None):
        """Sets up the basic configuration parameters for FlowApp
        to talk FlowServ and create local accounts.
        If arguments are empty, then it will try to determine the
        configuration.
        """
        self._check_file_exists(schema_dir)
        self._check_file_exists(db_dir, True)
        self._check_file_exists(attachment_dir, True)
        self._run(
            method="Config",
            FlowServHost=host,
            FlowServPort=port,
            FlowLocalDatabaseDir=db_dir,
            FlowLocalSchemaDir=schema_dir,
            FlowLocalAttachmentDir=attachment_dir,
            FlowUseTLS=use_tls,
            timeout=timeout,
        )

    def register_callback(self, notification_name,
                          callback, sid=0):
        """Registers a callback to be executed for
        a specific notification type.
        Arguments:
        sid : int, SessionID
        notification_name : string, type of the notification.
        callback : function object that receives a string as argument.
        Upon callback execution, the string argument of the callback
        will contain the "data" section of the notification.
        """
        sid = self._get_session_id(sid)
        self.sessions[sid].register_callback(notification_name, callback)

    def unregister_callback(self, notification_name, sid=0):
        """Unregisters a callback, this makes the Flow module
        to ignore notifications of this type.
        Arguments:
        sid : int, SessionID
        notification_name : string, type of the notification.
        """
        sid = self._get_session_id(sid)
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
        sid = self._get_session_id(sid)
        return self.sessions[sid].consume_notification(timeout_secs)

    def get_notification_error(self, timeout_secs=0.05, sid=0):
        """Returns a notification error from the error queue.
        Returns 'None' if there's no error on the queue.
        Arguments:
        timeout_secs : float, seconds to block on the notification queue.
        sid : int, SessionI.
        """
        sid = self._get_session_id(sid)
        try:
            error = self.sessions[sid].error_queue.get(
                block=True,
                timeout=timeout_secs,
            )
        except Queue.Empty:
            error = None
        return error

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
        sid = self._get_session_id(sid)
        self._loop_process_notifications = True
        while self._loop_process_notifications:
            self.sessions[sid].consume_notification(timeout_secs)

    def new_session(self, timeout=None):
        """Creates a new session.
        Returns an integer representing a SessionID.
        """
        response = self._run(
            method="NewSession",
            timeout=timeout,
        )
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

    def start_up(self, username="", timeout=None, sid=0):
        """Starts the flowapp instance (notification internal loop, etc)
        for an account that is already created and has a device already
        configured in the current device.
        Internally, it starts a thread that calls WaitForNotifications
        and stores the notifications on a event queue.
        If 'username' is empty, then it will start up the
        first local account on the current device.
        """
        if not username:
            local_accounts = self.enumerate_local_accounts()
            if local_accounts:
                username = local_accounts[0]["username"]
        sid = self._get_session_id(sid)
        self._run(
            method="StartUp",
            SessionID=sid,
            Username=username,
            ServerURI=self.server_uri,
            timeout=timeout,
        )
        self.sessions[sid].start_notification_loop()

    def create_account(
            self,
            username,
            password,
            device_name,
            phone_number,
            platform=sys.platform,
            os_release=platform_module.release(),
            email_confirm_code="",
            totpverifier="",
            timeout=None,
            sid=0):
        """Creates an account with the specified data.
        'phone_number', along with 'username' and 'server_uri'
        (these last two provided at 'start_up') must be unique.
        This call also starts the notification
        loop for this session.
        """
        sid = self._get_session_id(sid)
        self._run(
            method="CreateAccount",
            SessionID=sid,
            PhoneNumber=phone_number,
            DeviceName=device_name,
            Username=username,
            ServerURI=self.server_uri,
            Platform=platform,
            OSRelease=os_release,
            Password=password,
            TotpVerifier=totpverifier,
            EmailConfirmCode=email_confirm_code,
            NotifyToken="",
            timeout=timeout,
        )
        self.sessions[sid].start_notification_loop()

    def create_device(self,
                      username,
                      device_name,
                      password,
                      platform=sys.platform,
                      os_release=platform_module.release(),
                      timeout=None,
                      sid=0):
        """CreateDevice creates a new device for an existing account,
        similar to CreateAccount in terms of parameters.
        It also starts the notification loop (like create_account).
        Returns a 'Device' dict.
        """
        sid = self._get_session_id(sid)
        response = self._run(
            method="CreateDevice",
            SessionID=sid,
            Username=username,
            ServerURI=self.server_uri,
            DeviceName=device_name,
            Password=password,
            Platform=platform,
            OSRelease=os_release,
            timeout=timeout,
        )
        self.sessions[sid].start_notification_loop()
        return response

    def account_id(self, timeout=None, sid=0):
        """Returns the accountId for this account."""
        sid = self._get_session_id(sid)
        return self._run(
            method="AccountId",
            SessionID=sid,
            timeout=timeout,
        )

    def new_org(self, name, discoverable=True, timeout=None, sid=0):
        """Creates a new organization. Returns an 'Org' dict."""
        sid = self._get_session_id(sid)
        return self._run(
            method="NewOrg",
            SessionID=sid,
            Name=name,
            Discoverable=discoverable,
            timeout=timeout,
        )

    def new_channel(self, oid, name, timeout=None, sid=0):
        """Creates a new channel in a specific 'OrgID'.
        Returns a string that represents the `ChannelID` created.
        """
        sid = self._get_session_id(sid)
        return self._run(
            method="NewChannel",
            SessionID=sid,
            OrgID=oid,
            Name=name,
            timeout=timeout,
        )

    def enumerate_orgs(self, timeout=None, sid=0):
        """Lists all the orgs the caller is a member of.
        Returns array of 'Org' dicts.
        """
        sid = self._get_session_id(sid)
        return self._run(
            method="EnumerateOrgs",
            SessionID=sid,
            timeout=timeout,
        )

    def enumerate_org_members(self, oid, timeout=None, sid=0):
        """Lists all members for an org and their state."""
        sid = self._get_session_id(sid)
        return self._run(
            method="EnumerateOrgMembers",
            SessionID=sid,
            OrgID=oid,
            timeout=timeout,
        )

    def enumerate_channels(self, oid, timeout=None, sid=0):
        """Lists the channels available for an 'OrgID'.
        Returns an array of 'Channel' dicts.
        """
        sid = self._get_session_id(sid)
        return self._run(
            method="EnumerateChannels",
            SessionID=sid,
            OrgID=oid,
            timeout=timeout,
        )

    def enumerate_channel_members(self, cid, timeout=None, sid=0):
        """Lists the channel members for a given 'ChannelID'.
        Returns an array of 'ChannelMember' dicts.
        """
        sid = self._get_session_id(sid)
        return self._run(
            method="EnumerateChannelMembers",
            SessionID=sid,
            ChannelID=cid,
            timeout=timeout,
        )

    def new_attachment(self, oid, file_path, timeout=None, sid=0):
        """Returns an 'Attachment' dict ready to be used on send_message().
        file_path must be the absolute path.
        """
        sid = self._get_session_id(sid)
        aid = self._run(
            method="NewAttachment",
            SessionID=sid,
            OrgID=oid,
            FilePath=file_path,
            timeout=timeout,
        )
        file_basename = os.path.basename(file_path)
        return {"id": aid, "filename": file_basename}

    def start_attachment_download(
            self, aid, oid, cid, mid, timeout=None, sid=0):
        """Requests download of an attachment.
        Status will be reported on the notification channel.
        """
        sid = self._get_session_id(sid)
        self._run(
            method="StartAttachmentDownload",
            SessionID=sid,
            AttachmentID=aid,
            OrgID=oid,
            ChannelID=cid,
            MessageID=mid,
            timeout=timeout,
        )

    def update_attachment_path(self, aid, new_path, timeout=None, sid=0):
        """Moves the attachment represented by the id
        specified to 'new_path', if it has completed
        uploading or downloading.
        """
        sid = self._get_session_id(sid)
        self._run(
            method="UpdateAttachmentPath",
            SessionID=sid,
            AttachmentID=aid,
            NewPath=new_path,
            timeout=timeout,
        )

    def stored_attachment_path(self, oid, aid, timeout=None, sid=0):
        """Returns the path where the attachment has been
        stored when the download is complete."""
        sid = self._get_session_id(sid)
        return self._run(
            method="StoredAttachmentPath",
            SessionID=sid,
            OrgID=oid,
            AttachmentID=aid,
            timeout=timeout,
        )

    def send_message(self, oid, cid, msg, attachments=None,
                     other_data=None, timeout=None, sid=0):
        """Sends a message to a channel this user is a member of.
        Returns a string that represents the 'MessageID'
        that has just been sent.
        """
        sid = self._get_session_id(sid)
        return self._run(
            method="SendMessage",
            SessionID=sid,
            OrgID=oid,
            ChannelID=cid,
            Text=msg,
            OtherData=other_data,
            Attachments=attachments,
            timeout=timeout,
        )

    def wait_for_notification(self, timeout=None, sid=0):
        """Returns the oldest unseen notification
        in the queue for this device.
        WARNING: it will block until there's a new notification
        if there isn't any at the time it is called.
        It's advised to call this method in a thread outside of
        the main one. Returns a 'Change' dict.
        """
        sid = self._get_session_id(sid)
        return self._run(
            method="WaitForNotification",
            SessionID=sid,
            timeout=timeout,
        )

    def enumerate_messages(self, oid, cid, filters=None, timeout=None, sid=0):
        """Lists all the messages for a channel.
        Returns an array of 'Message' dicts.
        """
        sid = self._get_session_id(sid)
        return self._run(
            method="EnumerateMessages",
            SessionID=sid,
            OrgID=oid,
            ChannelID=cid,
            Filters=filters,
            timeout=timeout,
        )

    def get_unread_count(self, oid, cid, timeout=None, sid=0):
        """Returns the amount of unread
        messages for a channel based on the known HWM.
        It will report up to 101 unread messages since
        the goal is to just show '100+'
        in that case and over.
        """
        sid = self._get_session_id(sid)
        return self._run(
            method="GetUnreadCount",
            SessionID=sid,
            OrgID=oid,
            ChannelID=cid,
            timeout=timeout,
        )

    def search(self, oid, cid, search, timeout=None, sid=0):
        """Returns a list of 'message' notification dicts for
        all messages matching a search string."""
        sid = self._get_session_id(sid)
        return self._run(
            method="Search",
            SessionID=sid,
            OrgID=oid,
            ChannelID=cid,
            Search=search,
            timeout=timeout,
        )

    def get_channel(self, cid, timeout=None, sid=0):
        """Returns all the metadata for a channel the user is a member of.
        Returns a 'Channel' dict.
        """
        sid = self._get_session_id(sid)
        return self._run(
            method="GetChannel",
            SessionID=sid,
            ChannelID=cid,
            timeout=timeout,
        )

    def new_org_join_request(self, oid, timeout=None, sid=0):
        """Creates a new request to join an existing organization."""
        sid = self._get_session_id(sid)
        self._run(
            method="NewOrgJoinRequest",
            SessionID=sid,
            OrgID=oid,
            timeout=timeout,
        )

    def enumerate_org_join_requests(self, oid, timeout=None, sid=0):
        """Lists all the join requests for an 'OrgID'.
        Returns an array of 'OrgJoinRequest' dicts.
        """
        sid = self._get_session_id(sid)
        return self._run(
            method="EnumerateOrgJoinRequests",
            SessionID=sid,
            OrgID=oid,
            timeout=timeout,
        )

    def org_add_member(self, oid, account_id,
                       member_state, timeout=None, sid=0):
        """Adds a member to an organization, assuming the user has
        the proper permissions.
        'member_state' argument valid values are
        'm' (member), 'a' (admin), 'o' (owner), 'b' blocked.
        """
        sid = self._get_session_id(sid)
        self._run(
            method="OrgAddMember",
            SessionID=sid,
            OrgID=oid,
            MemberAccountID=account_id,
            MemberState=member_state,
            timeout=timeout,
        )

    def channel_add_member(self, oid, cid, account_id,
                           member_state, timeout=None, sid=0):
        """Adds the specified member to the channel as long as
        the requestor has the right permissions.
        """
        sid = self._get_session_id(sid)
        self._run(
            method="ChannelAddMember",
            SessionID=sid,
            OrgID=oid,
            ChannelID=cid,
            MemberAccountID=account_id,
            MemberState=member_state,
            timeout=timeout,
        )

    def new_direct_conversation(self, oid, account_id, timeout=None, sid=0):
        """Creates a new channel to initiate a
        direct conversation with another user.
        Returns a 'ChannelID'.
        """
        sid = self._get_session_id(sid)
        return self._run(
            method="NewDirectConversation",
            SessionID=sid,
            OrgID=oid,
            MemberID=account_id,
            timeout=timeout,
        )

    def get_peer(self, username, timeout=None, sid=0):
        """Returns all the metadata of a peer from username.
        Returns a 'Peer' dict.
        """
        sid = self._get_session_id(sid)
        return self._run(
            method="GetPeer",
            SessionID=sid,
            PeerUsername=username,
            timeout=timeout,
        )

    def get_peer_from_id(self, account_id, timeout=None, sid=0):
        """Returns all the metadata of a peer from account id.
        Returns a 'Peer' dict.
        """
        sid = self._get_session_id(sid)
        return self._run(
            method="GetPeerFromID",
            SessionID=sid,
            PeerID=account_id,
            timeout=timeout,
        )

    def enumerate_local_accounts(self, timeout=None):
        """Lists all the accounts configured locally (not the peers).
        Returns an array of 'AccountIdentifier' dicts.
        """
        return self._run(
            method="EnumerateLocalAccounts",
            timeout=timeout,
        )

    def enumerate_peer_accounts(self, timeout=None, sid=0):
        """Lists all the peer accounts.
        Returns an array of 'Peer' dicts.
        """
        sid = self._get_session_id(sid)
        return self._run(
            method="EnumeratePeerAccounts",
            SessionID=sid,
            timeout=timeout,
        )

    def new_org_member_state(self,
                             oid,
                             member_account_id,
                             member_state,
                             timeout=None,
                             sid=0):
        """Sets the Org member state for a given account.
        'member_state' can be one of the following:
        'a' (admin), 'm' (member), 'o' (owner), 'b' (blocked).
        """
        sid = self._get_session_id(sid)
        return self._run(
            method="NewOrgMemberState",
            SessionID=sid,
            OrgID=oid,
            MemberAccountID=member_account_id,
            MemberState=member_state,
            timeout=timeout,
        )

    def new_channel_member_state(self,
                                 oid,
                                 cid,
                                 member_account_id,
                                 member_state,
                                 timeout=None,
                                 sid=0):
        """Sets the Channel member state for a given account.
        'member_state' can be one of the following:
        'a' (admin), 'm' (member), 'o' (owner), 'b' (blocked).
        """
        sid = self._get_session_id(sid)
        return self._run(
            method="NewChannelMemberState",
            SessionID=sid,
            OrgID=oid,
            ChannelID=cid,
            MemberAccountID=member_account_id,
            MemberState=member_state,
            timeout=timeout,
        )

    def get_devices(self, timeout=None, sid=0):
        """Returns all devices associated to the current account.
        Returns a list of 'Device' dicts.
        """
        sid = self._get_session_id(sid)
        return self._run(
            method="GetDevices",
            SessionID=sid,
            timeout=timeout,
        )

    def start_d2d_rendezvous(self, timeout=None, sid=0):
        """StartD2DRendezvous generates a 32 random bytes for usage as a
        rendezvous ID in device to device provsioning and a key pair for DH.
        It returns the 32 random bytes for them to be shared in some way
        Only the established devices use this method.
        Returns string with the rendezvous ID.
        """
        sid = self._get_session_id(sid)
        return self._run(
            method="StartD2DRendezvous",
            SessionID=sid,
            timeout=timeout,
        )

    def provision_new_device(self, timeout=None, sid=0):
        """ProvisionNewDevice pushes the provisioning payload for
        a new device to be created from it.
        Only the established device uses this after
        calling StartD2DRendezvous.
        This call blocks the caller until the new
        device creates the device.
        """
        sid = self._get_session_id(sid)
        self._run(
            method="ProvisionNewDevice",
            SessionID=sid,
            timeout=timeout,
        )

    def create_device_from_rendezvous(self,
                                      rendezvous_id,
                                      device_name,
                                      platform=sys.platform,
                                      os_release=platform_module.release(),
                                      timeout=None,
                                      sid=0):
        """CreateDeviceFromRendezvous creates a new device by downloading a
        provisioning payload using the rendezvousID.
        Only the new device uses this method.
        This call also starts the notification
        loop for this session.
        """
        sid = self._get_session_id(sid)
        self._run(
            method="CreateDeviceFromD2D",
            SessionID=sid,
            RendezvousID=rendezvous_id,
            DeviceName=device_name,
            Platform=platform,
            OSRelease=os_release,
            timeout=timeout,
        )
        self.sessions[sid].start_notification_loop()

    def cancel_rendezvous(self, timeout=None, sid=0):
        """CancelRendezvous tries cancelling an ongoing rendezvous, if any."""
        sid = self._get_session_id(sid)
        self._run(
            method="CancelRendezvous",
            SessionID=sid,
            timeout=timeout,
        )

    @staticmethod
    def get_profile_item_json(display_name, biography, photo):
        """Create 'Content' JSON to be used by set_profile()."""
        content = json.dumps(dict(
            displayName=display_name,
            biography=biography,
            photo=photo,
        ))
        return content

    def set_profile(self, item, content, timeout=None, sid=0):
        """CancelRendezvous tries cancelling an ongoing rendezvous, if any."""
        sid = self._get_session_id(sid)
        self._run(
            method="SetProfile",
            SessionID=sid,
            Content=content,
            Item=item,
            timeout=timeout,
        )

    def identifier(self, timeout=None, sid=0):
        """Identifier returns the Username and ServerURI for this account.
        Returns an 'AccountIdentifier' dict.
        """
        sid = self._get_session_id(sid)
        return self._run(
            method="Identifier",
            SessionID=sid,
            timeout=timeout,
        )

    def peer_data(self, timeout=None, sid=0):
        """Returns 'Peer' dict for this account."""
        sid = self._get_session_id(sid)
        return self._run(
            method="PeerData",
            SessionID=sid,
            timeout=timeout,
        )

    def verify_peer_keyring(self,
                            username,
                            account_id,
                            keyring_id,
                            verification_method,
                            timeout=None,
                            sid=0):
        """Peer Key Verification for web of trust."""
        sid = self._get_session_id(sid)
        return self._run(
            method="VerifyPeerKeyRing",
            SessionID=sid,
            PeerUsername=username,
            PeerAccountID=account_id,
            PeerKeyRingID=keyring_id,
            VerificationMethod=verification_method,
            timeout=timeout,
        )

    def set_channel_read_hwm(self, oid, cid, mid, timeout=None, sid=0):
        """Sets a new HWM for an account in a channel."""
        sid = self._get_session_id(sid)
        self._run(
            method="SetChannelReadHWM",
            SessionID=sid,
            OrgID=oid,
            ChannelID=cid,
            MessageID=mid,
            timeout=timeout,
        )

    def verification_hash(self,
                          timeout=None,
                          sid=0):
        """Returns the verification hash for this account."""
        sid = self._get_session_id(sid)
        return self._run(
            method="VerificationHash",
            SessionID=sid,
            timeout=timeout,
        )

    def peer_verification_hash(self,
                               username,
                               fingerprint,
                               provided_hash,
                               timeout=None,
                               sid=0):
        """Computes:
        hash(username + separator + serverURI + separator + fingerprint)
        for the specified account and compares it in constant time
        with the provided hash.
        Returns bool whether the hash is valid or not.
        """
        sid = self._get_session_id(sid)
        return self._run(
            method="PeerVerificationHash",
            SessionID=sid,
            PeerUsername=username,
            Fingerprint=fingerprint,
            ProvidedHash=provided_hash,
            timeout=timeout,
        )

    def confirm_email(self,
                      username,
                      timeout=None,
                      sid=0):
        """Sends a confirmation request to the server
        The server will email a confirm code to the specified address
        The caller should use the code as the 'email_confirm_code' argument
        on 'create_account'.
        """
        sid = self._get_session_id(sid)
        self._run(
            method="ConfirmEmail",
            SessionID=sid,
            Username=username,
            ServerURI=self.server_uri,
            timeout=timeout,
        )

    def rotate_channel_session_key(self,
                                   oid,
                                   cid,
                                   timeout=None,
                                   sid=0):
        """Declares a new channel session key
        and notifies all channel members.
        """
        sid = self._get_session_id(sid)
        self._run(
            method="RotateChannelSessionKey",
            SessionID=sid,
            OrgID=oid,
            ChannelID=cid,
            timeout=timeout,
        )

    def delete_channel(self,
                       oid,
                       cid,
                       timeout=None,
                       sid=0):
        """Removes a channel by banning all channel members."""
        sid = self._get_session_id(sid)
        self._run(
            method="DeleteChannel",
            SessionID=sid,
            OrgID=oid,
            ChannelID=cid,
            timeout=timeout,
        )

    def pause(self, timeout=None, sid=0):
        """Disconnect from the notification service.
        Any existing already-in-progress
        request to the server may continue.
        """
        sid = self._get_session_id(sid)
        self._run(
            method="Pause",
            SessionID=sid,
            timeout=timeout,
        )

    def resume(self, timeout=None, sid=0):
        """Resume after a 'pause' operation."""
        sid = self._get_session_id(sid)
        self._run(
            method="Resume",
            SessionID=sid,
            timeout=timeout,
        )

    def close(self, timeout=None, sid=0):
        """Closes a session and cleanly finishes any long running operations.
        It could be seen as a logout.
        """
        sid = self._get_session_id(sid)
        self.sessions[sid].close()
        del self.sessions[sid]
        # TODO: 'Close' fails with error
        # "Caused by <class 'socket.error'>:
        # [Errno 104] Connection reset by peer"
        # because of two possible scenarios:
        # loop thread is blocked in a wait_for_notification call
        # or flowappglue is not running anymore.
        try:
            self._run(
                method="Close",
                SessionID=sid,
                timeout=timeout,
            )
        except Exception as exception:
            LOG.debug("%s", str(exception))
