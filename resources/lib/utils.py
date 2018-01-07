# -*- coding: utf-8 -*-

###############################################################################
from logging import getLogger
from cProfile import Profile
from pstats import Stats
from sqlite3 import connect, OperationalError
from datetime import datetime, timedelta
from StringIO import StringIO
from time import localtime, strftime, strptime
from unicodedata import normalize
import xml.etree.ElementTree as etree
from functools import wraps, partial
from calendar import timegm
from os.path import join
from os import remove, walk, makedirs
from shutil import rmtree
from urllib import quote_plus

import xbmc
import xbmcaddon
import xbmcgui
from xbmcvfs import exists, delete

from variables import DB_VIDEO_PATH, DB_MUSIC_PATH, DB_TEXTURE_PATH, \
    DB_PLEX_PATH, KODI_PROFILE, KODIVERSION
import state

###############################################################################

log = getLogger("PLEX."+__name__)

WINDOW = xbmcgui.Window(10000)
ADDON = xbmcaddon.Addon(id='plugin.video.plexkodiconnect')

###############################################################################
# Main methods


def reboot_kodi(message=None):
    """
    Displays an OK prompt with 'Kodi will now restart to apply the changes'
    Kodi will then reboot.

    Set optional custom message
    """
    message = message or language(33033)
    dialog('ok', heading='{plex}', line1=message)
    xbmc.executebuiltin('RestartApp')

def window(property, value=None, clear=False, windowid=10000):
    """
    Get or set window property - thread safe!

    Returns unicode.

    Property and value may be string or unicode
    """
    if windowid != 10000:
        win = xbmcgui.Window(windowid)
    else:
        win = WINDOW

    if clear:
        win.clearProperty(property)
    elif value is not None:
        win.setProperty(tryEncode(property), tryEncode(value))
    else:
        return tryDecode(win.getProperty(property))


def plex_command(key, value):
    """
    Used to funnel states between different Python instances. NOT really thread
    safe - let's hope the Kodi user can't click fast enough

        key:   state.py variable
        value: either 'True' or 'False'
    """
    while window('plex_command'):
        xbmc.sleep(20)
    window('plex_command', value='%s-%s' % (key, value))


def settings(setting, value=None):
    """
    Get or add addon setting. Returns unicode

    setting and value can either be unicode or string
    """
    # We need to instantiate every single time to read changed variables!
    addon = xbmcaddon.Addon(id='plugin.video.plexkodiconnect')
    if value is not None:
        # Takes string or unicode by default!
        addon.setSetting(tryEncode(setting), tryEncode(value))
    else:
        # Should return unicode by default, but just in case
        return tryDecode(addon.getSetting(setting))


def exists_dir(path):
    """
    Safe way to check whether the directory path exists already (broken in Kodi
    <17)

    Feed with encoded string or unicode
    """
    if KODIVERSION >= 17:
        answ = exists(tryEncode(path))
    else:
        dummyfile = join(tryDecode(path), 'dummyfile.txt')
        try:
            with open(dummyfile, 'w') as f:
                f.write('text')
        except IOError:
            # folder does not exist yet
            answ = 0
        else:
            # Folder exists. Delete file again.
            delete(tryEncode(dummyfile))
            answ = 1
    return answ


def language(stringid):
    # Central string retrieval
    return ADDON.getLocalizedString(stringid)


