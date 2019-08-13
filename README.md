# Alastore

#### What is this?
Alastore is a small program that makes it easy to watch, organize, and track anime series you have downloaded through shanaproject.com RSS feeds. Alastore's GUI allows you to quickly see when new episodes are released and, with a double-click, an
episode is automatically played, sorted into folders organized by year/season/series and added to your anidb mylist.
If you wish to see what this looks like, see "what is this.png"
Alastore is meant to be used alongside a torrent client which can automatically download from an RSS feed.

#### Setup
Binaries are available if you are on windows, see [Releases](https://github.com/NeverDecaf/Alastore/releases/latest).

The bare minimum setup:
  1. Choose the config option from the tray icon right-click menu.  
  2. Copy and paste your **private** RSS feed from shanaproject.com (you can find it in settings). This should be the same feed you use with your torrent client.  
  3. Under "Download Directory" select the directory where your torrent client will place the downloaded episodes.  
  4. Under "Storage Directory" choose a folder you want all your episodes to be moved and sorted into.

You can double-click the "header" of any series to watch the latest (unwatched) episode. You can also expand a series if you want to rewatch older episodes.

Closing the main window will simply minimize it to tray. Double-click the icon to bring it back. Alastore is meant to run in the background and sit in your tray.

If you want to use a custom or alternative color scheme place alastore_theme.ini in the same folder as Alastore.exe and edit the colors as you see fit. Several sample themes are available in this repo, simply rename them to alastore_theme.ini to use them.

###### A final warning(s):
* If you add a season 2 on shanaproject **make sure you delete your follow for season 1.** Following both will cause you to have duplicate episodes downloaded to your computer (this isn't an issue with alastore but one with Shanaproject; it can, however, cause issues with Alastore as well.) With regards to Alastore's anidb update feature, you will want to keep the s2 follow and remove the s1 follow to prevent potential failed mylist adds.
* Functionality without a linked anidb account is completely untested. YMMV but it should work fairly well.
* On windows you may need to run as administrator to reorganize episodes. You will notice issues primarily at the beginning of a season. (Specifically, some episodes may not be sorted correctly and cannot be moved to their correct folders without admin privileges.)