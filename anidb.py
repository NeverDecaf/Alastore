# -*- coding: utf-8 -*-
'''
provides methods to access anidb:
add_File()returns aid if not provided.
'''
DEBUG_ADD_CHAIN=0 # set to 1 to debug mylistadd failures
import socket
import time
import hashlib
import os
##import re
import gzip
# get info from http api
import requests
from xml.dom import minidom
from xml.parsers.expat import ExpatError
from functools import reduce
from PIL import Image
from io import BytesIO
from constants import *
GLOBAL_ANIDB_TIMER = time.time()
RETURN_CODES={
    505:'ILLEGAL INPUT OR ACCESS DENIED',
    555:'BANNED',
    598:'UNKNOWN COMMAND',
    600:'INTERNAL SERVER ERROR',
    601:'ANIDB OUT OF SERVICE - TRY AGAIN LATER',
    602:'SERVER BUSY - TRY AGAIN LATER',
    604:'TIMEOUT - DELAY AND RESUBMIT',
    501:'LOGIN FIRST',
    502:'ACCESS DENIED',
    506:'INVALID SESSION',
    }
NERFED = 0 # set true to disable for testing
def anidb_series_info(aid):
    if NERFED:
        return None,None
    global GLOBAL_ANIDB_TIMER,ANIDB_RATE_LIMIT
    # returns None,None if you are banned
    url='http://api.anidb.net:9001/httpapi?request=anime&client=%s&clientver=%s&protover=1&aid=%s'%(CLIENT,CLIENTVER,aid)
    try:
        time.sleep(max(ANIDB_RATE_LIMIT-time.time()+GLOBAL_ANIDB_TIMER,0))
        response = requests.get(url,headers=ANIDB_FAKE_HEADERS)
        GLOBAL_ANIDB_TIMER = time.time()
        response.raise_for_status()
        response.encoding = 'utf-8' # anidb default
        xmldoc = minidom.parseString(response.text)
        if len(xmldoc.getElementsByTagName('error')):
            val = xmldoc.getElementsByTagName('error')[0].firstChild.nodeValue
            if val.lower()=='banned':
                print('series info request failed (banned by anidb)')
                return None,None
            raise Exception('Anidb Error:',val)
        imageurl = ANIDB_IMG_URL_BASE.format(xmldoc.getElementsByTagName('picture')[0].firstChild.nodeValue)
        airdate = xmldoc.getElementsByTagName('startdate')[0].firstChild.nodeValue
        for episode in xmldoc.getElementsByTagName('epno'):
            if episode.getAttribute('type')=='1' and episode.firstChild.nodeValue=='3':
                airdate = episode.parentNode.getElementsByTagName('airdate')[0].firstChild.nodeValue
    except requests.Timeout as e:
        print('series info request timed out (due to ban) (%r)'%e)
        return None,None
    return (airdate,imageurl)

def anidb_title_list():
    if NERFED:
        return []
    global GLOBAL_ANIDB_TIMER,ANIDB_RATE_LIMIT
    time.sleep(max(ANIDB_RATE_LIMIT-time.time()+GLOBAL_ANIDB_TIMER,0))
    response = requests.get('http://anidb.net/api/anime-titles.xml.gz',headers=ANIDB_FAKE_HEADERS)
    GLOBAL_ANIDB_TIMER = time.time()
    response.raise_for_status()
    response.encoding = 'utf-8' # anidb default
    try:
        xmldoc = minidom.parseString(response.text)
    except ExpatError:
        # requests does not gzip deflate this, so we must do it manually. (perhaps its a header error, hard to check without getting banned.)
        xmldoc = minidom.parseString(gzip.decompress(response.content))
    
    itemlist = xmldoc.getElementsByTagName('anime')
    titles=[]
    for series in itemlist:
        aid=int(series.attributes['aid'].value)
        for title in series.childNodes:
            if title.nodeType!=title.TEXT_NODE:
                ttype=title.attributes['type'].value
                lang=title.attributes['xml:lang'].value
                title=title.firstChild.nodeValue
                if lang in ['x-jat','en','x-unk']:#x-unk is unknown... prob the default
                    titles.append((aid,ttype,lang,title))
    return titles

def anidb_dl_poster_art(imageurl):
    if NERFED:
        return None
    global GLOBAL_ANIDB_TIMER,ANIDB_RATE_LIMIT
    time.sleep(max(ANIDB_RATE_LIMIT-time.time()+GLOBAL_ANIDB_TIMER,0))
    response = requests.get(imageurl,headers=ANIDB_FAKE_HEADERS)
    GLOBAL_ANIDB_TIMER = time.time()
    lazyopen = Image.open(BytesIO(response.content))
    lazyopen.load() # fix for a bug in PIL 1.1.7
    return lazyopen
        
