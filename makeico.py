'''downloads an image and resizes it to create an icon. sets desired folder to use said icon.'''
import pyico
import iconchange
from PIL import Image
from io import BytesIO
import os
import re
import anidb
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

def makeIcon(aid,url,dest_folder):
    img = anidb.anidb_dl_poster_art(url)
    img = resize_center_image(img)
    buf = BytesIO()
    img.save(buf, format="PNG")
    ico = pyico.Icon([BytesIO(buf.getvalue())],os.path.join(dest_folder,'%i.ico'%aid))
    ico.save()
    iconchange.seticon_unicode(dest_folder,'%i.ico'%aid,0) # dest_folder.encode('utf8') removed this and instead use seticon_unicode.
