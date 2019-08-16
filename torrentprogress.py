# due to the nature of magnet links, the data may not always be available. therefore we must timeout eventually.
MAGNET_TIMEOUT = 70 # in seconds
import requests
import libtorrent as lt
import tempfile
import shutil
from time import sleep
import socket
from constants import *
ses = None
def download_magnet(url):
    global ses
    tempdir = tempfile.mkdtemp()
    if not ses:
        ses = lt.session()
    params = {
        'save_path': tempdir,
        'storage_mode': lt.storage_mode_t(2),
        'url':url,
    }
    handle = ses.add_torrent(params)

    for i in range(MAGNET_TIMEOUT):
        sleep(1)
        if handle.has_metadata():
            break
    # if we timed out:
    if not handle.has_metadata():
        print("Could not create torrent from magnet")
        handle.pause()
        ses.remove_torrent(handle,option=lt.options_t.delete_files)
##        del ses
        shutil.rmtree(tempdir)
        return None
    handle.pause()
    

    torinfo = handle.get_torrent_info()
    torfile = lt.create_torrent(torinfo)
    # are these 2 needed? probably not.
##    torfile.set_comment(torinfo.comment())
##    torfile.set_creator(torinfo.creator())
    
    torcontent = lt.bencode(torfile.generate())
    ses.remove_torrent(handle,option=lt.options_t.delete_files)
##    del ses
    shutil.rmtree(tempdir)
    return torcontent

def download_torrent(url):
    if url.startswith('magnet:'):
        try:
            return download_magnet(url)
        except Exception as e:
            print(("There was an error downloading from the magnet link in torrentprogress.py: %r" % e))
            raise
            return None
    try:
        with requests.get(url, headers=TORRENT_HEADERS) as r:
            torrent = r.content
        return torrent
    except requests.exceptions.RequestException as e:
##        print(url)
        print(("There was an error in torrentprogress.py: %r" % e))
##        print(e.args)
##    except urllib.error.HTTPError as e:
##        print('(HTTP error code is:%s)'%e.code)
    except socket.timeout as e:
        print(("There was an error in torrentprogress.py: %r" % e))
    return None

import sys, os, hashlib, io#, bencode
import contextlib
##from bencode import BTFailure
class BatchTorrentException(Exception):
    pass
# returns a unicode filename as suggested by the given torrent file (bytesio or other buffer)
def file_name(torrent_file):
##    metainfo = bencode.bdecode(torrent_file.read())
    metainfo = lt.bdecode(torrent_file.read())
    info = metainfo[b'info']
    if b'files' in info:
            raise BatchTorrentException('torrent contains multiple files')
    return info[b'name'].decode('utf8')


#returns the percent completed of a SINGLE file torrent at filepath using the torrent, torrent.
# torrent is a stream, suggested you pass a bytesIO but you can pass a file handler as well
# just note that this method will not close the torrent so be sure to clean it up yourself.
# also make sure you open in binary mode if reading from a file.
def percentCompleted(torrent_file,filepath):
    import struct
    empty20bytes = struct.pack("5f",0,0,0,0,0)
    # Open torrent file
##    torrent_file = open(torrent, "rb")
##    metainfo = bencode.bdecode(torrent_file.read())
    metainfo = lt.bdecode(torrent_file.read())
    info = metainfo[b'info']
    if b'files' in info:
            raise BatchTorrentException('torrent contains multiple files')
    filename = io.BytesIO(info[b'name'])
    pieces = io.BytesIO(info[b'pieces'])
    piececount=0
    totalpieces=0
##    skipped=0
    piece_length = info[b'piece length']
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
    info[b'pieces'] = pieces.read()
##    reencode = bencode.bencode(metainfo)
    reencode = lt.bencode(metainfo)
    return (int(100.*(totalpieces-piececount)/totalpieces) , reencode) #buffer(reencode)
