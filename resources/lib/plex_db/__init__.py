#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from .common import PlexDBBase, initialize, wipe
from .tvshows import TVShows
from .movies import Movies
from .music import Music
from .playlists import Playlists


class PlexDB(PlexDBBase, TVShows, Movies, Music, Playlists):
    pass
