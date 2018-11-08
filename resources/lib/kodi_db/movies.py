#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger

from .video import KodiVideoDB

LOG = getLogger('PLEX.kodi_db.movies')


class KodiMovieDB(KodiVideoDB):
