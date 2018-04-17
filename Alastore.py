from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QMutexLocker
import sys
import sqlite3
import time
import rss
import os
import re
import io
import torrentprogress
import urllib
import anidb
import datetime
import makeico
import sql
import shutil
import subprocess
import logging
from contextlib import closing
from functools import partial
from shana_interface import ShanaLink
from functools import reduce
import stat
FULLUPDATE_TIME = 1000 * 60 * 10 #once every 10 m
INITIALUPDATE_GRACEPERIOD = 1000 * 60 * 2 # 2m (this is time before the first (only) quick update)
COLORSCHEME = {'background': QtGui.QColor(255,255,255),#
               'watchedh': QtGui.QColor(215,215,215),#
               'downloadedh': QtGui.QColor(255,255,255),#
               'notdownloadedh': QtGui.QColor(225,225,225),#
               'downloadprogressh':QtGui.QColor(255,255,255),
               'forcewatchedh':QtGui.QColor(225,225,225),
               'watched': QtGui.QColor(255,255,255),#
               'downloaded': QtGui.QColor(255,255,255),#
               'notdownloaded': QtGui.QColor(220,220,220),#
               'forcewatched':QtGui.QColor(220,220,220),
               'watchedfg': QtGui.QColor(125,25,25),
               'downloadedfg': QtGui.QColor(25,125,25),
               'notdownloadedfg': QtGui.QColor(30,120,120),
               'forcewatchedfg':QtGui.QColor(180,55,55),
               }

class Node(object):
    def __init__(self, data, parent=None):
        self._data = data
        self._children = []
        self._parent = parent
        
        if parent is not None:
            parent.addChild(self)
            
    def setData(self,newData):
        self._data = newData
        
    def watched(self):
        return self._data['watched']
    def title(self):
        return self._data['title']
    def downloaded(self):
        return self._data['downloaded']
    def downloadProgress(self):
        return self._data['download_percent']
    def episode(self):
        return self._data['episode']
    def id(self):
        return self._data['id']
    def torrent_url(self):
        return self._data['torrent_url']
    def season(self):
        return self._data['season']
    def path(self):
        return self._data['path']
    def file_name(self):
        return self._data['file_name']
    def name(self):
        return self._data['display_name']
    
    def getChildById(self,series_id):
        for i in self._children:
            if i.id() == series_id:
                return i
    def getChildByTorrent(self,torrent_url):
        for j in self._children:
            if j.torrent_url() == torrent_url:
                return j
    def getChildBySeries(self,series):
        for j in self._children:
            if j.title() == series:
                return j
            
    def typeInfo(self):
        return "NODE"

    def addChild(self, child):
        self._children.append(child)

    def insertChild(self, position, child):
        if position < 0 or position > len(self._children):
            return False
        
        self._children.insert(position, child)
        child._parent = self
        return True

    def getChildren(self):
        return self._children

    def removeChild(self, position):
        if position < 0 or position > len(self._children):
            return False
        
        child = self._children.pop(position)
        child._parent = None
        return True

    def child(self, row):
        return self._children[row]
    
    def childCount(self):
        return len(self._children)

    def parent(self):
        return self._parent
    
    def row(self):
        if self._parent is not None:
            return self._parent._children.index(self)

    def sort(self):
        self._children.sort(key=lambda n: (n.watched(),n.downloaded(),n.name().lower()))
        
    def log(self, tabLevel=-1):
        output     = ""
        tabLevel += 1
        
        for i in range(tabLevel):
            output += "\t"
        
        output += "|------" + self.name() + "\n"
        
        for child in self._children:
            output += child.log(tabLevel)
        
        tabLevel -= 1
        output += "\n"
        return output

    def __repr__(self):
        return self.log()

class HeaderNode(Node):
    def __init__(self, data, series, parent=None):
        super(HeaderNode, self).__init__(data, parent)
        self._series = series
        self.update()
        
    def typeInfo(self):
        return "HEADERNODE"

    def series(self):
        return self._series
    
    def name(self):
        if self.watched():
            return self._series+' [%i]'%self._current.episode()
        else:
            return self._series+' %i'%self._current.episode()

    def _getlatest(self):
        for i, child in enumerate(reversed(self._children)):
            if not child.watched():
                self._currentIndex = i
                self._current = child
                return
        if len(self._children):
            self._currentIndex = 0
            self._current = self._children[0]
            return
        #this isnt good but this case should never be reached
        self._currentIndex = 0
        self._current = self

    def update(self):
        self._getlatest()
        self._data = self._current._data

    def currentIndex(self):
        return self._currentIndex
    def current(self):
        return self._current
    def setepisode(self,i):
        self._episode = i
    def setwatched(self, i):
        super(HeaderNode, self).setwatched(i)
        self.update()
    
