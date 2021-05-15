# -*- coding: utf-8 -*-
try:
    from urllib import urlencode
except:
    from urllib.parse import urlencode

class API():
    def __init__(self, Basics, ssl):
        self.Basics = Basics
        self.verify_ssl = ssl

    def get_playcount(self, played, playcount):
        return (playcount or 1) if played else None

    def get_actors(self, people):
        cast = []
        self.get_people_artwork(people)

        for person in people:
            if person['Type'] == "Actor":
                cast.append({
                    'name': person['Name'],
                    'role': person.get('Role', "Unknown"),
                    'order': len(cast) + 1,
                    'thumbnail': person['imageurl']
                })

        return cast

    def media_streams(self, video, audio, subtitles):
        return {
            'video': video or [],
            'audio': audio or [],
            'subtitle': subtitles or []
        }

    def video_streams(self, tracks, container, item):
        if container:
            container = container.split(',')[0]

        for track in tracks:
            track.update({
                'codec': track.get('Codec', "").lower(),
                'profile': track.get('Profile', "").lower(),
                'height': track.get('Height'),
                'width': track.get('Width'),
                '3d': item.get('Video3DFormat'),
                'aspect': 1.85
            })

            if "msmpeg4" in track['codec']:
                track['codec'] = "divx"

            elif "mpeg4" in track['codec']:
                if "simple profile" in track['profile'] or not track['profile']:
                    track['codec'] = "xvid"
            elif "h264" in track['codec']:
                if container in ('mp4', 'mov', 'm4v'):
                    track['codec'] = "avc1"

            try:
                width, height = item.get('AspectRatio', track.get('AspectRatio', "0")).split(':')
                track['aspect'] = round(float(width) / float(height), 6)
            except (ValueError, ZeroDivisionError):

                if track['width'] and track['height']:
                    track['aspect'] = round(float(track['width'] / track['height']), 6)

            track['duration'] = self.get_runtime(item)

        return tracks

    def audio_streams(self, tracks):
        for track in tracks:
            track.update({
                'codec': track.get('Codec', "").lower(),
                'profile': track.get('Profile', "").lower(),
                'channels': track.get('Channels'),
                'language': track.get('Language')
            })

            if "dts-hd ma" in track['profile']:
                track['codec'] = "dtshd_ma"
            elif "dts-hd hra" in track['profile']:
                track['codec'] = "dtshd_hra"

        return tracks

    def get_runtime(self, item):
        try:
            runtime = item['RunTimeTicks'] / 10000000.0
        except KeyError:
            runtime = item.get('CumulativeRunTimeTicks', 0) / 10000000.0

        return runtime

    def adjust_resume(self, resume_seconds):
        resume = 0

        if resume_seconds:
            resume = round(float(resume_seconds), 6)
            jumpback = int(self.Basics.settings('resumeJumpBack'))

            if resume > jumpback:
                # To avoid negative bookmark
                resume = resume - jumpback

        return resume

    def validate_studio(self, studio_name):
        # Convert studio for Kodi to properly detect them
        studios = {
            'abc (us)': "ABC",
            'fox (us)': "FOX",
            'mtv (us)': "MTV",
            'showcase (ca)': "Showcase",
            'wgn america': "WGN",
            'bravo (us)': "Bravo",
            'tnt (us)': "TNT",
            'comedy central': "Comedy Central (US)"
        }
        return studios.get(studio_name.lower(), studio_name)

    def get_overview(self, overview, item):
        overview = overview or item.get('Overview')

        if not overview:
            return

        overview = overview.replace("\"", "\'")
        overview = overview.replace("\n", "[CR]")
        overview = overview.replace("\r", " ")
        overview = overview.replace("<br>", "[CR]")
        return overview

    def get_DateAdded(self, DateInfo):
        if DateInfo:
            DateAdded = DateInfo.split('.')[0].replace('T', " ")
            FileDate = "%s.%s.%s" % tuple(reversed(DateAdded.split('T')[0].split('-')))
            return DateAdded, FileDate

        return None, None

    def get_mpaa(self, rating, item):
        mpaa = rating or item.get('OfficialRating', "")

        if mpaa in ("NR", "UR"):
            # Kodi seems to not like NR, but will accept Not Rated
            mpaa = "Not Rated"

        if "FSK-" in mpaa:
            mpaa = mpaa.replace("-", " ")

        if "GB-" in mpaa:
            mpaa = mpaa.replace("GB-", "UK:")

        return mpaa

    def get_file_path(self, path, item):
        if path is None:
            path = item.get('Path')

        path = self.Basics.StringMod(path)

        #Addonmode replace filextensions
        if path.endswith('.strm'):
            path = path.replace('.strm', "")

            if 'Container' in item:
                if not path.endswith(self.Basics.StringMod(item['Container'])):
                    path = path + "." + self.Basics.StringMod(item['Container'])

        if not path:
            return ""

        if path.startswith('\\\\'):
            path = path.replace('\\\\', "smb://", 1).replace('\\\\', "\\").replace('\\', "/")

        if 'Container' in item:
            if item['Container'] == 'dvd':
                path = "%s/VIDEO_TS/VIDEO_TS.IFO" % path
            elif item['Container'] == 'bluray':
                path = "%s/BDMV/index.bdmv" % path

        path = path.replace('\\\\', "\\")

        if '\\' in path:
            path = path.replace('/', "\\")

        if '://' in path:
            protocol = path.split('://')[0]
            path = path.replace(protocol, protocol.lower())

        return path

    #Get people (actor, director, etc) artwork.
    def get_people_artwork(self, people):
        for person in people:
            if 'PrimaryImageTag' in person:
                #query = [('MaxWidth', 400), ('MaxHeight', 400), ('Index', 0)]
                query = [('Index', 0)]
                person['imageurl'] = self.get_artwork(person['Id'], "Primary", person['PrimaryImageTag'], query)
            else:
                person['imageurl'] = None

        return people

    #Get all artwork possible. If parent_info is True, it will fill missing artwork with parent artwork.
    def get_all_artwork(self, obj, parent_info=False):
        query = []
        all_artwork = {
            'Primary': "",
            'BoxRear': "",
            'Art': "",
            'Banner': "",
            'Logo': "",
            'Thumb': "",
            'Disc': "",
            'Backdrop': []
        }
        all_artwork['Backdrop'] = self.get_backdrops(obj['Id'], obj['BackdropTags'] or [], query)

        for artwork in (obj['Tags'] or []):
            all_artwork[artwork] = self.get_artwork(obj['Id'], artwork, obj['Tags'][artwork], query)

        if parent_info:
            if not all_artwork['Backdrop'] and obj['ParentBackdropId']:
                all_artwork['Backdrop'] = self.get_backdrops(obj['ParentBackdropId'], obj['ParentBackdropTags'], query)

            for art in ('Logo', 'Art', 'Thumb'):
                if not all_artwork[art] and obj['Parent%sId' % art]:
                    all_artwork[art] = self.get_artwork(obj['Parent%sId' % art], art, obj['Parent%sTag' % art], query)

            if obj.get('SeriesTag'):
                all_artwork['Series.Primary'] = self.get_artwork(obj['SeriesId'], "Primary", obj['SeriesTag'], query)

                if not all_artwork['Primary']:
                    all_artwork['Primary'] = all_artwork['Series.Primary']

            elif not all_artwork['Primary'] and obj.get('AlbumId'):
                all_artwork['Primary'] = self.get_artwork(obj['AlbumId'], "Primary", obj['AlbumTag'], query)

        return all_artwork

    #Get backdrops based of "BackdropImageTags" in the emby object.
    def get_backdrops(self, item_id, tags, query):
        query = list(query) if query else []
        backdrops = []

        if item_id is None:
            return backdrops

        for index, tag in enumerate(tags):
            query.append(('Tag', tag))
            artwork = "http://127.0.0.1:57578/%s/Images/Backdrop/%s?%s" % (item_id, index, urlencode(query))

            if not self.verify_ssl:
                artwork += "|verifypeer=false"

            backdrops.append(artwork)

        return backdrops

    #Get any type of artwork: Primary, Art, Banner, Logo, Thumb, Disc
    def get_artwork(self, item_id, image, tag, query):
        query = list(query) if query else []

        if item_id is None:
            return ""

        if tag is not None:
            query.append(('Tag', tag))

        artwork = "http://127.0.0.1:57578/%s/Images/%s/0?%s" % (item_id, image, urlencode(query))

        if not self.verify_ssl:
            artwork += "|verifypeer=false"

        return artwork
