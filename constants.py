import sys,os,re
##try:
##    sys._MEIPASS
##    os.chdir(os.path.dirname(sys.executable))
##except:
##    os.chdir(os.path.dirname(os.path.realpath(__file__)))    

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(base_path, relative_path)

def storage_path(relative_path):
    """ Get absolute path to dir where .exe or .py is located. """
    try:
        sys._MEIPASS
        base_path = os.path.dirname(sys.executable)
    except Exception:
        base_path = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(base_path, relative_path)

#torrentprogress:
TORRENT_HEADERS = {'User-Agent':'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.0.7) Gecko/2009021910 Firefox/3.0.7'}# we will now get a 403 without these, it might not be long before we need cookies too.

#anidb:
ANIDB_RATE_LIMIT = 2.5 # specified as 2s but add a bit to be safe.
ANIDB_FAKE_HEADERS={
'Accept-Charset':'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
'Accept-Encoding':'gzip',
'Accept-Language':'en-US,en;q=0.8',
'User-Agent':'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.56 Safari/535.11',
    }
ANIDB_RATE_LIMIT = 2.5 # specified as 2s but add a bit to be safe.
ANIDB_IMG_URL_BASE = 'http://img7.anidb.net/pics/anime/{}'
CLIENT='alastorehttp'
CLIENTVER='1'
UDPCLIENT='alastore'
UDPCLIENTVER='1'

#shana_interface:
SP_LOGIN_URL = 'https://www.shanaproject.com/login/'
SP_LIST_URL = 'http://www.shanaproject.com/follows/list/'
SP_DELETE_URL = 'http://www.shanaproject.com/ajax/delete_follow/'
SP_LOGGED_IN_XPATH = "//a[@href='/logout/']"

#sql:
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

COLUMN_NAMES = ['RSS Feed','Download Directory','Save Directory','anidb Username','anidb Password','Season Sort','Poster Icons','Auto Hide Old','Shana Project Username','Shana Project Password']

RSS_TITLE_RE = re.compile('.*(?= - \d)') #title as given in rss feed.

#Alastore:
FULLUPDATE_TIME = 60 * 10 #once every 10 m
INITIALUPDATE_GRACEPERIOD = 30 # this is time before the first (only) quick update
FULLUPDATE_GRACEPERIOD = 60*5 # 5m time before first full update
ANIDB_DEFAULT_DELAY = 675
ANIDB_MAX_DELAY = ONE_DAY*4 # 4 days
