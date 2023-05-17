Eyes Robot Framework SDK for Robot Framework v3.1.2
========================

Applitools Eyes SDK For Robot Framework v3.1.2

**NOTE: This is a customized version of the Eyes SDK for Robot Framework, slightly modified for backward compatibility with Robot Framework v3.1.2.
Using this version of the Eyes SDK for Robot Framework requires a Python environment with carefully selected dependency package versions.**


Installation
------------

**Optional** - Install the recommended dependency versions (best done inside of a fresh virtual environment):

::

    pip install --no-deps -r https://raw.githubusercontent.com/rogerjefferiesEyes/eyes_robotframework/master/requirements.txt



Install Eyes SDK v5.11.2 For Robot Framework v3.1.2:

::

    pip install --no-deps git+https://github.com/rogerjefferiesEyes/eyes_robotframework.git@v5.11.2



Docs
-----

1. `Complete guide to using Eyes with the Robot framework <https://applitools.com/docs/api/robot/robot-eyes-library.html>`_
2. `Keyword documentation <https://applitools.github.io/eyes.sdk.javascript1/python/docs/eyes_robotframework/keywords.html>`_.
3. `Configuration file overview <https://applitools.com/docs/api/robot/robot-configuration-file.html>`_

Robot Framework SDK example repo: https://github.com/applitools/robotframework-quickstart

Robot Framework autocompletion plugins
--------------------------------------

**IntelliJ (PyCharm and friends)** *Recommended - most full support*
https://plugins.jetbrains.com/plugin/17424-intellibot-patched

**RobotFramework language server based** (`pip install robotframework-lsp`)
These plugins have issues with auto-completion of check settings keywords.


**IntelliJ (PyCharm and friends)**

https://plugins.jetbrains.com/plugin/16086-robot-framework-language-server

**VSCode**

https://marketplace.visualstudio.com/items?itemName=robocorp.robotframework-lsp

.. |Black Formatter| image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/ambv/black
.. |pypi version| image:: https://img.shields.io/pypi/v/eyes-robotframework
   :target: https://pypi.org/project/eyes-robotframework/
.. |pypi downloads| image:: https://img.shields.io/pypi/dw/eyes-robotframework
   :target: https://pypi.org/project/eyes-robotframework/
