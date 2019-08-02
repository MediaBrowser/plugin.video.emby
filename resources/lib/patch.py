# -*- coding: utf-8 -*-

#################################################################################################

import imp
import logging
import os
import sys

import xbmc
import xbmcvfs
import xbmcaddon

try:
    import objects
except ImportError:
    objects = None

import client
import requests
from helper.utils import delete_folder, delete_pyo, copytree
from helper import _, settings, dialog, find, compare_version, unzip

#################################################################################################

__addon__ = xbmcaddon.Addon(id='plugin.video.emby')
__addon_path__ = __addon__.getAddonInfo('path').decode('utf-8')
BASE = xbmc.translatePath(os.path.join(__addon_path__, 'resources', 'lib', 'objects')).decode('utf-8')
CACHE = xbmc.translatePath(os.path.join(__addon__.getAddonInfo('profile').decode('utf-8'), 'emby')).decode('utf-8')
OBJ = "https://raw.githubusercontent.com/MediaBrowser/plugin.video.emby.objects/master/objects.json"
LOG = logging.getLogger("EMBY."+__name__)

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

    def get_objects(self, src, filename, dest=None):

        ''' Download objects dependency to temp cache folder.
        '''
        dest = dest or CACHE
        path = os.path.join(dest, filename).encode('utf-8')

        if (settings('appliedPatch') or "") == filename:
            LOG.warn("Something went wrong applying this patch %s previously.", filename)

        delete_folder(dest if dest is CACHE else os.path.join(dest, "objects"))
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
        unzip(path, dest, "objects")

        return

    def get_objects_versions(self):

        try:
            return requests.get(OBJ).json()
        except Exception as error:
            LOG.error(error)

            return requests.get(OBJ, verify=False).json()

    def check_update(self, forced=False, versions=None):

        ''' Check for objects build version and compare.
            This pulls a dict that contains all the information for the build needed.
        '''
        if not objects:
            forced = True
            current_version = None
        else:
            current_version = objects.version

        LOG.warn("--[ check updates/%s ]", current_version)
        
        if settings('devMode.bool'):
            kodi = "DEV"
        elif not self.addon_version.replace(".", "").isdigit():

            LOG.warn("[ objects/beta check ]")
            kodi = "beta-%s" % xbmc.getInfoLabel('System.BuildVersion')
        else:
            kodi = xbmc.getInfoLabel('System.BuildVersion')

        try:
            versions = versions or self.get_objects_versions()
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
                    #dialog("ok", heading="{emby}", line1="%s %s" % (_(33160), min_version))

                    return False

            elif label == current_version:

                LOG.warn("--<[ objects/%s ]", current_version)
                settings('patchVersion', current_version)

                return False

            self.get_objects(zipfile, label + '.zip')
            self.reload_objects()
            dialog("notification", heading="{emby}", message=_(33156), icon="{emby}")
            LOG.warn("--<[ new objects/%s ]", objects.version)
            settings('patchVersion', objects.version)

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

        try:
            delete_pyo(CACHE)
        except Exception:
            pass

        import objects
        imp.reload(objects)

        import library
        from hooks import webservice

        imp.reload(library)
        imp.reload(webservice)

        LOG.warn("---[ objects reloaded ]")

    def reset(self):

        ''' Delete /emby folder and retry download for patch.
        '''
        delete_folder(CACHE)
        copytree(BASE, os.path.join(CACHE, 'objects'))

        import objects
        imp.reload(objects)

        self.check_update()
