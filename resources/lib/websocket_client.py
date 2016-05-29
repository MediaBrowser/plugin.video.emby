# -*- coding: utf-8 -*-

###############################################################################

import json
import threading
import Queue
import websocket
import ssl

import xbmc

import utils


###############################################################################


@utils.logging
@utils.ThreadMethodsAdditionalSuspend('suspend_LibraryThread')
@utils.ThreadMethods
class WebSocket(threading.Thread):
    opcode_data = (websocket.ABNF.OPCODE_TEXT, websocket.ABNF.OPCODE_BINARY)

    def __init__(self, queue):
        self.ws = None
        # Communication with librarysync
        self.queue = queue
        threading.Thread.__init__(self)

    def process(self, opcode, message):
        if opcode not in self.opcode_data:
            return False

        try:
            message = json.loads(message)
        except Exception as ex:
            self.logMsg('Error decoding message from websocket: %s' % ex, -1)
            self.logMsg(message, -1)
            return False

        # Triage
        typus = message.get('type')
        if typus is None:
            self.logMsg('No message type, dropping message: %s' % message, -1)
            return False
        self.logMsg('Received message from PMS server: %s' % message, 2)
        # Drop everything we're not interested in
        if typus not in ('playing', 'timeline'):
            return True

        # Put PMS message on queue and let libsync take care of it
        try:
            self.queue.put(message)
            return True
        except Queue.Full:
            # Queue only takes 200 messages. No worries if we miss one or two
            self.logMsg('Queue is full, dropping PMS message %s' % message, 0)
            return False

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
        server = utils.window('pms_server')
        # Need to use plex.tv token, if any. NOT user token
        token = utils.window('plex_token')
        # Get the appropriate prefix for the websocket
        if "https" in server:
            server = server.replace('https', "wss")
        else:
            server = server.replace('http', "ws")
        uri = "%s/:/websockets/notifications" % server
        if token:
            uri += '?X-Plex-Token=%s' % token
        sslopt = {}
        if utils.settings('sslverify') == "false":
            sslopt["cert_reqs"] = ssl.CERT_NONE
        return uri, sslopt

    def run(self):
        log = self.logMsg
        log("----===## Starting WebSocketClient ##===----", 0)

        counter = 0
        threadStopped = self.threadStopped
        threadSuspended = self.threadSuspended
        while not threadStopped():
            # In the event the server goes offline
            while threadSuspended():
                # Set in service.py
                if self.ws is not None:
                    try:
                        self.ws.shutdown()
                    except:
                        pass
                    self.ws = None
                if threadStopped():
                    # Abort was requested while waiting. We should exit
                    log("##===---- WebSocketClient Stopped ----===##", 0)
                    return
                xbmc.sleep(1000)
            try:
                self.process(*self.receive(self.ws))
            except websocket.WebSocketTimeoutException:
                # No worries if read timed out
                pass
            except websocket.WebSocketConnectionClosedException:
                log("Connection closed, (re)connecting", 0)
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
                    log("Error connecting", 0)
                    self.ws = None
                    counter += 1
                    if counter > 10:
                        log("Repeatedly could not connect to PMS, declaring "
                            "the connection dead", -1)
                        utils.window('emby_online', value='false')
                        counter = 0
                    xbmc.sleep(1000)
                except websocket.WebSocketTimeoutException:
                    log("timeout while connecting, trying again", 0)
                    self.ws = None
                    xbmc.sleep(1000)
                except Exception as e:
                    log("Unknown exception encountered in connecting: %s" % e)
                    self.ws = None
                    xbmc.sleep(1000)
                else:
                    counter = 0
            except Exception as e:
                log("Unknown exception encountered: %s" % e)
                try:
                    self.ws.shutdown()
                except:
                    pass
                self.ws = None

        log("##===---- WebSocketClient Stopped ----===##", 0)

    def stopThread(self):
        """
        Overwrite this method from ThreadMethods to close websockets
        """
        self.logMsg("Stopping websocket client thread.", 1)
        self._threadStopped = True
        try:
            self.ws.shutdown()
        except:
            pass
