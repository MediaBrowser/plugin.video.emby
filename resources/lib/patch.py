# -*- coding: utf-8 -*-

#################################################################################################

import imp
import logging
import os
import sys

import xbmc
import xbmcvfs
import xbmcaddon

import client
import objects
import requests
from helper.utils import delete_folder, delete_pyo
from helper import _, settings, dialog, find, compare_version, unzip

#################################################################################################

LOG = logging.getLogger("EMBY."+__name__)
CACHE = xbmc.translatePath(os.path.join(xbmcaddon.Addon(id='plugin.video.emby').getAddonInfo('profile').decode('utf-8'), 'emby')).decode('utf-8')
OBJ = "https://raw.githubusercontent.com/MediaBrowser/plugin.video.emby.objects/master/objects.json"

#################################################################################################


def test_versions():
    return {
                "17.*": {
                    "desc": "Krypton objects",
                    "objects": [
                        "171076032-3.1.38-https://github.com/MediaBrowser/plugin.video.emby.objects/archive/krypton.zip"
                    ]
                },
                "beta-17.*": {
                    "desc": "Krypton objects (beta)",
                    "objects": [
                        "171076040-4.0.15-https://github.com/MediaBrowser/plugin.video.emby.objects/archive/171076040.zip",
                        "171076038-4.0.13-https://github.com/MediaBrowser/plugin.video.emby.objects/archive/171076038.zip"
                    ]
                },
                "18.*": {
                    "desc": "Leia objects",
                    "objects": [
                        "181167211-3.1.38-https://github.com/MediaBrowser/plugin.video.emby.objects/archive/leia.zip"
                    ]
                },
                "beta-18.*": {
                    "desc": "Leia objects (beta)",
                    "objects": [
                        "181167226-4.0.17-https://github.com/MediaBrowser/plugin.video.emby.objects/archive/develop.zip",
                        "181167225-4.0.15-https://github.com/MediaBrowser/plugin.video.emby.objects/archive/181167225.zip",
                        "181167224-4.0.14-https://github.com/MediaBrowser/plugin.video.emby.objects/archive/181167224.zip"
                    ]
                },
                "DEV": {
                    "desc": "Developer objects (unstable)",
                    "objects": [
                        "DEV-0.1-https://github.com/MediaBrowser/plugin.video.emby.objects/archive/develop.zip"
                    ]
                }
            }

class Patch(object):

    def __init__(self):

        self.addon_version = client.get_version()
        LOG.warn("--->[ patch ]")

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

            LOG.warn("From %s to %s", src, path.decode('utf-8'))
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
        LOG.warn("--[ check updates/%s ]", objects.version)
        
        if settings('devMode.bool'):
            kodi = "DEV"
        elif not self.addon_version.replace(".", "").isdigit():

            LOG.warn("[ objects/beta check ]")
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
                LOG.warn("--[ force/objects/%s ]", label)

            elif compare_version(self.addon_version, min_version) < 0:
                try:
                    build['objects'].pop(0)
                    versions[key]['objects'] = build['objects']
                    LOG.warn("<[ patch min not met: %s ]", min_version)

                    return self.check_update(versions=versions)

                except Exception as error:
                    LOG.warn("--<[ min add-on version not met: %s ]", min_version)

                    return False

            elif label == objects.version:
                LOG.warn("--<[ objects/%s ]", objects.version)

                return False

            self.get_objects(zipfile, label + '.zip')
            self.reload_objects()

            dialog("notification", heading="{emby}", message=_(33156), icon="{emby}")
            LOG.warn("--<[ new objects/%s ]", objects.version)

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
        reload_modules = ['objects.core.movies', 'objects.core.musicvideos', 'objects.core.tvshows',
                          'objects.core.music', 'objects.core.obj', 'objects.kodi.kodi',
                          'objects.kodi.movies', 'objects.kodi.musicvideos', 'objects.kodi.tvshows',
                          'objects.kodi.music', 'objects.kodi.artwork', 'objects.kodi.queries',
                          'objects.kodi.queries_music', 'objects.kodi.queries_texture', 'objects.monitor',
                          'objects.player', 'objects.utils', 'objects.core.listitem', 'objects.play.playlist', 
                          'objects.play.strm', 'objects.play.single', 'objects.play.plugin',

                          'objects.movies', 'objects.musicvideos', 'objects.tvshows',
                          'objects.music', 'objects.obj', 'objects.actions']

        for mod in reload_modules:

            if mod in sys.modules:
                del sys.modules[mod]

        import objects

        try:
            delete_pyo(CACHE)
        except Exception:
            pass

        imp.reload(objects)

        import library
        from hooks import webservice

        reload(library)
        reload(webservice)

        LOG.warn("---[ objects reloaded ]")
