import requests
from requests.compat import urljoin
from constants import *
import re
import inspect

# To add support for a different RSS feed
# you MUST subclass Torrent and implement these 3 methods:
# match
# _get_active_torrents
# get_add_args

# see the Shana class for an example

class QBittorrent(object):
    TRIES = 2
    def __init__(self,username='',password=''):
        super().__init__()
        self.s = requests.Session()
        self.set_credentials(username,password)
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
        # this would allow multiple rss feeds at once: (commented because only one Torrent subclass can be used at a time)
##        l=[feed['articles'] for key,feed in r.json().items() if key.startswith(feedname)]
##        return [item for sublist in l for item in sublist] # flatten
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
        rssData = self._get_rss_entries()
        for name, obj in inspect.getmembers(self):
            if hasattr(obj, "__bases__") and self.Torrent in obj.__bases__:
                if obj.match(rssData[0]['link']):
                    return [obj(data) for data in obj._get_active_torrents(self,rssData)]

                
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
            return re.compile('^https?://(www\.)?animebytes.tv/torrent').match(url)
        @staticmethod
        def _get_active_torrents(qblink,rssData):
            rssData = {data['comments']:data for data in rssData}
            torrents = []
            for torrent in qblink._get_torrent_list():
                props = qblink._get_properties(torrent['hash'])
                if len(qblink._get_files(torrent['hash'])) == 1:
                    try:
                        rdata = rssData[props['comment']]
                        torrents.append((torrent['name'],rdata['title'],torrent['hash'],torrent['save_path'],torrent['progress']))
                    except:
                        pass
            return torrents
        def get_add_args(self):
            return (self._display_name_from_torrent(),
                    self._series_title_from_torrent(),
                    self._episode_no_from_torrent(),
                    self._subgroup_name_from_torrent(),
                    self.data[2])
        def series_title_from_torrent(self):
            'use data from get_active_torrents'
            return self.RSS_TITLE_RE.findall(self.data[1])[0]
        def display_name_from_torrent(self):
            return '{} - {} [{}]({})'.format(self.series_title_from_torrent(self.data),
                                     self.episode_no_from_torrent(self.data),
                                     self.RESOLUTION.findall(self.data[1])[-1],
                                     self.subgroup_name_from_torrent(self.data))
        def episode_no_from_torrent(self):
            try:
                return self.EPISODE_NUM.findall(self.data[1])[-1]
            except IndexError:
                return 0 # pv,op,ed, 0 means it will be ignored.
        def subgroup_name_from_torrent(self):
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
            return re.compile('^https?://(www\.)?shanaproject\.com/download/',re.I).match(url)
        @staticmethod
        def _get_active_torrents(qblink,rssData):
            'returns a list of tuples, each tuple with the format:'
            '(filename, series title, hash, save_path(folder), dl_progress)'
            'the tricky part is pairing each rss entry with a torrent'
            'qbittorrent api does not provide a way to do this (yet)'
            rssData = {data['description']:data for data in rssData}
            torrents = []
            for torrent in qblink._get_torrent_list():
                if len(qblink._get_files(torrent['hash'])) == 1:
                    try:
                        rdata = rssData[torrent['name']]
                        torrents.append((torrent['name'],rdata['title'],torrent['hash'],torrent['save_path'],torrent['progress']))
                    except:
                        'torrent too old, not in rss feed anymore'
                        pass
            return torrents
        def get_add_args(self):
            return (self._display_name_from_torrent(),
                    self._series_title_from_torrent(),
                    self._episode_no_from_torrent(),
                    self._subgroup_name_from_torrent(),
                    self.data[2])
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
                return self.SUBGROUP.findall(self.data[1])[-1]
            except IndexError:
                return None
