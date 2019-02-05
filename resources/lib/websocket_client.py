#!/usr/bin/env python
# -*- coding: utf-8 -*-
from logging import getLogger
from json import loads
from ssl import CERT_NONE

from . import backgroundthread, websocket, utils, companion, app, variables as v

###############################################################################

LOG = getLogger('PLEX.websocket_client')

###############################################################################


class WebSocket(backgroundthread.KillableThread):
    opcode_data = (websocket.ABNF.OPCODE_TEXT, websocket.ABNF.OPCODE_BINARY)

    def __init__(self):
        self.ws = None
        self.redirect_uri = None
        super(WebSocket, self).__init__()

    def process(self, opcode, message):
        raise NotImplementedError

    def receive(self, ws):
        # Not connected yet
        if ws is None:
            raise websocket.WebSocketConnectionClosedException

        frame = ws.recv_frame()

        if not frame:
            raise websocket.WebSocketException("Not a valid frame %s" % frame)
        elif frame.opcode in self.opcode_data:
            return frame.opcode, frame.data
        elif frame.opcode == websocket.ABNF.OPCODE_CLOSE:
            ws.send_close()
            return frame.opcode, None
        elif frame.opcode == websocket.ABNF.OPCODE_PING:
            ws.pong("Hi!")
        return None, None

    def getUri(self):
        raise NotImplementedError

    def run(self):
        LOG.info("----===## Starting %s ##===----", self.__class__.__name__)
        counter = 0
        while not self.isCanceled():
            # In the event the server goes offline
            while self.isSuspended():
                # Set in service.py
                if self.ws is not None:
                    self.ws.close()
                    self.ws = None
                if self.isCanceled():
                    # Abort was requested while waiting. We should exit
                    LOG.info("##===---- %s Stopped ----===##",
                             self.__class__.__name__)
                    return
                app.APP.monitor.waitForAbort(1)
            try:
                self.process(*self.receive(self.ws))
            except websocket.WebSocketTimeoutException:
                # No worries if read timed out
                pass
            except websocket.WebSocketConnectionClosedException:
                LOG.info("%s: connection closed, (re)connecting",
                         self.__class__.__name__)
                uri, sslopt = self.getUri()
                try:
                    # Low timeout - let's us shut this thread down!
                    self.ws = websocket.create_connection(
                        uri,
                        timeout=1,
                        sslopt=sslopt,
                        enable_multithread=True)
                except IOError:
                    # Server is probably offline
                    LOG.info("%s: Error connecting", self.__class__.__name__)
                    self.ws = None
                    counter += 1
                    if counter >= 10:
                        LOG.info('%s: Repeated IOError detected. Stopping now',
                                 self.__class__.__name__)
                        break
                    app.APP.monitor.waitForAbort(1)
                except websocket.WebSocketTimeoutException:
                    LOG.info("%s: Timeout while connecting, trying again",
                             self.__class__.__name__)
                    self.ws = None
                    app.APP.monitor.waitForAbort(1)
                except websocket.WebsocketRedirect as e:
                    LOG.info('301 redirect detected')
                    self.redirect_uri = e.headers.get('location', e.headers.get('Location'))
                    if self.redirect_uri:
                        self.redirect_uri.decode('utf-8')
                    counter += 1
                    if counter >= 10:
                        LOG.info('%s: Repeated WebsocketRedirect detected. Stopping now',
                                 self.__class__.__name__)
                        break
                except websocket.WebSocketException as e:
                    LOG.info('%s: WebSocketException: %s',
                             self.__class__.__name__, e)
                    if ('Handshake Status 401' in e.args or
                            'Handshake Status 403' in e.args):
                        counter += 1
                        if counter >= 5:
                            LOG.info('%s: Error in handshake detected. '
                                     'Stopping now', self.__class__.__name__)
                            break
                    self.ws = None
                    app.APP.monitor.waitForAbort(1)
                except Exception as e:
                    LOG.error('%s: Unknown exception encountered when '
                              'connecting: %s', self.__class__.__name__, e)
                    import traceback
                    LOG.error("%s: Traceback:\n%s",
                              self.__class__.__name__, traceback.format_exc())
                    self.ws = None
                    app.APP.monitor.waitForAbort(1)
                else:
                    counter = 0
            except Exception as e:
                LOG.error("%s: Unknown exception encountered: %s",
                          self.__class__.__name__, e)
                import traceback
                LOG.error("%s: Traceback:\n%s",
                          self.__class__.__name__, traceback.format_exc())
                if self.ws is not None:
                    self.ws.close()
                self.ws = None
        # Close websocket connection on shutdown
        if self.ws is not None:
            self.ws.close()
        LOG.info("##===---- %s Stopped ----===##", self.__class__.__name__)


