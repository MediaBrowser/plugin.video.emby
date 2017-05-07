# -*- coding: utf-8 -*-
from logging import getLogger
from re import compile as re_compile
import xml.etree.ElementTree as etree

from utils import advancedsettings_xml, indent, tryEncode
from PlexFunctions import get_plex_sections
from PlexAPI import API
import variables as v

###############################################################################
log = getLogger("PLEX."+__name__)

REGEX_MUSICPATH = re_compile(r'''^\^(.+)\$$''')
###############################################################################


def get_current_music_folders():
    """
    Returns a list of encoded strings as paths to the currently "blacklisted"
    excludefromscan music folders in the advancedsettings.xml
    """
    paths = []
    try:
        root, _ = advancedsettings_xml(['audio', 'excludefromscan'])
    except TypeError:
        return paths

    for element in root:
        try:
            path = REGEX_MUSICPATH.findall(element.text)[0]
        except IndexError:
            log.error('Could not parse %s of xml element %s'
                      % (element.text, element.tag))
            continue
        else:
            paths.append(path)
    return paths


def set_excludefromscan_music_folders():
    """
    Gets a complete list of paths for music libraries from the PMS. Sets them
    to be excluded in the advancedsettings.xml from being scanned by Kodi.
    Existing keys will be replaced

    Returns False if no new Plex libraries needed to be exluded, True otherwise
    """
    changed = False
    write_xml = False
    xml = get_plex_sections()
    try:
        xml[0].attrib
    except (TypeError, IndexError, AttributeError):
        log.error('Could not get Plex sections')
        return
    # Build paths
    paths = []
    api = API(item=None)
    for library in xml:
        if library.attrib['type'] != v.PLEX_TYPE_ARTIST:
            # Only look at music libraries
            continue
        for location in library:
            if location.tag == 'Location':
                path = api.validatePlayurl(location.attrib['path'],
                                           typus=v.PLEX_TYPE_ARTIST,
                                           omitCheck=True)
                path = tryEncode(path)
                paths.append(__turn_to_regex(path))
    # Get existing advancedsettings
    root, tree = advancedsettings_xml(['audio', 'excludefromscan'],
                                      force_create=True)

    for path in paths:
        for element in root:
            if element.text == path:
                # Path already excluded
                break
        else:
            changed = True
            write_xml = True
            log.info('New Plex music library detected: %s' % path)
            element = etree.Element(tag='regexp')
            element.text = path
            root.append(element)

    # Delete obsolete entries (unlike above, we don't change 'changed' to not
    # enforce a restart)
    for element in root:
        for path in paths:
            if element.text == path:
                break
        else:
            log.info('Deleting Plex music library from advancedsettings: %s'
                     % element.text)
            root.remove(element)
            write_xml = True

    if write_xml is True:
        indent(tree.getroot())
        tree.write('%sadvancedsettings.xml' % v.KODI_PROFILE)
    return changed


def __turn_to_regex(path):
    """
    Turns a path into regex expression to be fed to Kodi's advancedsettings.xml
    """
    # Make sure we have a slash or backslash at the end of the path
    if '/' in path:
        if not path.endswith('/'):
            path = '%s/' % path
    else:
        if not path.endswith('\\'):
            path = '%s\\' % path
    # Need to escape backslashes
    path = path.replace('\\', '\\\\')
    # Beginning of path only needs to be similar
    return '^%s' % path
