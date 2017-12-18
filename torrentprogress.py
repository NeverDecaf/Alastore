import urllib2
HEADERS={'User-Agent':'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.0.7) Gecko/2009021910 Firefox/3.0.7'} # we will now get a 403 without these, it might not be long before we need cookies too.
# due to the nature of magnet links, the data may not always be available. therefore we must timeout eventually.
MAGNET_TIMEOUT = 70 # in seconds
import libtorrent as lt
import tempfile
import shutil
from time import sleep
import socket
ses = None
def download_magnet(url):
    global ses
    tempdir = tempfile.mkdtemp()
    if not ses:
        ses = lt.session()
    params = {
        'save_path': tempdir,
        'storage_mode': lt.storage_mode_t(2),
        'paused': False,
        'auto_managed': True,
        'duplicate_is_error': True
    }
    handle = lt.add_magnet_uri(ses, url, params)

    for i in range(MAGNET_TIMEOUT):
        sleep(1)
        if handle.has_metadata():
            break
    # if we timed out:
    if not handle.has_metadata():
        print("Could not create torrent from magnet")
        handle.pause()
        ses.remove_torrent(handle)
##        del ses
        shutil.rmtree(tempdir)
        return None
    handle.pause()

    torinfo = handle.get_torrent_info()
    torfile = lt.create_torrent(torinfo)
    # are these 2 needed? not sure.
    torfile.set_comment(torinfo.comment())
    torfile.set_creator(torinfo.creator())

    torcontent = lt.bencode(torfile.generate())
    ses.remove_torrent(handle)
##    del ses
    shutil.rmtree(tempdir)
    return torcontent

def download_torrent(url):
    if url.startswith('magnet:'):
        try:
            return download_magnet(url)
        except Exception as e:
            print ("There was an error downloading from the magnet link in torrentprogress.py: %r" % e)
            return None
    request = urllib2.Request(url, headers=HEADERS)
    try:
        a=urllib2.urlopen(request)
        torrent = a.read()
        a.close()
        return torrent
    except urllib2.URLError, e:
        print url
        print ("There was an error in torrentprogress.py: %r" % e)
        print e.args
    except urllib2.HTTPError, e:
        print '(HTTP error code is:%s)'%e.code
    except socket.timeout, e:
        print ("There was an error in torrentprogress.py: %r" % e)
    return None

import sys, os, hashlib, StringIO, bencode
import contextlib
from bencode import BTFailure
def pieces_generator(info,path):
    """Yield pieces from download file(s)."""
    piece_length = info['piece length']
##    if 'files' in info: # yield pieces from a multi-file torrent, hasnt been properly implemented in this script
##        piece = ""
##        for file_info in info['files']:
##            path=os.path.join(info['name'],
##                                   file_info['path'])
##            print 'path:',path
##            sfile = open(path.decode('UTF-8'), "rb")
##            while True:
##                piece += sfile.read(piece_length-len(piece))
##                if len(piece) != piece_length:
##                    sfile.close()
##                    break
##                yield piece
##                piece = ""
##        if piece != "":
##            yield piece
##    else: # yield pieces from a single file torrent
    sfile = open(path.decode('UTF-8'), "rb")
    while True:
        piece = sfile.read(piece_length)
        if not piece:
            sfile.close()
            return
        yield piece

##def corruption_failure():
##    """Display error message and exit"""
##    print("download corrupted")
##    raise Exception('download corrupted')
##    exit(1)


# returns a unicode filename as suggested by the given torrent file (stringio or other buffer)
def file_name(torrent_file):
    metainfo = bencode.bdecode(torrent_file.read())
    info = metainfo['info']
    if 'files' in info:
            raise BTFailure('torrent contains multiple files')
    return info['name'].decode('utf8')


#returns the percent completed of a SINGLE file torrent at filepath using the torrent, torrent.
# torrent is a stream, suggested you pass a stringIO but you can pass a file handler as well
# just note that this method will not close the torrent so be sure to clean it up yourself.
# also make sure you open in binary mode if reading from a file.
def percentCompleted(torrent_file,filepath):
    import struct
    empty20bytes = struct.pack("5f",0,0,0,0,0)
    # Open torrent file
##    torrent_file = open(torrent, "rb")
    metainfo = bencode.bdecode(torrent_file.read())
    info = metainfo['info']
    filename = StringIO.StringIO(info['name'])
    pieces = StringIO.StringIO(info['pieces'])
    piececount=0
    totalpieces=0
##    skipped=0
    piece_length = info['piece length']
    with contextlib.closing(open(filepath, "rb")) as sfile: #filepath.decode('UTF-8') removed this decode as the path is PROBABLY already unicode
        sfile.seek(0,2)
        fileend = sfile.tell()
        sposition = 0
        sfile.seek(0)
        while sposition<fileend:
        # Iterate through pieces
    ##    for piece in pieces_generator(info,filepath):
            # Compare piece hash with expected hash
            
            torrent_hash = pieces.read(20)
            if torrent_hash != empty20bytes:
                piece = sfile.read(piece_length)
                if not piece:
                    break
                piece_hash = hashlib.sha1(piece).digest()
                if (piece_hash != torrent_hash):
                    piececount+=1
                else:
                    pieces.seek(-20,1)
                    pieces.write(empty20bytes)
            else:
##                skipped+=1
                sfile.seek(piece_length,1)
            sposition += piece_length
            totalpieces+=1
##    print 'skipped %i pieces'%skipped
    # ensure we've read all pieces
    if pieces.read():
        piececount+=1
        #this will leave it at 99% at most which is no good really but who cares.
    pieces.seek(0)
    info['pieces'] = pieces.read()
    reencode = bencode.bencode(metainfo)
    return int(100.*(totalpieces-piececount)/totalpieces) , buffer(reencode)