class TreeModel(QtCore.QAbstractItemModel):
    """INPUTS: Node, QObject"""
    def __init__(self, root, writelock, updatelock, threadpool, parent=None):
        super(TreeModel, self).__init__(parent)
        self._rootNode = root
        self._sqlManager = sql.SQLManager()
        self._updateData()
        self._writelock = writelock
        self._updatelock = updatelock
        self._threadpool = threadpool
        self._shanalink = ShanaLink()

    def _updateData(self):
        self.data = self._sqlManager.getSeries()
        # remove headers that no longer exist in data:
        for toremove in [header for header in self._rootNode.getChildren() if header.series() not in self.data or not self.data[header.series()]]:
            self.removeHeader(toremove)
        for series in sorted(self.data.keys()):
            if self.data[series]:
                head = self._rootNode.getChildBySeries(series)
                if not head:
                    head = HeaderNode(self.data[series][-1], series, self._rootNode)
                else:
                    # remove all contents of old header
                    headIndex = self.createIndex(head.row(), 0, head)
                    self.removeRows(0,head.childCount(),headIndex)
                for ep in reversed(self.data[series]):
                    n=Node(ep,head)
                head.update()
        
    def playandsort(self, index, parent=None, syncplayPath=None):
        if index.internalPointer().downloaded()>0:
            user_settings = self._sqlManager.getSettings()
            if not user_settings['Save Directory']:
                QtWidgets.QMessageBox.information(None,
                        self.tr("No Settings Found!"),
                        self.tr("Please fill out the required user settings\nbefore watching an episode."))
            else:
                'play the file in a separate thread to prevent ui lag.'
                if index.internalPointer().watched():
                    if syncplayPath:
                        subprocess.Popen((os.path.join(syncplayPath,'Syncplay.exe'),index.internalPointer().path()))
                    else:
                        self.watchfile(index.internalPointer().path())
                else:
                    t = SingleFunction(lambda:playmove(user_settings,index),self._writelock)
                    t._signals.finished.connect(self.sqlDataChanged)
                    self._threadpool.start(t)
                def playmove(user_settings, index):
                    with closing(sql.SQLManager()) as sqlmanager:
                        def moveAllToFolder(dest_path):
                            dest = os.path.dirname(dest_path)
                            episodes = sqlmanager.getAllWatchedPaths(dest)
                            for episode in episodes:
                                path = episode[0]
                                directory = os.path.dirname(path)
                                filename = os.path.basename(path)
                                if directory!=dest and os.path.exists(directory):
                                    destfile = os.path.join(dest,filename)
                                    try:
                                        shutil.move(path,destfile)
                                        sqlmanager.changePath(path,destfile)
                                    except IOError as e:
                                        print('failed to move file: %r'%e)
                                    TreeModel.cleanFolder(directory)                        
                        shana_title = index.internalPointer().title()#self.SQL.getSeriesTitle(data['id'])#.decode('utf8')
                        st_dir = user_settings['Save Directory']#.decode('utf8')
                        folder_title = r''.join(i for i in shana_title if i not in r'\/:*?"<>|.')

                        # check usersettings for usesubfolders.
                        # if true/false move existing files from one to the other

                        toplevel_folder = os.path.join(st_dir,folder_title)
                        season=index.internalPointer().season()#self.SQL.getSeriesSeason(data['id'])
                        if season:
                            year = season.split()[1]
                            seasonsorted_folder = os.path.join(st_dir,year,season,folder_title)
                            
                        
                        if user_settings['Season Sort'] and season:
                            dest_folder = seasonsorted_folder
                        else:
                            dest_folder = toplevel_folder

                        dest_file = os.path.join(dest_folder,index.internalPointer().file_name())
                        
                        if not os.path.isdir(dest_folder):
                            os.makedirs(dest_folder)
                        if not os.path.exists(dest_file):
                            shutil.move(index.internalPointer().path(),dest_file)#.decode('utf8'),dest_file)
                        if syncplayPath:
                            subprocess.Popen((os.path.join(syncplayPath,'Syncplay.exe'),dest_file))
                        else:
                            self.watchfile(dest_file)
                        # we also want to get the ed2k hash asap in case you decide to drop the series right after watching an episode.
                        try:
                            ed2k,filesize=None,None
                            ed2k,filesize=anidb.anidbInterface.ed2k_hash(dest_file)
                        except Exception as e:
                            print('Error hashing file (initial hash) %s; %r'%(dest_file,e))
                        sqlmanager.watchMoveQueue(index.internalPointer().path(),dest_file,ed2k,filesize)
                        try:
                            moveAllToFolder(dest_file)
                        except Exception as e:
                            print('Unexpected error, moveAllToFolder failed: %r'%e)

    # BE VERY CAREFUL WITH THIS.
    @staticmethod
    def cleanFolder(path):
        if os.path.isdir(path):
            files = os.listdir(path)
            if len(files)<=2:
                isEmpty = not reduce(lambda x,y: x or not (y.endswith('.ico') or y.lower()=='desktop.ini'), [0]+files)
                if isEmpty:
                    shutil.rmtree(path, onerror=TreeModel.remove_readonly)

    # AND EVEN MORE CAREFUL WITH THIS
    @staticmethod
    def remove_readonly(func, path, excinfo):
        os.chmod(path, stat.S_IWRITE)
        func(path)
        
    def getContextOptions(self,isheader):
        opt = []
        opt.append((self.tr("&Hide Series"),self.hideSeries,{}))
        if os.name=='nt':
            opt.append((self.tr("&Show in Explorer"),self.openInFileExplorer,{}))
            from winreg import OpenKey,QueryValueEx,HKEY_LOCAL_MACHINE
            try:
                with OpenKey(HKEY_LOCAL_MACHINE, r"SOFTWARE\Wow6432Node\Syncplay") as key:
                    opt.append((self.tr("&Play in Syncplay"),self.playandsort,{'syncplayPath':QueryValueEx(key,'Install_Dir')[0]}))
            except WindowsError:
                pass # syncplay probably not installed
        opt.append((self.tr("&Mark All Watched"),self.markSeriesWatched,{}))
##        if not isheader:
        opt.append((self.tr("&Mark Episode Watched"),self.markEpisodeWatched,{}))
        user_settings = self._sqlManager.getSettings()
        if user_settings['Shana Project Username'] and user_settings['Shana Project Password']:
            opt.append((self.tr("&Drop Series"),self.dropSeries,{}))
        return opt

    def openInFileExplorer(self,index,parent):
        import ctypes
        ctypes.windll.ole32.CoInitialize(None)
        upath = index.internalPointer().path()
        pidl = ctypes.windll.shell32.ILCreateFromPathW(upath)
        ctypes.windll.shell32.SHOpenFolderAndSelectItems(pidl, 0, None, 0)
        ctypes.windll.shell32.ILFree(pidl)
        ctypes.windll.ole32.CoUninitialize()
        
    def hideSeries(self,index,parent):
        if QtWidgets.QMessageBox.Yes == QtWidgets.QMessageBox.warning(
                parent, self.tr("Hide Series?"),
                self.tr('''This series will be removed from this list until a new episode appears in your RSS.
***You cannot undo this action***
Are you sure you wish to hide the following series?
{}''').format(index.internalPointer().title()),
               QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No):
            if self._writelock.tryLock():
                try:
                    self._sqlManager.hideSeries(index.internalPointer().id())
                finally:
                    self._writelock.unlock()
                self.sqlDataChanged()
            else:
                t = SQLSingleFunction(self._writelock,'hideSeries',index.internalPointer().id())
                t._signals.finished.connect(self.sqlDataChanged)
                self._threadpool.start(t)

    def markSeriesWatched(self,index,parent):
        if QtWidgets.QMessageBox.Yes == QtWidgets.QMessageBox.warning(
            parent, self.tr("Mark Watched?"),
            self.tr('''This will mark every episode in this series ({}) as watched.
This includes files which have not yet been downloaded.
Marking files watched this way will NOT add them to your mylist nor will it move
and sort them. It will also render them incapable of being added or sorted in the future.
Make sure you have watched every episode you mean to watch before doing this.
Are you sure you wish to mark all episodes of {} as watched?
(You cannot undo this action)''').format(index.internalPointer().title(),index.internalPointer().title()),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No):
            if self._writelock.tryLock():
                try:
                    self._sqlManager.forceWatched(id = index.internalPointer().id())
                finally:
                    self._writelock.unlock()
                self.sqlDataChanged()
            else:
                t = SQLSingleFunction(self._writelock,'forceWatched',id=index.internalPointer().id())
                t._signals.finished.connect(self.sqlDataChanged)
                self._threadpool.start(t)
                
    def markEpisodeWatched(self,index,parent):
        if QtWidgets.QMessageBox.Yes == QtWidgets.QMessageBox.warning(
            parent, self.tr("Mark Watched?"),
            self.tr('''Are you sure you want to force mark the file: {} as watched?
Force marking a file this way will NOT automatically sort/move the file and it will NEVER add the file to your mylist.
You should only use this option if a file fails to download or is moved/deleted before you can watch it through Alastore.''').format(index.internalPointer().name()),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No):
            if self._writelock.tryLock():
                try:
                    self._sqlManager.forceWatched(torrenturl = index.internalPointer().torrent_url())
                finally:
                    self._writelock.unlock()
                self.sqlDataChanged()
##                self.updateEpisodeByIndex(index)
            else:
                t = SQLSingleFunction(self._writelock,'forceWatched',torrenturl = index.internalPointer().torrent_url())
