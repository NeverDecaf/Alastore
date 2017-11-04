'''
maintains a listing of all series currently being watched.
has methods to check the filesystem/rss for new downloads to refresh its data.
also has methods to move/play the files and start the anidb add process.
basically this is the controller class for all the other classes.
'''
import sql
import rss
import os
import anidb
if os.name=='nt':
    import makeico
import re
import torrentprogress
import StringIO
import shutil
from bencode import BTFailure
import logging
import errno
from shana_interface import ShanaLink
import stat

class SeriesList:
    series=None
    SQL=None
    RSS=None
    user_settings=None
    def __init__(self):
        if os.path.exists('DEBUG_TEST'):
            logging.basicConfig(level=logging.DEBUG, filename='DEBUG.log')
        else:
            logging.basicConfig(level=logging.DEBUG, stream=StringIO.StringIO())
            logging.disable(logging.DEBUG)
        self.SQL=sql.SQLManager()
        self.SQL.connect()
        self.RSS=rss.RSSReader()
        self.series={}
        self.SHANALINK = ShanaLink()
        #just init the bare minimum things.
        self._getUserSettings()
        self._populateSeries()
##        self.doUpdates(True)

    def _populateSeries(self):
        self.series = self.SQL.getSeries()

    def DownloadTorrents(self):
        for episode in self.removeInvalidTorrents:
            self.SQL.removeEpisode(episode[0],episode[1])
        for data in self.torrentDatum:
            self.SQL.addTorrentData(data[0],data[1],data[2],data[3])
        return len(self.torrentDatum) + len(self.removeInvalidTorrents)
            
    def iDownloadTorrents(self):
        'download all new torrent files'
        self.torrentDatum = []
        self.removeInvalidTorrents = []
        for entry in self.newEntries:
            torrent = torrentprogress.download_torrent(entry[2])
            if torrent:
                torrentdata=buffer(torrent)
                try:
                    filename = torrentprogress.file_name(StringIO.StringIO(torrentdata))
                except BTFailure,e:
                    print 'initial bencode failed %r'%e
                    if str(e)=='not a valid bencoded string' or str(e)=='torrent contains multiple files':
                        print 'pre-removing %s.'%entry[1]
                        self.removeInvalidTorrents.append((entry[2],len(torrentdata)))
                        continue
                path = os.path.join(self.user_settings['Download Directory'],filename)
                self.torrentDatum.append((path,entry[2],torrentdata,filename))
            
        return len(self.torrentDatum)

    def prepLoadRSS(self):
        self.torrentBlacklist = self.SQL.getTorrentBlacklist()
    
    def loadRSS(self):
        '''downloads RSS feed and loads its contents into the db'''
        self.newEntries = []
        if not self.user_settings:
            return -1
        for item in self.rssitems:
            if item[2] not in self.torrentBlacklist:
                                                                                            #file name, rsstitle,torrent url 
                if self.SQL.addEpisode(os.path.join(self.user_settings['Download Directory'],item[1]),item[0],item[2]):
                    self.newEntries.append(item)
        return len(self.newEntries)

    def iloadRSS(self):
        if not self.user_settings:
            return -1
        self.rssitems=self.RSS.getFiles(self.user_settings['RSS Feed'])

    def checkFiles(self):
        '''Scans the download directory for any matches'''
        if not self.user_settings:
            return 0
        for episode in self.changedFiles:
            self.SQL.setDownloading(episode[0],episode[1],episode[2],episode[3])
        for episode in self.removeInvalid:
            self.SQL.removeEpisode(episode)
        return len(self.changedFiles)

    
    
    # STRONGLY recommended that you call populateseries before running this method.
    def icheckFiles(self):
##        import time
##        start = time.time()
        '''Scans the download directory for any matches'''
        self.changedFiles=[]
        self.removeInvalid=[]
        if not self.user_settings:
            return -1
        dl_dir = self.user_settings['Download Directory']#.decode('utf8')
##        potentialFiles=os.listdir(dl_dir)
        # we replace space with _ here, make sure to do this to all the strings you want to match.
        originalFiles = os.listdir(dl_dir)
        potentialFiles = map(lambda x: re.sub(ur'[ ]',ur'_',x), originalFiles)
        potentialMatches = dict(zip(potentialFiles,originalFiles))
