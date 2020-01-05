
import sys
sys.path.append("..")
import torrentclient
import sql
from lxml import html as lxmlhtml
from PyQt5.QtWidgets import QApplication,QWidget,QLabel,QGridLayout,QPushButton
from PyQt5.QtGui import QIcon,QPixmap  
from PyQt5.QtCore import QTimer

encoding = 'utf8'
site_filename = 'Currently Airing Anime   AnimeBytes'
qual = '720p'
group = 'HorribleSubs'
# create a file rss_url which contains your private AB feed: https://animebytes.tv/feed/rss_torrents_airing_anime/<YOUR_SECRET_HERE>

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
        try:
            with open('ignorelist','rb') as i:
                self.alreadysorted = i.read().decode(encoding).splitlines()
        except FileNotFoundError:
            self.alreadysorted = []
        try:
            with open('followlist','rb') as i:
                self.alreadysorted += i.read().decode(encoding).splitlines()
        except FileNotFoundError:
            pass
        self.followlist = open('followlist','ab')
        self.ignorelist = open('ignorelist','ab')
        
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
            title,src = next(series)
        except StopIteration:
            self.followlist.close()
            self.ignorelist.close()
            self.close()
            app.quit()
            return
        cleantitle = (' - '.join(title.split(' - ')[:-1])).strip()
        if cleantitle in self.alreadysorted:
            return self.prompt()
        cleansrc = src.split('/')[-1]
        pixmap=QPixmap(r'{}_files\{}'.format(site_filename,cleansrc)).scaledToWidth(self.width,1)
        self.img.setPixmap(pixmap)
        self.titlelabel.setText(cleantitle)
        self.workingtitle = cleantitle
        
    def process(self,add):
        if add:
            self.followlist.write('{}\n'.format(self.workingtitle).encode(encoding))
        else:
            self.ignorelist.write('{}\n'.format(self.workingtitle).encode(encoding))
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
    
    a = sql.SQLManager()
    a._createTables()
    qb = torrentclient.QBittorrent(a)
    with open('rss_url','r') as f:
        rssurl = f.readline()
    with open('followlist','rb') as i:
        for title in i.read().decode(encoding).splitlines():
            qb.add_rss_rule(title,qual,group,[rssurl])