def dialog(typus, *args, **kwargs):
    """
    Displays xbmcgui Dialog. Pass a string as typus:
        'yesno', 'ok', 'notification', 'input', 'select', 'numeric'

    kwargs:
        heading='{plex}'        title bar (here PlexKodiConnect)
        message=lang(30128),    Actual dialog content. Don't use with OK
        line1=str(),            For 'OK' and 'yesno' dialogs use line1...line3!
        time=5000,
        sound=True,
        nolabel=str(),          For 'yesno' dialogs
        yeslabel=str(),         For 'yesno' dialogs

    Icons:
        icon='{plex}'       Display Plex standard icon
        icon='{info}'       xbmcgui.NOTIFICATION_INFO
        icon='{warning}'    xbmcgui.NOTIFICATION_WARNING
        icon='{error}'      xbmcgui.NOTIFICATION_ERROR

    Input Types:
        type='{alphanum}'   xbmcgui.INPUT_ALPHANUM (standard keyboard)
        type='{numeric}'    xbmcgui.INPUT_NUMERIC (format: #)
        type='{date}'       xbmcgui.INPUT_DATE (format: DD/MM/YYYY)
        type='{time}'       xbmcgui.INPUT_TIME (format: HH:MM)
        type='{ipaddress}'  xbmcgui.INPUT_IPADDRESS (format: #.#.#.#)
        type='{password}'   xbmcgui.INPUT_PASSWORD
                            (return md5 hash of input, input is masked)
    """
    d = xbmcgui.Dialog()
    if "icon" in kwargs:
        types = {
            '{plex}': 'special://home/addons/plugin.video.plexkodiconnect/icon.png',
            '{info}': xbmcgui.NOTIFICATION_INFO,
            '{warning}': xbmcgui.NOTIFICATION_WARNING,
            '{error}': xbmcgui.NOTIFICATION_ERROR
        }
        for key, value in types.iteritems():
            kwargs['icon'] = kwargs['icon'].replace(key, value)
    if 'type' in kwargs:
        types = {
            '{alphanum}': xbmcgui.INPUT_ALPHANUM,
            '{numeric}': xbmcgui.INPUT_NUMERIC,
            '{date}': xbmcgui.INPUT_DATE,
            '{time}': xbmcgui.INPUT_TIME,
            '{ipaddress}': xbmcgui.INPUT_IPADDRESS,
            '{password}': xbmcgui.INPUT_PASSWORD
        }
        kwargs['type'] = types[kwargs['type']]
    if "heading" in kwargs:
        kwargs['heading'] = kwargs['heading'].replace("{plex}",
                                                      language(29999))
    types = {
        'yesno': d.yesno,
        'ok': d.ok,
        'notification': d.notification,
        'input': d.input,
        'select': d.select,
        'numeric': d.numeric
    }
    return types[typus](*args, **kwargs)


def millis_to_kodi_time(milliseconds):
    """
    Converts time in milliseconds to the time dict used by the Kodi JSON RPC:
    {
        'hours': [int],
        'minutes': [int],
        'seconds'[int],
        'milliseconds': [int]
    }
    Pass in the time in milliseconds as an int
    """
    seconds = milliseconds / 1000
    minutes = seconds / 60
    hours = minutes / 60
    seconds = seconds % 60
    minutes = minutes % 60
    milliseconds = milliseconds % 1000
    return {'hours': hours,
            'minutes': minutes,
            'seconds': seconds,
            'milliseconds': milliseconds}


def kodi_time_to_millis(time):
    """
    Converts the Kodi time dict
    {
        'hours': [int],
        'minutes': [int],
        'seconds'[int],
        'milliseconds': [int]
    }
    to milliseconds [int]. Will not return negative results but 0!
    """
    ret = (time['hours'] * 3600 +
           time['minutes'] * 60 +
           time['seconds']) * 1000 + time['milliseconds']
    ret = 0 if ret < 0 else ret
    return ret


def tryEncode(uniString, encoding='utf-8'):
    """
    Will try to encode uniString (in unicode) to encoding. This possibly
    fails with e.g. Android TV's Python, which does not accept arguments for
    string.encode()
    """
    if isinstance(uniString, str):
        # already encoded
        return uniString
    try:
        uniString = uniString.encode(encoding, "ignore")
    except TypeError:
        uniString = uniString.encode()
    return uniString


def tryDecode(string, encoding='utf-8'):
    """
    Will try to decode string (encoded) using encoding. This possibly
    fails with e.g. Android TV's Python, which does not accept arguments for
    string.encode()
    """
    if isinstance(string, unicode):
        # already decoded
        return string
    try:
        string = string.decode(encoding, "ignore")
    except TypeError:
        string = string.decode()
    return string


def slugify(text):
    """
    Normalizes text (in unicode or string) to e.g. enable safe filenames.
    Returns unicode
    """
    if not isinstance(text, unicode):
        text = unicode(text)
    return unicode(normalize('NFKD', text).encode('ascii', 'ignore'))


def escape_html(string):
    """
    Escapes the following:
        < to &lt;
        > to &gt;
        & to &amp;
    """
    escapes = {
        '<': '&lt;',
        '>': '&gt;',
        '&': '&amp;'
    }
    for key, value in escapes.iteritems():
        string = string.replace(key, value)
    return string


