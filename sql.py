import sqlite3
import os.path
import re
import urllib.parse
from StringMatcher import StringMatcher
from rss import RSSReader
from collections import defaultdict
import asyncio
### READ THIS BEFORE CHANGING THE TIMES BELOW ###
# setting these higher is a terrible idea
# because failures still reset the timer so you may wait a week even though it was a simple outage
# (exceptions to this will be marked with #exception, though I'm not 100% sure these are accurate)
# setting some of these any lower than 1 day may result in you getting IP banned by anidb.
ONE_DAY = 86400
ONE_WEEK = ONE_DAY * 7
'time between cover art updates, not suggested to set lower than a day.'
COVER_UPDATE_TIME=ONE_DAY
'time between series info updates (aid, season, etc), do not set lower than 1 day'
SERIES_UPDATE_TIME=ONE_DAY
'time between download of full title list, DO NOT set lower than 1 day'
TITLE_UPDATE_TIME=ONE_DAY
'time before a file will be generic added. should be sufficiently long to give others time to add the file to anidb.'
ANIDB_WAIT_TIME=ONE_WEEK#exception
'''after this interval, series will stop being updated in any way.
this should be long enough that if no episode has been released in this time period,
it is safe to assume the series has ended.
HOWEVER, if a new episode for the series is released, it will be automatically unhidden, so you don't need to go too extreme.'''
LAST_UPDATE_TIME=2 * ONE_WEEK + ONE_DAY#exception
'time between title match (levenshtein) to guess aids'
AID_UPDATE_TIME=ONE_DAY#exception
'''time before bad torrent entries are removed from blacklist'''
BLACKLIST_UPDATE_TIME=ONE_DAY#exception

