#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Used to save PKC's application state and share between modules. Be careful
if you invoke another PKC Python instance (!!) when e.g. PKC.movies is called
"""
from __future__ import absolute_import, division, unicode_literals
from .account import Account
from .application import App
from .connection import Connection
from .libsync import Sync
from .playstate import PlayState

ACCOUNT = None
APP = None
CONN = None
SYNC = None
PLAYSTATE = None


def init():
    global ACCOUNT, APP, CONN, SYNC, PLAYSTATE
    ACCOUNT = Account()
    APP = App()
    CONN = Connection()
    SYNC = Sync()
    PLAYSTATE = PlayState()