def DateToKodi(stamp):
    """
    converts a Unix time stamp (seconds passed sinceJanuary 1 1970) to a
    propper, human-readable time stamp used by Kodi

    Output: Y-m-d h:m:s = 2009-04-05 23:16:04

    None if an error was encountered
    """
    try:
        stamp = float(stamp) + state.KODI_PLEX_TIME_OFFSET
        date_time = localtime(stamp)
        localdate = strftime('%Y-%m-%d %H:%M:%S', date_time)
    except:
        localdate = None
    return localdate


def IntFromStr(string):
    """
    Returns an int from string or the int 0 if something happened
    """
    try:
        result = int(string)
    except:
        result = 0
    return result


def getUnixTimestamp(secondsIntoTheFuture=None):
    """
    Returns a Unix time stamp (seconds passed since January 1 1970) for NOW as
    an integer.

    Optionally, pass secondsIntoTheFuture: positive int's will result in a
    future timestamp, negative the past
    """
    if secondsIntoTheFuture:
        future = datetime.utcnow() + timedelta(seconds=secondsIntoTheFuture)
    else:
        future = datetime.utcnow()
    return timegm(future.timetuple())


def kodiSQL(media_type="video"):
    if media_type == "plex":
        dbPath = DB_PLEX_PATH
    elif media_type == "music":
        dbPath = DB_MUSIC_PATH
    elif media_type == "texture":
        dbPath = DB_TEXTURE_PATH
    else:
        dbPath = DB_VIDEO_PATH
    return connect(dbPath, timeout=60.0)


