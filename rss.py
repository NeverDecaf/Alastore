from xml.dom import minidom
import urllib2
import contextlib
import socket
import re
import urlparse
class RSSReader:
    url=None
    source = 'unknown'
    # you can add additional websites here; [scheme, netloc, path, query, fragment]
    # A non-None value will replace the value in the original url.
    CLEANER = {'unknown': (None,None,None,None,None),
               'shanaproject': ('https',None,None,'show_all',''),
               }
    # if key is found in the url, will assume it is from `value` website.
    WEBSITE = {'shanaproject.com':'shanaproject',
               }
    
    def __init__(self,url=None):
        self._changeWebsite(url)
        self._changeUrl(url)

    def _changeUrl(self,url):
        self._changeWebsite(url)
        self.url=self._cleanUrl(url)

    def _changeWebsite(self,url=None):
        if not url:
            url = self.url
        if url:
            for site in self.WEBSITE:
                if site in url:
                    self.source = self.WEBSITE[site]
    
    def _cleanUrl(self,url):
        if url:
            t = urlparse.urlsplit(url)
            combo = [x if x is not None else t[i] for i,x in enumerate(self.CLEANER[self.source])]
            return urlparse.urlunsplit(combo)
        return url

    def _stripAndEnforceSSL(self,url):
        if url:
            t = urlparse.urlsplit(url)
            return urlparse.urlunsplit(('https',)+t[1:3]+('',''))
        return url

    def _getFilesShanaproject(self,url,count):
        request = urllib2.Request(self.url+'&count='+str(count))
        try:
            with contextlib.closing(urllib2.urlopen(request)) as response:
                xmldoc = minidom.parseString(response.read())
                itemlist = xmldoc.getElementsByTagName('item')
                episodes=[]
                for item in itemlist:
                    #this tuple is title, filename, torrent link
                    episodes.append((item.childNodes[0].firstChild.nodeValue,
                      item.childNodes[2].firstChild.nodeValue,
                      self._stripAndEnforceSSL(item.childNodes[1].firstChild.nodeValue)))
            return episodes
        except urllib2.URLError, e:
            print ("There was an error in rss.py: %r" % e)
        except socket.timeout, e:
            print ("There was an error in rss.py: %r" % e)
        return []

    def _getFilesGeneric(self,url,count):
        # if you intend to use an RSS feed from a different site, you will need to write a custom
        # getfiles for that site as well as adding values to CLEANER and WEBSITE to accomodate.
        return []

    
    def getFiles(self,url=None,count=200):
        ''' returns a list of all files referenced in the rss feed. the format is a list of tuples
            [(rss title, file name, torrent url),]
            '''
        if url:
            self._changeUrl(url)
        if not self.url:
            return []
        if self.source == 'shanaproject':
            return self._getFilesShanaproject(url,count)
        return self._getFilesGeneric(url,count)
