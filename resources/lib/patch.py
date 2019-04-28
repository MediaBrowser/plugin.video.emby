# -*- coding: utf-8 -*-

#################################################################################################

import logging
import os
import sys

import xbmc
import xbmcvfs
import xbmcaddon

import client
import objects
import requests
from helper.utils import delete_folder
from helper import _, settings, dialog, find, compare_version, unzip

#################################################################################################

LOG = logging.getLogger("EMBY."+__name__)
CACHE = xbmc.translatePath(os.path.join(xbmcaddon.Addon(id='plugin.video.emby').getAddonInfo('profile').decode('utf-8'), 'emby')).decode('utf-8')
OBJ = "https://raw.githubusercontent.com/MediaBrowser/plugin.video.emby.objects/master/objects.json"

#################################################################################################


class Patch(object):

    def __init__(self):

        self.addon_version = client.get_version()
        LOG.info("---[ patch ]")

    def get_objects(self, src, filename):

        ''' Download objects dependency to temp cache folder.
        '''
        temp = CACHE
        restart = not xbmcvfs.exists(os.path.join(temp, "objects") + '/')
        path = os.path.join(temp, filename).encode('utf-8')

        if restart and (settings('appliedPatch') or "") == filename:

            LOG.warn("Something went wrong applying this patch %s previously.", filename)
            restart = False

        if not xbmcvfs.exists(path) or filename.startswith('DEV'):
            delete_folder(CACHE)

            LOG.info("From %s to %s", src, path.decode('utf-8'))
            try:
                response = requests.get(src, stream=True, verify=True)
                response.raise_for_status()
            except requests.exceptions.SSLError as error:

                LOG.error(error)
                response = requests.get(src, stream=True, verify=False)
            except Exception as error:
                raise

            dl = xbmcvfs.File(path, 'w')
            dl.write(response.content)
            dl.close()
            del response

            settings('appliedPatch', filename)

        unzip(path, temp, "objects")

        return restart

    def check_update(self, forced=False, versions=None):

        ''' Check for objects build version and compare.
            This pulls a dict that contains all the information for the build needed.
        '''
        LOG.info("--[ check updates/%s ]", objects.version)
        
        if settings('devMode.bool'):
            kodi = "DEV"
        elif not self.addon_version.replace(".", "").isdigit():

            LOG.info("[ objects/beta check ]")
            kodi = "beta-%s" % xbmc.getInfoLabel('System.BuildVersion')
        else:
            kodi = xbmc.getInfoLabel('System.BuildVersion')

        try:
            versions = versions or requests.get(OBJ).json()
            build, key = find(versions, kodi)

            if not build:
                raise Exception("build %s incompatible?!" % kodi)

            label, min_version, zipfile = build['objects'][0].split('-', 2)

            if label == 'DEV' and forced:
                LOG.info("--[ force/objects/%s ]", label)

            elif compare_version(self.addon_version, min_version) < 0:
                try:
                    build['objects'].pop(0)
                    versions[key]['objects'] = build['objects']
                    LOG.info("<[ patch min not met: %s ]", min_version)

                    return self.check_update(versions=versions)

                except Exception as error:
                    LOG.info("--<[ min add-on version not met: %s ]", min_version)

                    return False

            elif label == objects.version:
                LOG.info("--<[ objects/%s ]", objects.version)

                return False

            self.get_objects(zipfile, label + '.zip')
            self.reload_objects()

            dialog("notification", heading="{emby}", message=_(33156), icon="{emby}")
            LOG.info("--<[ new objects/%s ]", objects.version)

            try:
                if compare_version(self.addon_version, objects.embyversion) < 0:
                    dialog("ok", heading="{emby}", line1="%s %s" % (_(33160), objects.embyversion))
            except Exception:
                pass

        except Exception as error:
            LOG.exception(error)

        return True

    def reload_objects(self):

        ''' Reload objects which depends on the patch module.
            This allows to see the changes in code without restarting the python interpreter.
        '''
        reload_modules = ['objects.movies', 'objects.musicvideos', 'objects.tvshows',
                          'objects.music', 'objects.obj', 'objects.actions', 'objects.kodi.kodi',
                          'objects.kodi.movies', 'objects.kodi.musicvideos', 'objects.kodi.tvshows',
                          'objects.kodi.music', 'objects.kodi.artwork', 'objects.kodi.queries',
                          'objects.kodi.queries_music', 'objects.kodi.queries_texture']

        for mod in reload_modules:
            del sys.modules[mod]

        import library
        import monitor
        import webservice
        from helper import playstrm

        reload(objects.kodi)
        reload(objects)
        reload(library)
        reload(monitor)

        reload(webservice)
        reload(playstrm)

        objects.obj.Objects().mapping()

        LOG.warn("---[ objects reloaded ]")