class anidbInterface:
    LOCALPORT = 30575
    STATE = 1 # on hdd
    ## 0 - unknown - state is unknown or the user doesn't want to provide this information
    ## 1 - on hdd - the file is stored on hdd (but is not shared)
    ## 2 - on cd - the file is stored on cd
    ## 3 - deleted - the file has been deleted or is not available for other reasons (i.e. reencoded)
    VIEWED = 1
    socket=None
    SK=None
    def __init__(self,port=LOCALPORT):
        if NERFED:
            return None
        self.LOCALPORT=port
        self._setup()
        
            
##    ERROR_FILE = 'anidb_failed_mylist_adds.log'
##    def report_failure(path,s=None,reason=None):
##        with open(ERROR_FILE,'ab') as er:
##            er.write(path+'\r\n')
##            if reason:
##                er.write('\t'+str(reason)+'\r\n')
##            er.close()
##        if s!=None:s.close()
##        pass

##    def end_session(self):
##        self._close_socket()
        
    def open_session(self,user,passw):
        if user==None or passw==None:
            self.SK=None
            self.socket=None
            return None
        try:
            if not self._auth(user,passw):
                return None
        except socket.timeout as e:
            print(("anidb auth timed out: %r"%e))
            return 0
        except Exception as e:
            print(("error with anidb auth: %r"%e))
            return None
        return -1
        
    def close(self):
        if not self.socket:
            return None
        self._logout()
        self._close_socket()

    'should return -1 or aid on success'
    'None or 0 on failure'
    def add_file(self,path,aid,group,epno,ed2k,do_generic_add,viewdate):
        ''' path should be the full path '''
        if not self.SK:
            return None #there was a problem somewhere in logging in but we'll just ignore it and come back later
