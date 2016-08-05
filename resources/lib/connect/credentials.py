# -*- coding: utf-8 -*-

#################################################################################################

import json
import logging
import os
from datetime import datetime

#################################################################################################

log = logging.getLogger("EMBY."+__name__)

#################################################################################################


class Credentials(object):

    credentials = None
    path = ""
    

    def __init__(self):
        pass

    def setPath(self, path):
        # Path to save persistant data
        self.path = path

    def _ensure(self):
        
        if self.credentials is None:
            try:
                with open(os.path.join(self.path, 'data.txt')) as infile:
                    self.credentials = json.load(infile)
            
            except Exception as e: # File is either empty or missing
                log.warn(e)
                self.credentials = {}
            
            log.info("credentials initialized with: %s" % self.credentials)
            self.credentials['Servers'] = self.credentials.setdefault('Servers', [])

    def _get(self):

        self._ensure()
        return self.credentials

    def _set(self, data):

        if data:
            self.credentials = data
            # Set credentials to file
            with open(os.path.join(self.path, 'data.txt'), 'w') as outfile:
                json.dump(data, outfile, indent=4, ensure_ascii=False)
        else:
            self._clear()

        log.info("credentialsupdated")

    def _clear(self):

        self.credentials = None
        # Remove credentials from file
        with open(os.path.join(self.path, 'data.txt'), 'w'): pass

    def getCredentials(self, data=None):

        if data is not None:
            self._set(data)

        return self._get()

    def addOrUpdateServer(self, list_, server):

        if not server.get('Id'):
            raise KeyError("Server['Id'] cannot be null or empty")

        for existing in list_:
            if existing['Id'] == server['Id']:
                
                # Merge the data
                existing['DateLastAccessed'] = existing.get('DateLastAccessed', "2001-01-01T00:00:00Z")
                if server.get('DateLastAccessed'):
                    if self.dateObject(server['DateLastAccessed']) > self.dateObject(existing['DateLastAccessed']):
                        existing['DateLastAccessed'] = server['DateLastAccessed']

                if server.get('UserLinkType'):
                    existing['UserLinkType'] = server['UserLinkType']

                if server.get('AccessToken'):
                    existing['AccessToken'] = server['AccessToken']
                    existing['UserId'] = server['UserId']

                if server.get('ExchangeToken'):
                    existing['ExchangeToken'] = server['ExchangeToken']

                if server.get('RemoteAddress'):
                    existing['RemoteAddress'] = server['RemoteAddress']

                if server.get('ManualAddress'):
                    existing['ManualAddress'] = server['ManualAddress']

                if server.get('LocalAddress'):
                    existing['LocalAddress'] = server['LocalAddress']

                if server.get('Name'):
                    existing['Name'] = server['Name']

                if server.get('WakeOnLanInfos'):
                    existing['WakeOnLanInfos'] = server['WakeOnLanInfos']

                if server.get('LastConnectionMode') is not None:
                    existing['LastConnectionMode'] = server['LastConnectionMode']

                if server.get('ConnectServerId'):
                    existing['ConnectServerId'] = server['ConnectServerId']

                return existing
        else:
            list_.append(server)
            return server

    def addOrUpdateUser(self, server, user):

        for existing in server.setdefault('Users', []):
            if existing['Id'] == user['Id']:
                # Merge the data
                existing['IsSignedInOffline'] = True
                break
        else:
            server['Users'].append(user)

    def dateObject(self, date):
        # Convert string to date
        date_obj = datetime.strptime(date, "%Y-%m-%dT%H:%M:%SZ")
        return date_obj