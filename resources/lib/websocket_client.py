# -*- coding: utf-8 -*-

###############################################################################
import logging
import websocket
from json import loads
import xml.etree.ElementTree as etree
from threading import Thread
from Queue import Queue
from ssl import CERT_NONE

from xbmc import sleep

from utils import window, settings, thread_methods
from companion import process_command
import state

###############################################################################

log = logging.getLogger("PLEX."+__name__)

###############################################################################


@thread_methods(add_suspends=['SUSPEND_LIBRARY_THREAD'])
class WebSocket(Thread):
    opcode_data = (websocket.ABNF.OPCODE_TEXT, websocket.ABNF.OPCODE_BINARY)

    def __init__(self, callback=None):
        if callback is not None:
            self.mgr = callback
        self.ws = None
        Thread.__init__(self)

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
        log.info("----===## Starting %s ##===----" % self.__class__.__name__)

        counter = 0
        handshake_counter = 0
        thread_stopped = self.thread_stopped
        thread_suspended = self.thread_suspended
        while not thread_stopped():
            # In the event the server goes offline
            while thread_suspended():
                # Set in service.py
                if self.ws is not None:
                    try:
                        self.ws.shutdown()
                    except:
                        pass
                    self.ws = None
                if thread_stopped():
                    # Abort was requested while waiting. We should exit
                    log.info("##===---- %s Stopped ----===##"
                             % self.__class__.__name__)
                    return
                sleep(1000)
            try:
                self.process(*self.receive(self.ws))
            except websocket.WebSocketTimeoutException:
                # No worries if read timed out
                pass
            except websocket.WebSocketConnectionClosedException:
                log.info("Connection closed, (re)connecting")
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
                    log.info("Error connecting")
                    self.ws = None
                    counter += 1
                    if counter > 3:
                        counter = 0
                        self.IOError_response()
                    sleep(1000)
                except websocket.WebSocketTimeoutException:
                    log.info("timeout while connecting, trying again")
                    self.ws = None
                    sleep(1000)
                except websocket.WebSocketException as e:
                    log.info('WebSocketException: %s' % e)
                    if 'Handshake Status 401' in e.args:
                        handshake_counter += 1
                        if handshake_counter >= 5:
                            log.info('Error in handshake detected. Stopping '
                                     '%s now' % self.__class__.__name__)
                            break
                    self.ws = None
                    sleep(1000)
                except Exception as e:
                    log.error("Unknown exception encountered in connecting: %s"
                              % e)
                    import traceback
                    log.error("Traceback:\n%s" % traceback.format_exc())
                    self.ws = None
                    sleep(1000)
                else:
                    counter = 0
                    handshake_counter = 0
            except Exception as e:
                log.error("Unknown exception encountered: %s" % e)
                import traceback
                log.error("Traceback:\n%s" % traceback.format_exc())
                try:
                    self.ws.shutdown()
                except:
                    pass
                self.ws = None
        log.info("##===---- %s Stopped ----===##" % self.__class__.__name__)

    def stopThread(self):
        """
        Overwrite this method from thread_methods to close websockets
        """
        log.info("Stopping %s thread." % self.__class__.__name__)
        self.__threadStopped = True
        try:
            self.ws.shutdown()
        except:
            pass


class PMS_Websocket(WebSocket):
    """
    Websocket connection with the PMS for Plex Companion
    """
    # Communication with librarysync
    queue = Queue()

    def getUri(self):
        server = window('pms_server')
        # Get the appropriate prefix for the websocket
        if server.startswith('https'):
            server = "wss%s" % server[5:]
        else:
            server = "ws%s" % server[4:]
        uri = "%s/:/websockets/notifications" % server
        # Need to use plex.tv token, if any. NOT user token
        if state.PLEX_TOKEN:
            uri += '?X-Plex-Token=%s' % state.PLEX_TOKEN
        sslopt = {}
        if settings('sslverify') == "false":
            sslopt["cert_reqs"] = CERT_NONE
        log.debug("Uri: %s, sslopt: %s" % (uri, sslopt))
        return uri, sslopt

    def process(self, opcode, message):
        if opcode not in self.opcode_data:
            return False

        try:
            message = loads(message)
        except Exception as ex:
            log.error('Error decoding message from websocket: %s' % ex)
            log.error(message)
            return False
        try:
            message = message['NotificationContainer']
        except KeyError:
            log.error('Could not parse PMS message: %s' % message)
            return False
        # Triage
        typus = message.get('type')
        if typus is None:
            log.error('No message type, dropping message: %s' % message)
            return False
        log.debug('Received message from PMS server: %s' % message)
        # Drop everything we're not interested in
        if typus not in ('playing', 'timeline'):
            return True

        # Put PMS message on queue and let libsync take care of it
        self.queue.put(message)
        return True

    def IOError_response(self):
        log.warn("Repeatedly could not connect to PMS, "
                 "declaring the connection dead")
        window('plex_online', value='false')


class Alexa_Websocket(WebSocket):
    """
    Websocket connection to talk to Amazon Alexa
    """
    def getUri(self):
        self.plex_client_Id = window('plex_client_Id')
        uri = ('wss://pubsub.plex.tv/sub/websockets/%s/%s?X-Plex-Token=%s'
               % (window('currUserId'), self.plex_client_Id, state.PLEX_TOKEN))
        sslopt = {}
        log.debug("Uri: %s, sslopt: %s" % (uri, sslopt))
        return uri, sslopt

    def process(self, opcode, message):
        if opcode not in self.opcode_data:
            return False
        log.debug('Received the following message from Alexa:')
        log.debug(message)
        try:
            message = etree.fromstring(message)
        except Exception as ex:
            log.error('Error decoding message from Alexa: %s' % ex)
            return False
        try:
            if message.attrib['command'] == 'processRemoteControlCommand':
                message = message[0]
            else:
                log.error('Unknown Alexa message received')
                return False
        except:
            log.error('Could not parse Alexa message')
            return False
        process_command(message.attrib['path'][1:],
                        message.attrib,
                        queue=self.mgr.plexCompanion.queue)
        return True

    def IOError_response(self):
        pass

    def thread_suspended(self):
        """
        Overwrite method since we need to check for plex token
        """
        if self.__thread_suspended is True:
            return True
        if not state.PLEX_TOKEN:
            return True
        if state.RESTRICTED_USER:
            return True
        return False