def create_actor_db_index():
    """
    Index the "actors" because we got a TON - speed up SELECT and WHEN
    """
    conn = kodiSQL('video')
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE UNIQUE INDEX index_name
            ON actor (name);
        """)
    except OperationalError:
        # Index already exists
        pass
    conn.commit()
    conn.close()


def reset():
    # Are you sure you want to reset your local Kodi database?
    if not dialog('yesno',
                  heading='{plex} %s ' % language(30132),
                  line1=language(39600)):
        return

    # first stop any db sync
    plex_command('STOP_SYNC', 'True')
    count = 10
    while window('plex_dbScan') == "true":
        log.debug("Sync is running, will retry: %s..." % count)
        count -= 1
        if count == 0:
            # Could not stop the database from running. Please try again later.
            dialog('ok',
                   heading='{plex} %s' % language(30132),
                   line1=language(39601))
            return
        xbmc.sleep(1000)

    # Clean up the playlists
    deletePlaylists()

    # Clean up the video nodes
    deleteNodes()

    # Wipe the kodi databases
    log.info("Resetting the Kodi video database.")
    connection = kodiSQL('video')
    cursor = connection.cursor()
    cursor.execute('SELECT tbl_name FROM sqlite_master WHERE type="table"')
    rows = cursor.fetchall()
    for row in rows:
        tablename = row[0]
        if tablename != "version":
            cursor.execute("DELETE FROM %s" % tablename)
    connection.commit()
    cursor.close()

    if settings('enableMusic') == "true":
        log.info("Resetting the Kodi music database.")
        connection = kodiSQL('music')
        cursor = connection.cursor()
        cursor.execute('SELECT tbl_name FROM sqlite_master WHERE type="table"')
        rows = cursor.fetchall()
        for row in rows:
            tablename = row[0]
            if tablename != "version":
                cursor.execute("DELETE FROM %s" % tablename)
        connection.commit()
        cursor.close()

    # Wipe the Plex database
    log.info("Resetting the Plex database.")
    connection = kodiSQL('plex')
    cursor = connection.cursor()
    cursor.execute('SELECT tbl_name FROM sqlite_master WHERE type="table"')
    rows = cursor.fetchall()
    for row in rows:
        tablename = row[0]
        if tablename != "version":
            cursor.execute("DELETE FROM %s" % tablename)
    cursor.execute('DROP table IF EXISTS plex')
    cursor.execute('DROP table IF EXISTS view')
    connection.commit()
    cursor.close()

    # Remove all cached artwork? (recommended!)
    if dialog('yesno',
              heading='{plex} %s ' % language(30132),
              line1=language(39602)):
        log.info("Resetting all cached artwork.")
        # Remove all existing textures first
        path = xbmc.translatePath("special://thumbnails/")
        if exists(path):
            rmtree(tryDecode(path), ignore_errors=True)
        # remove all existing data from texture DB
        connection = kodiSQL('texture')
        cursor = connection.cursor()
        query = 'SELECT tbl_name FROM sqlite_master WHERE type=?'
        cursor.execute(query, ("table", ))
        rows = cursor.fetchall()
        for row in rows:
            tableName = row[0]
            if(tableName != "version"):
                cursor.execute("DELETE FROM %s" % tableName)
        connection.commit()
        cursor.close()

    # reset the install run flag
    settings('SyncInstallRunDone', value="false")

    # Reset all PlexKodiConnect Addon settings? (this is usually NOT
    # recommended and unnecessary!)
    if dialog('yesno',
              heading='{plex} %s ' % language(30132),
              line1=language(39603)):
        # Delete the settings
        addon = xbmcaddon.Addon()
        addondir = tryDecode(xbmc.translatePath(addon.getAddonInfo('profile')))
        dataPath = "%ssettings.xml" % addondir
        log.info("Deleting: settings.xml")
        remove(dataPath)
    reboot_kodi()


def profiling(sortby="cumulative"):
    # Will print results to Kodi log
    def decorator(func):
        def wrapper(*args, **kwargs):

            pr = Profile()

            pr.enable()
            result = func(*args, **kwargs)
            pr.disable()

            s = StringIO()
            ps = Stats(pr, stream=s).sort_stats(sortby)
            ps.print_stats()
            log.info(s.getvalue())

            return result

        return wrapper
    return decorator

def convertdate(date):
    try:
        date = datetime.strptime(date, "%Y-%m-%dT%H:%M:%SZ")
    except TypeError:
        # TypeError: attribute of type 'NoneType' is not callable
        # Known Kodi/python error
        date = datetime(*(strptime(date, "%Y-%m-%dT%H:%M:%SZ")[0:6]))

    return date


def compare_version(current, minimum):
    """
    Returns True if current is >= then minimum. False otherwise. Returns True
    if there was no valid input for current!

    Input strings: e.g. "1.2.3"; always with Major, Minor and Patch!
    """
    log.info("current DB: %s minimum DB: %s" % (current, minimum))
    try:
        currMajor, currMinor, currPatch = current.split(".")
    except ValueError:
        # there WAS no current DB, e.g. deleted.
        return True
    minMajor, minMinor, minPatch = minimum.split(".")
    currMajor = int(currMajor)
    currMinor = int(currMinor)
    currPatch = int(currPatch)
    minMajor = int(minMajor)
    minMinor = int(minMinor)
    minPatch = int(minPatch)

    if currMajor > minMajor:
        return True
    elif currMajor < minMajor:
        return False

    if currMinor > minMinor:
        return True
    elif currMinor < minMinor:
        return False

    if currPatch >= minPatch:
        return True
    else:
        return False


def normalize_nodes(text):
    # For video nodes
    text = text.replace(":", "")
    text = text.replace("/", "-")
    text = text.replace("\\", "-")
    text = text.replace("<", "")
    text = text.replace(">", "")
    text = text.replace("*", "")
    text = text.replace("?", "")
    text = text.replace('|', "")
    text = text.replace('(', "")
    text = text.replace(')', "")
    text = text.strip()
    # Remove dots from the last character as windows can not have directories
    # with dots at the end
    text = text.rstrip('.')
    text = tryEncode(normalize('NFKD', unicode(text, 'utf-8')))

    return text

def normalize_string(text):
    # For theme media, do not modify unless
    # modified in TV Tunes
    text = text.replace(":", "")
    text = text.replace("/", "-")
    text = text.replace("\\", "-")
    text = text.replace("<", "")
    text = text.replace(">", "")
    text = text.replace("*", "")
    text = text.replace("?", "")
    text = text.replace('|', "")
    text = text.strip()
    # Remove dots from the last character as windows can not have directories
    # with dots at the end
    text = text.rstrip('.')
    text = tryEncode(normalize('NFKD', unicode(text, 'utf-8')))

    return text


def indent(elem, level=0):
    """
    Prettifies xml trees. Pass the etree root in
    """
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def guisettingsXML():
    """
    Returns special://userdata/guisettings.xml as an etree xml root element
    """
    path = tryDecode(xbmc.translatePath("special://profile/"))
    xmlpath = "%sguisettings.xml" % path

    try:
        xmlparse = etree.parse(xmlpath)
    except IOError:
        # Document is blank or missing
        root = etree.Element('settings')
    except etree.ParseError:
        log.error('Error parsing %s' % xmlpath)
        # "Kodi cannot parse {0}. PKC will not function correctly. Please visit
        # {1} and correct your file!"
        dialog('ok', language(29999), language(39716).format(
            'guisettings.xml', 'http://kodi.wiki/view/userdata'))
        return
    else:
        root = xmlparse.getroot()
    return root


class XmlKodiSetting(object):
    """
    Used to load a Kodi XML settings file from special://profile as an etree
    object to read settings or set them. Usage:
        with XmlKodiSetting(filename,
                            path=None,
                            force_create=False,
                            top_element=None) as xml:
            xml.get_setting('test')

    filename [str]:      filename of the Kodi settings file under
    path [str]:          if set, replace special://profile path with custom
                         path
    force_create:        will create the XML file if it does not exist
    top_element [str]:   Name of the top xml element; used if xml does not
                         yet exist

    Raises IOError if the file does not exist or is empty and force_create
    has been set to False.
    Raises etree.ParseError if the file could not be parsed by etree

    xml.write_xml        Set to True if we need to write the XML to disk
    """
    def __init__(self, filename, path=None, force_create=False,
                 top_element=None):
        self.filename = filename
        if path is None:
            self.path = join(KODI_PROFILE, filename)
        else:
            self.path = join(path, filename)
        self.force_create = force_create
        self.top_element = top_element
        self.tree = None
        self.root = None
        self.write_xml = False

    def __enter__(self):
        try:
            self.tree = etree.parse(self.path)
        except IOError:
            # Document is blank or missing
            if self.force_create is False:
                log.debug('%s does not seem to exist; not creating', self.path)
                # This will abort __enter__
                self.__exit__(IOError, None, None)
            # Create topmost xml entry
            self.tree = etree.ElementTree(
                element=etree.Element(self.top_element))
            self.write_xml = True
        except etree.ParseError:
            log.error('Error parsing %s', self.path)
            # "Kodi cannot parse {0}. PKC will not function correctly. Please
            # visit {1} and correct your file!"
            dialog('ok', language(29999), language(39716).format(
                self.filename,
                'http://kodi.wiki'))
            self.__exit__(etree.ParseError, None, None)
        self.root = self.tree.getroot()
        return self

    def __exit__(self, e_typ, e_val, trcbak):
        if e_typ:
            raise
        # Only safe to file if we did not botch anything
        if self.write_xml is True:
            # Indent and make readable
            indent(self.root)
            # Safe the changed xml
            self.tree.write(self.path, encoding="UTF-8")

    @staticmethod
    def _set_sub_element(element, subelement):
        """
        Returns an etree element's subelement. Creates one if not exist
        """
        answ = element.find(subelement)
        if answ is None:
            answ = etree.SubElement(element, subelement)
        return answ

    def get_setting(self, node_list):
        """
        node_list is a list of node names starting from the outside, ignoring
        the outter advancedsettings.
        Example nodelist=['video', 'busydialogdelayms'] for the following xml
        would return the etree Element:

            <busydialogdelayms>750</busydialogdelayms>

        for the following example xml:

        <advancedsettings>
            <video>
                <busydialogdelayms>750</busydialogdelayms>
            </video>
        </advancedsettings>

        Returns the etree element or None if not found
        """
        element = self.root
        for node in node_list:
            element = element.find(node)
            if element is None:
                break
        return element

    def set_setting(self, node_list, value=None, attrib=None,
                    check_existing=True):
        """
        node_list is a list of node names starting from the outside, ignoring
        the outter advancedsettings.
        Example nodelist=['video', 'busydialogdelayms'] for the following xml
        would return the etree Element:

            <busydialogdelayms>750</busydialogdelayms>

        for the following example xml:

        <advancedsettings>
            <video>
                <busydialogdelayms>750</busydialogdelayms>
            </video>
        </advancedsettings>

        value, e.g. '750' will be set accordingly, returning the new
        etree Element. Advancedsettings might be generated if it did not exist
        already

        If the dict attrib is set, the Element's attributs will be appended
        accordingly

        If check_existing is True, it will return the FIRST matching element of
        node_list. Set to False if there are several elements of the same tag!

        Returns the (last) etree element
        """
        attrib = attrib or {}
        value = value or ''
        if check_existing is True:
            old = self.get_setting(node_list)
            if old is not None:
                already_set = True
                if old.text.strip() != value:
                    already_set = False
                elif old.attrib != attrib:
                    already_set = False
                if already_set is True:
                    log.debug('Element has already been found')
                    return old
        # Need to set new setting, indeed
        self.write_xml = True
        element = self.root
        for node in node_list:
            element = self._set_sub_element(element, node)
        # Write new values
        element.text = value
        if attrib:
            for key, attribute in attrib.iteritems():
                element.set(key, attribute)
        return element


def sourcesXML():
    # To make Master lock compatible
    path = tryDecode(xbmc.translatePath("special://profile/"))
    xmlpath = "%ssources.xml" % path

    try:
        xmlparse = etree.parse(xmlpath)
    except IOError:  # Document is blank or missing
        root = etree.Element('sources')
    except etree.ParseError:
        log.error('Error parsing %s' % xmlpath)
        # "Kodi cannot parse {0}. PKC will not function correctly. Please visit
        # {1} and correct your file!"
        dialog('ok', language(29999), language(39716).format(
            'sources.xml', 'http://kodi.wiki/view/sources.xml'))
        return
    else:
        root = xmlparse.getroot()

    video = root.find('video')
    if video is None:
        video = etree.SubElement(root, 'video')
        etree.SubElement(video, 'default', attrib={'pathversion': "1"})

    # Add elements
    count = 2
    for source in root.findall('.//path'):
        if source.text == "smb://":
            count -= 1

        if count == 0:
            # sources already set
            break
    else:
        # Missing smb:// occurences, re-add.
        for i in range(0, count):
            source = etree.SubElement(video, 'source')
            etree.SubElement(source, 'name').text = "Plex"
            etree.SubElement(source, 'path', attrib={'pathversion': "1"}).text = "smb://"
            etree.SubElement(source, 'allowsharing').text = "true"
    # Prettify and write to file
    try:
        indent(root)
    except: pass
    etree.ElementTree(root).write(xmlpath, encoding="UTF-8")


def passwordsXML():
    # To add network credentials
    path = tryDecode(xbmc.translatePath("special://userdata/"))
    xmlpath = "%spasswords.xml" % path
    dialog = xbmcgui.Dialog()

    try:
        xmlparse = etree.parse(xmlpath)
    except IOError:
        # Document is blank or missing
        root = etree.Element('passwords')
        skipFind = True
    except etree.ParseError:
        log.error('Error parsing %s' % xmlpath)
        # "Kodi cannot parse {0}. PKC will not function correctly. Please visit
        # {1} and correct your file!"
        dialog.ok(language(29999), language(39716).format(
            'passwords.xml', 'http://forum.kodi.tv/'))
        return
    else:
        root = xmlparse.getroot()
        skipFind = False

    credentials = settings('networkCreds')
    if credentials:
        # Present user with options
        option = dialog.select(
            "Modify/Remove network credentials", ["Modify", "Remove"])

        if option < 0:
            # User cancelled dialog
            return

        elif option == 1:
            # User selected remove
            for paths in root.getiterator('passwords'):
                for path in paths:
                    if path.find('.//from').text == "smb://%s/" % credentials:
                        paths.remove(path)
                        log.info("Successfully removed credentials for: %s"
                                 % credentials)
                        etree.ElementTree(root).write(xmlpath,
                                                      encoding="UTF-8")
                        break
            else:
                log.error("Failed to find saved server: %s in passwords.xml"
                          % credentials)

            settings('networkCreds', value="")
            xbmcgui.Dialog().notification(
                heading='PlexKodiConnect',
                message="%s removed from passwords.xml" % credentials,
                icon="special://home/addons/plugin.video.plexkodiconnect/icon.png",
                time=1000,
                sound=False)
            return

        elif option == 0:
            # User selected to modify
            server = dialog.input("Modify the computer name or ip address", credentials)
            if not server:
                return
    else:
        # No credentials added
        dialog.ok(
            heading="Network credentials",
            line1= (
                "Input the server name or IP address as indicated in your plex library paths. "
                'For example, the server name: \\\\SERVER-PC\\path\\ or smb://SERVER-PC/path is "SERVER-PC".'))
        server = dialog.input("Enter the server name or IP address")
        if not server:
            return
        server = quote_plus(server)

    # Network username
    user = dialog.input("Enter the network username")
    if not user:
        return
    user = quote_plus(user)
    # Network password
    password = dialog.input("Enter the network password",
                            '',  # Default input
                            xbmcgui.INPUT_ALPHANUM,
                            xbmcgui.ALPHANUM_HIDE_INPUT)
    # Need to url-encode the password
    password = quote_plus(password)
    # Add elements. Annoying etree bug where findall hangs forever
    if skipFind is False:
        skipFind = True
        for path in root.findall('.//path'):
            if path.find('.//from').text.lower() == "smb://%s/" % server.lower():
                # Found the server, rewrite credentials
                path.find('.//to').text = "smb://%s:%s@%s/" % (user, password, server)
                skipFind = False
                break
    if skipFind:
        # Server not found, add it.
        path = etree.SubElement(root, 'path')
        etree.SubElement(path, 'from', attrib={'pathversion': "1"}).text = "smb://%s/" % server
        topath = "smb://%s:%s@%s/" % (user, password, server)
        etree.SubElement(path, 'to', attrib={'pathversion': "1"}).text = topath

    # Add credentials
    settings('networkCreds', value="%s" % server)
    log.info("Added server: %s to passwords.xml" % server)
    # Prettify and write to file
    try:
        indent(root)
    except:
        pass
    etree.ElementTree(root).write(xmlpath, encoding="UTF-8")

    # dialog.notification(
    #     heading="PlexKodiConnect",
    #     message="Added to passwords.xml",
    #     icon="special://home/addons/plugin.video.plexkodiconnect/icon.png",
    #     time=5000,
    #     sound=False)


def playlistXSP(mediatype, tagname, viewid, viewtype="", delete=False):
    """
    Feed with tagname as unicode
    """
    path = tryDecode(xbmc.translatePath("special://profile/playlists/video/"))
    if viewtype == "mixed":
        plname = "%s - %s" % (tagname, mediatype)
        xsppath = "%sPlex %s - %s.xsp" % (path, viewid, mediatype)
    else:
        plname = tagname
        xsppath = "%sPlex %s.xsp" % (path, viewid)

    # Create the playlist directory
    if not exists(tryEncode(path)):
        log.info("Creating directory: %s" % path)
        makedirs(path)

    # Only add the playlist if it doesn't already exists
    if exists(tryEncode(xsppath)):
        log.info('Path %s does exist' % xsppath)
        if delete:
            remove(xsppath)
            log.info("Successfully removed playlist: %s." % tagname)
        return

    # Using write process since there's no guarantee the xml declaration works
    # with etree
    itemtypes = {
        'homevideos': 'movies',
        'movie': 'movies',
        'show': 'tvshows'
    }
    log.info("Writing playlist file to: %s" % xsppath)
    with open(xsppath, 'wb') as f:
        f.write(tryEncode(
            '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
            '<smartplaylist type="%s">\n\t'
                '<name>Plex %s</name>\n\t'
                '<match>all</match>\n\t'
                '<rule field="tag" operator="is">\n\t\t'
                    '<value>%s</value>\n\t'
                '</rule>\n'
            '</smartplaylist>\n'
            % (itemtypes.get(mediatype, mediatype), plname, tagname)))
    log.info("Successfully added playlist: %s" % tagname)


def deletePlaylists():
    # Clean up the playlists
    path = tryDecode(xbmc.translatePath("special://profile/playlists/video/"))
    for root, _, files in walk(path):
        for file in files:
            if file.startswith('Plex'):
                remove(join(root, file))

def deleteNodes():
    # Clean up video nodes
    path = tryDecode(xbmc.translatePath("special://profile/library/video/"))
    for root, dirs, _ in walk(path):
        for directory in dirs:
            if directory.startswith('Plex-'):
                rmtree(join(root, directory))
        break


###############################################################################
# WRAPPERS

def CatchExceptions(warnuser=False):
    """
    Decorator for methods to catch exceptions and log them. Useful for e.g.
    librarysync threads using itemtypes.py, because otherwise we would not
    get informed of crashes

    warnuser=True:      sets the window flag 'plex_scancrashed' to true
                        which will trigger a Kodi infobox to inform user
    """
    def decorate(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log.error('%s has crashed. Error: %s' % (func.__name__, e))
                import traceback
                log.error("Traceback:\n%s" % traceback.format_exc())
                if warnuser:
                    window('plex_scancrashed', value='true')
                return
        return wrapper
    return decorate


def LogTime(func):
    """
    Decorator for functions and methods to log the time it took to run the code
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        starttotal = datetime.now()
        result = func(*args, **kwargs)
        elapsedtotal = datetime.now() - starttotal
        log.info('It took %s to run the function %s'
                 % (elapsedtotal, func.__name__))
        return result
    return wrapper


