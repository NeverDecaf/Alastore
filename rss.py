from xml.dom import minidom
import urllib.request, urllib.error, urllib.parse
import contextlib
import socket
import re
import urllib.parse
try:
    # Python 2.6-2.7 
    from html.parser import HTMLParser
except ImportError:
    # Python 3
    from html.parser import HTMLParser
htmlparser = HTMLParser()
IS_MAGNET = re.compile('^magnet\:.*')
# IF YOU PLAN ON ADDING SUPPORT FOR A DIFFERENT RSS, READ THIS FIRST:
# besides adding new entires to CLEANER and WEBSITE and INVALID_REPLACEMENT you must also make a new _getFilesXXXX method.
# that should be all the changes required.
class RSSReader:
    url=None
    source = 'unknown'

    # if key is found in the url, will assume it is from `value` website.
    # the value here is used as a key in CLEANER and INVALID_REPLACEMENT so make sure it matches.
    WEBSITE = {'shanaproject.com':'shanaproject',
               }

    # you can add additional websites here; [scheme, netloc, path, query, fragment]
    # A non-None value will replace the value in the original url.
    # in most cases you probably just want (None,None,None,'','') though you may want to use 'http(s)' just in case.
    CLEANER = {'unknown': (None,None,None,None,None),
               'shanaproject': ('https',None,None,'show_all',''),
               }
    # This is the character the RSS source uses to replace invalid filename characters [\/:*?"<>| ]
    # you will need to find a file that contains one of these invalid characters to find out what it is.
    # don't forget the ur as paths are unicode, leaving this out may break the whole program.
    INVALID_REPLACEMENT = {'unknown':(r'[\/:*?"<>| ]',r'.'),
                           'shanaproject':(r'[\/:*?"<>| ]',r'_'),
                           }
    
    def __init__(self,url=None):
        self._changeUrl(url)

    def _changeUrl(self,url):
        self.url=self.cleanUrl(url)

    @staticmethod
    def invalidCharReplacement(url):
        source = 'unknown'
        for site in RSSReader.WEBSITE:
            if site in url:
                source = RSSReader.WEBSITE[site]
        return RSSReader.INVALID_REPLACEMENT[source]

    @staticmethod
    def cleanUrl(url):
        if url:
            source = 'unknown'
            for site in RSSReader.WEBSITE:
                if site in url:
                    source = RSSReader.WEBSITE[site]
            t = urllib.parse.urlsplit(url)
            combo = [x if x is not None else t[i] for i,x in enumerate(RSSReader.CLEANER[source])]
            return urllib.parse.urlunsplit(combo)
        return url

    def _stripAndEnforceSSL(self,url):
        if IS_MAGNET.match(url):
            return url
        if url:
            t = urllib.parse.urlsplit(url)
            return urllib.parse.urlunsplit(('https',)+t[1:3]+('',''))
        return url

    def _getFilesShanaproject(self,url,count):
        request = urllib.request.Request(self.url+'&count='+str(count))
        try:
            with contextlib.closing(urllib.request.urlopen(request)) as response:
                xmldoc = minidom.parseString(response.read())
                itemlist = xmldoc.getElementsByTagName('item')
                episodes=[]
                for item in itemlist:
                    #this tuple is title, filename, torrent link
                    episodes.append(list(map(htmlparser.unescape,(item.childNodes[0].firstChild.nodeValue,
                      item.childNodes[2].firstChild.nodeValue,
                      self._stripAndEnforceSSL(item.childNodes[1].firstChild.nodeValue)))))
            return episodes
        except urllib.error.URLError as e:
            print(("There was an error in rss.py: %r" % e))
        except TimeoutError as e:
            print(("There was an error in rss.py: %r" % e))
        return []

    def _getFilesGeneric(self,url,count):
        # if you intend to use an RSS feed from a different site, you will need to write a custom
        # getfiles for that site as well as adding values to CLEANER, WEBSITE, and INVALID_REPLACEMENT to accomodate.
        return []

    
    def getFiles(self,url=None,count=200):
        ''' returns a list of all files referenced in the rss feed. the format is a list of tuples
            [(rss title, file name, torrent url),]
            '''
        if url:
            self._changeUrl(url)
        if not self.url:
            return []
        for site in self.WEBSITE:
            if site in self.url:
                self.source = self.WEBSITE[site]
        # add a new if here for your new RSS feed.
        if self.source == 'shanaproject':
            return self._getFilesShanaproject(url,count)
        return self._getFilesGeneric(url,count)
    
if __name__=='__main__':
    test = RSSReader('')
    print(test.getFiles())
    
