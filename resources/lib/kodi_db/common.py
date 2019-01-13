#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from threading import Lock
from functools import wraps

from .. import utils, path_ops, app

KODIDB_LOCK = Lock()
DB_WRITE_ATTEMPTS = 10


def catch_operationalerrors(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        attempts = DB_WRITE_ATTEMPTS
        while True:
            try:
                return method(*args, **kwargs)
            except utils.OperationalError as err:
                if 'database is locked' not in err:
                    raise
                app.APP.monitor.waitForAbort(0.05)
                attempts -= 1
                if attempts == 0:
                    raise
    return wrapped


class KodiDBBase(object):
    """
    Kodi database methods used for all types of items
    """
    def __init__(self, texture_db=False, cursor=None, artcursor=None, lock=True):
        """
        Allows direct use with a cursor instead of context mgr
        """
        self._texture_db = texture_db
        self.cursor = cursor
        self.artconn = None
        self.artcursor = artcursor
        self.lock = lock

    def __enter__(self):
        if self.lock:
            KODIDB_LOCK.acquire()
        self.kodiconn = utils.kodi_sql(self.db_kind)
        self.cursor = self.kodiconn.cursor()
        if self._texture_db:
            self.artconn = utils.kodi_sql('texture')
            self.artcursor = self.artconn.cursor()
        return self

    def __exit__(self, e_typ, e_val, trcbak):
        try:
            if e_typ:
                # re-raise any exception
                return False
            self.kodiconn.commit()
            if self.artconn:
                self.artconn.commit()
        finally:
            self.kodiconn.close()
            if self.artconn:
                self.artconn.close()
            if self.lock:
                KODIDB_LOCK.release()

    def art_urls(self, kodi_id, kodi_type):
        return (x[0] for x in
                self.cursor.execute('SELECT url FROM art WHERE media_id = ? AND media_type = ?',
                                    (kodi_id, kodi_type)))

    def artwork_generator(self, kodi_type, limit, offset):
        query = 'SELECT url FROM art WHERE type == ? LIMIT ? OFFSET ?'
        return (x[0] for x in
                self.cursor.execute(query, (kodi_type, limit, offset)))

    def add_artwork(self, artworks, kodi_id, kodi_type):
        """
        Pass in an artworks dict (see PlexAPI) to set an items artwork.
        """
        for kodi_art, url in artworks.iteritems():
            self.add_art(url, kodi_id, kodi_type, kodi_art)

    @catch_operationalerrors
    def add_art(self, url, kodi_id, kodi_type, kodi_art):
        """
        Adds or modifies the artwork of kind kodi_art (e.g. 'poster') in the
        Kodi art table for item kodi_id/kodi_type. Will also cache everything
        except actor portraits.
        """
        self.cursor.execute('''
            INSERT INTO art(media_id, media_type, type, url)
            VALUES (?, ?, ?, ?)
        ''', (kodi_id, kodi_type, kodi_art, url))

    def modify_artwork(self, artworks, kodi_id, kodi_type):
        """
        Pass in an artworks dict (see PlexAPI) to set an items artwork.
        """
        for kodi_art, url in artworks.iteritems():
            self.modify_art(url, kodi_id, kodi_type, kodi_art)

    @catch_operationalerrors
    def modify_art(self, url, kodi_id, kodi_type, kodi_art):
        """
        Adds or modifies the artwork of kind kodi_art (e.g. 'poster') in the
        Kodi art table for item kodi_id/kodi_type. Will also cache everything
        except actor portraits.
        """
        self.cursor.execute('''
            SELECT url FROM art
            WHERE media_id = ? AND media_type = ? AND type = ?
            LIMIT 1
        ''', (kodi_id, kodi_type, kodi_art,))
        try:
            # Update the artwork
            old_url = self.cursor.fetchone()[0]
        except TypeError:
            # Add the artwork
            self.cursor.execute('''
                INSERT INTO art(media_id, media_type, type, url)
                VALUES (?, ?, ?, ?)
            ''', (kodi_id, kodi_type, kodi_art, url))
        else:
            if url == old_url:
                # Only cache artwork if it changed
                return
            self.delete_cached_artwork(old_url)
            self.cursor.execute('''
                UPDATE art SET url = ?
                WHERE media_id = ? AND media_type = ? AND type = ?
            ''', (url, kodi_id, kodi_type, kodi_art))

    def delete_artwork(self, kodi_id, kodi_type):
        self.cursor.execute('SELECT url FROM art WHERE media_id = ? AND media_type = ?',
                            (kodi_id, kodi_type, ))
        for row in self.cursor.fetchall():
            self.delete_cached_artwork(row[0])

    @catch_operationalerrors
    def delete_cached_artwork(self, url):
        try:
            self.artcursor.execute("SELECT cachedurl FROM texture WHERE url = ? LIMIT 1",
                                   (url, ))
            cachedurl = self.artcursor.fetchone()[0]
        except TypeError:
            # Could not find cached url
            pass
        else:
            # Delete thumbnail as well as the entry
            path = path_ops.translate_path("special://thumbnails/%s"
                                           % cachedurl)
            if path_ops.exists(path):
                path_ops.rmtree(path, ignore_errors=True)
            self.artcursor.execute("DELETE FROM texture WHERE url = ?", (url, ))