def thread_methods(cls=None, add_stops=None, add_suspends=None):
    """
    Decorator to add the following methods to a threading class:

    suspend_thread():    pauses the thread
    resume_thread():     resumes the thread
    stop_thread():       stopps/kills the thread

    thread_suspended():  returns True if thread is suspended
    thread_stopped():    returns True if thread is stopped (or should stop ;-))
                         ALSO returns True if PKC should exit

    Also adds the following class attributes:
        __thread_stopped
        __thread_suspended
        __stops
        __suspends

    invoke with either
        @Newthread_methods
        class MyClass():
    or
        @Newthread_methods(add_stops=['SUSPEND_LIBRARY_TRHEAD'],
                          add_suspends=['DB_SCAN', 'WHATEVER'])
        class MyClass():
    """
    # So we don't need to invoke with ()
    if cls is None:
        return partial(thread_methods,
                       add_stops=add_stops,
                       add_suspends=add_suspends)
    # Because we need a reference, not a copy of the immutable objects in
    # state, we need to look up state every time explicitly
    cls.__stops = ['STOP_PKC']
    if add_stops is not None:
        cls.__stops.extend(add_stops)
    cls.__suspends = add_suspends or []

    # Attach new attributes to class
    cls.__thread_stopped = False
    cls.__thread_suspended = False

    # Define new class methods and attach them to class
    def stop_thread(self):
        self.__thread_stopped = True
    cls.stop_thread = stop_thread

    def suspend_thread(self):
        self.__thread_suspended = True
    cls.suspend_thread = suspend_thread

    def resume_thread(self):
        self.__thread_suspended = False
    cls.resume_thread = resume_thread

    def thread_suspended(self):
        if self.__thread_suspended is True:
            return True
        for suspend in self.__suspends:
            if getattr(state, suspend):
                return True
        return False
    cls.thread_suspended = thread_suspended

    def thread_stopped(self):
        if self.__thread_stopped is True:
            return True
        for stop in self.__stops:
            if getattr(state, stop):
                return True
        return False
    cls.thread_stopped = thread_stopped

    # Return class to render this a decorator
    return cls