class SQLManager:
    conn=None
    cursor=None
    db=None
    EPISODE_NUM = re.compile('(?<= - )(\d+\.?\d*)') #make sure you get the last one [-1]
    SHANA_TITLE = re.compile('.*(?= - \d)')
    SUBGROUP = re.compile('(?<=\[)[^\]]*(?=])')#make sure you get the last one [-1]
    COLUMN_NAMES = ['RSS Feed','Download Directory','Save Directory','anidb Username','anidb Password','Season Sort','Poster Icons','Auto Hide Old','Shana Project Username','Shana Project Password']

    # init. supply the name of the db.
    def __init__(self, db='Alastore.db', createtables = False):
        self.db=db
        self.conn=sqlite3.connect(self.db)#,check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        if createtables:
            self._createTables()
        self.conn.create_function('removeNonAlphaAndSpaces',1,self.removeNonAlphaAndSpaces)
        self.conn.create_function('editdist',2,self.editdist)
        self.conn.create_function('expandvars',1,self.expandvars)
        
    # Open a connection to the db. Will be used by this SQLManager until it is closed.
    def connect(self):
        self.conn=sqlite3.connect(self.db)
        self.cursor=self.conn.cursor()
        self._createTables()

    # Closes this SQLManager's current connection to the db.
    def close(self):
        self.conn.close()
        self.conn=None
        self.cursor=None

    #functions used in conn.create_function
    def removeNonAlphaAndSpaces(self,string):
        return re.sub('[^0-9a-zA-Z]+', '', string)
    
    def editdist(self,string1,string2):
        a=StringMatcher(None,string1.lower(),string2.lower())
        return a.distance()

    def expandvars(self,path):
        return os.path.expanduser(os.path.expandvars(path)) if path else ''
    
    # Creates all the tables we will be using. can be called each connect just for safety.
    def _createTables(self):
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS titles
                 (aid integer, type text, lang text, title text PRIMARY KEY)''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS user_settings
                 (id integer PRIMARY KEY DEFAULT 0, rss text DEFAULT '', dl_dir text DEFAULT '', st_dir text DEFAULT '', anidb_username text DEFAULT '', anidb_password text DEFAULT '',
                 season_sort integer DEFAULT 2, custom_icons integer DEFAULT 2, title_update integer DEFAULT 0, dont_show_again integer DEFAULT 0,
                 auto_hide_old integer DEFAULT 2, shanaproject_username text DEFAULT '', shanaproject_password text DEFAULT '')''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS shana_series
                 (id integer PRIMARY KEY AUTOINCREMENT, title text, aid integer DEFAULT NULL, cover_art integer DEFAULT 0,
                 hidden integer DEFAULT 0, airdate text, season text, poster_url text, series_info integer DEFAULT 0,
                 last_poster_url text DEFAULT NULL, last_update integer DEFAULT (strftime('%s', 'now')), verified_aid integer DEFAULT 0, aid_update integer DEFAULT 0)''')

        # these must have the same structure with the addition of aid to anidb_force_added
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS parse_data
                 (path text PRIMARY KEY, ed2k text, filesize integer, id integer, episode integer, subgroup text, added_on integer DEFAULT (strftime('%s', 'now')), last_add_attempt integer DEFAULT (strftime('%s', 'now')))''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS anidb_force_added
                 (path text PRIMARY KEY, ed2k text, filesize integer, id integer, episode integer, subgroup text, added_on integer DEFAULT (strftime('%s', 'now')), last_add_attempt integer DEFAULT (strftime('%s', 'now')), aid integer)''')
        
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS episode_data
                 (id integer, file_name text, episode integer, path text, display_name text, watched integer DEFAULT 0,downloaded integer DEFAULT 0,
                 subgroup text, torrent text PRIMARY KEY, torrent_data BLOB DEFAULT NULL, download_percent integer DEFAULT 0)''')
##        self.cursor.execute('''INSERT OR IGNORE INTO user_settings (id, rss, dl_dir, st_dir, anidb_username, anidb_password, shanaproject_username, shanaproject_password) VALUES (0,'','','','','','','')''')
        self.cursor.execute('''INSERT OR IGNORE INTO user_settings (id) VALUES (0)''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS bad_torrents
                 (url text PRIMARY KEY, last_update integer DEFAULT (strftime('%s', 'now')))''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS anidb_limiting
                 (id integer PRIMARY KEY DEFAULT 0,
                 delay real DEFAULT 675,
                 last_update real DEFAULT 0,
                 last_seriesinfo real DEFAULT 0)''')
        self.cursor.execute('''INSERT OR IGNORE INTO anidb_limiting (id) VALUES (0)''')
        self.conn.commit()

    # saves the supplied user settings into the db.
    def saveSettings(self, rss_url, download_directory, store_directory, anidb_username, anidb_password, sort_by_season, custom_icons, auto_hide_old, shanaproject_username, shanaproject_password):
        rss_url = RSSReader.cleanUrl(rss_url)
##        t = urlparse.urlsplit(rss_url)
##        rss_url = urlparse.urlunsplit(t[:3]+('show_all',''))
        self.cursor.execute('''REPLACE INTO user_settings (id, rss, dl_dir, st_dir, anidb_username, anidb_password, season_sort,custom_icons,title_update,dont_show_again,auto_hide_old,shanaproject_username,shanaproject_password) VALUES
                                (?,?,?,?,?,?,?,?,COALESCE((SELECT title_update FROM user_settings WHERE id=0),0),COALESCE((SELECT dont_show_again FROM user_settings WHERE id=0),0),?,?,?)''',
                            (0, rss_url, download_directory, store_directory, anidb_username, anidb_password,sort_by_season,custom_icons,auto_hide_old,shanaproject_username,shanaproject_password))
        self.conn.commit()

    # returns a dict of all settings, keys are the full name of each setting, which can be used directly in a GUI.
    # raw doesn't expand the dir names, allowing you to use env variables if you wish
    # fetchanyway will retrieve settings even if they aren't valid.
    def getSettings(self,raw=False,fetchanyway=False):
        if raw:
            self.cursor.execute('''SELECT rss AS "{}", dl_dir AS "{}", st_dir AS "{}", anidb_username AS "{}", anidb_password AS "{}", season_sort AS "{}",
custom_icons AS "{}", auto_hide_old AS "{}", shanaproject_username AS "{}", shanaproject_password AS "{}" FROM user_settings WHERE id=0'''.format(*self.COLUMN_NAMES))
        else:
            self.cursor.execute('''SELECT rss AS "{}", expandvars(dl_dir) AS "{}", expandvars(st_dir) AS "{}", anidb_username AS "{}", anidb_password AS "{}", season_sort AS "{}",
