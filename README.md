#Alastore

####What is this?
Alastore is a small program that makes it exceedingly easy to watch, organize, and track anime series you have downloaded through shanaproject.com RSS feeds. Alastore's GUI allows you to quickly see when new episodes are released and, with a double-click, the
episode is automatically played, sorted into folders organized by year/season/series and (optionally) added to your anidb mylist.
If you wish to see what this looks like, see "what is this.png"
Alastore is meant to be used alongside a torrent client set to automatically download from an RSS feed. Shanaproject has since
added a feature that lets you use deluge to sort your downloads so if that is all you are looking for that is likely a much
better alternative.

####Setup
Binaries are available if you are on windows, see the binaries folder.  

The bare minimum setup:  
1. Choose the config option from the tray icon.  
2. Copy and paste your **private** RSS feed from shanaproject.com (you can find it in settings). This should be the same feed you use with
your torrent client.  
3. Under "Download Directory" select the directory where your torrent client will place the downloaded episodes.  
4. Under "Storage Directory" choose a folder you want all your episodes to be moved and sorted into.  

Closing the main window will simply minimize it to tray. Double-click the icon to bring it back. Alastore is meant to run in the background
and sit in your tray at all times. You can run it on startup with the -q switch to have it start minimized to tray.


Functionality without a linked anidb account is completely untested. YMMV but it should work fairly well.

For more detail choose the help option in the tray menu.

####Extra Notes (for devs)
First, my apologies about the generally digusting and amateruish spaghetti code, I am not a professional.

In theory Alastore should work in linux as it uses Qt but you may need to do some debugging to get UI elements like the tray icon to
look right or even show up at all.

If Alastore starts to become a memory hog delete your db and start over (Haven't added any sort of pruning yet; after using it for 
around 4 years and watching 10-20 shows a season it uses ~100Mb of RAM)

It should be possible to "port" Alastore to other RSS feeds or database sites.
Switching from shanaproject to, say, bakabt should be as easy as modifying the rss.py file.
Switching from anidb may prove slightly more difficult but is far from impossible (anidb.py would be a good place to start)

Be careful with anything involving anidb as it is very easy to get banned.

If you wish to make an exe with pyinstaller you must first run
pyi-makespec Alastore.py then edit the spec to add [(r'book.ico',r'book.ico','DATA')] as an arugment to EXE()
the full series of commands is:
pyi-makespec --onefile --noconsole --name=Alastore --icon=book.ico Alastore.py
(edit the spec file now)
pyinstaller --clean --noconfirm Alastore.spec