class Lock_Function(object):
    """
    Decorator for class methods and functions to lock them with lock.

    Initialize this class first
    lockfunction = Lock_Function(lock), where lock is a threading.Lock() object

    To then lock a function or method:

    @lockfunction.lockthis
    def some_function(args, kwargs)
    """
    def __init__(self, lock):
        self.lock = lock

    def lockthis(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with self.lock:
                result = func(*args, **kwargs)
            return result
        return wrapper

###############################################################################
# UNUSED METHODS


# def changePlayState(itemType, kodiId, playCount, lastplayed):
#     """
#     YET UNUSED

#     kodiId: int or str
#     playCount: int or str
#     lastplayed: str or int unix timestamp
#     """
#     lastplayed = DateToKodi(lastplayed)

#     kodiId = int(kodiId)
#     playCount = int(playCount)
#     method = {
#         'movie': ' VideoLibrary.SetMovieDetails',
#         'episode': 'VideoLibrary.SetEpisodeDetails',
#         'musicvideo': ' VideoLibrary.SetMusicVideoDetails',  # TODO
#         'show': 'VideoLibrary.SetTVShowDetails',  # TODO
#         '': 'AudioLibrary.SetAlbumDetails',  # TODO
#         '': 'AudioLibrary.SetArtistDetails',  # TODO
#         'track': 'AudioLibrary.SetSongDetails'
#     }
#     params = {
#         'movie': {
#             'movieid': kodiId,
#             'playcount': playCount,
#             'lastplayed': lastplayed
#         },
#         'episode': {
#             'episodeid': kodiId,
#             'playcount': playCount,
#             'lastplayed': lastplayed
#         }
#     }
#     result = jsonrpc(method[itemType]).execute(params[itemType])
#     log.debug("JSON result was: %s" % result)
