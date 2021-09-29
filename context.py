# -*- coding: utf-8 -*-
import xbmc

if __name__ == "__main__":
    if xbmc.getCondVisibility('System.HasAddon(plugin.video.emby-next-gen)'):
        xbmc.executebuiltin('NotifyAll(plugin.video.emby-next-gen,context)')
    else:
        xbmc.executebuiltin('NotifyAll(plugin.video.emby,context)')