##        contString=u'\n'.join(potentialFiles)+u'\n'
        for series in self.series.values():
            for episode in series:
                # narrow the search to undownloaded, unwatched series to save time. (also you can ignore hidden series)
                if episode['downloaded']==0 and episode['watched']==0 and episode['hidden']==0:
##                    # basically we want to match the episode name excepting '_' for ' ' if necessary
##                    # meaning 'the game' will match to 'the game' or 'the_game'
##                    workingFile = episode['file_name']#.decode('utf8')
##                    # we also need to check for invalid filename chars, which shanaproject replaces with _ (probably)
##                    # ur'\/:*?"<>|'
##                    matcher = re.compile(ur'('+
##                                         re.sub(ur'\\ ',ur'[ _]',re.escape(re.sub(ur'[\/:*?"<>|]',ur'_',workingFile)))
##                                         +u')\n')#(\.!ut)?\n')
##                    match = matcher.search(contString)
                    pattern,replacement = self.RSS.invalidCharReplacement(self.user_settings['RSS Feed'])                    
                    workingFile = re.sub(pattern,replacement,episode['file_name'])
##                    if match:
                    if workingFile in potentialMatches:
                        filename = potentialMatches[workingFile]
                        # we only want to find NEWLY downloaded files so only check those that aren't marked.
##                        if episode['downloaded']==0:# and workingFile in potentialFiles:
                        #this is a downloading file that is just not completely downloaded.
##                        path=os.path.join(dl_dir,match.group(1))
                        path=os.path.join(dl_dir,filename)
                        torrentdata=episode['torrent_data']
                        percent_downloaded=episode['download_percent']

                        if not torrentdata:
                            torrent = torrentprogress.download_torrent(episode['torrent_url'])
                            if torrent:
                                torrentdata=buffer(torrent)
                        if torrentdata:
##                            if match.group(2):
##                                path = path+match.group(2)
                            try:
                                percent_downloaded, torrentdata=torrentprogress.percentCompleted(StringIO.StringIO(torrentdata),path)
                            except BTFailure,e:
                                print 'bencode failed %r'%e
                                if str(e)=='not a valid bencoded string' and len(torrentdata):
                                    print 'episode (%s) was removed.'%episode['display_name']
                                    self.removeInvalid.append(episode['torrent_url'])
                                    continue
                                
##                            print 'torrent hashing took %f seconds'%(time.time()-star)
##                        self.changedFiles.append((episode['torrent_url'],match.group(1),torrentdata,percent_downloaded))
                        self.changedFiles.append((episode['torrent_url'],filename,torrentdata,percent_downloaded))
##        print 'checkfiles took %f seconds'%(time.time()-start)
        
    def prepCheckFiles(self):
        return
    
    def watchfile(self,filepath):
        import sys,subprocess, os
        if sys.platform.startswith('darwin'):
            subprocess.call(('open', filepath))
        elif os.name == 'nt':
            os.startfile(filepath)
        elif os.name == 'posix':
            subprocess.call(('xdg-open', filepath))

    def dropSeries(self, title, delete):
        self.SQL.hideSeries(title)
        if delete:
            paths = self.SQL.getAllPaths(title)
            for path in paths:
                directory = os.path.dirname(path[0])
                if os.path.isfile(path[0]):
                    os.remove(path[0])
                self.cleanFolder(directory)
            self.SQL.dropSeries(title)

