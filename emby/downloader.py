# -*- coding: utf-8 -*-
import helper.loghandler

class Downloader():
    def __init__(self, Utils, EmbyServer):
        self.Utils = Utils
        self.EmbyServer = EmbyServer
        self.LOG = helper.loghandler.LOG('EMBY.emby.downloader.Downloader')
        self.LIMIT = min(int(self.Utils.settings('limitIndex') or 15), 50)
        self.info = ("Path,Genres,SortName,Studios,Writer,Taglines,LocalTrailerCount,Video3DFormat,OfficialRating,CumulativeRunTimeTicks,ItemCounts,PremiereDate,ProductionYear,Metascore,AirTime,DateCreated,People,Overview,CommunityRating,StartDate,CriticRating,CriticRatingSummary,Etag,ShortOverview,ProductionLocations,Tags,ProviderIds,ParentId,RemoteTrailers,SpecialEpisodeNumbers,Status,EndDate,MediaSources,VoteCount,RecursiveItemCount,PrimaryImageAspectRatio,DisplayOrder,PresentationUniqueKey,OriginalTitle,MediaSources,AlternateMediaSources,PartCount")
        self.browse_info = ("DateCreated,EpisodeCount,SeasonCount,Path,Genres,Studios,Taglines,MediaStreams,Overview,Etag,ProductionLocations,Width,Height,RecursiveItemCount,ChildCount")

    def get_embyserver_url(self, handler):
        if handler.startswith('/'):
            handler = handler[1:]
            self.LOG.warning("handler starts with /: %s" % handler)

        return "{server}/emby/%s" % handler

    def _http(self, action, url, request):
        request.update({'url': url, 'type': action})
        return self.EmbyServer.http.request(request)

    def _get(self, handler, params):
        return self._http("GET", self.get_embyserver_url(handler), {'params': params})

    def _post(self, handler, json, params):
        return self._http("POST", self.get_embyserver_url(handler), {'params': params, 'json': json})

    def _delete(self, handler, params):
        return self._http("DELETE", self.get_embyserver_url(handler), {'params': params})

    #This confirms a single item from the library matches the view it belongs to.
    #Used to detect grouped libraries.
    def validate_view(self, library_id, item_id):
        try:
            result = self._get("Users/{UserId}/Items", {'ParentId': library_id, 'Recursive': True, 'Ids': item_id})
        except Exception:
            return False

        return bool(len(result['Items']))

    #Get dynamic listings
    def get_filtered_section(self, parent_id, media, limit, recursive, sort, sort_order, filters, extra, NoSort):
        if NoSort:
            params = {
                'ParentId': parent_id,
                'IncludeItemTypes': media,
                'IsMissing': False,
                'Recursive': recursive if recursive is not None else True,
                'Limit': limit,
                'ImageTypeLimit': 1,
                'IsVirtualUnaired': False,
                'Fields': self.browse_info
            }
        else:
            params = {
                'ParentId': parent_id,
                'IncludeItemTypes': media,
                'IsMissing': False,
                'Recursive': recursive if recursive is not None else True,
                'Limit': limit,
                'SortBy': sort or "SortName",
                'SortOrder': sort_order or "Ascending",
                'ImageTypeLimit': 1,
                'IsVirtualUnaired': False,
                'Fields': self.browse_info
            }

        if filters:
            if 'Boxsets' in filters:
                filters.remove('Boxsets')
                params['CollapseBoxSetItems'] = self.Utils.settings('groupedSets.bool')

            params['Filters'] = ','.join(filters)

        if self.Utils.settings('getCast.bool'):
            params['Fields'] += ",People"

        if media and 'Photo' in media:
            params['Fields'] += ",Width,Height"

        if extra is not None:
            params.update(extra)

        return self._get("Users/{UserId}/Items", params)

    def get_movies_by_boxset(self, boxset_id):
        for items in self.get_items(boxset_id, "Movie", False, None):
            yield items

    def get_episode_by_show(self, show_id):
        query = {
            'url': "Shows/%s/Episodes" % show_id,
            'params': {
                'EnableUserData': True,
                'EnableImages': True,
                'UserId': "{UserId}",
                'Fields': self.info
            }
        }

        for items in self._get_items(query, self.LIMIT):
            yield items

    def get_episode_by_season(self, show_id, season_id):
        query = {
            'url': "Shows/%s/Episodes" % show_id,
            'params': {
                'SeasonId': season_id,
                'EnableUserData': True,
                'EnableImages': True,
                'UserId': "{UserId}",
                'Fields': self.info
            }
        }

        for items in self._get_items(query, self.LIMIT):
            yield items

    def get_items(self, parent_id, item_type, basic, params):
        query = {
            'url': "Users/{UserId}/Items",
            'params': {
                'ParentId': parent_id,
                'IncludeItemTypes': item_type,
                'Fields': "Etag,PresentationUniqueKey" if basic else self.info,
                'SortOrder': "Ascending",
                'SortBy': "SortName",
                'CollapseBoxSetItems': False,
                'IsVirtualUnaired': False,
                'EnableTotalRecordCount': False,
                'LocationTypes': "FileSystem,Remote,Offline",
                'IsMissing': False,
                'Recursive': True
            }
        }

        if params:
            query['params'].update(params)

        for items in self._get_items(query, self.LIMIT):
            yield items

    def get_artists(self, parent_id, basic, params):
        music_info = (
            "Etag,Genres,SortName,Studios,Writer,PremiereDate,ProductionYear,"
            "OfficialRating,CumulativeRunTimeTicks,Metascore,CommunityRating,"
            "AirTime,DateCreated,MediaStreams,People,ProviderIds,Overview,ItemCounts,"
            "PresentationUniqueKey"
        )
        query = {
            'url': "Artists",
            'params': {
                'UserId': "{UserId}",
                'ParentId': parent_id,
                'SortBy': "SortName",
                'SortOrder': "Ascending",
                'Fields': "Etag,PresentationUniqueKey" if basic else music_info,
                'CollapseBoxSetItems': False,
                'IsVirtualUnaired': False,
                'EnableTotalRecordCount': False,
                'LocationTypes': "FileSystem,Remote,Offline",
                'IsMissing': False,
                'Recursive': True
            }
        }

        if params:
            query['params'].update(params)

        for items in self._get_items(query, self.LIMIT):
            yield items

    def get_albums_by_artist(self, parent_id, artist_id, basic):
        params = {
            'SortBy': "DateCreated",
            'ParentId': parent_id,
            'ArtistIds': artist_id
        } #fixme: test -> remove sortby, but check impact on dynamic lists

        for items in self.get_items(None, "MusicAlbum", basic, params):
            yield items

    def get_songs_by_artist(self, parent_id, artist_id, basic):
        params = {
            'SortBy': "DateCreated",
            'ParentId': parent_id,
            'ArtistIds': artist_id
        } #fixme: test -> remove sortby, but check impact on dynamic lists

        for items in self.get_items(None, "Audio", basic, params):
            yield items

    def get_TotalRecordsRegular(self, parent_id, item_type):
        Params = {
            'ParentId': parent_id,
            'IncludeItemTypes': item_type,
            'CollapseBoxSetItems': False,
            'IsVirtualUnaired': False,
            'IsMissing': False,
            'EnableTotalRecordCount': True,
            'LocationTypes': "FileSystem,Remote,Offline",
            'Recursive': True,
            'Limit': 1
        }

        return self._get("Users/{UserId}/Items", Params)['TotalRecordCount']

    def get_TotalRecordsArtists(self, parent_id):
        Params = {
            'UserId': "{UserId}",
            'ParentId': parent_id,
            'CollapseBoxSetItems': False,
            'IsVirtualUnaired': False,
            'IsMissing': False,
            'EnableTotalRecordCount': True,
            'LocationTypes': "FileSystem,Remote,Offline",
            'Recursive': True,
            'Limit': 1
        }
        return self._get("Artists", Params)['TotalRecordCount']

    def _get_items(self, query, LIMIT):
        items = {
            'Items': [],
            'RestorePoint': {}
        }

        url = query['url']
        params = query.get('params', {})
        index = params.get('StartIndex', 0)

        while True:
            params['StartIndex'] = index
            params['Limit'] = LIMIT

            try:
                result = self._get(url, params) or {'Items': []}
            except Exception as error:
                self.LOG.error("ERROR: %s" % error)
                result = {'Items': []}

            if result['Items'] == []:
                items['TotalRecordCount'] = index
                break

            items['Items'].extend(result['Items'])
            items['RestorePoint'] = query
            yield items
            del items['Items'][:]
            index += LIMIT