##                t._signals.finished.connect(lambda: self.updateEpisodeByIndex(index)) # idk this func has issues.
                t._signals.finished.connect(self.sqlDataChanged)
                self._threadpool.start(t)
                
    def dropSeries(self,index,parent):
        drop = DropDialog(index.internalPointer().title(),parent)
        drop.exec_()
        drop,delete = drop.getValues()
        if drop:
            t = SingleFunction(lambda:dropfunc(self._shanalink,index,parent),self._writelock)
            t._signals.finished.connect(self.sqlDataChanged)
            t._signals.finishedWithErrors.connect(lambda: QtWidgets.QMessageBox.information(parent,self.tr('Drop Failed'),self.tr('Could not connect to Shana Project to drop {}, check your login credentials and internet connection.').format(index.internalPointer().title())))
            self._threadpool.start(t)
        def dropfunc(shanalink,index,parent):
            with closing(sql.SQLManager()) as _sql:
                user_settings = _sql.getSettings()
                title = index.internalPointer().title()
                id = index.internalPointer().id()
                # is shanalink threadsafe?
                if user_settings['Shana Project Username'] and user_settings['Shana Project Password']:
                    shanalink.update_creds(user_settings['Shana Project Username'],user_settings['Shana Project Password'])
                    success = 0
                    try:
                        success = shanalink.delete_follow(title)
                    except Exception as e:
                        print('Error dropping series: %r'%e)
                        raise
                    if success:
                        _sql.hideSeries(id)
                        if delete:
                            paths = _sql.getAllPaths(id)
                            for path in paths:
                                directory = os.path.dirname(path)
                                if os.path.isfile(path):
                                    os.remove(path)
                                TreeModel.cleanFolder(directory)
                            _sql.dropSeries(id)
                    
    def showAgainDialog(self,parent):
        if not self._sqlManager.getShowAgain():
            d=StillRunningDialog(parent)
            d.exec_()
            showagain=d.getValues()
            if showagain:
                if self._writelock.tryLock():
                    try:
                        self._sqlManager.setShowAgain(showagain)
                    finally:
                        self._writelock.unlock()
                else:
                    t = SQLSingleFunction(self._writelock,'setShowAgain',showagain)
                    self._threadpool.start(t)
                    
    def configDialog(self,parent):
        settings = self._sqlManager.getSettings(raw=True,fetchanyway=True)
        d=SettingsDialog(settings,parent)
        d.exec_()
        if d.getValues():
            settings = d.getValues()
            if self._writelock.tryLock():
                try:
                    self._sqlManager.saveSettings(*[settings[key] for key in self._sqlManager.COLUMN_NAMES])
                finally:
                    self._writelock.unlock()
            else:
                t = SQLSingleFunction(self._writelock,'saveSettings',*[settings[key] for key in self._sqlManager.COLUMN_NAMES])
                self._threadpool.start(t)
        d.deleteLater()

    def quickUpdate(self):
        fileupdate = FullUpdate(self._writelock,self._updatelock,quick=True)
        fileupdate._signals.dataModified.connect(self.sqlDataChanged)
        fileupdate._signals.updateEpisode.connect(self.updateEpisode)
        self._threadpool.start(fileupdate)
        
    def sqlDataChanged(self):
        # if something was changed by an external source (thread)
        # just reload all data and emit layoutchanged
        self._updateData()
        self.sort()
        self.dataChanged.emit(QtCore.QModelIndex(),QtCore.QModelIndex(),[]) # keep it simple and just refresh everything.

    def updateEpisode(self, data):
        series_id, torrent_url = data
        parent = self._rootNode.getChildById(series_id)
        child = parent.getChildByTorrent(torrent_url)

        child.setData(self._sqlManager.getEpisode(series_id,torrent_url))
        parent.update()

        parentIndex = self.createIndex(parent.row(), 0, parent)
        thisIndex = self.createIndex(child.row(), 0, child) # is col supposed to be 0?
        self.dataChanged.emit(parentIndex,parentIndex,[])
        self.dataChanged.emit(thisIndex,thisIndex,[])
        
    def updateEpisodeByIndex(self, index):
        series_id, torrent_url = index.internalPointer().id(),index.internalPointer().torrent_url()
        if not index.parent().isValid():
            # this is a header, edit its child instead
            parent = index.internalPointer()
            child = parent.current()
        else:
            child = index.internalPointer()
            parent = self._rootNode.getChildById(series_id)

        child.setData(self._sqlManager.getEpisode(series_id,torrent_url))
        parent.update()

        parentIndex = self.createIndex(parent.row(), 0, parent)
        thisIndex = self.createIndex(child.row(), 0, child) # is col supposed to be 0?
        self.dataChanged.emit(parentIndex,parentIndex,[])
        self.dataChanged.emit(thisIndex,thisIndex,[])
    
    """INPUTS: QModelIndex"""
    """OUTPUT: int"""
    def rowCount(self, parent):
        if not parent.isValid():
            parentNode = self._rootNode
        else:
            parentNode = parent.internalPointer()

        return parentNode.childCount()

    """INPUTS: QModelIndex"""
    """OUTPUT: int"""
    def columnCount(self, parent):
        return 1
    
    def watchfile(self,filepath):
        if os.path.exists(filepath):
            if sys.platform.startswith('darwin'):
                subprocess.Popen(('open', filepath))
            elif os.name == 'nt':
                os.startfile(filepath)
            elif os.name == 'posix':
                subprocess.Popen(('xdg-open', filepath))
        else:
            return -1
            
    def dblClickEvent(self, index):
        self.playandsort(index)        
    
    """INPUTS: QModelIndex, int"""
    """OUTPUT: QVariant, strings are cast to QString which is a QVariant"""
    def data(self, index, role):
        
        if not index.isValid():
            return None

        node = index.internalPointer()

        if role == QtCore.Qt.DisplayRole or role == QtCore.Qt.EditRole:
            if index.column() == 0:
                return node.name()

    """INPUTS: QModelIndex, QVariant, int (flag)"""
    def setData(self, index, value, role=QtCore.Qt.EditRole):
        if index.isValid():
            
            if role == QtCore.Qt.EditRole:
                
                node = index.internalPointer()
                node.setName(value)

                self.dataChanged.emit(index,index,[])
                return True
        return False

    
    """INPUTS: int, Qt::Orientation, int"""
    """OUTPUT: QVariant, strings are cast to QString which is a QVariant"""
    def headerData(self, section, orientation, role):
        if role == QtCore.Qt.DisplayRole:
            if section == 0:
                return "Scenegraph"
            else:
                return "Typeinfo"

        
    
    """INPUTS: QModelIndex"""
    """OUTPUT: int (flag)"""
    def flags(self, index):
        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable #| QtCore.Qt.ItemIsEditable

    

    """INPUTS: QModelIndex"""
    """OUTPUT: QModelIndex"""
    """Should return the parent of the node with the given QModelIndex"""
    def parent(self, index):
        
        node = self.getNode(index)
        parentNode = node.parent()
        
        if parentNode == self._rootNode:
            return QtCore.QModelIndex()
        
        return self.createIndex(parentNode.row(), 0, parentNode)
        
    """INPUTS: int, int, QModelIndex"""
    """OUTPUT: QModelIndex"""
    """Should return a QModelIndex that corresponds to the given row, column and parent node"""
    def index(self, row, column, parent):
        
        parentNode = self.getNode(parent)

        childItem = parentNode.child(row)


        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QtCore.QModelIndex()



    """CUSTOM"""
    """INPUTS: QModelIndex"""
    def getNode(self, index):
        if index.isValid():
            node = index.internalPointer()
            if node:
                return node
            
        return self._rootNode

    
    """INPUTS: int, int, QModelIndex"""
    def insertRows(self, position, rows, parent=QtCore.QModelIndex()):
        
        parentNode = self.getNode(parent)
        
        self.beginInsertRows(parent, position, position + rows - 1)
        
        for row in range(rows):
            
            childCount = parentNode.childCount()
            childNode = Node("untitled" + str(childCount))
            success = parentNode.insertChild(position, childNode)
        
        self.endInsertRows()

        return success
    
    def removeHeader(self, node):
        if not isinstance(node,HeaderNode):
            return None

        self.beginRemoveRows(QtCore.QModelIndex(), node.row(), node.row())
        
        success = self._rootNode.removeChild(node.row())
        
        self.endRemoveRows()
        
        return success
    
    """INPUTS: int, int, QModelIndex"""
    def removeRows(self, position, rows, parent=QtCore.QModelIndex()):
        
        parentNode = self.getNode(parent)
        self.beginRemoveRows(parent, position, position + rows - 1)
        
        for row in range(rows):
            success = parentNode.removeChild(position)
            
        self.endRemoveRows()
        
        return success
    
    def sort(self, column=0, order=QtCore.Qt.AscendingOrder):
        #only 1 column here
        self.layoutAboutToBeChanged.emit()
        self._rootNode.sort()
        self.layoutChanged.emit()
        pass
        
