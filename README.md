### Download the Kodi Repository
[ ![Download](https://api.bintray.com/packages/croneter/PlexKodiConnect/PlexKodiConnect/images/download.svg) ](https://dl.bintray.com/croneter/PlexKodiConnect/bin/repository.plexkodiconnect/repository.plexkodiconnect-1.0.0.zip)

The easiest way to install PlexKodiConnect (PKC) is via its dedicated PKC Kodi repository (we cannot use the official Kodi repository as PKC messes with Kodi's databases). See the [installation guideline](https://github.com/croneter/PlexKodiConnect/wiki/Installation).

### Donations
I'm not in any way affiliated with Plex. Thank you very much for your small donation via ko-fi.com and PayPal if you appreciate PlexKodiConnect. 

###IMPORTANT###

1. If your are using a **low CPU device like a raspberry pi or a CuBox**, PKC might be instable or crash during initial sync. Lower the number of threads in the [PKC settings under Sync Options](https://github.com/croneter/PlexKodiConnect/wiki/PKC-settings#sync-options):
    - Limit artwork cache threads: 5
    - Limit download sync threads: 1  
Don't forget to reboot Kodi
2. If you post logs, your **Plex tokens** might be included. Be sure to double and tripple check for tokens before posting any logs anywhere by searching for `token`
3. **Compatibility**: PKC is currently not compatible with Kodi's Video Extras plugin. **Deactivate Video Extras** if trailers/movies start randomly playing. 


### [Checkout the Wiki](https://github.com/croneter/PlexKodiConnect/wiki)
[The Wiki will hopefully answer all your questions](https://github.com/croneter/PlexKodiConnect/wiki)

### [Please Post Your Bugs on Github](https://github.com/croneter/PlexKodiConnect/issues)
And not on the plex.tv forums. I can't find anything there...

### Welcome to PlexKodiConnect
**Connect your Plex Media Server to a Kodi Front End**  

PlexKodiConnect combines the best of Kodi - ultra smooth navigation, beautiful UIs and playback of any file under the sun, and Plex to manage all your media without lifting a finger.


**What does it do?**

With other addons for Kodi there are a couple of issues:
- 3rd party addons such as NextAired, remote apps etc. won't work
- Slow speed: when browsing the data has to be retrieved from the server. Especially on slower devices this can take too much time.
- You can only use special Kodi skins
- All kinds of workarounds are needed to get the best experience on Kodi clients

This addon synchronizes your media on your Plex server to the native Kodi database. Because we use the native Kodi database with this new approach the above limitations are gone! 
- You can browse your media full speed, images are cached
- All other Kodi addons will be able to "see" your media, thinking it's normal Kodi stuff
- Use any Kodi skin you want!


**Installation in Kodi**

Check out the [Wiki for installation instructions](https://github.com/croneter/PlexKodiConnect/wiki)


**What is currently supported?**

Currently these features are working:
- Movies and Home Videos
- TV Shows
- Music
- [Plex Watch Later / Plex It!](https://support.plex.tv/hc/en-us/sections/200211783-Plex-It-)
- Full sync at first run, then periodic delta syncs every 60min (customizable)
- Instant watched state/resume status sync: This is a 2-way synchronisation. Any watched state or resume status will be instantly (within seconds) reflected to or from Kodi and the server
- [Plex Companion](https://support.plex.tv/hc/en-us/sections/200276908-Plex-Companion): fling Plex media (or anything else) from other Plex devices to PlexKodiConnect
- Automatically download more artwork from [Fanart.tv](https://fanart.tv/), just like the Kodi addon Artwork Downloader
    + Banners
    + Disc art
    + Clear logos
    + Landscapes
    + Clear art
    + Extra fanart backgrounds
- Play directly from network paths (e.g. "\\\\server\\Plex\\movie.mkv" or "smb://server/Plex/movie.mkv") instead of slow HTTP (e.g. "192.168.1.1:32400"). You have to setup all your Plex libraries to point to such network paths. Do have a look at [the wiki here](https://github.com/croneter/PlexKodiConnect/wiki/Direct-Paths)
- [Plex Transcoding](https://support.plex.tv/hc/en-us/articles/200250377-Transcoding-Media)


**Known Issues:**

Solutions are unlikely due to the nature of these issues
- *Plex Music when using Addon paths instead of Native Direct Paths:* Kodi tries to scan every(!) single Plex song on startup. This leads to errors in the Kodi log file and potentially even crashes. See the [Github issue](https://github.com/croneter/PlexKodiConnect/issues/14) for more details
- *Plex Music when using Addon paths instead of Native Direct Paths:* You must have a static IP address for your Plex media server if you plan to use Plex Music features
- If something on the PMS has changed, this change is synced to Kodi. Hence if you rescan your entire library, a long PlexKodiConnect re-sync is triggered
- External Plex subtitles (in separate files, e.g. mymovie.srt) can be used, but it is impossible to label them correctly and tell what language they are in. However, this is not the case if you use direct paths

*Background Sync:*
The Plex Server does not tell anyone of the following changes. Hence PKC cannot detect these changes instantly but will notice them only on full/delta syncs
- Toggle the viewstate of an item to (un)watched outside of Kodi
- Changing details of an item, e.g. replacing a poster  

However, some changes to individual items are instantly detected, e.g. if you match a yet unrecognized movie. 


**Known Bugs:**
- Have a look at the [Github Issues Page](https://github.com/croneter/PlexKodiConnect/issues)


**What could be in the pipeline for future development?**
- Playlists
- Pictures
- Music Videos
- Automatic updates
- Simultaneously connecting to several PMS
- TV Shows Theme Music (ultra-low prio)


**Important note about MySQL database in kodi**

The addon is not (and will not be) compatible with the MySQL database replacement in Kodi. In fact, PlexKodiConnect takes over the point of having a MySQL database because it acts as a "man in the middle" for your entire media library.

**Important note about user collections/nodes**

Plex has the ability to create custom libraries for your Media, such as having a separate folder for your "Kids Movies" etc. In Kodi this isn't supported, you just have "movies" or "tvshows". But... Kodi let's you create your own playlists and tags to get this same experience. During the sync the foldernode from the Plex server is added to the movies that are imported. In Kodi you can browse to Movie library --> tags and you will have a filtered result that points at your custom node. If you have a skin that let's you create any kind of shortcut on the homescreen you can simply create a shortcut to that tag. Another possibility is to create a "smart playlist" with Kodi and set it to show the content of a certain tag. 

**Credits**
- PlexKodiConnect shamelessly uses pretty much all the code of "Emby for Kodi" by the awesome Emby team (see https://github.com/MediaBrowser/plugin.video.emby). Thanks for sharing guys!!
- Plex Companion ("PlexBMC Helper") and other stuff was adapted from @Hippojay 's great work (see https://github.com/hippojay).
- The foundation of the Plex API is all iBaa's work (https://github.com/iBaa/PlexConnect).