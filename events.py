# -*- coding: utf-8 -*-
import sys
import socket
import xbmc

if int(xbmc.getInfoLabel('System.BuildVersion')[:2]) >= 19:
    from urllib.parse import parse_qsl
else:
    from urlparse import parse_qsl


def EmbyQueryData(Method, Data, server_id, handle):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    request = "%s;%s;%s;%s" % (Method, Data, server_id, handle)

    for _ in range(10):
        try:
            sock.connect(('127.0.0.1', 60001))
            sock.send(request.encode('utf-8'))
            sock.recv(16)
            break
        except:
            if xbmc.Monitor().waitForAbort(5):
                return


if __name__ == "__main__":
    Handle = sys.argv[1]
    params = dict(parse_qsl(sys.argv[2][1:]))
    mode = params.get('mode')
    ServerId = params.get('server')

    if mode == 'photoviewer':
        xbmc.executebuiltin('ShowPicture(http://127.0.0.1:57578/embyimage-%s-%s-0-Primary-%s)' % (ServerId, params['id'], params['imageid']))
    elif mode == 'nextepisodes':
        EmbyQueryData('nextepisodes', params.get('libraryname', ""), ServerId, Handle)
    elif mode == 'browse':
        EmbyQueryData('browse', "%s;%s;%s;%s;%s" % (params.get('type', ""), params.get('id', ""), params.get('folder', ""), params.get('name', ""), params.get('extra', "")), ServerId, Handle)
    elif mode in ('texturecache', 'delete', 'managelibsselection', 'favepisodes', 'settings', 'databasereset'):
        EmbyQueryData(mode, "", ServerId, Handle)
    else:
        EmbyQueryData('listing', "", ServerId, Handle)
