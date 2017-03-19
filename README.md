## Status

[![GitHub issues](https://img.shields.io/github/issues/croneter/PlexKodiConnect.svg?maxAge=60&style=flat-square)](https://github.com/croneter/PlexKodiConnect/issues)
[![GitHub pull requests](https://img.shields.io/github/issues-pr/croneter/PlexKodiConnect.svg?maxAge=60&style=flat-square)](https://github.com/croneter/PlexKodiConnect/pulls)


# PlexKodiConnect (PKC)
**Combine the best frontend media player Kodi with the best multimedia backend server Plex**

PKC combines the best of Kodi - ultra smooth navigation, beautiful and highly customizable user interfaces and playback of any file under the sun - and the Plex Media Server.

Have a look at [some screenshots](https://github.com/croneter/PlexKodiConnect/wiki/Some-PKC-Screenshots) to see what's possible. 

### Help Translate!

Please help translate PlexKodiConnect into your language: [crowdin.com](https://crowdin.com/project/plexkodiconnect/invite)


### Content
* [**Warning**](#warning)
* [**What does PKC do?**](#what-does-pkc-do)
* [**PKC Features**](#pkc-features)
* [**PKC Wiki & Frequently Asked Questions**](#pkc-wiki--frequently-asked-questions)
* [**Download and Installation**](#download-and-installation)
* [**Important notes**](#important-notes)
* [**Donations**](#donations)
* [**Request a New Feature**](#request-a-new-feature)
* [**Known Larger Issues**](#known-larger-issues)
* [**Issues being worked on**](#issues-being-worked-on)
* [**Credits**](#credits)

### Warning
Use at your own risk! This plugin assumes that you manage all your videos with Plex (and none with Kodi). You might lose data already stored in the Kodi video and music databases as this plugin directly changes them. Don't worry if you want Plex to manage all your media (like you should ;-)). 

### What does PKC do?
PKC synchronizes your media from your Plex server to the native Kodi database. Hence:
- Use virtually any other Kodi add-on
- Use any Kodi skin, completely customize Kodi's look
- Browse your media at full speed (cached artwork)
- Automatically get additional artwork (more than e.g. Plex offers)
- Enjoy Plex features using the Kodi interface

Some people argue that PKC is 'hacky' because of the way it directly accesses the Kodi database. See [here for a more thorough discussion](https://github.com/croneter/PlexKodiConnect/wiki/Is-PKC-'hacky'%3F). 

### PKC Features

- [Amazon Alexa voice recognition](https://www.plex.tv/apps/streaming-devices/amazon-alexa)
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
- PKC interface languages:
    + English
    + German
    + Czech, thanks @Pavuucek
    + Spanish, thanks @bartolomesoriano
    + Danish, thanks @FIGHT
    + Italian, thanks @nikkux, @chicco83
    + More coming up: [you can help!](https://crowdin.com/project/plexkodiconnect/invite)
- Automatically group movies into [movie sets](http://kodi.wiki/view/movie_sets)
- Direct play from network paths (e.g. "\\\\server\\Plex\\movie.mkv") instead of streaming from slow HTTP (e.g. "192.168.1.1:32400"). You have to setup all your Plex libraries to point to such network paths. Do have a look at [the wiki here](https://github.com/croneter/PlexKodiConnect/wiki/Direct-Paths)
- Delete PMS items from the Kodi context menu

### PKC Wiki & Frequently Asked Questions
The [Wiki can be found here](https://github.com/croneter/PlexKodiConnect/wiki) and will hopefully answer all your questions. You can even edit the wiki yourself!

### Download and Installation
[ ![Download](https://api.bintray.com/packages/croneter/PlexKodiConnect/PlexKodiConnect/images/download.svg) ](https://dl.bintray.com/croneter/PlexKodiConnect/bin/repository.plexkodiconnect/repository.plexkodiconnect-1.0.0.zip)

Install PKC via the PlexKodiConnect Kodi repository (we cannot use the official Kodi repository as PKC messes with Kodi's databases). See the [installation guideline on how to do this](https://github.com/croneter/PlexKodiConnect/wiki/Installation).

**Possibly UNSTABLE BETA version:** [ ![Download](https://api.bintray.com/packages/croneter/PlexKodiConnect_BETA/images/download.svg) ](https://dl.bintray.com/croneter/PlexKodiConnect_BETA/bin-BETA/repository.plexkodiconnectbeta/repository.plexkodiconnectbeta-1.0.0.zip)

### Important Notes

1. If you are using a **low CPU device like a Raspberry Pi or a CuBox**, PKC might be instable or crash during initial sync. Lower the number of threads in the [PKC settings under Sync Options](https://github.com/croneter/PlexKodiConnect/wiki/PKC-settings#sync-options). Don't forget to reboot Kodi after that.
2. **Compatibility**: 
    * PKC is currently not compatible with Kodi's Video Extras plugin. **Deactivate Video Extras** if trailers/movies start randomly playing. 
    * PKC is not (and will never be) compatible with the **MySQL database replacement** in Kodi. In fact, PKC replaces the MySQL functionality because it acts as a "man in the middle" for your entire media library.
    * If **another plugin is not working** like it's supposed to, try to use [PKC direct paths](https://github.com/croneter/PlexKodiConnect/wiki/Direct-Paths)

### Donations
I'm not in any way affiliated with Plex. Thank you very much for a small donation via ko-fi.com and PayPal if you appreciate PKC.  
**Full disclaimer:** I will see your name and address on my PayPal account. Rest assured that I will not share this with anyone. 

[![Donations](https://az743702.vo.msecnd.net/cdn/kofi1.png?v=a)](https://ko-fi.com/A8182EB)

### Request a New Feature

[![Feature Requests](http://feathub.com/croneter/PlexKodiConnect?format=svg)](http://feathub.com/croneter/PlexKodiConnect)

### Known Larger Issues

Solutions are unlikely due to the nature of these issues
- A Plex Media Server "bug" leads to frequent and slow syncs, see [here for more info](https://github.com/croneter/PlexKodiConnect/issues/135)
- *Plex Music when using Addon paths instead of Native Direct Paths:* Kodi tries to scan every(!) single Plex song on startup. This leads to errors in the Kodi log file and potentially even crashes. See the [Github issue](https://github.com/croneter/PlexKodiConnect/issues/14) for more details
- *Plex Music when using Addon paths instead of Native Direct Paths:* You must have a static IP address for your Plex media server if you plan to use Plex Music features
- External Plex subtitles (in separate files, e.g. mymovie.srt) can be used, but it is impossible to label them correctly and tell what language they are in. However, this is not the case if you use direct paths

*Background Sync:*
The Plex Server does not tell anyone of the following changes. Hence PKC cannot detect these changes instantly but will notice them only on full/delta syncs (standard settings is every 60 minutes)
- Toggle the viewstate of an item to (un)watched outside of Kodi
- Changing details of an item, e.g. replacing a poster  

However, some changes to individual items are instantly detected, e.g. if you match a yet unrecognized movie. 


### Issues being worked on

Have a look at the [Github Issues Page](https://github.com/croneter/PlexKodiConnect/issues). Before you open your own issue, please read [How to report a bug](https://github.com/croneter/PlexKodiConnect/wiki/How-to-Report-A-Bug).


### Credits

- PlexKodiConnect shamelessly uses pretty much all the code of "Emby for Kodi" by the awesome Emby team (see https://github.com/MediaBrowser/plugin.video.emby). Thanks for sharing guys!!
- Plex Companion ("PlexBMC Helper") and other stuff were adapted from @Hippojay 's great work (see https://github.com/hippojay).
- The foundation of the Plex API is all iBaa's work (https://github.com/iBaa/PlexConnect).
