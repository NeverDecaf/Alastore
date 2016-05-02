'''downloads an image and resizes it to create an icon. sets desired folder to use said icon.'''
import pyico
import iconchange
from PIL import Image
import urllib2
import contextlib
from xml.dom import minidom
import gzip
from StringIO import StringIO
import os
import os.path
import re
IMG_URL=re.compile('http://img7\.anidb\.net/pics/anime/\d*\.jpg')
def resize_center_image(image):
        IMAGE_SIZE=(256,256)
        zero,zero,w,h=image.getbbox()
        w+=0.0
        h+=0.0
        ratio= min(IMAGE_SIZE[0]/w,IMAGE_SIZE[1]/h)
        if ratio!=1:
            image = image.resize((int(w*ratio),int(h*ratio)),Image.ANTIALIAS)# 4 should be antialias
        background = Image.new('RGBA',IMAGE_SIZE,(255,255,255,0))
        x=int((IMAGE_SIZE[0]-w*ratio)/2)
        y=int((IMAGE_SIZE[1]-h*ratio)/2)
        background.paste(image,(x,y))
        return background
        return image.crop((x,y,IMAGE_SIZE[0]+x,IMAGE_SIZE[1]+y))
FAKE_HEADERS={
'Accept-Charset':'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
'Accept-Encoding':'gzip',
'Accept-Language':'en-US,en;q=0.8',
'User-Agent':'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.56 Safari/535.11',
    }

def download_picture(url):
   request = urllib2.Request(url,None,FAKE_HEADERS)
   with contextlib.closing(urllib2.urlopen(request)) as response:
        if response.info().get('Content-Encoding') == 'gzip':
                buf = StringIO(response.read())
                f = gzip.GzipFile(fileobj=buf)
                data = f.read()
        else:
                data=response.read()
        im = StringIO(data)
        lazyopen = Image.open(im)
        lazyopen.load()                 # fix for a bug in PIL 1.1.7
        return lazyopen

def makeIcon(aid,url,dest_folder):
    img = download_picture(url)
    img = resize_center_image(img)
    buf = StringIO()
    img.save(buf, format="PNG")
    ico = pyico.Icon([StringIO(buf.getvalue())],os.path.join(dest_folder,'%i.ico'%aid))
    ico.save()
    iconchange.seticon_unicode(dest_folder,'%i.ico'%aid,0) # dest_folder.encode('utf8') removed this and instead use seticon_unicode.