custom_icons AS "{}", auto_hide_old AS "{}", shanaproject_username AS "{}", shanaproject_password AS "{}" FROM user_settings WHERE id=0'''.format(*self.COLUMN_NAMES))
        settings = self.cursor.fetchone()
        if fetchanyway:
            return settings
        if not settings:
            return None
        if not settings['RSS Feed'] and not settings['Download Directory'] and not settings['Save Directory']:
            return None
        #expand environment vars in the paths.
        return settings
    
    def watchMoveQueue(self,source_path,dest_path,ed2k,filesize):
        self.cursor.execute('''UPDATE episode_data SET watched=1,path=? WHERE path=?''',(dest_path,source_path))
        self.cursor.execute('''REPLACE INTO parse_data (path,id,episode,subgroup,ed2k,filesize) SELECT path,id,episode,subgroup,?,? FROM episode_data WHERE path=? LIMIT 1''',(ed2k,filesize,dest_path))
        self.conn.commit()

    def getShowAgain(self):
        self.cursor.execute('''SELECT dont_show_again FROM user_settings where id=0''')
        return self.cursor.fetchone()['dont_show_again']
    def setShowAgain(self,dont):
        self.cursor.execute('''UPDATE user_settings SET dont_show_again=?''',(dont,))
        self.conn.commit()
    # get a dict of all series by title:episodes
    def getSeries(self, fetchHidden = False):
        self.cursor.execute('''SELECT shana_series.id as id,file_name,episode,path,display_name,watched,downloaded,subgroup,hidden,torrent as torrent_url,torrent_data,download_percent,title,season FROM
                        episode_data JOIN shana_series ON shana_series.id=episode_data.id {} ORDER BY episode ASC'''.format('WHERE hidden=0' if not fetchHidden else ''))
        results = self.cursor.fetchall()
        d = defaultdict(list)
        for r in results:
            d[r['title']].append(r)
        return d
    
    def getEpisode(self, shana_id, torrent_url):
        self.cursor.execute('''SELECT shana_series.id as id,file_name,episode,path,display_name,watched,downloaded,subgroup,hidden,torrent as torrent_url,torrent_data,download_percent,title,season FROM
                        episode_data JOIN shana_series ON shana_series.id=episode_data.id WHERE shana_series.id=? AND torrent=? ORDER BY episode ASC''',(shana_id,torrent_url))
        results = self.cursor.fetchone()
        return results
    
    def getDownloadingSeries(self):
        self.cursor.execute('''SELECT shana_series.id as id,file_name,episode,path,display_name,watched,downloaded,subgroup,hidden,torrent as torrent_url,torrent_data,download_percent,title,season FROM
                        episode_data JOIN shana_series ON shana_series.id=episode_data.id WHERE watched=0 AND downloaded=0 AND hidden=0 ORDER BY episode ASC''')
        results = self.cursor.fetchall()
        d = defaultdict(list)
        for r in results:
            d[r['title']].append(r)
        return d
    
    def cacheTitles(self, titles_full, query_max = 999//4): # SQLITE_MAX_VARIABLE_NUMBER defaults to 999
        self.cursor.execute('''UPDATE user_settings SET title_update=strftime('%s', 'now') WHERE id=0''')
        self.conn.commit()
        for titles in [titles_full[i:i+query_max] for i in range(0,len(titles_full),query_max)]:
            query = '''REPLACE INTO titles VALUES {}'''.format(','.join(['(?,?,?,?)']*len(titles)))
            self.cursor.execute(query,[item for sublist in titles for item in sublist])
        self.conn.commit()
        
    def titleUpdateTime(self, override = 0):
        self.cursor.execute('''SELECT title_update FROM user_settings WHERE title_update<strftime('%s', 'now')-?''',(max(override,TITLE_UPDATE_TIME),))
        return self.cursor.fetchone()
        
    def hideSeries(self, id):
        self.cursor.execute('''UPDATE shana_series SET hidden=1 WHERE id=?''',(id,))
        self.conn.commit()

    def dropSeries(self, id):
        self.cursor.execute('''UPDATE episode_data SET downloaded=0, download_percent=0, torrent_data=NULL WHERE id = ?''',(id,))
        self.conn.commit()

    # marks an/all episodes of a series as watched, regardless of file state.
    def forceWatched(self,id=None,torrenturl=None):
        if torrenturl:
            self.cursor.execute('''UPDATE episode_data SET watched=1 WHERE torrent=?''',(torrenturl,))
        elif id:
            self.cursor.execute('''UPDATE episode_data SET watched=1 WHERE id =?''',(id,))
        self.conn.commit()
        
    def unHideSeries(self, title):
        self.cursor.execute('''UPDATE shana_series SET hidden=0 WHERE title=?''',(title,))
        self.conn.commit()

    def addTorrentData(self,path,torrenturl,torrentdata,filename):
        self.cursor.execute('''UPDATE episode_data SET path=?,torrent_data=?,file_name=? WHERE torrent=?''',
                            (path,torrentdata,filename,torrenturl))
        self.conn.commit()
                        
    def addEpisode(self,path,rssTitle,torrenturl,watched=0):
        '''parse the path into relevant stuff, use rssTitle to match against shana_title db'''
        '''return 1 if something has changed, 0 if not'''
        file_name = os.path.basename(path)
        try:
            episode = self.EPISODE_NUM.findall(rssTitle)[-1]
        except Exception as e:
            'no episode number means this is a pv or op/ed or something we should just ignore.'
            return 0
        display_name = rssTitle
        shana_title = self.SHANA_TITLE.findall(rssTitle)[0]
        try:
            subgroup = self.SUBGROUP.findall(rssTitle)[-1]
        except IndexError:
            subgroup = None
        self.cursor.execute('''SELECT id FROM shana_series WHERE title=?''',(shana_title,))
        lid = self.cursor.fetchone()#format is (lid,)
        if lid==None:
            self.cursor.execute('''INSERT INTO shana_series (title) VALUES (?)''', (shana_title,))
            self.conn.commit()
            self.cursor.execute('''SELECT id FROM shana_series WHERE title=?''',(shana_title,))
            lid = self.cursor.fetchone()['id']
        else:
            lid=lid['id']
        try:
            self.cursor.execute('''INSERT INTO episode_data (id,file_name,episode,path,display_name,watched,subgroup,torrent) VALUES (?,?,?,?,?,?,?,?)''',
                                                            (lid,file_name,episode,path,display_name,watched,subgroup,torrenturl))#downloaded,torrent_data,download_percent omitted
        except sqlite3.IntegrityError as msg:
            self.conn.commit()
            'means it already exists'
            'why didnt we just use replace here i dont know but too afraid to change it now.'
            'could be because we dont want to replace something we already edited (in an exisitng series) like the path or w/e'
            return 0
        else:
            #Since we got a new episode, unhide the series.
            self.cursor.execute('''UPDATE shana_series SET hidden=0,last_update=strftime('%s', 'now') WHERE id=?''',(lid,))
            self.conn.commit()
            return 1

    def getTorrentBlacklist(self):
        ' returns a set() of blacklisted torrents where each key is a url'
        ' also removes any outdated blacklist entries '
        self.cursor.execute('''DELETE FROM bad_torrents WHERE last_update<strftime('%s', 'now')-?''',(BLACKLIST_UPDATE_TIME,))
        self.conn.commit()
        self.cursor.execute('''SELECT url FROM bad_torrents''')
        return set([r['url'] for r in self.cursor.fetchall()])
##        return dict((key[0],0) for key in self.cursor.fetchall())
        
    def removeEpisode(self,torrenturl,blacklist = 1, permablacklist=False):
        ''' removes an episode by torrent url, also blacklists the url so the episode cannot be re-added'''
        self.cursor.execute('''DELETE FROM episode_data WHERE torrent=?''',(torrenturl,))
        if permablacklist:
            # this is a hack so we dont have to modify the table def
            self.cursor.execute('''REPLACE INTO bad_torrents (url,last_update) VALUES (?,9999999999999999)''',(torrenturl,))
        elif blacklist:
            self.cursor.execute('''REPLACE INTO bad_torrents (url) VALUES (?)''',(torrenturl,))
        self.conn.commit()

    'prioritizes null aids, then orders by last update (guess) of aid.'
    def updateOneUnknownAid(self):
        self.cursor.execute('''SELECT title from shana_series WHERE verified_aid=0 AND aid_update<strftime('%s', 'now')-? AND last_update>strftime('%s', 'now')-? ORDER BY CASE WHEN aid IS NULL THEN 0 ELSE aid_update+1 END LIMIT 1''',(AID_UPDATE_TIME,LAST_UPDATE_TIME))
        title = self.cursor.fetchone()
        if not title:
            return     
        self.cursor.execute('''UPDATE shana_series SET aid_update=strftime('%s', 'now'),aid=(
SELECT aid FROM (
    SELECT aid,editdist(alphatitle,alphainput) AS dist, ABS(LENGTH(alphainput)-LENGTH(alphatitle))+2 AS goaldist FROM (
        SELECT aid,removeNonAlphaAndSpaces(title) AS alphatitle,removeNonAlphaAndSpaces(?) AS alphainput FROM titles
        )
    ) WHERE dist <= goaldist ORDER BY dist ASC, aid DESC LIMIT 1) where title=?''',[title['title']]*2)
        self.conn.commit()
    
    def setDownloading(self,torrent_url,filename,torrentdata,percent_downloaded):
        path=(os.path.join(self.getSettings()['Download Directory'],filename))
        '''given the local id and episode number, mark an episode as downloaded. If download is complete, delete torrent data from db to reclaim space.'''
        downloaded=0
        if percent_downloaded==100:
            downloaded=1
        if downloaded:
            torrentdata = None
        self.cursor.execute('''UPDATE episode_data SET downloaded=?,file_name=?,path=?,torrent_data=?,download_percent=? WHERE torrent=?''',(downloaded,filename,path,torrentdata,percent_downloaded,torrent_url))
        self.conn.commit()

    def getAllWatchedPaths(self,path):
        '''gets a list of paths for all watched files/episodes for series matching the given filepath'''
##        self.cursor.execute('''SELECT path from episode_data WHERE id=? AND watched=1 AND downloaded=1''',(id,))
        self.cursor.execute('''SELECT path from episode_data WHERE id=(SELECT id FROM episode_data WHERE path=? LIMIT 1) AND watched=1 AND downloaded=1''',(path,))
        return set([r['path'] for r in self.cursor.fetchall()])

    def getAllPaths(self,id):
        '''gets a list of paths for all files/episodes for series with given id'''
        self.cursor.execute('''SELECT path from episode_data JOIN shana_series WHERE shana_series.id=episode_data.id AND shana_series.id=? AND downloaded=1''',(id,))
        return set([r['path'] for r in self.cursor.fetchall()])
        
    def changePath(self,oldPath,newPath):
        '''given the local id and episode number, change the path.'''
        self.cursor.execute('''UPDATE episode_data SET path=? WHERE path=?''',(newPath,oldPath))
        self.cursor.execute('''UPDATE parse_data SET path=? WHERE path=?''',(newPath,oldPath))
        self.conn.commit()
        
    def updateCoverArts(self,pairs):
        for aid,imgurl in pairs:
            self.cursor.execute('''UPDATE shana_series SET cover_art=strftime('%s', 'now'),last_poster_url=? WHERE aid=?''',(imgurl,aid))
        self.conn.commit()

    def updateSeriesInfo(self,tuples):#in format aid,airdate,seasonname,imgurl
        for aid,airdate,season,imgurl in tuples:
            self.cursor.execute('''UPDATE shana_series SET series_info=strftime('%s', 'now'),airdate=?,season=?,poster_url=? WHERE aid=?''',(airdate,season,imgurl,aid))
        self.conn.commit()

    def updateSeriesInfoTime(self,aids):
        for aid in aids:
            self.cursor.execute('''UPDATE shana_series SET series_info=strftime('%s', 'now') WHERE aid=?''',(aid,))
        self.conn.commit()
        
    def getOutdatedPosters(self):
        self.cursor.execute('''SELECT aid,title,season,poster_url,poster_url LIKE last_poster_url as nochange FROM shana_series WHERE cover_art<strftime('%s', 'now')-? AND poster_url IS NOT NULL AND last_update>strftime('%s', 'now')-?''',(COVER_UPDATE_TIME,LAST_UPDATE_TIME))
        return self.cursor.fetchall()
    
    def oneDayOldAids(self):
        self.cursor.execute('''SELECT aid FROM shana_series WHERE series_info<strftime('%s', 'now')-? AND last_update>strftime('%s', 'now')-? AND aid IS NOT NULL''',(SERIES_UPDATE_TIME,LAST_UPDATE_TIME))
        return set([r['aid'] for r in self.cursor.fetchall()])

    def hideOldSeries(self):
        '''
        will only hide older series if all episodes in that series are marked watched. if you're lagging behind on a series (or you dropped it) you can hide it manually with right-click.
        '''
        self.cursor.execute('''UPDATE shana_series SET hidden=1 WHERE hidden=0
                                AND (SELECT auto_hide_old FROM user_settings WHERE id=0)
                                AND (
                                    last_update<strftime('%s', 'now')-?
                                    OR
                                    (last_update<strftime('%s', 'now')-? AND (SELECT MAX(episode) FROM episode_data WHERE shana_series.id=episode_data.id)>7)
                                    )
                                AND (SELECT MIN(watched) FROM episode_data WHERE shana_series.id=episode_data.id)''',(LAST_UPDATE_TIME * 2, LAST_UPDATE_TIME))
        self.conn.commit()
        return self.cursor.rowcount

    def getUnhashed(self):
        self.cursor.execute('''SELECT path,id FROM parse_data WHERE ed2k IS NULL''')
        return set([r['path'] for r in self.cursor.fetchall()])

    def updateHash(self,path,ed2k,filesize):
        if path!=None:
            self.cursor.execute('''UPDATE parse_data SET ed2k=?,filesize=? WHERE path=?''',(ed2k,filesize,path))
        self.conn.commit()

    def updateHashes(self,hashed):
        for path in list(hashed.keys()):
            if hashed[path]!=None:
                self.cursor.execute('''UPDATE parse_data SET ed2k=?,filesize=? WHERE path=?''',(hashed[path][0],hashed[path][1],path))
        self.conn.commit()

    'note: if the aid is not verified it will be returned as NULL/None by this function.'
    'this is to prevent generic adds of series with uncertain aids.'
    '''also note: if you choose to return an aid regardless of its verified state, the series method
    ianidbadd will not function correctly as it only updates the aids for series which reportedly do not have one (null/none)
    therefore you will have to modify that method to always update aids'''
    # some clarification: an add attempt is made based on the last add attempt. the formula is: gap since last add = number of days since file was added /2  in hours.
    # in other words, a file that was hashed 200 days ago will wait 400 hours between successive anidb add attempts.
    # min is equiv to 2 days (so min of 4 hr between adds)

    # there is now a "force_generic_add" logic in place:
    # if a series has not been aid_verified for LAST_UPDATE_TIME since the series ended
    # (and it has an aid (guess) from updateoneunknownaid)
    # this function will return an aid instead of None which will in turn cause the generic add to go through despite the unverified aid.
    # this has a chance of mistakenly generic adding wrong series (will mostly be season 2 eps getting added as s2, etc)
    # this should rarely happen though, only if you maybe drop a s2 after 1 episode or something

    # the point of this force generic add feature is to prevent episodes just rotting in parse_data forever and never getting added while spamming anidb the whole time.
    def getToAdd(self):
        settings=self.getSettings()
        if not settings or not settings['anidb Username']:
            return None,[]
        self.cursor.execute('''SELECT path,
