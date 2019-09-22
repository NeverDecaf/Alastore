# Alastore-qbittorrent

#### What is this branch?
This branch uses the QBittorrent Web UI to interface directly with your torrent client. It should behave very similarly to the main branch with a few differences:
- When a file is sorted its location will also be updated in qbittorrent meaning it will no longer be reported as file missing and can continue to be seeded.
- Adding different RSS sources is very easy, just subclass Torrent in torrentclient.py. Currently supported RSS Feeds: Shanaproject, AnimeBytes.
- Adding support for other torrent clients is possible as long as they provide the minimum api necessary (would require modifying torrentclient.py)
#### Binaries
- Check the dist/ folder for an updated .exe
#### Requirements
- QBittorrent v4.1+ is required to have access to the RSS api.
#### Setup
- In QBittorrent options, enable the Web UI and ensure the port is 8080. Alastore will connect via http://localhost:8080
- Add your RSS feed and name it something beginning with `Alastore`.
- In RSS Downloader settings for this feed, set `Assign Category` to `Alastore` (Create the category if necessary)
- In Alastore Config, you must provide the required settings (username/password may be blank if you checked `Bypass authentication for clients on localhost` in QBittorrent.
- Multiple (supported) feeds can be used at once, just make sure they are all prefixed with `Alastore`. `Alastore_Shana` and `Alastore_AB` for example.
