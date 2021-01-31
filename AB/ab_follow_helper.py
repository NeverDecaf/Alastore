
import sys
sys.path.append("..")
import torrentclient
import sql
from lxml import html as lxmlhtml
from PyQt5.QtWidgets import QApplication,QWidget,QLabel,QGridLayout,QPushButton
from PyQt5.QtGui import QIcon,QPixmap  
from PyQt5.QtCore import QTimer
import sqlite3
import requests
import time

encoding = 'utf8'
site_filename = 'Currently Airing Anime AnimeBytes'
# can use regex for the below, but be careful of duplicate episodes as qbittorrent does not correctly handle these (yet?)
qual = '720p'
group = '.*'#'HorribleSubs'
IGNORE_DAYS = 5 # if using .* as group, set this to ~5 to prevent downloading duplicate episodes
# create a file rss_url which contains your private AB feed: https://animebytes.tv/feed/rss_torrents_airing_anime/<YOUR_SECRET_HERE>
class ABAPI(object):
    def __init__(self,uname,pkey):
        self.user = uname
        self.pss = pkey
    def _fetch_all_airing(self):
        api = 'https://animebytes.tv/scrape.php?torrent_pass={}&username={}&type=anime&page={}&airing=1'
        for page in range(1,10):
            r=requests.get(api.format(self.pss,self.user,page))
            js = r.json()
            print(js)
            if js['Matches'] < js['Limit']:
                break
            time.sleep(4)
class App(QWidget):  
    def __init__(self,series):  
        super().__init__()  
        self.title='AnimeBytes Series Sorter'  
        self.left=10  
        self.top=70  
        self.width=400
        self.height=650
        self.series = series
        self.workingtitle = None
        self.follow_db = sqlite3.connect('follows.sqlitedb')
        self.cursor = self.follow_db.cursor()
        
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS follows
        (name text, following int, airing int)''')
        self.cursor.execute('''UPDATE follows
        SET airing = 0''')
        
        self.initUI()
        QTimer.singleShot(0, self.prompt)
        
    def initUI(self):  
        self.setWindowTitle(self.title)  
        self.setGeometry(self.left,self.top,self.width,self.height)
        layout = QGridLayout()
        self.setLayout(layout)
        
        self.img=QLabel()
        self.titlelabel = QLabel()
        self.add = QPushButton("Follow")
        self.skip = QPushButton("Ignore")
        layout.addWidget(self.img,0,0,1,2)
        layout.addWidget(self.titlelabel,1,0,1,2)
        layout.addWidget(self.add,2,0,1,1)
        layout.addWidget(self.skip,2,1,1,1)
        
        self.add.clicked.connect(lambda:self.process(1))
        self.skip.clicked.connect(lambda:self.process(0))
        self.show()
    def prompt(self):
        try:
            title,src = next(self.series)
        except StopIteration:
            self.follow_db.commit()
            self.follow_db.close()
            self.close()
            app.quit()
            return
        cleantitle = (' - '.join(title.split(' - ')[:-1])).strip()
        r=self.cursor.execute('''UPDATE follows
        SET airing=1
        WHERE name=?''',(cleantitle,))
        if self.cursor.rowcount:
            return self.prompt()
        cleansrc = src.split('/')[-1]
        pixmap=QPixmap(r'{}_files\{}'.format(site_filename,cleansrc)).scaledToWidth(self.width,1)
        self.img.setPixmap(pixmap)
        self.titlelabel.setText(cleantitle)
        self.workingtitle = cleantitle
        
    def process(self,add):
        r=self.cursor.execute('''REPLACE INTO follows (name,following,airing)
        VALUES (?,?,?)''',(self.workingtitle, add, 1))
        self.prompt()

if __name__=='__main__':  
    print('visit https://animebytes.tv/airing and ctrl+s save it to this folder, then press enter to continue...')
    input()
    with open('{}.htm'.format(site_filename),'rb') as f:
        etree = lxmlhtml.fromstring(f.read().decode(encoding))

    series = zip(etree.xpath('//td/a/img/@title'),etree.xpath('//td/a/img/@src'))
    app=QApplication(sys.argv)
    ex=App(series)
    app.exec_()
    
    # ab = ABAPI(uname,pkey)
    # ab._fetch_all_airing()
    
    # just actually delete all RSS filters from qbittorrent if series no longer airing
    a = sql.SQLManager()
    a._createTables()
    qb = torrentclient.QBittorrent(a)
    with open('rss_url','r') as f:
        rssurl = f.readline()
    db = sqlite3.connect('follows.sqlitedb')
    r=db.cursor().execute('SELECT name,following FROM follows WHERE airing=1')
    spairs = dict(r.fetchall())
    print(spairs)
    # mark old rules for deletion
    for k,v in qb.get_all_rss_rules().items():
        if v['assignedCategory'] == 'Alastore' and k not in spairs:
            spairs[k] = 0
        else:
            spairs[k] = -1
    for title,follow in spairs.items():
        if follow==1:
            qb.add_rss_rule(title,qual,group,[rssurl],ignoreDays = IGNORE_DAYS)
        elif follow==0:
            qb.remove_rss_rule(title)
        # else follow == -1, do not modify.
