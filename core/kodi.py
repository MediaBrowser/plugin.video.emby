# -*- coding: utf-8 -*-
import helper.loghandler
from . import artwork
from . import queries_videos

class Kodi():
    def __init__(self, cursor, Utils):
        self.LOG = helper.loghandler.LOG('EMBY.core.kodi.Kodi')
        self.Utils = Utils
        self.cursor = cursor
        self.artwork = artwork.Artwork(cursor, self.Utils)

    def create_entry_path(self):
        self.cursor.execute(queries_videos.create_path)
        return self.cursor.fetchone()[0] + 1

    def create_entry_file(self):
        self.cursor.execute(queries_videos.create_file)
        return self.cursor.fetchone()[0] + 1

    def create_entry_rating(self):
        self.cursor.execute(queries_videos.create_rating)
        return self.cursor.fetchone()[0] + 1

    def create_entry_person(self):
        self.cursor.execute(queries_videos.create_person)
        return self.cursor.fetchone()[0] + 1

    def create_entry_genre(self):
        self.cursor.execute(queries_videos.create_genre)
        return self.cursor.fetchone()[0] + 1

    def create_entry_studio(self):
        self.cursor.execute(queries_videos.create_studio)
        return self.cursor.fetchone()[0] + 1

    def create_entry_bookmark(self):
        self.cursor.execute(queries_videos.create_bookmark)
        return self.cursor.fetchone()[0] + 1

    def create_entry_tag(self):
        self.cursor.execute(queries_videos.create_tag)
        return self.cursor.fetchone()[0] + 1

    def add_path(self, *args):
        path_id = self.get_path(*args)

        if path_id is None:
            path_id = self.create_entry_path()
            self.cursor.execute(queries_videos.add_path, (path_id,) + args)

        return path_id

    def get_path(self, *args):
        self.cursor.execute(queries_videos.get_path, args)
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return None

    def update_path(self, *args):
        self.cursor.execute(queries_videos.update_path, args)

    def add_link(self, link, person_id, args):
        self.cursor.execute(queries_videos.get_update_link.replace("{LinkType}", link), (person_id,) + args)
        Temp = self.cursor.fetchone()

        #No primary Key in DB -> INSERT OR REPLACE not working -> check manually
        if not Temp:
            self.cursor.execute(queries_videos.update_link.replace("{LinkType}", link), (person_id,) + args)

    def remove_path(self, *args):
        self.cursor.execute(queries_videos.delete_path, args)

    def add_file(self, filename, path_id):
        self.cursor.execute(queries_videos.get_file, (path_id, filename,))
        Data = self.cursor.fetchone()

        if Data:
            file_id = Data[0]
        else:
            file_id = self.create_entry_file()
            self.cursor.execute(queries_videos.add_file, (file_id, path_id, filename))

        return file_id

    def update_file(self, *args):
        self.cursor.execute(queries_videos.update_file, args)

    def remove_file(self, path, *args):
        path_id = self.get_path(path)

        if path_id is not None:
            self.cursor.execute(queries_videos.delete_file_by_path, (path_id,) + args)

    def get_filename(self, *args):
        self.cursor.execute(queries_videos.get_filename, args)
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return ""

    def add_people(self, people, *args):
        def add_thumbnail(person_id, person, person_type):
            if person['imageurl']:
                art = person_type.lower()
                if "writing" in art:
                    art = "writer"

                self.artwork.update(person['imageurl'], person_id, art, "thumb")

        cast_order = 1

        for person in people:
            if 'Name' not in person:
                self.LOG.error("Unable to identify person object")
                self.LOG.error(person)
                continue

            person_id = self.get_person(person['Name'])

            if person['Type'] == 'Actor':
                role = person.get('Role')
                self.cursor.execute(queries_videos.update_actor, (person_id,) + args + (role, cast_order,))
                cast_order += 1
            elif person['Type'] == 'Director':
                self.add_link('director_link', person_id, args)
            elif person['Type'] == 'Writer':
                self.add_link('writer_link', person_id, args)
            elif person['Type'] == 'Artist':
                self.add_link('actor_link', person_id, args)

            add_thumbnail(person_id, person, person['Type'])

    def add_person(self, *args):
        person_id = self.create_entry_person()
        self.cursor.execute(queries_videos.add_person, (person_id,) + args)
        return person_id

    def get_person(self, *args):
        self.cursor.execute(queries_videos.get_person, args)
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return self.add_person(*args)

    #Delete current genres first for clean slate
    def add_genres(self, genres, *args):
        self.cursor.execute(queries_videos.delete_genres, args)

        for genre in genres:
            self.cursor.execute(queries_videos.update_genres, (self.get_genre(genre),) + args)

    def add_genre(self, *args):
        genre_id = self.create_entry_genre()
        self.cursor.execute(queries_videos.add_genre, (genre_id,) + args)
        return genre_id

    def get_genre(self, *args):
        self.cursor.execute(queries_videos.get_genre, args)
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return self.add_genre(*args)

    def add_studios(self, studios, *args):
        for studio in studios:
            studio_id = self.get_studio(studio)
            self.cursor.execute(queries_videos.update_studios, (studio_id,) + args)

    def add_studio(self, *args):
        studio_id = self.create_entry_studio()
        self.cursor.execute(queries_videos.add_studio, (studio_id,) + args)
        return studio_id

    def get_studio(self, *args):
        self.cursor.execute(queries_videos.get_studio, args)
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return self.add_studio(*args)

    #First remove any existing entries
    #Then re-add video, audio and subtitles
    def add_streams(self, file_id, streams, runtime):
        self.cursor.execute(queries_videos.delete_streams, (file_id,))

        if streams:
            for track in streams['video']:
                track['FileId'] = file_id
                track['Runtime'] = runtime
                self.add_stream_video(*self.Utils.values(track, queries_videos.add_stream_video_obj))

            for track in streams['audio']:
                track['FileId'] = file_id
                self.add_stream_audio(*self.Utils.values(track, queries_videos.add_stream_audio_obj))

            for track in streams['subtitle']:
                self.add_stream_sub(*self.Utils.values({'language': track, 'FileId': file_id}, queries_videos.add_stream_sub_obj))

    def add_stream_video(self, *args):
        self.cursor.execute(queries_videos.add_stream_video, args)

    def add_stacktimes(self, *args):
        self.cursor.execute(queries_videos.add_stacktimes, args)

    def add_stream_audio(self, *args):
        self.cursor.execute(queries_videos.add_stream_audio, args)

    def add_stream_sub(self, *args):
        self.cursor.execute(queries_videos.add_stream_sub, args)

    #Delete the existing resume point
    #Set the watched count
    def add_playstate(self, file_id, playcount, date_played, resume, *args):
        self.cursor.execute(queries_videos.delete_bookmark, (file_id,))
        self.set_playcount(playcount, date_played, file_id)

        if resume:
            bookmark_id = self.create_entry_bookmark()
            self.cursor.execute(queries_videos.add_bookmark, (bookmark_id, file_id, resume,) + args)

    def set_playcount(self, *args):
        self.cursor.execute(queries_videos.update_playcount, args)

    def add_tags(self, tags, *args):
        self.cursor.execute(queries_videos.delete_tags, args)

        for tag in tags:
            self.get_tag(tag, *args)

    def add_tag(self, *args):
        tag_id = self.create_entry_tag()
        self.cursor.execute(queries_videos.add_tag, (tag_id,) + args)
        return tag_id

    def get_tag(self, tag, *args):
        self.cursor.execute(queries_videos.get_tag, (tag,))
        Data = self.cursor.fetchone()

        if Data:
            tag_id = Data[0]
        else:
            tag_id = self.add_tag(tag)

        self.cursor.execute(queries_videos.update_tag, (tag_id,) + args)
        return tag_id

    def remove_tag(self, tag, *args):
        self.cursor.execute(queries_videos.get_tag, (tag,))
        Data = self.cursor.fetchone()

        if Data:
            tag_id = Data[0]
        else:
            return

        self.cursor.execute(queries_videos.delete_tag, (tag_id,) + args)

    def get_rating_id(self, *args):
        self.cursor.execute(queries_videos.get_rating, args)
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return self.create_entry_rating()

    #Add ratings, rating type and votes
    def add_ratings(self, *args):
        self.cursor.execute(queries_videos.add_rating, args)

    #Update rating by rating_id
    def update_ratings(self, *args):
        self.cursor.execute(queries_videos.update_rating, args)

    #Remove all unique ids associated.
    def remove_unique_ids(self, *args):
        self.cursor.execute(queries_videos.delete_unique_ids, args)