##    def dropSeries(self, title, delete):
##        try:
##            if self.SHANALINK.delete_follow(title):
##                #only hide if successful.
##                self.SQL.hideSeries(title)
##                if delete:
##                    import shutil
##                    paths = self.SQL.getAllPaths(title)
##                    for path in paths:
##                        directory = os.path.dirname(path[0])
##                        if os.path.exists(directory):
####                            shutil.rmtree(directory, ignore_errors=True)
##                            print 'rming %s'%directory
##                    
##                return 1
##        except:
##            raise
##            return 0
##        return 0

    def validShanaProjectCredentials(self):
        return not not self.user_settings['Shana Project Username'] and not not self.user_settings['Shana Project Password']
    
    #data in this case is the list that can be obtained from self.series
    #it contains all the info available about a specific episode, making it easy to manipulate it.
    def prepPlayAndSort(self):
        '''move/sort the episode into its proper folder then play it in the default media player.
            also queue the file for anidb add and update its watched status in the db'''
        self._getUserSettings()
        self._populateSeries()
        if not self.user_settings:
            return -1
        return 0
    
    def playAndSort(self,data):
        if data['watched']:
            self.watchfile(data['path'])#.decode('utf8'))
            return 'watched','watched'
        import shutil
        shana_title = data['title']#self.SQL.getSeriesTitle(data['id'])#.decode('utf8')
        st_dir = self.user_settings['Save Directory']#.decode('utf8')
        folder_title = ur''.join(i for i in shana_title if i not in ur'\/:*?"<>|.')

        # check usersettings for usesubfolders.
        # if true/false move existing files from one to the other

        toplevel_folder = os.path.join(st_dir,folder_title)
        season=data['season']#self.SQL.getSeriesSeason(data['id'])
        if season:
            year = season.split()[1]
            seasonsorted_folder = os.path.join(st_dir,year,season,folder_title)
            
        
        if self.user_settings['Season Sort'] and season:
            dest_folder = seasonsorted_folder
        else:
            dest_folder = toplevel_folder

        dest_file = os.path.join(dest_folder,data['file_name'])
        
        if not os.path.isdir(dest_folder):
            os.makedirs(dest_folder)
        if not os.path.exists(dest_file):
            shutil.move(data['path'],dest_file)#.decode('utf8'),dest_file)
        self.watchfile(dest_file)
##        self.SQL.watchMoveQueue(data['path'],dest_file)
        try:
            if season and self.user_settings['Season Sort']:
                self.moveAllToFolder(data['id'], seasonsorted_folder)
            else:
                self.moveAllToFolder(data['id'], toplevel_folder)
        except Exception, e:
            print 'Unexpected error, moveAllToFolder @ series.py failed: %r'%e
        return data['path'],dest_file

    def playAndSortFinalize(self,path,dest_file):
        self.SQL.watchMoveQueue(path,dest_file)
        self._populateSeries()

    def moveAllToFolder(self, id, dest):
        episodes = self.SQL.getAllWatchedPaths(id)
        for episode in episodes:
            path = episode[0]
            directory = os.path.dirname(path)
            filename = os.path.basename(path)
            if directory!=dest and os.path.exists(directory):
                destfile = os.path.join(dest,filename)
                try:
                    shutil.move(path,destfile)
                    self.SQL.changePath(path,destfile)
                except IOError,e:
                    print 'failed to move file: %r'%e
                self.cleanFolder(directory)

    # BE VERY CAREFUL WITH THIS.
    def cleanFolder(self,path):
        if os.path.isdir(path):
            files = os.listdir(path)
            if len(files)<=2:
                isEmpty = not reduce(lambda x,y: x or not (y.endswith('.ico') or y.endswith('esktop.ini')), [0]+files)
                if isEmpty:
                    shutil.rmtree(path, onerror=self.remove_readonly)
                
    # AND EVEN MORE CAREFUL WITH THIS
    def remove_readonly(self, func, path, excinfo):
        os.chmod(path, stat.S_IWRITE)
        func(path)

    def close(self):
        self.SQL.close()

    def sqlIndependantUpdates(self,quick=False):
        ''' this method will do all the time intensive tasks and leave the data available to be stored later'''
        ''' this really isnt thread safe at all so make sure you arent trying to use this data before/during its gathered'''
    def sqlUpdate(self,quick=False):
        ''' the other half of the update. should only be called after independantupdates are COMPLETED.'''
        self._populateSeries()

    def hashFiles(self):
        '''performs ed2k hash on any new files. will be used later for anidb add'''
        self.SQL.updateHashes(self.toHash)

    def ihashFiles(self):
        '''hashes the selected files, also downloads poster art if applicable'''
        hasherrors = 0
        for file in self.toHash.keys():
            try:
                ed2k,filesize=anidb.anidbInterface.ed2k_hash(file)
                self.toHash[file]=(ed2k,filesize)
            except:
                # if hashing fails on one file, we don't want to exclude the others.
                hasherrors+=1
        return hasherrors
            
    def prepHashFiles(self):
        self.toHash = self.SQL.getUnhashed()

    def makeIcon(self):
        self.SQL.updateCoverArts(self.successfulIcons)
                
    def iMakeIcon(self):
        '''hashes the selected files, also downloads poster art if applicable'''
        self.successfulIcons=[]
        if not self.user_settings:
            return -1
        for aid,title,season,imgurl,nochange in self.newIcons:
            folder_title = ur''.join(i for i in title if i not in ur'\/:*?"<>|.')
            dest_folder = os.path.join(self.user_settings['Save Directory'],folder_title)
            if self.user_settings['Season Sort'] and season:
                year = season.split()[1]
                dest_folder = os.path.join(self.user_settings['Save Directory'],year,season,folder_title)
            try:
                try:
                    if aid and os.path.exists(dest_folder) and (not os.path.exists(os.path.join(dest_folder,u'%i.ico'%aid)) or not nochange):
                        makeico.makeIcon(aid,imgurl,dest_folder)
                    self.successfulIcons.append((aid,imgurl))
                except IOError,e:
                    if e.errno!=errno.ENOENT:
                        raise
                    else:
                        '''errno 2 is file/directory does not exist.
                        this simply means you tried to get poster art before any episodes were downloaded.
                        we will just try to get the art again at a later date'''
                        self.successfulIcons.append((aid,None))
            except Exception, e:
                print 'failed to download series image for %s b/c %r'%(title,e)
                self.successfulIcons.append((aid,None))
        
    def prepMakeIcon(self):
        self.newIcons = []
        if not self.user_settings:
            return
        if os.name == 'nt' and self.user_settings['Poster Icons']: # only works on windows.
            self.newIcons = self.SQL.getOutdatedPosters()