#-------------------------------------------------------------------------------
class TreeView(QtWidgets.QTreeView):
#---------------------------------------------------------------------------
    def __init__(self, parent=None):
        super(TreeView, self).__init__(parent)
        self.setContextMenuPolicy( QtCore.Qt.CustomContextMenu )
        self.customContextMenuRequested.connect( self.openMenu )
        
    def openMenu(self, position):
        index = self.selectedIndexes()[0]
        menu = QtWidgets.QMenu()
        for text, func, kwargs in self.model().getContextOptions(not index.parent().isValid()):
            action = menu.addAction(text)
            action.triggered.connect(partial(func,index,self,**kwargs))
        menu.exec_(self.viewport().mapToGlobal(position))
        
    def drawBranches(self, painter, rect, index):
        # don't draw the dropdown decorations.
        pass
    
class ItemDelegate(QtWidgets.QStyledItemDelegate):
    listPadding = (0,2)#padding that will go around the sides of the list. you only get horizontal and vertical
    textPadding = (6,4)#inner padding basically. between the sides of the box and the text inside. ( this is left and right padding where the above is horiz and verti)
    textVertPadding = 6 # total vertical space (top and bot combined)
    
    def paint(self,painter,option,index):
        from PyQt5.QtCore       import Qt, QRect


        from PyQt5.QtGui        import (QPainter, QPainterPath,
                                                QPalette, QPixmap, QPen)
        painter.save()
        painter.setRenderHint( painter.Antialiasing )
        x = option.rect.x()
        x= 1
        dw = option.decorationSize.width()
        dh = option.decorationSize.height()
        y = option.rect.y() + self.listPadding[1]//2
        w = option.rect.width()+option.rect.x()-3
        h = option.rect.height() - self.listPadding[1]
        if index.parent().isValid():
            rowcount = index.parent().internalPointer().childCount()
        else:
            rowcount = 0 #doesn't matter
        pen = QPen( option.palette.color( QPalette.Light ) )
        painter.setRenderHint( painter.Antialiasing, False )
        pen.setColor( option.palette.color( QPalette.Shadow ) )
        painter.setPen( pen )

        if index.internalPointer().downloaded():
            if index.internalPointer().watched():
                fg = COLORSCHEME['watchedfg']
                bg = COLORSCHEME['watched']
                if not index.parent().isValid():
                    bg = COLORSCHEME['watchedh']
            else:
                fg = COLORSCHEME['downloadedfg']
                bg = COLORSCHEME['downloaded']
                if not index.parent().isValid():
                    bg = COLORSCHEME['downloadedh']
        else:
            if index.internalPointer().watched():
                fg = COLORSCHEME['forcewatchedfg']
                bg = COLORSCHEME['forcewatched']
                if not index.parent().isValid():
                    bg = COLORSCHEME['forcewatchedh']
            else:
                fg = COLORSCHEME['notdownloadedfg']
                bg = COLORSCHEME['notdownloaded']
                if not index.parent().isValid():
                    bg = COLORSCHEME['notdownloadedh']

        if not index.parent().isValid():
            painter.fillRect( x , y , w , h, bg )
            if not index.internalPointer().downloaded() and not index.internalPointer().watched():
                painter.fillRect( x , y , max(0,int(index.internalPointer().downloadProgress()*(w/100.))) , h, COLORSCHEME['downloadprogressh'] )
            painter.drawRect( x , y , w , h)     
        else:
            painter.fillRect( x , option.rect.y() , w , option.rect.height(), bg )
            if not index.internalPointer().downloaded() and not index.internalPointer().watched():
                painter.fillRect( x , option.rect.y() , max(0,int(index.internalPointer().downloadProgress()*(w/100.))) , option.rect.height(), COLORSCHEME['downloadprogressh'] )
            ypad = 0
            if index.row() == rowcount-1:
                painter.drawRect( x , y+h , w , 0)
                ypad = - self.listPadding[1]
            painter.drawRect( x , option.rect.y() , 0 , option.rect.height()+ypad)
            painter.drawRect( w+1, option.rect.y() , 0 , option.rect.height()+ypad)
            
        if not index.parent().isValid(): # if this is a root node
            painter.drawRect( x+h,y,0,h)
            # draw the +/-
            if not option.state & QtWidgets.QStyle.State_Open:
                painter.fillRect( x+h/2 , y+h/4 , 1,1+h-h/4*2+1,painter.pen().color())
            painter.fillRect( x+h/4 , y+h/2 , 1+h-h/4*2+1,1,painter.pen().color())

        pen.setColor(fg)
        painter.setPen(pen)
        text = index.data(Qt.DisplayRole)
        if not index.parent().isValid():
            painter.drawText( x + h + self.textPadding[0], y , w - self.textPadding[0]-self.textPadding[1]-h, h, Qt.AlignLeft | Qt.AlignVCenter, text)
        else:
            painter.drawText( x + self.textPadding[0], y, w - self.textPadding[0]-self.textPadding[1], h, Qt.AlignLeft | Qt.AlignVCenter, text)
        painter.restore()
        
    def sizeHint(self, option, index):
        fontMetrics = option.fontMetrics
        if not index.parent().isValid():
            return QtCore.QSize(option.rect.width()+option.rect.x(),fontMetrics.height()+self.textVertPadding+self.listPadding[1]*2)
        else:
            return QtCore.QSize(option.rect.width()+option.rect.x(),fontMetrics.height()+self.textVertPadding-self.listPadding[1])
        
    def getHeaderHeight(self, fontMetrics):
        return fontMetrics.height()+self.textVertPadding+self.listPadding[1]*2

class SingleFunction(QtCore.QRunnable):
    '''
    Worker thread
    '''
    def __init__(self, func, lock):
        super(SingleFunction, self).__init__()
        self._func = func
        self._writelock = lock
        self._signals = WorkerSignals()

    @QtCore.pyqtSlot()
    def run(self):
        '''
        Your code goes in this function
        '''
        with QMutexLocker(self._writelock):
            try:
                self._func()
                self._signals.finished.emit()
            except:
                self._signals.finishedWithErrors.emit()

