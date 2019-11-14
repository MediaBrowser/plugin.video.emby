#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from . import common
from .. import db


class KodiTextureDB(common.KodiDBBase):
    db_kind = 'texture'

    def url_not_yet_cached(self, url):
        """
        Returns True if url has not yet been cached to the Kodi texture cache
        """
        self.artcursor.execute('SELECT url FROM texture WHERE url = ? LIMIT 1',
                               (url, ))
        return self.artcursor.fetchone() is None

    @db.catch_operationalerrors
    def reset_cached_images(self):
        for row in self.cursor.execute('SELECT tbl_name '
                                       'FROM sqlite_master WHERE type=?',
                                       ('table', )):
            if row[0] != 'version':
                self.cursor.execute("DELETE FROM %s" % row[0])
