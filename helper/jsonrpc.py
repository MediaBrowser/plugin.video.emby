# -*- coding: utf-8 -*-
import json

import xbmc
class JSONRPC():
    def __init__(self, method, **kwargs):
        self.method = method
        self.params = False

        for arg in kwargs:
            self.arg = kwargs[arg]

    def _query(self):
        query = {
            'jsonrpc': "2.0",
            'id': 1,
            'method': self.method,
        }

        if self.params:
            query['params'] = self.params

        return json.dumps(query)

    def execute(self, params):
        self.params = params
        return json.loads(xbmc.executeJSONRPC(self._query()))