class SQLSingleFunction(QtCore.QRunnable):
    '''
    Worker thread
    '''
    def __init__(self, lock, func, *args, **kwargs):
        super(SingleFunction, self).__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs
        self._writelock = lock
        self._signals = WorkerSignals()

    @QtCore.pyqtSlot()
    def run(self):
        '''
        Your code goes in this function
        '''
        with closing(sql.SQLManager()) as sql:
            with QMutexLocker(self._writelock):
                try:
                    getattr(sql, self._func)(*self._args, **self._kwargs)
                    self._signals.finished.emit()
                except:
                    self._signals.finishedWithErrors.emit()

class WorkerSignals(QtCore.QObject):
    finished = QtCore.pyqtSignal()
    finishedWithErrors = QtCore.pyqtSignal()
    dataModified = QtCore.pyqtSignal()
    updateEpisode = QtCore.pyqtSignal(tuple)
    error = QtCore.pyqtSignal(tuple)
    result = QtCore.pyqtSignal(object)
    
class FullUpdate(QtCore.QRunnable):
    '''
    Worker thread
    '''
    def __init__(self, writelock, updatelock, quick=False):
        super(FullUpdate, self).__init__()
##        self._conn=conn
        self._quick=quick
        self._writelock = writelock
        self._updatelock = updatelock
        self._signals = WorkerSignals()
        
    def dl_titlelist(self):
        titleUpdateTime = self._sql.titleUpdateTime()
        if titleUpdateTime:
            titleList = None
            try:
                titleList = anidb.anidb_title_list() ## WEB-DEPENDENT
            except (urllib.error.URLError,urllib.error.HTTPError,TimeoutError) as e:
                'banned or site is down'
                print('failed to fetch anidb title list. (%r)'%e)
            if titleList:
                with QMutexLocker(self._writelock):
                    self._sql.cacheTitles(titleList)# updates user_settings
    def hash_files(self):
        toHash = self._sql.getUnhashed()
        hasherrors=0
        for file in toHash:
            ed2k = None
            try:
                ed2k,filesize=anidb.anidbInterface.ed2k_hash(file) ## WEB-DEPENDENT
            except (urllib.error.URLError,urllib.error.HTTPError,TimeoutError) as e:
                # if hashing fails on one file, we don't want to exclude the others.
                hasherrors+=1 # we never do anything with this
            if ed2k:
                with QMutexLocker(self._writelock):
                    self._sql.updateHash(file,ed2k,filesize)
        return hasherrors

    def get_new_from_rss(self):
        '''parse your rss and find new files; for each file download the torrent file'''
        user_settings = self._sql.getSettings()
        rssitems = rss.RSSReader().getFiles(user_settings['RSS Feed']) ## WEB-DEPENDENT ( but handles exceptions itself )
        with QMutexLocker(self._writelock):
            torrentBlacklist = self._sql.getTorrentBlacklist()
        for item in rssitems:
            if item[2] not in torrentBlacklist:
                                                                                            #file name, rsstitle,torrent url 
                if self._sql.addEpisode(os.path.join(user_settings['Download Directory'],item[1]),item[0],item[2]):
                    torrentdata = torrentprogress.download_torrent(item[2]) ## WEB-DEPENDENT ( but handles exceptions itself )
                    if torrentdata:
                        try:
                            filename = torrentprogress.file_name(io.BytesIO(torrentdata))
                        except torrentprogress.BatchTorrentException as e:
                            print('initial bencode failed %r'%e)
                            print('episode (%s) was removed and blacklisted.'%item[1])
                            with QMutexLocker(self._writelock):
                                self._sql.removeEpisode(item[2],permablacklist=True)
                        except Exception as e:
                            print('initial bencode failed %r'%e)
                            print('pre-removing %s.'%item[1])
                            with QMutexLocker(self._writelock):
                                self._sql.removeEpisode(item[2],len(torrentdata)) # if torrentdata is len(0) don't blacklist <== this state is impossible to reach
                        else:
                            path = os.path.join(user_settings['Download Directory'],filename)
                            with QMutexLocker(self._writelock):
                                self._sql.addTorrentData(path,item[2],torrentdata,filename)
                            self._signals.dataModified.emit()

    def anidb_adds(self):
        with QMutexLocker(self._writelock):
            user_settings, toAdd = self._sql.getToAdd()
            
        self.newAids=[]
        if user_settings and len(toAdd) and user_settings['anidb Username'] and user_settings['anidb Password']:
            with closing(anidb.anidbInterface()) as anidbLink: ## WEB-DEPENDENT
                if anidbLink.open_session(user_settings['anidb Username'],user_settings['anidb Password']):
                    for datum in toAdd:
                        aid=anidbLink.add_file(datum['path'],datum['aid'],datum['group'],datum['epno'],datum['ed2k'],datum['do_generic_add'])
                        # these match with: status, filepath, aid, subgroup, epnum, ed2k, do_generic_add
                        logging.debug('anidb add status:%s, vars used: %s\t%s\t%s\t%s\t%s\t%s'%(aid,datum['path'],datum['aid'],datum['group'],datum['epno'],datum['ed2k'],datum['do_generic_add']))
                        
                        if aid:#if the add succeeded.
                            with QMutexLocker(self._writelock):
                                self._sql.removeParsed(datum['path'],forceadded=datum['force_generic_add'],aid=datum['aid'])
                            if not datum['aid'] and aid>0: # if an aid did not exist but was returned by add
                                with QMutexLocker(self._writelock):
                                    self._sql.updateAids(((aid,datum['id']),)) # we most likely don't need to update data for this...

    def check_file_changes(self):
        # this is the file update (the part that should run when you pick the context menu option)
        user_settings = self._sql.getSettings()
        allseries = self._sql.getDownloadingSeries()
        dl_dir = user_settings['Download Directory']
        # we replace space with _ here, make sure to do this to all the strings you want to match.
        originalFiles = os.listdir(dl_dir)
        potentialFiles = [re.sub(r'[ ]+',r'_',x) for x in originalFiles]
        potentialMatches = dict(list(zip(potentialFiles,originalFiles)))
        for series in list(allseries.values()):
            for episode in series:
                pattern,replacement = rss.RSSReader.invalidCharReplacement(user_settings['RSS Feed'])                    
                workingFile = re.sub(pattern,replacement,episode['file_name'])
                if workingFile in potentialMatches:
                    filename = potentialMatches[workingFile]
                    path=os.path.join(dl_dir,filename)
                    torrentdata=episode['torrent_data']
                    percent_downloaded=episode['download_percent']
                    if not torrentdata:
                        torrent = torrentprogress.download_torrent(episode['torrent_url'])
                        if torrent:
                            torrentdata=torrent
                    if torrentdata:
                        try:
                            percent_downloaded, torrentdata=torrentprogress.percentCompleted(io.BytesIO(torrentdata),path)
                        except torrentprogress.BatchTorrentException as e:
                            print('bencode failed %r'%e)
                            print('episode (%s) was removed and blacklisted.'%episode['display_name'])
                            with QMutexLocker(self._writelock):
                                self._sql.removeEpisode(episode['torrent_url'],permablacklist=True)
                            continue
                        except Exception as e:
                            print('bencode failed %r'%e)
                            print('episode (%s) was removed.'%episode['display_name'])
                            with QMutexLocker(self._writelock):
                                self._sql.removeEpisode(episode['torrent_url'],len(torrentdata))
                            continue
                        with QMutexLocker(self._writelock):
                            self._sql.setDownloading(episode['torrent_url'],filename,torrentdata,percent_downloaded)
