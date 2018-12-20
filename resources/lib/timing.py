#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from datetime import datetime, timedelta
from time import localtime, strftime

EPOCH = datetime.utcfromtimestamp(0)

# What's the time offset between the PMS and Kodi?
KODI_PLEX_TIME_OFFSET = 0.0


def unix_timestamp(seconds_into_the_future=None):
    """
    Returns a Unix time stamp (seconds passed since January 1 1970) for NOW as
    an integer.

    Optionally, pass seconds_into_the_future: positive int's will result in a
    future timestamp, negative the past
    """
    if seconds_into_the_future:
        future = datetime.utcnow() + timedelta(seconds=seconds_into_the_future)
    else:
        future = datetime.utcnow()
    return int((future - EPOCH).total_seconds())


def unix_date_to_kodi(unix_kodi_time):
    """
    converts a Unix time stamp (seconds passed sinceJanuary 1 1970) to a
    propper, human-readable time stamp used by Kodi

    Output: Y-m-d h:m:s = 2009-04-05 23:16:04
    """
    return strftime('%Y-%m-%d %H:%M:%S', localtime(float(unix_kodi_time)))


def plex_date_to_kodi(plex_timestamp):
    """
    converts a Unix time stamp (seconds passed sinceJanuary 1 1970) to a
    propper, human-readable time stamp used by Kodi

    Output: Y-m-d h:m:s = 2009-04-05 23:16:04

    Returns None if plex_timestamp is not valid (e.g. -1))
    """
    try:
        return strftime('%Y-%m-%d %H:%M:%S',
                        localtime(float(plex_timestamp) + KODI_PLEX_TIME_OFFSET))
    except ValueError:
        # the PMS can return -1 as plex_timestamp - great!
        return


def kodi_date_to_plex(kodi_timestamp):
    return float(kodi_timestamp) - KODI_PLEX_TIME_OFFSET


def plex_now():
    return kodi_date_to_plex(unix_timestamp())


def kodi_timestamp(plex_timestamp):
    return unix_date_to_kodi(plex_timestamp)


def kodi_now():
    return unix_date_to_kodi(unix_timestamp())


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
    seconds = int(milliseconds / 1000)
    minutes = int(seconds / 60)
    seconds = seconds % 60
    hours = int(minutes / 60)
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
    return 0 if ret < 0 else ret