##        hashingisslow = time.time()
##        ed2k_hash = self._ed2k_hash(path)
##        while time.time()-hashingisslow<2:pass
        try:
            if DEBUG_ADD_CHAIN:
                print('adding with vars:',path,aid,group,epno,ed2k,do_generic_add,viewdate)
            aid=self._add(ed2k,aid,group,epno,do_generic_add,viewdate)
        except Exception as e:#socket.error,e:
            print(("error with anidb add: %r"%e))
            return None
        #only need this if we are issuing another command.. but do it anyway just for safety
        if aid==None:
            return aid
        return int(aid)
        
    def _setup(self):
        '''Sets up the UDP connection to anidb'''
        host = 'api.anidb.net'
        textport = "9000"

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(20)
        port = int(textport)
        self.socket.bind(('',self.LOCALPORT))#bind to local port
        try:
            self.socket.connect((host, port))
        except socket.error as e:
            print(("There was an error: %r" % e))
            self._close_socket()
        return self.socket
        
    ###############
    ## hash code ##
    ###############
    @staticmethod
    def ed2k_hash(file_path):
        """ Returns the ed2k hash of a given file. """
        md4 = hashlib.new('md4').copy

        def gen(f):
            while True:
                x = f.read(9728000)
                if x: yield x
                else: return

        def md4_hash(data):
            m = md4()
            m.update(data)
            return m

        with open(file_path, 'rb') as f:
            a = gen(f)
            hashes = [md4_hash(data).digest() for data in a]
            if len(hashes) == 1:
                md4 = hashes[0].encode("hex")
            else: md4 = md4_hash(reduce(lambda a,d: a + d, hashes, b'')).hexdigest()
            f.close()
            
        return 'ed2k://|file|'+os.path.basename(file_path)+'|'\
            +str(os.path.getsize(file_path))+'|'+str(md4)+'|',os.path.getsize(file_path)
    
    ##############
    #### AUTH ####
    ##############
    # returns session key
    def _auth(self,USERNAME,PASSWORD):
        global GLOBAL_ANIDB_TIMER,ANIDB_RATE_LIMIT
        self.SK=None
        if not self.socket:
            return None
        '''auths with anidb using passed credentials and socket. returns None on failure.'''
        data = 'AUTH user='+USERNAME+'&pass='+PASSWORD+'&protover=3&client=%s&clientver=%s'%(UDPCLIENT,UDPCLIENTVER)
        time.sleep(max(ANIDB_RATE_LIMIT-time.time()+GLOBAL_ANIDB_TIMER,0))
        self.socket.sendall(data.encode('utf8'))
        GLOBAL_ANIDB_TIMER = time.time()
        
        buf = self.socket.recv(2048).decode('utf8')
        if str(buf).split(' ')[0] != '200':
            return None
        self.SK=str(buf).split(' ')[1]
        return self.SK

    ##############
    #### ADD #####
    ##############
    def _add(self,full_ed2k,aid=None,group=None,epno=None,do_generic_add=0,viewdate=None):
        global GLOBAL_ANIDB_TIMER,ANIDB_RATE_LIMIT
        '''Adds the given file to mylist, on failure attempts to add a generic file. returns None on failure.'''
        ed2k=full_ed2k.split('|')[4]
        filesize=full_ed2k.split('|')[3]
        data = 'MYLISTADD size={}&ed2k={}&state={}&viewed={}&s={}'.format(filesize,ed2k,self.STATE,self.VIEWED,self.SK)
        if viewdate:
            data += '&viewdate={}'.format(viewdate)
        time.sleep(max(ANIDB_RATE_LIMIT-time.time()+GLOBAL_ANIDB_TIMER,0))
        self.socket.sendall(data.encode('utf8'))
        GLOBAL_ANIDB_TIMER = time.time()
        
        buf = self.socket.recv(2048).decode('utf8')
        if str(buf).split(' ')[0] =='320':
            if aid:
                if DEBUG_ADD_CHAIN:
                    print('NO SUCH FILE, performing generic add with vars:',aid,group,epno,do_generic_add,viewdate)
                return self._add_generic(aid,group,epno,do_generic_add,viewdate)
            else:
                if DEBUG_ADD_CHAIN:
                    print('No aid provided, returning none as generic add cannot be done without aid.')
                return None#can't add generic without aid. try later.
        if str(buf).split(' ')[0] =='210':
            if DEBUG_ADD_CHAIN:
                print('add returned 210, should be successful')
            lid=str(buf).split('\n')[1]
            if lid=='0':
                if DEBUG_ADD_CHAIN:
                    print('impossible error')
                return None#failure, though im not sure if this can occur here or only in generic add
            if not aid:
                return self._get_aid(lid)
            else:
                return -1
        if str(buf).split(' ')[0] =='310':
            if not aid:
                return str(buf).split('|')[3]
            else:
                return -1
        
        return None #failure

    ###########################################
    #### CHECK FOR (GENERIC) FILE IN LIST #####
    ###########################################
    def _check_exists(self,aid,epno):
        global GLOBAL_ANIDB_TIMER,ANIDB_RATE_LIMIT
        '''Checks for a file by aid and episode number. used to verify generic adds.'''
        data = 'MYLIST aid='+str(aid)+'&epno='+str(epno)+'&s='+self.SK
        time.sleep(max(ANIDB_RATE_LIMIT-time.time()+GLOBAL_ANIDB_TIMER,0))
        self.socket.sendall(data.encode('utf8'))
        GLOBAL_ANIDB_TIMER = time.time()
        
        buf = self.socket.recv(2048).decode('utf8')
        return str(buf).split(' ')[0] !='321' # 321 is the code for NO SUCH ENTRY
        
    ##############################
    #### GET AID FROM MYLIST #####
    ##############################
    def _get_aid(self,lid):
        global GLOBAL_ANIDB_TIMER,ANIDB_RATE_LIMIT
        '''Retreives the aid for the file in mylist referenced by list id.'''
        data = 'MYLIST lid='+str(lid)+'&s='+self.SK
        time.sleep(max(ANIDB_RATE_LIMIT-time.time()+GLOBAL_ANIDB_TIMER,0))
        self.socket.sendall(data.encode('utf8'))
        GLOBAL_ANIDB_TIMER = time.time()
        
        buf = self.socket.recv(2048).decode('utf8')
        if str(buf).split(' ')[0] =='221':
            #{int4 lid}|{int4 fid}|{int4 eid}|{int4 aid}|{int4 gid}|{int4 date}|{int2 state}|{int4 viewdate}|{str storage}|{str source}|{str other}|{int2 filestate}
            return str(buf).split('|')[3]#this should be the aid.
        return -1 #failure to get aid. doesn't mean the initial add failed so just return -1
    ######################
    #### ADD GENERIC #####
    ######################

    def _add_generic(self,aid,group,epno,do_generic_add,viewdate):
        global GLOBAL_ANIDB_TIMER,ANIDB_RATE_LIMIT
        '''Adds the given generic file to mylist. returns None on failure.'''
        ''' IMPORTANT TO NOTE: when doing MYLISTADD by aid instead of file(ed2k) a lid is NOT returned, instead the number of files added is returned'''
        ''' EVEN MORE IMPORTANT NOTE:
            MYLISTADD with generic=1 CANNOT return code 310 (file already in list) so it will return 210 MYLIST ENTRY ADDED
            If the file already exists it reports 0 files added, which is true because the file already exists.
            HOWEVER, the problem is it also reports 210 0 files added on FAILURE.
            This means there is no way to determine whether a generic MYLISTADD failed because the file is already in mylist or because it could not be added.
            Because of this, we must first check to see if the file already exists in mylist before attempting any kind of generic add.'''
        
        if DEBUG_ADD_CHAIN:
            print('adding generic with vars:',aid,group,epno,do_generic_add,viewdate)

        if self._check_exists(aid,epno):
            if DEBUG_ADD_CHAIN:
                print('file already in mylist, returning success')
            return -1
        