##                          self._signals.updateEpisode.emit((episode['id'],episode['torrent_url']))
        if len(allseries):
            self._signals.dataModified.emit()
    def get_series_info(self):
        wait= time.time()
        for aid in self._sql.oneDayOldAids():
            try:
                while time.time() - wait < 2: pass
                airdate,imgurl = anidb.anidb_series_info(aid)
                wait = time.time()
                SEASONS = ['Spring','Summer','Fall','Winter']
                date = datetime.datetime.strptime(airdate,'%Y-%m-%d')
                sixtydays = datetime.timedelta(60)
                date-=sixtydays
                dayofyear = int(date.strftime('%j'))
                dayofseason = datetime.timedelta(dayofyear%91)
                date -= dayofseason
                date += sixtydays
                seasonindex =(dayofyear-(dayofyear%91))//91
                seasonname= '%s %s'%(SEASONS[seasonindex],date.strftime('%Y'))
                with QMutexLocker(self._writelock):
                    self._sql.updateSeriesInfo(((aid,airdate,seasonname,imgurl),))
            except Exception as e:
                print('anidb_series_info failed on %s [%r]'%(aid,e))
                with QMutexLocker(self._writelock):
                    self._sql.updateSeriesInfoTime((aid,))
    def dl_poster_icons(self):
        ''' also sets the icons '''
        user_settings = self._sql.getSettings()
        if os.name == 'nt' and user_settings['Poster Icons']: # only works on windows.
            newIcons = self._sql.getOutdatedPosters()
            
            '''hashes the selected files, also downloads poster art if applicable'''
            for icon in newIcons:
                folder_title = r''.join(i for i in icon['title'] if i not in r'\/:*?"<>|.')
                dest_folder = os.path.join(user_settings['Save Directory'],folder_title)
                if user_settings['Season Sort'] and icon['season']:
                    year = icon['season'].split()[1]
                    dest_folder = os.path.join(user_settings['Save Directory'],year,icon['season'],folder_title)
                try:
                    if icon['aid'] and os.path.exists(dest_folder) and (not os.path.exists(os.path.join(dest_folder,'%i.ico'%icon['aid'])) or not icon['nochange']):
                        makeico.makeIcon(icon['aid'],icon['poster_url'],dest_folder)
                    with QMutexLocker(self._writelock):
                        self._sql.updateCoverArts(((icon['aid'],icon['poster_url']),))
                except IOError as e:
                    if e.errno!=errno.ENOENT:
                        raise
                    '''errno 2 is file/directory does not exist.
                    this simply means you tried to get poster art before any episodes were downloaded.
                    we will just try to get the art again at a later date'''
                except Exception as e:
                    print('failed to download series image for %s [%r]'%(icon['title'],e))
                finally:
                    with QMutexLocker(self._writelock):
                        self._sql.updateCoverArts(((icon['aid'],None),))
    
    @QtCore.pyqtSlot()
    def run(self):
        '''
        Your code goes in this function
        '''
        try:
            with QMutexLocker(self._updatelock):
                with closing(sql.SQLManager()) as self._sql:
                    quick = self._quick
                    if not self._sql.getSettings():
                        self._signals.finished.emit()
                        return
                    # do some bookkeeping
                    with QMutexLocker(self._writelock):
                        changes = self._sql.hideOldSeries()
                        if changes:
                            self._signals.dataModified.emit()
                    
                    # some time consuming stuff:
                    # download the anidb title list if needed
                    # hash all files awaiting hashing
                    if not quick:
                        self.dl_titlelist()
                        self.hash_files()

                    # get new files from rss and also download the torrents
                    self.get_new_from_rss()

                    if not quick:
                        try:
                            # add parsed files to anidb, very finnicky so we wrap it in a try
                            self.anidb_adds()
                        except (ConnectionRefusedError, TimeoutError) as e:
                            logging.error('AniDB add failed (%r)'%e)

                        # attempt to title match one unconfirmed aid
                        with QMutexLocker(self._writelock):
                            self._sql.updateOneUnknownAid()

                    # check for downloaded files
                    self.check_file_changes()
                    
                    if not quick:
                        # get anidb info for new series
                        self.get_series_info()
                        # set poster icons
                        self.dl_poster_icons()
                    self._signals.finished.emit()
        except Exception as e:
            import traceback
            logging.error(str(e))
            logging.error(traceback.format_exc())
            self._signals.finishedWithErrors.emit()

class SettingsDialog(QtWidgets.QDialog):
    def __init__(self,initialSettings, parent=None):
        from PyQt5.QtCore import Qt
        super(SettingsDialog, self).__init__(parent)
        self.result=None
        self.setWindowTitle(self.tr("User Settings"))
        self.setWindowFlags(self.windowFlags() &~ Qt.WindowContextHelpButtonHint)

        mainLayout = QtWidgets.QVBoxLayout()

        mainLayout.setAlignment(Qt.AlignCenter)

        optionsLayout = QtWidgets.QFormLayout()
        confirmLayout = QtWidgets.QGridLayout()

        top=QtWidgets.QWidget()
        bottom=QtWidgets.QWidget()
        top.setLayout(optionsLayout)
        bottom.setLayout(confirmLayout)


        optionsLayout.addRow("<b>Required Settings:</b>",None)

        self.options = {}

        self.options['RSS Feed'] = QtWidgets.QLineEdit()
        self.options['RSS Feed'].setPlaceholderText("Paste your private RSS feed here.")
        optionsLayout.addRow("Private RSS Feed",self.options['RSS Feed'])

        
        fileSelect=QtWidgets.QWidget()
        fileSelectLayout=QtWidgets.QGridLayout()
        fileSelect.setLayout(fileSelectLayout)

        self.options['Download Directory']=QtWidgets.QLineEdit()
        self.options['Download Directory'].setPlaceholderText("Source Directory")
        self.dlBrowse=QtWidgets.QPushButton('&Browse')

        self.dlBrowse.released.connect(lambda:self.folderSelect(self.options['Download Directory']))
        
        fileSelectLayout.addWidget(self.options['Download Directory'],0,0)
        fileSelectLayout.addWidget(self.dlBrowse,0,1)
        optionsLayout.addRow("Download Directory",fileSelect)

        fileSelectLayout.setContentsMargins(0, 0, 0, 0)
        fileSelect.setContentsMargins(0, 0, 0, 0)


        fileSelect=QtWidgets.QWidget()
        fileSelectLayout=QtWidgets.QGridLayout()
        fileSelect.setLayout(fileSelectLayout)

        self.options['Save Directory']=QtWidgets.QLineEdit()
        self.options['Save Directory'].setPlaceholderText("Destination Directory")
        self.stBrowse=QtWidgets.QPushButton('&Browse')

        self.stBrowse.released.connect(lambda:self.folderSelect(self.options['Save Directory']))
        
        fileSelectLayout.addWidget(self.options['Save Directory'],0,0)
        fileSelectLayout.addWidget(self.stBrowse,0,1)
        optionsLayout.addRow("Storage Directory",fileSelect)

        fileSelectLayout.setContentsMargins(0, 0, 0, 0)
        fileSelect.setContentsMargins(0, 0, 0, 0)

        optionsLayout.addRow("<b>Optional Settings:</b>",None)
        self.options['anidb Username'] = QtWidgets.QLineEdit()
        optionsLayout.addRow("anidb Username",self.options['anidb Username'])

        self.options['anidb Password'] = QtWidgets.QLineEdit()
        self.options['anidb Password'].setEchoMode(QtWidgets.QLineEdit.Password)
        optionsLayout.addRow("anidb Password",self.options['anidb Password'])

        self.options['Shana Project Username'] = QtWidgets.QLineEdit()
        optionsLayout.addRow("Shana Project Username",self.options['Shana Project Username'])

        self.options['Shana Project Password'] = QtWidgets.QLineEdit()
        self.options['Shana Project Password'].setEchoMode(QtWidgets.QLineEdit.Password)
        optionsLayout.addRow("Shana Project Password",self.options['Shana Project Password'])

