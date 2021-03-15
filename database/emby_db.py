# -*- coding: utf-8 -*-
from . import queries

class EmbyDatabase():
    def __init__(self, cursor):
        self.cursor = cursor

    def get_item_by_id(self, *args):
        self.cursor.execute(queries.get_item, args)
        return self.cursor.fetchone()

    def add_reference(self, *args):
        self.cursor.execute(queries.add_reference, args)

    def add_mediasource(self, *args):
        self.cursor.execute(queries.add_mediasource, args)

    def add_videostreams(self, *args):
        self.cursor.execute(queries.add_videostreams, args)

    def add_audiostreams(self, *args):
        self.cursor.execute(queries.add_audiostreams, args)

    def add_subtitles(self, *args):
        self.cursor.execute(queries.add_subtitles, args)

    def update_reference(self, *args):
        self.cursor.execute(queries.update_reference, args)

    #Parent_id is the parent Kodi id
    def update_parent_id(self, *args):
        self.cursor.execute(queries.update_parent, args)

    def get_item_id_by_parent_id(self, *args):
        self.cursor.execute(queries.get_item_id_by_parent, args)
        return self.cursor.fetchall()

    def get_item_by_parent_id(self, *args):
        self.cursor.execute(queries.get_item_by_parent, args)
        return self.cursor.fetchall()

    def get_item_by_media_folder(self, *args):
        self.cursor.execute(queries.get_item_by_media_folder, args)
        return self.cursor.fetchall()

    def get_item_by_wild_id(self, item_id):
        self.cursor.execute(queries.get_item_by_wild, (item_id + "%",))
        return self.cursor.fetchall()

    def get_checksum(self, *args):
        self.cursor.execute(queries.get_checksum, args)
        return self.cursor.fetchall()

    def get_item_by_kodi_id(self, *args):
        try:
            self.cursor.execute(queries.get_item_by_kodi, args)
            return self.cursor.fetchone()[0]
        except TypeError:
            return

    def get_full_item_by_kodi_id(self, *args):
        try:
            self.cursor.execute(queries.get_item_by_kodi, args)
            return self.cursor.fetchone()
        except TypeError:
            return

    def get_full_item_by_kodi_id_complete(self, *args):
        try:
            self.cursor.execute(queries.get_item_by_kodi_complete, args)
            return self.cursor.fetchone()
        except TypeError:
            return

    def get_media_by_id(self, *args):
        try:
            self.cursor.execute(queries.get_media_by_id, args)
            return self.cursor.fetchone()[0]
        except TypeError:
            return

    def get_media_by_parent_id(self, *args):
        self.cursor.execute(queries.get_media_by_parent_id, args)
        return self.cursor.fetchall()

    def get_videostreams(self, *args):
        self.cursor.execute(queries.get_videostreams, args)
        return self.cursor.fetchall()

    def get_mediasourceid(self, *args):
        self.cursor.execute(queries.get_mediasourceid, args)
        return self.cursor.fetchall()

    def get_mediasource(self, *args):
        self.cursor.execute(queries.get_mediasource, args)
        return self.cursor.fetchall()

    def get_kodiid(self, *args):
        self.cursor.execute(queries.get_kodiid, args)
        return self.cursor.fetchone()

    def get_kodifileid(self, *args):
        self.cursor.execute(queries.get_kodifileid, args)
        return self.cursor.fetchone()[0]

    def get_AudioStreams(self, *args):
        self.cursor.execute(queries.get_AudioStreams, args)
        return self.cursor.fetchall()

    def get_Subtitles(self, *args):
        self.cursor.execute(queries.get_Subtitles, args)
        return self.cursor.fetchall()

    def get_embyid_by_kodiid(self, *args):
        self.cursor.execute(queries.get_embyid_by_kodiid, args)
        return self.cursor.fetchone()[0]

    def remove_item(self, *args):
        self.cursor.execute(queries.delete_item, args)
        self.cursor.execute(queries.delete_mediasources, args)
        self.cursor.execute(queries.delete_videostreams, args)
        self.cursor.execute(queries.delete_audiostreams, args)
        self.cursor.execute(queries.delete_subtitles, args)

    def remove_item_streaminfos(self, *args):
        self.cursor.execute(queries.delete_mediasources, args)
        self.cursor.execute(queries.delete_videostreams, args)
        self.cursor.execute(queries.delete_audiostreams, args)
        self.cursor.execute(queries.delete_subtitles, args)

    def remove_items_by_parent_id(self, *args):
        self.cursor.execute(queries.delete_item_by_parent, args)

    def remove_item_by_kodi_id(self, *args):
        self.cursor.execute(queries.delete_item_by_kodi, args)

    def remove_wild_item(self, item_id):
        self.cursor.execute(queries.delete_item_by_wild, (item_id + "%",))

    def get_view_name(self, item_id):
        try:
            self.cursor.execute(queries.get_view_name, (item_id,))
            return self.cursor.fetchone()[0]
        except TypeError:
            return

    def get_view(self, *args):
        try:
            self.cursor.execute(queries.get_view, args)
            return self.cursor.fetchone()
        except TypeError:
            return

    def add_view(self, *args):
        try:
            self.cursor.execute(queries.add_view, args)
        except:
            return

    def remove_view(self, *args):
        self.cursor.execute(queries.delete_view, args)

    def get_views(self, *args):
        try:
            self.cursor.execute(queries.get_views, args)
            return self.cursor.fetchall()
        except:
            return

    def get_views_by_media(self, *args):
        self.cursor.execute(queries.get_views_by_media, args)
        return self.cursor.fetchall()

    def get_items_by_media(self, *args):
        self.cursor.execute(queries.get_items_by_media, args)
        return self.cursor.fetchall()

    def remove_media_by_parent_id(self, *args):
        self.cursor.execute(queries.delete_media_by_parent_id, args)

    def get_stack(self, *args):
        try:
            self.cursor.execute(queries.get_presentation_key, args)
            return self.cursor.fetchone()[0]
        except:
            return

    def get_ItemsByPresentation_key(self, PresentationKey):
        self.cursor.execute(queries.get_presentation_key, (PresentationKey + "%",))
        return self.cursor.fetchall()

    def get_version(self, version=None):
        if version is not None:
            self.cursor.execute(queries.delete_version)
            self.cursor.execute(queries.add_version, (version,))
        else:
            try:
                self.cursor.execute(queries.get_version)
                version = self.cursor.fetchone()[0]
            except:
                pass

        return version