##        self.newIds = self.SQL.getNewIds()

    def anidbAdd(self):
        self.SQL.removeParses(self.parseRemove)
        self.SQL.updateAids(self.newAids)
##        if len(self.anidbAddSQL):
##            self.SQL.execScript(self.anidbAddSQL)
    def ianidbAdd(self):
##        self.anidbAddSQL=u''
        self.parseRemove=[]
        self.newAids=[]
        if not self.userSettings or not len(self.toAdd) or not self.userSettings['anidb Username'] or not self.userSettings['anidb Password']:
            return None
        anidbLink = anidb.anidbInterface()
        if len(self.toAdd):
            try:
                if anidbLink.open_session(self.userSettings['anidb Username'],self.userSettings['anidb Password']):
                    for datum in self.toAdd:
                        aid=anidbLink.add_file(datum[0],datum[1],datum[2],datum[3],datum[4],datum[6])
                        # these match with: status, filepath, aid, subgroup, epnum, ed2k, do_generic_add
                        logging.debug('anidb add status:%s, vars used: %s\t%s\t%s\t%s\t%s\t%s'%(aid,datum[0],datum[1],datum[2],datum[3],datum[4],datum[6]))
                        if aid:#if the add succeeded.
                            self.parseRemove.append(datum[0])
        ##                    self.anidbAddSQL+=u'DELETE FROM parse_data WHERE \'%s\';'%datum[0]
                            if not datum[1] and aid>0: # if an aid did not exist but was returned by add
                                self.newAids.append((aid,datum[5]))
        ##                    self.anidbAddSQL+=u'UPDATE shana_series SET aid=%s WHERE id=%s;'%(aid,datum[5])
                    anidbLink.close_session()
            finally:
                anidbLink.end_session()

    def prepAnidbAdd(self):
        self.userSettings,self.toAdd=self.SQL.getToAdd()

    def getSeriesInfo(self):
        self.SQL.updateSeriesInfo(self.toGetSeriesInfoAdds)
        self.SQL.updateSeriesInfoTime(self.toGetSeriesInfoFailedAdds)
    
    def iGetSeriesInfo(self):
        import time
        self.toGetSeriesInfoAdds=[]
        self.toGetSeriesInfoFailedAdds=[]
        wait= time.time()
        for wrappertuple in self.toGetSeriesInfo:
            aid=wrappertuple[0]
            try:
                while time.time() - wait < 2: pass
                airdate,imgurl = anidb.anidb_series_info(aid)
                wait = time.time()
                SEASONS = ['Spring','Summer','Fall','Winter']
                import datetime
                date = datetime.datetime.strptime(airdate,'%Y-%m-%d')
                sixtydays = datetime.timedelta(60)
                date-=sixtydays
                dayofyear = int(date.strftime('%j'))
                dayofseason = datetime.timedelta(dayofyear%91)
                date -= dayofseason
                date += sixtydays
                seasonindex =(dayofyear-(dayofyear%91))/91
                seasonname= '%s %s'%(SEASONS[seasonindex],date.strftime('%Y'))

                self.toGetSeriesInfoAdds.append((aid,airdate,seasonname,imgurl))
            except Exception, e:
                print 'anidb_series_info failed on %s b/c %r'%(aid,e)
                self.toGetSeriesInfoFailedAdds.append(aid)
                
    def prepGetSeriesInfo(self):
        self.toGetSeriesInfo = self.SQL.oneDayOldAids()#note this will be tuples like (aid,)

    def cacheTitles(self):
        if self.titleList:
            self.SQL.cacheTitles(self.titleList)

    def iCacheTitles(self):
        # do anidb.titlecache or w/e
        self.titleList=None
        if self.titleUpdateTime:
            self.titleList = anidb.anidb_title_list()

    def prepCacheTitles(self):
        self.titleUpdateTime = self.SQL.titleUpdateTime()

    def _getUserSettings(self):
        self.user_settings=self.SQL.getSettings()
        if self.user_settings:
            self.SHANALINK.update_creds(self.user_settings['Shana Project Username'],self.user_settings['Shana Project Password'])
    # these are all the phases of an update. anything with Thread is meant to be time intensive
    # and should be run in a separate thread. the other functions should be very light and execute
    # instantaneously from a human viewpoint.
    def phase1Prep(self,quick=False):
        self._getUserSettings()
        if not self.user_settings:
            return False
        self._populateSeries()
        self.SQL.hideOldSeries()
        self.prepLoadRSS()
        if not quick:
            self.prepCacheTitles()
            self.prepHashFiles()
        return True
            
    def phase1Thread(self,quick=False):
        self.iloadRSS()
        if not quick:
            self.iCacheTitles()
            self.ihashFiles()
            
    def phase1Gap(self,quick=False):
        self.phase1Changes = 0
        self.phase1Changes += self.loadRSS()
        return self.phase1Changes
        
    def phase1Thread2(self,quick=False):
        self.iDownloadTorrents()
        
    def phase1End(self,quick=False):
        self.phase1Changes += self.DownloadTorrents()
        if not quick:
            self.cacheTitles()
            self.hashFiles()
        return self.phase1Changes

    # phase 2 quick must only contain checkfiles.
    # it is special in that instead of normal changes it reports the number
    # of files currently being downloaded. it is also used in the quick check (not anymore)
    # for ONLY changes files.
    # I recommend you don't modify any phase2 function unless you know what youre doing
    def phase2Prep(self,quick=False):
        self.prepCheckFiles()
        if not quick:
            self.prepAnidbAdd()
    def phase2Thread(self,quick=False):
        self.icheckFiles()
        if not quick:
            self.ianidbAdd()
    def phase2End(self,quick=False):
        changes=0
        changes+=self.checkFiles()
        if not quick:
            self.SQL.updateOneUnknownAid()### This is probably the longest operation in all of the update
            self.anidbAdd()
        return changes
    def phase3Prep(self,quick=False):
        if not quick:
            self.prepGetSeriesInfo()
            self.prepMakeIcon()
        pass
    def phase3Thread(self,quick=False):
        if not quick:
            self.iGetSeriesInfo()
            self.iMakeIcon()
        pass
    def phase3End(self,quick=False):
        changes=0
        if not quick:
            self.getSeriesInfo()
            self.makeIcon()
        return changes

if __name__=='__main__':
    s=SeriesList()
    s.prepAnidbAdd()
    s.ianidbAdd()
