# -*- coding: utf-8 -*-
import json
import xbmc

if __name__ == "__main__":
    data = {}
    data = '"[%s]"' % json.dumps(data).replace('"', '\\"')
    xbmc.executebuiltin('NotifyAll(plugin.video.emby-next-gen, %s, %s)' % ("context", data))
