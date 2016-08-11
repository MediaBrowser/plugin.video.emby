# PlexKodiConnect (PKC)
**Combine the best frontend media player Kodi with the best multimedia backend server Plex**

PKC combines the best of Kodi - ultra smooth navigation, beautiful and highly customizable user interfaces and playback of any file under the sun, and the Plex Media Server to manage all your media without lifting a finger.

Have a look at [some screenshots](https://github.com/croneter/PlexKodiConnect/wiki/Some-PKC-Screenshots) to see what's possible. 

### Download and Installation
[ ![Download](https://api.bintray.com/packages/croneter/PlexKodiConnect/PlexKodiConnect/images/download.svg) ](https://dl.bintray.com/croneter/PlexKodiConnect/bin/repository.plexkodiconnect/repository.plexkodiconnect-1.0.0.zip)

The easiest way to install PKC is via our PlexKodiConnect Kodi repository (we cannot use the official Kodi repository as PKC messes with Kodi's databases). See the [installation guideline on how to do this](https://github.com/croneter/PlexKodiConnect/wiki/Installation).

#Danger Zone#
If you feel lucky, use the beta repository to download the PKC Beta version. Before new updates are released for the general public, they're first tested here. Uninstall the "normal" PKC first!
BETA VERSION: [ ![Download](https://api.bintray.com/packages/croneter/PlexKodiConnect_BETA/PlexKodiConnect_BETA/images/download.svg) ](https://dl.bintray.com/croneter/PlexKodiConnect_BETA/bin-BETA/repository.plexkodiconnect/:repository.plexkodiconnect-1.0.0.zip)

### Donations
I'm not in any way affiliated with Plex. Thank you very much for a small donation via ko-fi.com and PayPal if you appreciate PKC.  
**Full disclaimer:** I will see your name and address on my PayPal account. Rest assured that I will not share this with anyone. 

[ ![Download](https://az743702.vo.msecnd.net/cdn/kofi1.png?v=a|alt=Buy Me a Coffee)](https://ko-fi.com/A8182EB)

### IMPORTANT NOTES

1. If your are using a **low CPU device like a raspberry pi or a CuBox**, PKC might be instable or crash during initial sync. Lower the number of threads in the [PKC settings under Sync Options](https://github.com/croneter/PlexKodiConnect/wiki/PKC-settings#sync-options): `Limit artwork cache threads: 5`
Don't forget to reboot Kodi after that.
2. If you post logs, your **Plex tokens** might be included. Be sure to double and tripple check for tokens before posting any logs anywhere by searching for `token`
3. **Compatibility**: PKC is currently not compatible with Kodi's Video Extras plugin. **Deactivate Video Extras** if trailers/movies start randomly playing. 


### Checkout the PKC Wiki
The [Wiki can be found here](https://github.com/croneter/PlexKodiConnect/wiki) and will hopefully answer all your questions.


### What does PKC do?

With other addons for Kodi there are a couple of issues:
- 3rd party addons such as NextAired, remote apps etc. won't work
- Slow speed: when browsing the data has to be retrieved from the server. Especially on slower devices this can take too much time
- You can only use special Kodi skins
- All kinds of workarounds are needed to get the best experience on Kodi clients

PKC synchronizes your media from your Plex server to the native Kodi database. Because PKC uses the native Kodi database, the above limitations are gone! 
- You can browse your media full speed, images are cached
- All other Kodi addons will be able to "see" your media, thinking it's normal Kodi stuff
- Use any Kodi skin you want!


### What is currently supported?

PKC currently provides the following features:
- All Plex library types
    + Movies and Home Videos
    + TV Shows
    + Music
    + Pictures and Photos
- Different PKC interface languages:
    + English
    + German
    + More coming up
- [Plex Watch Later / Plex It!](https://support.plex.tv/hc/en-us/sections/200211783-Plex-It-)
- [Plex Companion](https://support.plex.tv/hc/en-us/sections/200276908-Plex-Companion): fling Plex media (or anything else) from other Plex devices to PlexKodiConnect
- [Plex Transcoding](https://support.plex.tv/hc/en-us/articles/200250377-Transcoding-Media)
- Automatically download more artwork from [Fanart.tv](https://fanart.tv/), just like the Kodi addon [Artwork Downloader](http://kodi.wiki/view/Add-on:Artwork_Downloader)
    + Banners
    + Disc art
    + Clear logos
    + Landscapes
    + Clear art
    + Extra fanart backgrounds
- Automatically group movies into [movie sets](http://kodi.wiki/view/movie_sets)
- Direct play from network paths (e.g. "\\\\server\\Plex\\movie.mkv") instead of streaming from slow HTTP (e.g. "192.168.1.1:32400"). You have to setup all your Plex libraries to point to such network paths. Do have a look at [the wiki here](https://github.com/croneter/PlexKodiConnect/wiki/Direct-Paths)


### Known Larger Issues

Solutions are unlikely due to the nature of these issues
- *Plex Music when using Addon paths instead of Native Direct Paths:* Kodi tries to scan every(!) single Plex song on startup. This leads to errors in the Kodi log file and potentially even crashes. See the [Github issue](https://github.com/croneter/PlexKodiConnect/issues/14) for more details
- *Plex Music when using Addon paths instead of Native Direct Paths:* You must have a static IP address for your Plex media server if you plan to use Plex Music features
- If something on the PMS has changed, this change is synced to Kodi. Hence if you rescan your entire library, a long PlexKodiConnect re-sync is triggered. You can [change your PMS settings to avoid that](https://github.com/croneter/PlexKodiConnect/wiki/Configure-PKC-on-the-First-Run#deactivate-frequent-updates)
- External Plex subtitles (in separate files, e.g. mymovie.srt) can be used, but it is impossible to label them correctly and tell what language they are in. However, this is not the case if you use direct paths

*Background Sync:*
The Plex Server does not tell anyone of the following changes. Hence PKC cannot detect these changes instantly but will notice them only on full/delta syncs (standard settings is every 60 minutes)
- Toggle the viewstate of an item to (un)watched outside of Kodi
- Changing details of an item, e.g. replacing a poster  

However, some changes to individual items are instantly detected, e.g. if you match a yet unrecognized movie. 


### Issues being worked on

Have a look at the [Github Issues Page](https://github.com/croneter/PlexKodiConnect/issues).


### What could be in the pipeline for future development?

- Playlists
- Music Videos
- Deleting PMS items from Kodi
- TV Shows Theme Music (ultra-low prio)


### Important note about MySQL database in Kodi

The addon is not (and will not be) compatible with the MySQL database replacement in Kodi. In fact, PlexKodiConnect takes over the point of having a MySQL database because it acts as a "man in the middle" for your entire media library.


### Credits

- PlexKodiConnect shamelessly uses pretty much all the code of "Emby for Kodi" by the awesome Emby team (see https://github.com/MediaBrowser/plugin.video.emby). Thanks for sharing guys!!
- Plex Companion ("PlexBMC Helper") and other stuff was adapted from @Hippojay 's great work (see https://github.com/hippojay).
- The foundation of the Plex API is all iBaa's work (https://github.com/iBaa/PlexConnect).