CASE WHEN verified_aid=0 AND last_update>strftime('%s', 'now')-? THEN NULL
ELSE aid END AS aid
,subgroup AS `group`,added_on,episode AS epno,ed2k,parse_data.id AS id,added_on<strftime('%s', 'now')-? as do_generic_add, verified_aid=0 AND last_update<strftime('%s', 'now')-? AS force_generic_add
                                FROM parse_data JOIN shana_series WHERE shana_series.id=parse_data.id AND ed2k NOT NULL AND strftime('%s', 'now') - 2*3600*((strftime('%s', 'now')-added_on)/86400+2) > last_add_attempt''', (LAST_UPDATE_TIME,ANIDB_WAIT_TIME,LAST_UPDATE_TIME))
        result = self.cursor.fetchall()       
        for file in result:
            self.cursor.execute('''UPDATE parse_data SET last_add_attempt=strftime('%s', 'now') WHERE ed2k=?''',(file['ed2k'],)) # go back in and updated the last_add_attempt of everything we are adding
        self.conn.commit()
        return settings,result
    
    def removeParsed(self,path,forceadded = False, aid=None):
        if forceadded:
            self.cursor.execute('''INSERT INTO anidb_force_added SELECT *,? FROM parse_data WHERE path=?''',(aid,path))
        self.cursor.execute('''DELETE FROM parse_data WHERE path=?''',(path,))
        self.conn.commit()

    def updateAids(self,aids):
        for pair in aids:
            self.cursor.execute('''UPDATE shana_series SET aid=?,verified_aid=1 WHERE id=?''',pair)
        self.conn.commit()

    def getAnidbSettings(self):
        self.cursor.execute('''SELECT delay,last_update,last_seriesinfo FROM anidb_limiting WHERE id=0''')
        result = self.cursor.fetchone()
        return result

    def anidbSetLastAdd(self,time):
        self.cursor.execute('''UPDATE anidb_limiting SET last_update=? WHERE id=0''',(time,))
        self.conn.commit()
    def anidbSetLastInfo(self,time):
        self.cursor.execute('''UPDATE anidb_limiting SET last_seriesinfo=? WHERE id=0''',(time,))
        self.conn.commit()
    def anidbSetDelay(self,delay):
        self.cursor.execute('''UPDATE anidb_limiting SET delay=? WHERE id=0''',(delay,))
        self.conn.commit()
        
