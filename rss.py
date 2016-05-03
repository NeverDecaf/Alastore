from xml.dom import minidom
import urllib2
import contextlib
import socket
import re
import urlparse
class RSSReader:
    url=None
##    PRIVATE_TO_PUBLIC = ur'(/secure)|(?<=/user/)(\d*/)(.*)'
    def __init__(self,url=None):
        self.url=self._changeUrl(url)

    def _changeUrl(self,url):
        self.url=self._cleanUrl(url)
        
    def _cleanUrl(self,url):
        if url:
            t = urlparse.urlsplit(url)
            return urlparse.urlunsplit(t[:3]+('show_all',''))
        return url

    def _stripAndNoSSL(self,url):
        if url:
            t = urlparse.urlsplit(url)
            return urlparse.urlunsplit(('https',)+t[1:3]+('',''))
        return url
    
    def getFiles(self,url=None,count=200):
        ''' returns a list of all files referenced in the rss feed. the format is a list of tuples
            [(rss title, file name, torrent url),]
            '''
        if url:
            self._changeUrl(url)
        if not self.url:
            return []
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
                      self._stripAndNoSSL(item.childNodes[1].firstChild.nodeValue)))
            return episodes
        except urllib2.URLError, e:
            print ("There was an error in rss.py: %r" % e)
        except socket.timeout, e:
            print ("There was an error in rss.py: %r" % e)
        return []

    #not fully tested, should work.
    # also not used anywhere.
##    def getPublicFeed(self):
##        return re.sub(self.PRIVATE_TO_PUBLIC,lambda m: m.group(2) or '',self.url)