##        optionsLayout.addRow("<b>Unreliable without an anidb account:</b>",None)
        self.options['Season Sort']=QtWidgets.QCheckBox('Sort Episodes by Season')
        optionsLayout.addRow(self.options['Season Sort'])

        self.options['Poster Icons']=QtWidgets.QCheckBox('Use Poster Art for Folder Icons (Windows Only)')
        if os.name!='nt':
                self.options['Poster Icons'].setDisabled(True)
        optionsLayout.addRow(self.options['Poster Icons'])

        self.options['Auto Hide Old']=QtWidgets.QCheckBox('Automatically Hide Older Series (~1 month old)')
        optionsLayout.addRow(self.options['Auto Hide Old'])

        self.saveButton=QtWidgets.QPushButton('Save')
        self.cancelButton=QtWidgets.QPushButton('Cancel')
        
        confirmLayout.addWidget(self.saveButton,0,0)
        confirmLayout.addWidget(self.cancelButton,0,1)
        
        self.cancelButton.released.connect(self.close)
        self.saveButton.released.connect(self.saveValues)

        mainLayout.addWidget(top)
        mainLayout.addWidget(bottom)
        self.setLayout(mainLayout)

        for key in initialSettings.keys():
                if isinstance(self.options[key], QtWidgets.QCheckBox):
                        self.options[key].setCheckState(initialSettings[key])
                else:
                        self.options[key].setText(initialSettings[key])
                        
    def getValues(self):
        return self.result

    def folderSelect(self,destInput):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Open Directory",
                                                   ".",
                                                   QtWidgets.QFileDialog.ShowDirsOnly|
                                                   QtWidgets.QFileDialog.DontResolveSymlinks)
        if folder:
            destInput.setText(folder)

    def saveValues(self):
        self.result={}
        for key in self.options:
                if isinstance(self.options[key], QtWidgets.QCheckBox):
                        self.result[key] = self.options[key].checkState()
                else:
                        self.result[key] = str(self.options[key].text())# or None
        self.close()
        
class StillRunningDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        from PyQt5.QtCore import Qt

        super(StillRunningDialog, self).__init__(parent)
        self.result=0
        self.setWindowTitle(self.tr("Application is still running!"))
        self.setWindowFlags(self.windowFlags() &~ Qt.WindowContextHelpButtonHint)

        mainLayout = QtWidgets.QVBoxLayout()

        mainLayout.setAlignment(Qt.AlignCenter)

        optionsLayout = QtWidgets.QFormLayout()
        confirmLayout = QtWidgets.QGridLayout()

        top=QtWidgets.QWidget()
        bottom=QtWidgets.QWidget()
        top.setLayout(optionsLayout)
        bottom.setLayout(confirmLayout)
        mainLayout.setAlignment(Qt.AlignCenter)

        optionsLayout.addRow('Alastore is still running, double click on the tray icon to show the main window again.\nRight click the tray icon to exit completely.',None)
        self.dontshow=QtWidgets.QCheckBox('Don\'t show this message again.')
        optionsLayout.addRow(self.dontshow)
        
        self.saveButton=QtWidgets.QPushButton('OK')
        confirmLayout.addWidget(self.saveButton,0,1)
        mainLayout.addWidget(top)
        mainLayout.addWidget(bottom)
        self.setLayout(mainLayout)

        self.saveButton.released.connect(self.saveValues)
        
    def getValues(self):
        return self.result

    def saveValues(self):
        self.result=self.dontshow.checkState()
        self.close()
        
class DropDialog(QtWidgets.QDialog):
    def __init__(self, title, parent=None):
        from PyQt5.QtCore import Qt
        super(DropDialog, self).__init__(parent)
        self.setWindowTitle(self.tr("Drop Series"))
        self.setWindowFlags(self.windowFlags() &~ Qt.WindowContextHelpButtonHint)

        mainLayout = QtWidgets.QVBoxLayout()
        mainLayout.setAlignment(Qt.AlignCenter)

        optionsLayout = QtWidgets.QFormLayout()
        confirmLayout = QtWidgets.QGridLayout()

        top=QtWidgets.QWidget()
        bottom=QtWidgets.QWidget()
        top.setLayout(optionsLayout)
        bottom.setLayout(confirmLayout)
        mainLayout.setAlignment(Qt.AlignCenter)

        optionsLayout.addRow('''You are about to drop the series: %s.
This will delete your Shana Project follow and hide this series.
Are you sure you want to drop %s?'''%(title,title),None)
        self.deleteall=QtWidgets.QCheckBox('Also delete all episodes on my computer.')
        optionsLayout.addRow(self.deleteall)
        
        self.confirmButton=QtWidgets.QPushButton('OK')
        self.cancelButton=QtWidgets.QPushButton('Cancel')
        confirmLayout.addWidget(self.confirmButton,0,1)
        confirmLayout.addWidget(self.cancelButton,0,2)
        mainLayout.addWidget(top)
        mainLayout.addWidget(bottom)
        self.setLayout(mainLayout)

        self.confirmButton.released.connect(self.saveValues)
        self.cancelButton.released.connect(self.close)

        self.confirm = 0
        self.delete = 0
        
    def getValues(self):
        return self.confirm,self.delete

    def saveValues(self):
        self.delete=self.deleteall.checkState()
        self.confirm = 1
        self.close()
        
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

from qtrayico import HideableWindow


class HideableWithDialog(HideableWindow):
    def __init__(self, model):
        super(HideableWithDialog,self).__init__()
        self._model = model
        
    def closeEvent(self,event):
            super(HideableWithDialog,self).closeEvent(event)
            self._model.showAgainDialog(self.centralWidget())

from qtrayico import Systray