##        'try to do a group name add first'
        if group:
            data = 'MYLISTADD aid={}&gname={}&epno={}&state={}&viewed={}&s={}'.format(aid,group,epno,self.STATE,self.VIEWED,self.SK)
            if viewdate:
                data+= '&viewdate={}'.format(viewdate)
            time.sleep(max(ANIDB_RATE_LIMIT-time.time()+GLOBAL_ANIDB_TIMER,0))
            self.socket.sendall(data.encode('utf8'))
            GLOBAL_ANIDB_TIMER = time.time()
            
            buf = self.socket.recv(2048).decode('utf8')
            if DEBUG_ADD_CHAIN:
                    print('result of generic add(1):',buf)
            if str(buf).split(' ')[0] =='210':
                added=str(buf).split('\n')[1]
                if added=='1':# this will be 0 if the add failed, despite the code 210 indicating a success (of 0 files added)
                    return -1 #success
        
##        'if the gname add failed (group not in anidb) we will try a simple generic add'
        if do_generic_add:
            data = 'MYLISTADD aid={}&generic=1&epno={}&state={}&viewed={}&s={}'.format(aid,epno,self.STATE,self.VIEWED,self.SK)
            if viewdate:
                data+= '&viewdate={}'.format(viewdate)
        else:
            return None#failure, not time yet for generic add

        if DEBUG_ADD_CHAIN:
            print('attempting generic add (w/o gname)')
        time.sleep(max(ANIDB_RATE_LIMIT-time.time()+GLOBAL_ANIDB_TIMER,0))
        self.socket.sendall(data.encode('utf8'))
        GLOBAL_ANIDB_TIMER = time.time()
        
        buf = self.socket.recv(2048).decode('utf8')
        if DEBUG_ADD_CHAIN:
                print('result of generic add(2):',buf)
        if str(buf).split(' ')[0] =='210':
            added=str(buf).split('\n')[1]
            if added=='1':
                return -1 #success
        return None #failure

    ##############
    ### LOGOUT ###
    ##############
    def _logout(self):
        global GLOBAL_ANIDB_TIMER,ANIDB_RATE_LIMIT
        '''Log out of mylist'''
        if not self.SK:
            return None
        data = 'LOGOUT s='+self.SK
        self.SK=None
        time.sleep(max(ANIDB_RATE_LIMIT-time.time()+GLOBAL_ANIDB_TIMER,0))
        self.socket.sendall(data.encode('utf8'))
        GLOBAL_ANIDB_TIMER = time.time()
        buf = self.socket.recv(2048).decode('utf8')
        if str(buf).split(' ')[0] =='203':
            return 1 # success
        return None
    
    def _close_socket(self):
        if not self.socket:
            return None
        self.socket.close()
        self.socket=None

if __name__ == '__main__':
##    import asyncio
##    titleList=anidb_title_list()
##    import sql
##    _sqlManager = sql.SQLManager()
##    async def say():
##        await _sqlManager.cacheTitles(titleList)
##
##    loop = asyncio.get_event_loop()
##    loop.run_until_complete(say())
##    loop.close()

##    print(len(anidb_title_list()))
    
    from contextlib import closing
    files = [r'']
    with closing(anidbInterface()) as a:
        a.open_session(username,password)
        for path in files:
            hashe = a.ed2k_hash(path)
            a.add_file(None,None,None,None,hashe[0],0,None)
    
