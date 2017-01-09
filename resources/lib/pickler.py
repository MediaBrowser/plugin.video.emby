# -*- coding: utf-8 -*-
###############################################################################
import logging
import cPickle as Pickle

from utils import pickl_window
###############################################################################
log = logging.getLogger("PLEX."+__name__)

###############################################################################


def pickle_me(obj, window_var='plex_result'):
    """
    Pickles the obj to the window variable. Use to transfer Python
    objects between different PKC python instances (e.g. if default.py is
    called and you'd want to use the service.py instance)

    obj can be pretty much any Python object. However, classes and
    functions won't work. See the Pickle documentation
    """
    log.debug('Start pickling: %s' % obj)
    pickl_window(window_var, value=Pickle.dumps(obj))
    log.debug('Successfully pickled')


def unpickle_me(window_var='plex_result'):
    """
    Unpickles a Python object from the window variable window_var.
    Will then clear the window variable!
    """
    result = pickl_window(window_var)
    pickl_window(window_var, clear=True)
    log.debug('Start unpickling')
    obj = Pickle.loads(result)
    log.debug('Successfully unpickled: %s' % obj)
    return obj


class Playback_Successful(object):
    """
    Used to communicate with another PKC Python instance
    """
    listitem = None