class PMS_Websocket(WebSocket):
    """
    Websocket connection with the PMS for Plex Companion
    """
    def isSuspended(self):
        """
        Returns True if the thread is suspended
        """
        return (self._suspended or
                app.APP.suspend_threads or
                app.SYNC.background_sync_disabled)

    def getUri(self):
        if self.redirect_uri:
            uri = self.redirect_uri
            self.redirect_uri = None
        else:
            server = app.CONN.server
            # Get the appropriate prefix for the websocket
            if server.startswith('https'):
                server = "wss%s" % server[5:]
            else:
                server = "ws%s" % server[4:]
            uri = "%s/:/websockets/notifications" % server
            # Need to use plex.tv token, if any. NOT user token
            if app.ACCOUNT.plex_token:
                uri += '?X-Plex-Token=%s' % app.ACCOUNT.plex_token
        sslopt = {}
        if utils.settings('sslverify') == "false":
            sslopt["cert_reqs"] = CERT_NONE
        LOG.debug("%s: Uri: %s, sslopt: %s",
                  self.__class__.__name__, uri, sslopt)
        return uri, sslopt

    def process(self, opcode, message):
        if opcode not in self.opcode_data:
            return

        try:
            message = loads(message)
        except ValueError:
            LOG.error('%s: Error decoding message from websocket',
                      self.__class__.__name__)
            LOG.error(message)
            return
        try:
            message = message['NotificationContainer']
        except KeyError:
            LOG.error('%s: Could not parse PMS message: %s',
                      self.__class__.__name__, message)
            return
        # Triage
        typus = message.get('type')
        if typus is None:
            LOG.error('%s: No message type, dropping message: %s',
                      self.__class__.__name__, message)
            return
        LOG.debug('%s: Received message from PMS server: %s',
                  self.__class__.__name__, message)
        # Drop everything we're not interested in
        if typus not in ('playing', 'timeline', 'activity'):
            return
        elif typus == 'activity' and app.SYNC.db_scan is True:
            # Only add to processing if PKC is NOT doing a lib scan (and thus
            # possibly causing these reprocessing messages en mass)
            LOG.debug('%s: Dropping message as PKC is currently synching',
                      self.__class__.__name__)
        else:
            # Put PMS message on queue and let libsync take care of it
            app.APP.websocket_queue.put(message)


class Alexa_Websocket(WebSocket):
    """
    Websocket connection to talk to Amazon Alexa.
    """
    def isSuspended(self):
        """
        Overwrite method since we need to check for plex token
        """
        return (self._suspended or
                not app.ACCOUNT.plex_token or
                app.ACCOUNT.restricted_user)

    def getUri(self):
        if self.redirect_uri:
            uri = self.redirect_uri
            self.redirect_uri = None
        else:
            uri = ('wss://pubsub.plex.tv/sub/websockets/%s/%s?X-Plex-Token=%s'
                   % (app.ACCOUNT.plex_user_id,
                      v.PKC_MACHINE_IDENTIFIER,
                      app.ACCOUNT.plex_token))
        sslopt = {}
        LOG.debug("%s: Uri: %s, sslopt: %s",
                  self.__class__.__name__, uri, sslopt)
        return uri, sslopt

    def process(self, opcode, message):
        if opcode not in self.opcode_data:
            return
        LOG.debug('%s: Received the following message from Alexa:',
                  self.__class__.__name__)
        LOG.debug('%s: %s', self.__class__.__name__, message)
        try:
            message = utils.defused_etree.fromstring(message)
        except Exception as ex:
            LOG.error('%s: Error decoding message from Alexa: %s',
                      self.__class__.__name__, ex)
            return
        try:
            if message.attrib['command'] == 'processRemoteControlCommand':
                message = message[0]
            else:
                LOG.error('%s: Unknown Alexa message received',
                          self.__class__.__name__)
                return
        except Exception:
            LOG.error('%s: Could not parse Alexa message',
                      self.__class__.__name__)
            return
        companion.process_command(message.attrib['path'][1:], message.attrib)
