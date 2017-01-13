# Changelog

## 0.5

- With the new auto-updates feature in Semaphor, the path to locate `semaphor-backend` and `flowapp/schema` was updated. If you are using the latest version of Semaphor with auto-updates, then you need to install `flow-python` v0.5.

## 0.4

- flowappglue now handles its own logging, therefore `Flow.__init__()` method does not need the `glue_out_filename` argument anymore. Logs are now placed under the directory specified by the `db_dir` argument, and are of the form `semaphor_${timestamp_in_microseconds}.log`.

## 0.3

- Config directory name is updated from `semaphor` to `flow-python`. This change is needed to avoid collision with Semaphor config directory. The full path of the config directory depends on the platform:
    - Windows: ~\AppData\Local\semaphor
    - Linux: ~/.config/semaphor
    - OSX: ~/Library/Application Support/semaphor

  If you have a bot running with version <0.3, then you should do one of these before updating flow-python:
    - If you are using flow-python along with Semaphor, then you have to update your bot code to use the existing `semaphor` directory:
      ```python
      # e.g. on Linux
      import os
      from flow import Flow

      db_dir = '%s/.config/semaphor' % os.environ["HOME"]
      attachment_dir = os.path.join(db_dir, 'downloads')
      flow = Flow(db_dir=db_dir, attachment_dir=attachment_dir)
      ```
    - If you are using flow-python without Semaphor, then you can:
      1. Stop bot execution.
      2. Rename the `semaphor` config dir to `flow-python` config dir.
      3. Update flow-python to 0.3.
      4. Start the bot again.
