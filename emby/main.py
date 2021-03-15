import logging
from . import client

LOG = logging.getLogger('EMBY')

def has_attribute(obj, name):
    try:
        object.__getattribute__(obj, name)
        return True
    except AttributeError:
        return False

def ensure_client():
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            if self.client.get(self.server_id) is None:
                self.construct()

            return func(self, *args, **kwargs)

        return wrapper
    return decorator

class Emby():
    client = {}
    server_id = "default"

    def __init__(self, server_id=None):
        self.server_id = server_id or "default"

    def get_client(self):
        return self.client[self.server_id]

    def close(self):
        if self.server_id not in self.client:
            return

        self.client[self.server_id].stop()
        self.client.pop(self.server_id, None)
        LOG.info("---[ STOPPED EMBYCLIENT: %s ]---", self.server_id)

    @classmethod
    def close_all(cls):
        for clientData in dict(cls.client):
            cls.client[clientData].stop()

        cls.client = {}
        LOG.info("---[ STOPPED ALL EMBYCLIENTS ]---")

    @classmethod
    def get_active_clients(cls):
        return cls.client

    @ensure_client()
    def __setattr__(self, name, value):
        if has_attribute(self, name):
            return super(Emby, self).__setattr__(name, value)

        setattr(self.client[self.server_id], name, value)

    @ensure_client()
    def __getattr__(self, name):
        return getattr(self.client[self.server_id], name)

    @ensure_client()
    def __getitem__(self, key):
        return self.client[self.server_id][key]

    def construct(self):
        self.client[self.server_id] = client.EmbyClient()

        if self.server_id == 'default':
            LOG.info("---[ START EMBYCLIENT ]---")
        else:
            LOG.info("---[ START EMBYCLIENT: %s ]---", self.server_id)