class trayIcon(Systray):
    def __init__(self,window,model):
        super(trayIcon,self).__init__(window)
        self._sql = sql.SQLManager()
        self._model = model
        
    def createActions(self):
        self.actions=[]

        self.updateAction= QtWidgets.QAction(self.tr("&Refresh"), self)
        self.updateAction.triggered.connect(self.refresh)
        
        self.configAction= QtWidgets.QAction(self.tr("&Config"), self)
        self.configAction.triggered.connect(self.showConfig)
        
        self.helpAction= QtWidgets.QAction(self.tr("&Help"), self)
        self.helpAction.triggered.connect(lambda:QtWidgets.QMessageBox.information(self,
                        "Guide",
'''<style>
dt {font-weight:bold;}
dd {margin-bottom:5px;margin-top:2px;}
ul { margin: 0; padding: 0; }
</style>
<dl>
<dt>Getting Started:</dt><dd>
        Select the Config option from the tray menu and fill out the required
        settings to get Alastore running. See below for details about the options.
        </dd>
<dt>Watching Series:</dt><dd>
        Double Click a header or any individual file to watch.
        Files that have not been previously watched will be sorted automatically into
        your specified storage directory.</div>

</dd>
<dt>Download Directory:</dt><dd>
        Download Directory refers to the location where completed downloads are
        saved to by your torrent application. User (~) and environment variables are
        supported.
    
</dd>
<dt>Storage Directory:</dt><dd>
        When you watch an episode, the file is sorted into a folder in your specified
        storage directory. If you choose 'C:/Anime' and watch 'SomeAnime_01.mkv'
        the file will be moved to 'C:/Anime/SomeAnime/SomeAnime_01.mkv'.
        If you have enabled "Sort Series by Season" in the config, series will be
        moved into a folder with the format: storagedirectory/year/season/title/
        for example: C:/Anime/2012/Winter 2012/SomeAnime/Someanime_01.mkv
        Additionally, if you are using Windows you have the option to give the folder
        a custom icon made from the poster art on anidb. User (~) and environment
        variables are supported.
        
</dd>
<dt>Anidb Username/Password:</dt><dd>
        If you provide these, each episode you watch will automatically be hashed and
        added to your anidb mylist.
        
</dd>
<dt>Shana Project Username/Password:</dt><dd>
        If you provide these, you will be given the option to drop a series, doing so will
        automatically delete the associated Shana Project feed. You can also choose to delete
        all downloaded episodes when you drop a series. (right-click to drop a series)
        
</dd>
<dt>Removing Series/Marking as Watched:</dt>
        <dd>Right click any series to show a context menu with two options.</dd><ul>
        <li>If you choose to hide a series it will reappear if a new episode appears in your
        RSS. If you want a series to be permanently hidden please also remove it from your
        RSS feed.</li><li>
        Marking a series as watched will mark all episodes of the series as having
        been watched. The only reason to do this is if you have previously watched
        episodes elsewhere and you want Alastore to keep you up to date on the
        latest episode without having to download/watch the previous ones.
        Note that there is (currently) no way to undo either of these actions.</li>
        <li>Two new options have been added, see ShanaProject username/password for info
        on dropping a series.</li></ul>

<dt>Tray Icon:</dt><dd>
        The refresh option checks your torrent folder and your RSS for any changes.
        Ordinarily this program will check for changes every 5-10 minutes but you can
        Refresh to check instantly.
        Double-click the icon to show the main window after it has been closed (minimized to tray).
    
</dd>
<dt>Missing Folder Icons/Series not Sorted:</dt><dd>
        These features will work more consistently if you provide a valid anidb account.
        They can (and likely will) function correctly without one but if you experience
        problems with either feature consider adding an anidb account.

</dd>
<dt>Extra:</dt><ul>
        <li>Use the -q arg to start Alastore minimized to tray, recommended if you have it in startup.</li>
        <li>Alastore is meant to be used in conjunction with anidb. Little testing has been done for usage without a linked account.
        If you experience issues try making a throwaway anidb account and adding it to the config.</li>
        <li>This software is very much beta. If you experience any strange behavior (bugs) first try restarting the
        program. If that doesn't fix your problem you can try deleting the .db
        file and starting over (not recommended unless you are experiencing a severe bug or are doing something like
        changing to a different RSS feed).</li></ul>
</dl>
'''))
                
        self.quitAction = QtWidgets.QAction(self.tr("&Quit"), self)
        self.quitAction.triggered.connect(QtWidgets.QApplication.quit)
        
        self.actions.append(self.updateAction)
        self.actions.append(self.configAction)
        self.actions.append(self.helpAction)
        self.actions.append(self.quitAction)

    def refresh(self):
        self._model.quickUpdate()

    def showConfig(self):
        self._model.configDialog(self.main_window)

if __name__ == '__main__':
    if os.path.exists('DEBUG_TEST'):
        logging.basicConfig(level=logging.DEBUG, filename='DEBUG.log')
    else:
        logging.basicConfig(level=logging.DEBUG, stream=io.BytesIO())
        logging.disable(logging.DEBUG)

    with closing(sql.SQLManager(createtables = True)) as s:pass
    
    app = QtWidgets.QApplication(sys.argv)
##    app.setStyle('Plastique')
    
    rootNode   = Node({})

    threadpool = QtCore.QThreadPool()
    writelock = QtCore.QMutex()
    updatelock = QtCore.QMutex()

    treeView = TreeView()
    model = TreeModel(rootNode,writelock,updatelock,threadpool)
    delegate = ItemDelegate()
    
    
    treeView.setExpandsOnDoubleClick(False)
    treeView.header().hide()
##    treeView.header().setStretchLastSection(True);
    treeView.setItemDelegate(delegate)
    treeView.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
    treeView.doubleClicked.connect(model.dblClickEvent)
##    treeView.resize(QtCore.QSize(350,delegate.listPadding[1]*2+delegate.getHeaderHeight(treeView.fontMetrics())*rootNode.childCount()))
    treeView.setIndentation(delegate.getHeaderHeight(treeView.fontMetrics()))
    treeView.setModel(model)
    
    model.sort(0)
##    treeView.show()

    fileupdate = FullUpdate(writelock,updatelock,quick=True)
    fileupdate._signals.dataModified.connect(model.sqlDataChanged)
    fileupdate._signals.updateEpisode.connect(model.updateEpisode)

    fullupdate = FullUpdate(writelock,updatelock)
    fullupdate._signals.dataModified.connect(model.sqlDataChanged)
    fullupdate._signals.updateEpisode.connect(model.updateEpisode)

    fullupdate.setAutoDelete(False)
    fullupdatetimer = QtCore.QTimer()
    fullupdatetimer.setInterval(FULLUPDATE_TIME)
    fullupdatetimer.timeout.connect(lambda: threadpool.start(fullupdate))
    fullupdatetimer.start()

##    QtCore.QTimer.singleShot(2000,lambda: threadpool.start(fullupdate))

    QtCore.QTimer.singleShot(INITIALUPDATE_GRACEPERIOD,lambda: threadpool.start(fileupdate))

    main = HideableWithDialog(model)#QtWidgets.QMainWindow()

    main.setWindowTitle('Alastore')
    main.setWindowIcon(QtGui.QIcon(resource_path("book.ico")))
    tray = trayIcon(main,model)

    main.setCentralWidget(treeView)
    main.resize(QtCore.QSize(350,delegate.listPadding[1]*2+delegate.getHeaderHeight(treeView.fontMetrics())*rootNode.childCount()))
##    main.move(QtCore.QPoint(main.pos().x(),0))
    if '-q' not in sys.argv and '/q' not in sys.argv and '/silent' not in sys.argv:
        main.show()
    app.setQuitOnLastWindowClosed(False)

    sys.exit(app.exec_())
