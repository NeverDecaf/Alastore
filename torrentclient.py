import requests
from requests.compat import urljoin
from constants import *
import re
import inspect
import bencoder
import hashlib
from binascii import hexlify
from base64 import b32decode
# To add support for a different RSS feed
# you MUST subclass Torrent and implement these methods:
# match (@staticmethod)
# get_add_args

# see the Shana class for an example

class QBittorrent(object):
    TRIES = 2
    def __init__(self, sqlmanager, username='',password=''):
        super().__init__()
        self.s = requests.Session()
        self.set_credentials(username,password)
        self.sql = sqlmanager
##        self._login()
    def set_credentials(self,uname=None,pword=None):
        if uname:
            self.username = uname
        if pword:
            self.password = pword
    def _login(self,uname=None,pword=None):
        self.set_credentials(uname,pword)
        r=self.s.post(url=urljoin(WEBUI_URL,'/login'),data={'username':self.username,'password':self.password})
        r.raise_for_status()
        
    def move_and_categorize(self, infohash, destination):
        'torrent_data is the torrent file, destination must be a full path'
        data = {'hashes':infohash,'location':destination}
        r = self._login_if_needed(lambda: self.s.post(url=urljoin(WEBUI_URL,'/api/v2/torrents/setLocation'), data=data))
        data = {'hashes':infohash,'category':TORRENTC_WATCHED_CATEGORY}
        r = self._login_if_needed(lambda: self.s.post(url=urljoin(WEBUI_URL,'/api/v2/torrents/setCategory'), data=data), raise_fs = False)
        if r.status_code == 409:
            data_cat = {'category':TORRENTC_WATCHED_CATEGORY}
            r=self._login_if_needed(lambda: self.s.post(url=urljoin(WEBUI_URL,'/api/v2/torrents/createCategory'), data=data_cat))
            r=self._login_if_needed(lambda: self.s.post(url=urljoin(WEBUI_URL,'/api/v2/torrents/setCategory'), data=data))
        else:
            r.raise_for_status()
        return 0
    
    def _login_if_needed(self,func,raise_fs = True):
        for i in range(self.TRIES):
            r=func()
            if r.status_code == 403:
                self._login()
                continue
            if raise_fs:
                r.raise_for_status()
            break
        return r
    def get_progress(self,ihash,category=TORRENTC_CATEGORY):
        r = self._login_if_needed(lambda: self.s.post(url=urljoin(WEBUI_URL,'/api/v2/torrents/info'), data={'category':category, 'hashes':ihash}))
        try:
            return r.json()[0]['progress']
        except:
            return 0
    def _get_rss_entries(self,feedname=TORRENTC_CATEGORY):
        r = self._login_if_needed(lambda: self.s.post(url=urljoin(WEBUI_URL,'/api/v2/rss/items'), data={'withData':True}))
        feeds = {}
        for key,feed in r.json().items():
            feeds[feed['url']]=feed['articles']
        return feeds
        # this would allow multiple rss feeds at once: (commented because only one Torrent subclass can be used at a time)
        l=[feed['articles'] for key,feed in r.json().items() if key.startswith(feedname)]
        return [item for sublist in l for item in sublist] # flatten
        return r.json()[feedname]['articles']
    def _get_torrent_list(self,category=TORRENTC_CATEGORY):
        r = self._login_if_needed(lambda: self.s.post(url=urljoin(WEBUI_URL,'/api/v2/torrents/info'), data={'category':category}))
        return r.json()
    def _get_properties(self,ihash):
        r = self._login_if_needed(lambda: self.s.post(url=urljoin(WEBUI_URL,'/api/v2/torrents/properties'), data={'hash':ihash}))
        return r.json()
    def _get_files(self,ihash):
        r = self._login_if_needed(lambda: self.s.post(url=urljoin(WEBUI_URL,'/api/v2/torrents/files'), data={'hash':ihash}))
        return r.json()
    def get_active_torrents(self):
        'use rss urls to match a parser, then return a list of Torrent objects'
        # rssData = self._get_rss_entries()
        exitinginfohashes = self.sql.getRSSUrls()
        # generate infohash from (new) torrent files:
        for feed_url, articles in self._get_rss_entries().items():
            for url,title in [(d['link'],d['title']) for d in articles]:
                if url not in exitinginfohashes:
                    # if magnet, just extract the infohash.
                    hash_re = re.compile('urn:btih:(\w{32,40})',re.I)
                    m = hash_re.search(url)
                    if m:
                        infohash = m.group(1)
                        if len(infohash)==32:
                            infohash = hexlify(b32decode(infohash))
                        self.sql.setRSSHashes(url, infohash.lower(), title, feed_url)
                    else:
                        with requests.get(url, timeout=REQUESTS_TIMEOUT) as r:
                            torrent_file = bencoder.decode(r.content)
                            m = hashlib.sha1(bencoder.encode(torrent_file[b'info']))
                            self.sql.setRSSHashes(url, m.hexdigest(), title, feed_url)
        rss_dict = self.sql.getRSSDict()
        
        feed_sources = []
        for name, obj in inspect.getmembers(self):
            if hasattr(obj, "__bases__") and self.Torrent in obj.__bases__:
                feed_sources.append(obj)

        torrents = []
        for torrent in self._get_torrent_list():
            props = self._get_properties(torrent['hash'])
            if len(self._get_files(torrent['hash'])) == 1:
                try:
                    for obj in feed_sources:
                        if obj.match(rss_dict[torrent['hash']][2]):
                            torrents.append(obj((torrent['name'],rss_dict[torrent['hash']][1],torrent['hash'],torrent['save_path'],torrent['progress'])))
                            break
                except:
                    pass
        return torrents
    class Torrent(object):
        def __init__(self,data):
            self.data = data
        def get_data(self):
            return self.data
    class AnimeBytes(Torrent):
        RSS_TITLE_RE = re.compile('^(.*) - .* :: ') #title as given in rss feed.
        EPISODE_NUM = re.compile(':: (?:[^\|]*\|){6} Episode (\d+\.?\d*v?\d*)') #make sure you get the last one [-1]
        SUBGROUP = re.compile(':: (?:[^\|]*\|){5}[^\|]*\(([^\)]*)\)')#make sure you get the last one [-1]

        RESOLUTION = re.compile(':: (?:[^\|]*\|){3} (\S*)')
        @staticmethod
        def match(url):
            return re.compile('^https?://(www\.)?animebytes.tv/feed/').match(url)
        def get_add_args(self):
            return (self._display_name_from_torrent(),
                    self._series_title_from_torrent(),
                    self._episode_no_from_torrent(),
                    self._subgroup_name_from_torrent(),
                    self.data[2]) # data[2] is infohash
        def _series_title_from_torrent(self):
            'use data from get_active_torrents'
            return self.RSS_TITLE_RE.findall(self.data[1])[0]
        def _display_name_from_torrent(self):
            return '{} - {} [{}][{}]'.format(self._series_title_from_torrent(),
                                     self._episode_no_from_torrent(),
                                     self.RESOLUTION.findall(self.data[1])[-1],
                                     self._subgroup_name_from_torrent())
        def _episode_no_from_torrent(self):
            try:
                return self.EPISODE_NUM.findall(self.data[1])[-1]
            except IndexError:
                return 0 # pv,op,ed, 0 means it will be ignored.
        def _subgroup_name_from_torrent(self):
            try:
                return self.SUBGROUP.findall(self.data[1])[-1]
            except IndexError:
                return None
    class Shana(Torrent):
        RSS_TITLE_RE = re.compile('.*(?= - \d)') #title as given in rss feed.
        EPISODE_NUM = re.compile('(?<= - )(\d+\.?\d*)') #make sure you get the last one [-1]
        SUBGROUP = re.compile('(?<=\[)[^\]]*(?=])')#make sure you get the last one [-1]
        @staticmethod
        def match(url):
            return re.compile('^https?://(www\.)?shanaproject\.com/feeds/',re.I).match(url)
        def get_add_args(self):
            return (self._display_name_from_torrent(),
                    self._series_title_from_torrent(),
                    self._episode_no_from_torrent(),
                    self._subgroup_name_from_torrent(),
                    self.data[2]) # data[2] is infohash
        def _series_title_from_torrent(self):
            return self.RSS_TITLE_RE.findall(self.data[1])[0] # data[1] is title (from rss)
        def _display_name_from_torrent(self):
            return self.data[1]
        def _episode_no_from_torrent(self):
            try:
                return self.EPISODE_NUM.findall(self.data[1])[-1] # data[1] is title (from rss)
            except IndexError:
                return 0 # pv,op,ed, 0 means it will be ignored.
        def _subgroup_name_from_torrent(self):
            try:
                return self.SUBGROUP.findall(self.data[1])[-1] # data[1] is title (from rss)
            except IndexError:
                return None
    class HorribleSubs(Torrent):
        RSS_TITLE_RE = re.compile('^[^\]]+] (.*) - \d') #title as given in rss feed.
        EPISODE_NUM = re.compile('(?<= - )(\d+\.?\d*)') #make sure you get the last one [-1]
        SUBGROUP = re.compile('^\[([^\]]*)')
        @staticmethod
        def match(url):
            return re.compile('^https?://(www\.)?horriblesubs\.info/rss',re.I).match(url)
        def get_add_args(self):
            return (self._display_name_from_torrent(),
                    self._series_title_from_torrent(),
                    self._episode_no_from_torrent(),
                    self._subgroup_name_from_torrent(),
                    self.data[2]) # data[2] is infohash
        def _series_title_from_torrent(self):
            return self.RSS_TITLE_RE.findall(self.data[1])[0]
        def _display_name_from_torrent(self):
            return self.data[1]
        def _episode_no_from_torrent(self):
            try:
                return self.EPISODE_NUM.findall(self.data[1])[-1]
            except IndexError:
                return 0 # pv,op,ed, 0 means it will be ignored.
        def _subgroup_name_from_torrent(self):
            try:
                return self.SUBGROUP.findall(self.data[1])[0]
            except IndexError:
                return None
if __name__ == "__main__":
    import sql
    qb = QBittorrent(sql.SQLManager())
    for t in qb.get_active_torrents():
        print(t.get_add_args())