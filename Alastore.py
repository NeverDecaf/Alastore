#!/usr/bin/env python

'''
Dependencies used in this project:
https://pypi.python.org/pypi/BitTorrent-bencode v5.0.8.1
https://pypi.python.org/pypi/python1-Levenshtein/ v0.10.2
https://pypi.python.org/pypi/PIL/ v1.1.6
https://pypi.python.org/pypi/PyQt4/ PyQt4-4.10-gpl-Py2.6-Qt4.8.4-x32


you can install everything except pyqt using the following pip command:
pip install python-Levenshtein pillow BitTorrent-bencode

python 2.7.9 or later is required. (not 3 obviously)
'''

from PyQt4 import QtGui
from PyQt4 import QtCore
import os
UPDATEINTERVAL=10*60*1000# ms between full updates (full update means poster dl, anidb add, file hashing.)
FILEUPDATEINTERVAL=120*1000# ms between file updates (only file check, though this can be a lengthy operation due to hashing.)
#feel free to add more/better color schemes.
# fg is text color, otherwise is background color, h is for the header (most recent episode)
# notdownloaded==downloading.
#downloadprogressh is the color of the progress bar for downloading episodes that will appear in the header
# in that case, notdownloadedh will provide the background for that bar.
#background is the main qscrollarea's background; the background of the main window
#this is the OG colorscheme:
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
from PyQt4.QtGui import QGroupBox
 
class AccordianItem( QGroupBox ):


                
        listPadding = (0,0)#padding that will go around the sides of the list. you only get horizontal and vertical
        textPadding = (6,4)#inner padding basically. between the sides of the box and the text inside.
        itemHeight = 20# these 2 will be reassigned later.
        collapseControlWidth = itemHeight # this is the +/- box on the left
        
        def __init__( self, accordian, title, widget ):
                QGroupBox.__init__( self, accordian )
 
                # create the layout
                from PyQt4.QtCore import Qt
                from PyQt4.QtGui import QVBoxLayout


                self._accordianWidget = accordian

                fm = self.fontMetrics()
                self.itemHeight = self.collapseControlWidth = (fm.boundingRect('test').height() + self.textPadding[1]*2)>>1<<1 # shift to round down to nearest multiple of 2
##                self._rolloutStyle = 2
##                self._dragDropMode = 0
 
                self.setContextMenuPolicy( Qt.CustomContextMenu )
                self.customContextMenuRequested.connect( self.showMenu )
 
                # create custom properties
                self._widget            = widget
                self._collapsed         = False
                self._collapsible       = True
                self._clicked           = False

                self.new = 0 # no new episodes(by default)
                self.downloading=0
                self.percentDownloaded=0
                # set common properties
                self.setTitle( title )


                self.contextMenu=QtGui.QMenu()
                self.contextMenu.addAction("&Hide Series", self, SLOT('hideSeries()'))

                self.contextMenu.addAction("&Mark All Watched", self, SLOT('markWatched()'))

                self.markWatchedAction = self.contextMenu.addAction("&Mark Episode Watched", self, SLOT('markIndivWatched()'))
                
                self.connect(self,SIGNAL("customContextMenuRequested(QPoint)"),self.execContextMenu)

                # instead of a layout we position the widget manually. there were some issues on
                # linux if this wasn't done.
                self._widget.setParent(self)
		wsize = widget.sizeHint()
		self._widget.setGeometry(1+self.listPadding[0],self.itemHeight + 1 + self.listPadding[1],wsize.width()-2-self.listPadding[0]*2,wsize.height())
 
        def accordianWidget( self ):
                """
                        \remarks        grabs the parent item for the accordian widget
                        \return         <blurdev.gui.widgets.accordianwidget.AccordianWidget>
                """
                return self._accordianWidget
 
        from PyQt4.QtCore import pyqtSlot
        @pyqtSlot() 
        def hideSeries(self):
            if not QtGui.QMessageBox.warning(
		self, "Hide Series?",
		'''This series will be removed from this list until a new episode appears in your RSS.
You cannot undo this action.
Are you sure you wish to hide the series:
"%s"'''%self._widget.title,
		"&Yes", "&No", defaultButtonNumber=1, escapeButtonNumber=1 ):
                self._widget.hideSeries()
                self._widget.refreshData()
        @pyqtSlot()
        def markWatched(self):
            if not QtGui.QMessageBox.warning(
		self, "Mark Watched?",
		'''This will mark every episode in this series "%s" as watched.
This includes files which have not yet been downloaded.
Marking files watched this way will NOT add them to your mylist nor will it move
and sort them. It will also render them incapable of being added or sorted in the future.
Make sure you have watched every episode you mean to watch before doing this.
Are you sure you wish to mark all episodes of %s as watched?
(You cannot undo this action)'''%(self._widget.title,self._widget.title),
		"&Yes", "&No", defaultButtonNumber=1, escapeButtonNumber=1 ):
                    self._widget.markSeriesWatched()
                    self._widget.refreshData()
        @pyqtSlot()
        def markIndivWatched(self):
            if not QtGui.QMessageBox.warning(
		self, "Mark Watched?",
		'''Are you sure you want to force mark the file: %s as watched?
Force marking a file this way will NOT automatically sort/move the file and it will NEVER add the file to your mylist.
You should only use this option if a file fails to download or is moved/deleted before you can watch it through Alastore.'''%(self._widget.selectedEpisodeName()),
		"&Yes", "&No", defaultButtonNumber=1, escapeButtonNumber=1 ):
                    self._widget.markEpisodeWatched()
                    self._widget.refreshData()
                    
        def execContextMenu(self,position):
##            gpos=self._accordianWidget.viewport().mapToGlobal(position)
            gpos=self.mapToGlobal(position)
            if self._widget.episodeSelected() and position.y()>self.itemHeight and position.y()<self.rect().height()-1:
                self.markWatchedAction.setEnabled(True)
            else:
                self.markWatchedAction.setEnabled(False)
            self.contextMenu.exec_(gpos)
            
        def doubleClickRect( self ):
                from PyQt4.QtCore import QRect
                return QRect( self.collapseControlWidth, 0, self.rect().width() - self.collapseControlWidth - 1, self.itemHeight )
            
        def dragEnterEvent( self, event ):
                if ( not self._dragDropMode ):
                        return
 
                source = event.source()
                if ( source != self and source.parent() == self.parent() and isinstance( source, AccordianItem ) ):
                        event.acceptProposedAction()

        def dragDropRect( self ):
                from PyQt4.QtCore import QRect
                return QRect( 25, 7, 10, 6 )
 
        def dragDropMode( self ):
                return self._dragDropMode
 
        def dragMoveEvent( self, event ):
                if ( not self._dragDropMode ):
                        return
 
                source = event.source()
                if ( source != self and source.parent() == self.parent() and isinstance( source, AccordianItem ) ):
                        event.acceptProposedAction()
 
        def dropEvent( self, event ):
                widget = event.source()
                layout = self.parent().layout()
                layout.insertWidget( layout.indexOf(self), widget )
                self._accordianWidget.emitItemsReordered()
 
        def expandCollapseRect( self ):
                from PyQt4.QtCore import QRect
                return QRect( 0, 0, self.collapseControlWidth, self.itemHeight )
 
        def enterEvent( self, event ):
                self.accordianWidget().leaveEvent( event )
                event.accept()
 
        def leaveEvent( self, event ):
                self.accordianWidget().enterEvent( event )
                event.accept()
                
        def mouseDoubleClickEvent( self, event ):
            from PyQt4.QtCore import Qt
            if ( event.button() == Qt.LeftButton and self.doubleClickRect().contains( event.pos() ) ):
                self._widget.headerClicked()
                                                      
        def mouseReleaseEvent( self, event ):
                if ( self._clicked and self.expandCollapseRect().contains( event.pos() ) ):
                        self.toggleCollapsed()
                        event.accept()
                else:
                        event.ignore()
 
                self._clicked = False
 
        def mouseMoveEvent( self, event ):
                event.ignore()
 
        def mousePressEvent( self, event ):
                # handle an internal move
                from PyQt4.QtCore import Qt
 
                if ( event.button() == Qt.LeftButton and self.expandCollapseRect().contains( event.pos() ) ):
                        self._clicked = True
                        event.accept()
                else:
                        event.ignore()
        
        def isCollapsed( self ):
                return self._collapsed
 
        def isCollapsible( self ):
                return self._collapsible
 
        def paintEvent( self, event ):
                from PyQt4.QtCore       import Qt, QRect
                from PyQt4.QtGui        import QPainter, QPainterPath, QPalette, QPixmap, QPen
 
                painter = QPainter()
                painter.begin( self )
                painter.setRenderHint( painter.Antialiasing )
 
                x = self.rect().x()
                y = self.rect().y()
                w = self.rect().width() - 1
                h = self.rect().height() - 1
                
                pen = QPen( self.palette().color( QPalette.Light ) )
                painter.setRenderHint( painter.Antialiasing, False )
                pen.setColor( self.palette().color( QPalette.Shadow ) )
                painter.setPen( pen )

                # this is the border for an expanded element. we only draw it if this series is expanded. (to avoid thick lines from overlap)
                if not self.isCollapsed():
                    # draw the borders
                    painter.drawRect( QRect( x, y, w, h ) )

                if self.new:
                    painter.setBrush( COLORSCHEME['downloadedh'] )
                elif self.downloading:
                    painter.setBrush( COLORSCHEME['notdownloadedh'] )
                else:
                    painter.setBrush( COLORSCHEME['watchedh'] )
                    
                painter.drawRect( x , y , w , self.itemHeight )
                if self.downloading:
                        painter.setBrush( COLORSCHEME['downloadprogressh'] )
                        painter.fillRect( x+1 , y+1 , max(0,int(self.percentDownloaded*(w/100.))-1) , self.itemHeight-1, COLORSCHEME['downloadprogressh'] )
                painter.drawLine( x+self.collapseControlWidth,y,x+self.collapseControlWidth,y+self.itemHeight)


                # draw the +/-
                if ( self.isCollapsed() ):
                    painter.fillRect( x+self.collapseControlWidth/2 , y+self.itemHeight/4 , 1,1+self.itemHeight-self.itemHeight/4*2,painter.pen().color())
                painter.fillRect( x+self.collapseControlWidth/4 , y+self.itemHeight/2 , 1+self.collapseControlWidth-self.collapseControlWidth/4*2,1,painter.pen().color())
##                if ( self.isCollapsed() ):
##                    print self.itemHeight>>1
##                    painter.fillRect( x+self.collapseControlWidth>>1 , y+self.itemHeight>>2 , 1,(self.itemHeight>>1)+1,painter.pen().color())
##                painter.fillRect( x+self.collapseControlWidth>>2 , y+self.itemHeight>>1 , (self.collapseControlWidth>>1)+1,1,painter.pen().color())
                
##                        painter.drawText( x + 16, y + 1, w - 32, 20, Qt.AlignLeft | Qt.AlignVCenter, text )
                if self.new:
                    pen.setColor(COLORSCHEME['downloadedfg'])
                elif self.downloading:
                    pen.setColor(COLORSCHEME['notdownloadedfg'] )
                else:
                    pen.setColor(COLORSCHEME['watchedfg'])
                painter.setPen(pen)
                
                painter.drawText( x + self.collapseControlWidth + self.textPadding[0], y , w - self.collapseControlWidth - self.textPadding[0], self.itemHeight, Qt.AlignLeft |Qt.AlignVCenter, self.title())


##                
##                print painter.fontInfo()
##                fm = painter.fontMetrics()
##                print fm.boundingRect(self.title()).size()
##                print fm.height()
##
##                
####                self.realWidth = fm.boundingRect(self.title()).size().width()
##                font = QtGui.QFont(self.font().family(),10)
##                font.setPixelSize(11)
##                fm = QtGui.QFontMetrics(font)
##                print fm.boundingRect(self.title()).size()
##

                
                painter.end()
        
        def minimumSizeHint(self):
                fm = self.fontMetrics()
                size = fm.boundingRect(self.title()).size()
                # the extra numbers are: 20 for the gap on the left where the + is drawn,
                # 6 and 6 to match the gap from the + to the beginning of the title as given in painter.drawText
                # (the second 6 is for the right hand side gap, in case that was unclear)
                size.setWidth(size.width()+self.collapseControlWidth + self.textPadding[0]*2)
##                print 'normal:',super(AccordianItem,self).minimumSizeHint()
##                print 'bounded:',size
                if not self._collapsed:
		    listSize = self._widget.listWidget.sizeHint()
		    listSize.setWidth(listSize.width() +2+self.listPadding[0]*2) #room for borders??
		    return self._widget.listWidget.sizeHint().expandedTo(size)
		return size
##                return super(AccordianItem,self).minimumSizeHint().expandedTo(size)
	
	def resizeEvent(self, event):
		#self._widget.setMinimumWidth(self.rect().width()-8)
		#print self.rect().width()
		geometry = self._widget.geometry()
		geometry.setWidth(self.rect().width()-2-self.listPadding[0]*2)
##		geometry.setHeight(self.rect().height()+2+self.listPadding[1]*2)
		self._widget.setGeometry(geometry)
		#self._widget.setGeometry(2,22,self.rect().width()-20,self.rect().height())
		
        def setCollapsed( self, state = True ):
                if ( self.isCollapsible() ):
                        accord = self.accordianWidget()
                        accord.setUpdatesEnabled(False)
 
                        self._collapsed = state
 
                        if ( state ):
                                self.setMinimumHeight( self.itemHeight + 2 )
                                self.setMaximumHeight( self.itemHeight + 2 )
                                self.widget().setVisible( False )
                        else:
                                self.setMinimumHeight(self._widget.minimumSizeHint().height()+self.itemHeight+self.listPadding[1]*2+2)
                                self.setMaximumHeight( 1000000 )
                                self.widget().setVisible( True )
 
                        self._accordianWidget.emitItemCollapsed( self )
                        accord.setUpdatesEnabled(True)
 
        def setCollapsible( self, state = True ):
                self._collapsible = state

        def setStatus(self,new,downloading,percent):
            self.new=new
            self.downloading=downloading
            self.percentDownloaded=percent
                
        def showMenu( self ):
                from PyQt4.QtCore import QRect
                from PyQt4.QtGui import QCursor
                if ( QRect( 0, 0, self.width(), self.itemHeight ).contains( self.mapFromGlobal( QCursor.pos() ) ) ):
                        self._accordianWidget.emitItemMenuRequested( self )
 
        def toggleCollapsed( self ):
                self.setCollapsed( not self.isCollapsed() )
 
        def widget( self ):
                return self._widget

from PyQt4.QtCore       import pyqtSignal, pyqtProperty
from PyQt4.QtGui        import QScrollArea
#from accordianitem     import AccordianItem
 
class AccordianWidget( QScrollArea ):
        itemCollapsed           = pyqtSignal(AccordianItem)
        itemMenuRequested       = pyqtSignal(AccordianItem)
        itemDragFailed          = pyqtSignal(AccordianItem)
        itemsReordered          = pyqtSignal()
 
        Boxed           = 1
        Rounded         = 2
 
        NoDragDrop              = 0
        InternalMove    = 1
 
        def __init__( self, seriesManager, parent):
                QScrollArea.__init__( self, parent )
 
                self.setFrameShape( QScrollArea.NoFrame )
                self.setAutoFillBackground( False )
                self.setWidgetResizable( True )
##                self.setMouseTracking(True)
##                self.verticalScrollBar().setMaximumWidth(10)
 
                from PyQt4.QtGui import QWidget
                widget = QWidget( self )
 
                # define custom properties
##                self._rolloutStyle      = AccordianWidget.Rounded
##                self._dragDropMode      = AccordianWidget.NoDragDrop
                self._scrolling         = False
                self._scrollInitY       = 0
                self._scrollInitVal     = 0
                self._itemClass         = AccordianItem
                
                pal = self.palette()
                pal.setColor(self.backgroundRole(), COLORSCHEME['background']);
                self.setPalette(pal)
                # create the layout
                from PyQt4.QtGui import QVBoxLayout
                self.expanded = []
                self.seriesManager=seriesManager
                self.lock=QtCore.QMutex()
 
                layout = QVBoxLayout()
                layout.setContentsMargins( 3, 3, 3, 3 )
                layout.setSpacing( 3 )
                layout.addStretch(1)

                self.firstStartLabel = QtGui.QLabel(' Right click the tray icon to get started!')
                widget.setLayout( layout )
                self.actualWidget = widget
 
                self.setWidget( self.firstStartLabel )
                self.quickUpdate()
##                self.waitThenUpdate()
                self.updateBegin(False,True)
                self.waitThenFUpdate()

                #DONT FORGET TO REMOVE THIS
##                self.debugUpdate()

                self.downloadInProgress=False
##                QtCore.QTimer.singleShot(0,lambda: self.resize(self.sizeHint()))
                
        def sizeHint(self):
                if self.widget() != self.firstStartLabel:
                        layout = self.widget().layout()
                        size = layout.minimumSize()
                        if self.verticalScrollBar().isVisible():
                                sw = self.verticalScrollBar().sizeHint().width()
                                size.setWidth(size.width()+sw)
                        return size
                return super(AccordianWidget,self).sizeHint()
        
        def addItem( self, title, widget, collapsed = False ):
                self.setUpdatesEnabled(False)
                item    = self._itemClass( self, title, widget )
                layout  = self.widget().layout()
                layout.insertWidget( layout.count() - 1, item )
                layout.setStretchFactor( item, 0 )

                if ( collapsed ):
                        item.setCollapsed(collapsed)
 
                self.setUpdatesEnabled(True)
                return item

        def clear( self ):
                if self.widget() == self.firstStartLabel:
                        return
                self.setUpdatesEnabled(False)
                layout = self.widget().layout()
                self.expanded=[]
                while ( layout.count() > 1 ):
                        item = layout.itemAt(0)

                        # remove the item from the layout
                        w = item.widget()
                        if not w.isCollapsed():
                            self.expanded.append(w.widget().getTitle())
                        layout.removeItem( item )
 
                        # close the widget and delete it
                        w.close()
                        w.deleteLater()
 
                self.setUpdatesEnabled(True)
 
##        def eventFilter( self, object, event ):
##                from PyQt4.QtCore import QEvent
## 
##                if ( event.type() == QEvent.MouseButtonPress ):
##                        self.mousePressEvent( event )
##                        return True
## 
##                elif ( event.type() == QEvent.MouseMove ):
##                        self.mouseMoveEvent( event )
##                        return True
## 
##                elif ( event.type() == QEvent.MouseButtonRelease ):
##                        self.mouseReleaseEvent( event )
##                        return True
## 
##                return False
 
        def canScroll( self ):
                return self.verticalScrollBar().maximum() > 0
 
        def count( self ):
                return self.widget().layout().count() - 1
 
        def dragDropMode( self ):
                return self._dragDropMode
 
        def indexOf(self, widget):
                """
                        \remarks        Searches for widget(not including child layouts).
                                                Returns the index of widget, or -1 if widget is not found
                        \return         <int>
                """
                layout = self.widget().layout()
                for index in range(layout.count()):
                        if layout.itemAt(index).widget().widget() == widget:
                                return index
                return -1
 
        def isBoxedMode( self ):
                return self._rolloutStyle == AccordianWidget.Boxed
 
        def itemClass( self ):
                return self._itemClass
 
        def itemAt( self, index ):
                layout = self.widget().layout()
                if ( 0 <= index and index < layout.count() - 1 ):
                        return layout.itemAt( index ).widget()
                return None
 
        def emitItemCollapsed( self, item ):
                if ( not self.signalsBlocked() ):
                        self.itemCollapsed.emit(item)
 
        def emitItemDragFailed( self, item ):
                if ( not self.signalsBlocked() ):
                        self.itemDragFailed.emit(item)
 
        def emitItemMenuRequested( self, item ):
                if ( not self.signalsBlocked() ):
                        self.itemMenuRequested.emit(item)
 
        def emitItemsReordered( self ):
                if ( not self.signalsBlocked() ):
                        self.itemsReordered.emit()
 
##        def enterEvent( self, event ):
##                if ( self.canScroll() ):
##                        from PyQt4.QtCore import Qt
##                        from PyQt4.QtGui import QApplication
##                        QApplication.setOverrideCursor( Qt.OpenHandCursor )
## 
##        def leaveEvent( self, event ):
##                if ( self.canScroll() ):
##                        from PyQt4.QtGui import QApplication
##                        QApplication.restoreOverrideCursor()
## 
##        def mouseMoveEvent( self, event ):
##                if ( self._scrolling ):
##                        sbar    = self.verticalScrollBar()
##                        smax    = sbar.maximum()
## 
##                        # calculate the distance moved for the moust point
##                        dy                      = event.globalY() - self._scrollInitY
## 
##                        # calculate the percentage that is of the scroll bar
##                        dval            = smax * ( dy / float(sbar.height()) )
## 
##                        # calculate the new value
##                        sbar.setValue( self._scrollInitVal - dval )
## 
##                event.accept()
## 
##        def mousePressEvent( self, event ):
##                # handle a scroll event
##                from PyQt4.QtCore import Qt
##                from PyQt4.QtGui import QApplication
## 
##                if ( event.button() == Qt.LeftButton and self.canScroll() ):
##                        self._scrolling                 = True
##                        self._scrollInitY               = event.globalY()
##                        self._scrollInitVal     = self.verticalScrollBar().value()
## 
##                        QApplication.setOverrideCursor( Qt.ClosedHandCursor )
## 
##                event.accept()
## 
##        def mouseReleaseEvent( self, event ):
##                from PyQt4.QtCore       import Qt
##                from PyQt4.QtGui        import QApplication
## 
##                if ( self._scrolling ):
##                        QApplication.restoreOverrideCursor()
## 
##                self._scrolling                 = False
##                self._scrollInitY               = 0
##                self._scrollInitVal             = 0
##                event.accept()
## 
##        def moveItemDown(self, index):
##                layout = self.widget().layout()
##                if (layout.count() - 1) > (index + 1):
##                        widget = layout.takeAt(index).widget()
##                        layout.insertWidget(index + 1, widget)
## 
##        def moveItemUp(self, index):
##                if index > 0:
##                        layout = self.widget().layout()
##                        widget = layout.takeAt(index).widget()
##                        layout.insertWidget(index - 1, widget)
                        
        def keyf(self,x):
            return str(1-x.hasUnwatched())+str(1-x.isDownloading())+x.getTitle().lower()
        
        def populate(self, seriesManager, expandAll=False):
            # load data from series
            self.manager=seriesManager
            self.data = seriesManager.SQL.getSeries()
            allItems=[]
            # create series widgets to be added
            for key in sorted(self.data.keys()):
                if self.data[key] and not self.data[key][0]['hidden']: #whats up with that, commented cus i dont understand
                    # I now understand, the first part of this if statement is necessary because a series can exist without any data (before its been fetched)
                    allItems.append(SeriesGui(dlg,self.data,seriesManager,key))
                    allItems[-1].generateBox()
            #sort items alphabetically with unwatched on top
            allItems.sort(key=self.keyf)
##            if 0==len(allItems):
##                self.setWidget(self.firstStartLabel)
##            elif self.widget() == self.firstStartLabel:
            if len(allItems) and self.widget() == self.firstStartLabel:
                self.setWidget(self.actualWidget)
            # insert items into this accordianwidget; init the title of each.
            for wrapper in allItems:
                item = self.addItem(key, wrapper, True)
                wrapper.setSeries(item)
                wrapper.setTitle()
                if wrapper.getTitle() in self.expanded:
                    item.setCollapsed(False)

        def refreshAll(self):
            self.clear()
            self.populate(self.manager)
            
        def setBoxedMode( self, state ):
                if ( state ):
                        self._rolloutStyle = AccordianWidget.Boxed
                else:
                        self._rolloutStyle = AccordianWidget.Rounded

        def queueShowAgain(self):
                QtCore.QTimer.singleShot(0,self.setShowAgain)
                
        def setShowAgain(self):
                if not self.seriesManager.SQL.getShowAgain():
                        d=StillRunningDialog(self)
                        d.exec_()
                        showagain=d.getValues()
                        self.seriesManager.SQL.setShowAgain(showagain)
                        
                
        def takeAt( self, index ):
                self.setUpdatesEnabled(False)
                layout = self.widget().layout()
                widget = None
                if ( 0 <= index and index < layout.count() - 1 ):
                        item = layout.itemAt(index)
                        widget = item.widget()
 
                        layout.removeItem(item)
                        widget.close()
                self.setUpdatesEnabled(True)
                return widget
 
        def widgetAt( self, index ):
                item = self.itemAt( index )
                if ( item ):
                        return item.widget()
                return None
 
        pyBoxedMode = pyqtProperty( 'bool', isBoxedMode, setBoxedMode )

        def quickUpdate(self):
            QtCore.QTimer.singleShot(0,lambda:self.updateBegin(True))

        def waitThenFUpdate(self):
            QtCore.QTimer.singleShot(FILEUPDATEINTERVAL,self.fileUpdateBegin)
            
        def waitThenUpdate(self):
            QtCore.QTimer.singleShot(UPDATEINTERVAL,lambda:self.updateBegin(False,True))

        def debugUpdate(self):
##            use only for debug purposes
            QtCore.QTimer.singleShot(1000,lambda:self.updateBegin(False,False))

##        fupdatecount = 0
        def fileUpdateBegin(self,quick=True):
            #create the business thread
            if not self.lock.tryLock():
                #requeue for a few seconds, this prevents hanging.
                QtCore.QTimer.singleShot(1*1000,lambda:self.fileUpdateBegin(quick))
                return
            # ensure another update even if these threads throw exceptions.
##            print 'file update begun (%i)'%self.fupdatecount
##            self.fupdatecount+=1
            if not self.downloadInProgress:
                self.waitThenFUpdate()
                self.lock.unlock()
                return
##            self.thread = SingleCallThread(lambda:self.seriesManager.phase2Thread(quick),self.lock,self)
            self.thread = SingleCallThread(self.seriesManager.icheckFiles,self.lock,self)
            self.connect(self.thread, SIGNAL("finished()"), lambda:self.fileUpdateEnd(quick))
            try:
                self.seriesManager._getUserSettings()
                self.seriesManager._populateSeries()
                self.seriesManager.prepCheckFiles()
##                self.seriesManager.phase2Prep(quick)
            except:
                self.waitThenFUpdate()
                self.lock.unlock()
                raise
            self.thread.start()

        def fileUpdateEnd(self,quick):
            try:
                self.downloadInProgress=self.seriesManager.checkFiles()
                if self.downloadInProgress:
                    self.refreshAll()
            finally:
                self.waitThenFUpdate()
                self.lock.unlock()

        def updateBegin(self,quick=False,schedule=False):
            #create the business thread
            if not self.lock.tryLock():
                #requeue for a few seconds, this prevents hanging.
                QtCore.QTimer.singleShot(1*1000,lambda:self.updateBegin(quick,schedule))
                return
            # ensure another update even if these threads throw exceptions.
            if schedule and not quick:
                self.waitThenUpdate()# only schedule another update if this is the slow update
            if schedule and quick:
                self.waitThenQUpdate()# only schedule another update if this is the quick update
                
            self.thread = SingleCallThread(lambda:self.seriesManager.phase1Thread(quick),self.lock,self)
            self.connect(self.thread, SIGNAL("finished()"), lambda:self.updateMid0(quick))
            try:
                if not self.seriesManager.phase1Prep(quick):
                        self.lock.unlock()
                        return # false means there is no config yet, just quit out.
            except:
                self.lock.unlock()
                raise
            self.thread.start()

        def updateMid0(self,quick):
            #create the business thread
            # no refresh, its a gap.
            self.thread = SingleCallThread(lambda:self.seriesManager.phase1Thread2(quick),self.lock,self)
            self.connect(self.thread, SIGNAL("finished()"), lambda:self.updateMid1(quick))
            try:
                self.seriesManager.phase1Gap(quick)
            except:
                self.lock.unlock()
                raise
            self.thread.start()
            
        def updateMid1(self,quick):
            #create the business thread
            try:
                if self.seriesManager.phase1End(quick):
##                    print 'phase 1 had changes'
                    self.refreshAll()
            except:
                self.lock.unlock()
                raise
            self.thread = SingleCallThread(lambda:self.seriesManager.phase2Thread(quick),self.lock,self)
            self.connect(self.thread, SIGNAL("finished()"), lambda:self.updateMid2(quick))
            try:
                self.seriesManager.phase2Prep(quick)
            except:
                self.lock.unlock()
                raise
            self.thread.start()

        def updateMid2(self,quick):
            #create the business thread
            try:
                self.downloadInProgress=self.seriesManager.phase2End(quick)
                if self.downloadInProgress:
                    self.refreshAll()
            except:
                self.lock.unlock()
                raise
            self.thread = SingleCallThread(lambda:self.seriesManager.phase3Thread(quick),self.lock,self)
            self.connect(self.thread, SIGNAL("finished()"), lambda:self.updateEnd(quick))
            try:
                self.seriesManager.phase3Prep(quick)
            except:
                self.lock.unlock()
                raise
            self.thread.start()

        def updateEnd(self,quick):
            try:
                if self.seriesManager.phase3End(quick):
                        self.refreshAll()
            finally:
                self.lock.unlock()


class SingleCallThread(QtCore.QThread):
    def __init__(self, method, lock, parent=None):
        QtCore.QThread.__init__(self, parent)
        self.runmethod = method
        self.lock=lock
        
    def run(self):
        try:
            changes = self.runmethod()
        except:
            self.lock.unlock()
            raise

class NonLockingCallThread(QtCore.QThread):
    finished = QtCore.pyqtSignal(object,object,QtGui.QListWidgetItem)
    
    def __init__(self, method, callback, item, parent=None):
        QtCore.QThread.__init__(self, parent)
        self.runmethod = method
        self.item=item
        self.finished.connect(callback)
        
    def run(self):
        r1,r2 = self.runmethod()
        self.finished.emit(r1,r2,self.item)


from PyQt4.QtCore import pyqtSlot,SIGNAL,SLOT

class myListWidget(QtGui.QListWidget):
    def __init__(self,parent=None):
        super(myListWidget,self).__init__(parent)
        self.setSelectionMode(QtGui.QListWidget.NoSelection)
##        self.setStyleSheet( """ QListWidget:item:selected:active {
##                                     background: none;
##                                }
##                                QListWidget:item:selected:!active {
##                                     background: none;
##                                }
##                                QListWidget:item:selected:disabled {
##                                     background: none;
##                                }
##                                QListWidget:item:selected:!disabled {
##                                     background: none;
##                                }
##                                """
##                                )
    def sizeHint(self):
        from PyQt4.QtCore import QSize
        return QSize(self.sizeHintForColumn(0),self.sizeHintForRow(0))
##        self.listWidget.setSizeHint(QSize(self.listWidget.sizeHintForColumn(0),self.listWidget.sizeHintForRow(0)*self.listWidget.count()))



        
class SeriesGui(QtGui.QWidget):

    #data wont be none in the final release
    def __init__(self,parent,data,seriesManager,title):
        QtGui.QWidget.__init__(self, parent)
##        self.setFlat(False)
        self.data = data
        self.title= title
        self.latest=None
        self.series=None
        self.latestDownloaded=None
        self.downloadPercent=None
        self.seriesManager=seriesManager
        self.layout = QtGui.QVBoxLayout(self)
        self.layout.setSpacing( 0 )
        self.layout.setContentsMargins(0,0,0,0)
        self.listWidget= myListWidget()#QtGui.QListWidget()
        self.listWidget.setFrameStyle(0)
        self.listWidget.connect(self.listWidget,SIGNAL("itemDoubleClicked(QListWidgetItem*)"),
               self,SLOT("doubleClickedSlot(QListWidgetItem*)"))
        self.layout.addWidget(self.listWidget)
##        GroupBox.setWindowTitle(QtGui.QApplication.translate("GroupBox", "GroupBox", None, QtGui.QApplication.UnicodeUTF8))
##        return self

    def setSeries(self,widget):
        self.series = widget

    @pyqtSlot(QtGui.QListWidgetItem)    
    def doubleClickedSlot(self,item):
        self.play(item)

    def play(self,item):
        from PyQt4.QtCore import Qt
        data = item.data(Qt.UserRole).toPyObject()[0]
        if data['downloaded']>0:
            if self.seriesManager.prepPlayAndSort()==-1:
                QtGui.QMessageBox.information(self,
                        "No Settings Found!",
			"Please fill out the required user settings\nbefore watching an episode.")
            else:
                'play the file in a separate thread to prevent ui lag.'
                self.pthread = NonLockingCallThread(lambda:self.seriesManager.playAndSort(data),self.playEnd,item,self)
                self.pthread.start()

    def playEnd(self,path,dest_file,item):
        if path!='watched':
            self.seriesManager.playAndSortFinalize(path,dest_file)
            self.refreshData()
            self.colorize(item)
            
    def refreshData(self):
        self.parent()._accordianWidget.refreshAll()

    def hasUnwatched(self):
        return self.latestDownloaded!=None

    def isDownloading(self):
        return self.downloading!=None

    def getTitle(self):
        return self.title
        
    def generateBox(self):
        from PyQt4.QtCore import Qt
        # god this line ruined everything
##        self.data=self.seriesManager.SQL.getSeries()
        self.latest=None
        self.downloading = None
        self.latestEpisode=None
        self.upToDate=None
        self.latestDownloaded=None
        self.downloadPercent=None
        #ADVANCED TECHNIQUE:
        ''' if self.title no longer a key in self.data then have self.parent remove self.series'''
        ''' dont know how safe this is so check this out later'''
        ''' not needed since we just refresh the entire list every update'''
        for i in range(len(self.data[self.title])):
            item=self.data[self.title][i]
            if i<self.listWidget.count():
                newItem=self.listWidget.item(self.listWidget.count()-1-i)
                newItem.setData(Qt.UserRole,(item,))
                #already exists just update its data.
            else:
                listItem = QtGui.QListWidgetItem(item['display_name'])
                self.listWidget.insertItem(0,listItem)
                newItem=self.listWidget.item(0)
                newItem.setData(Qt.UserRole,(item,))
                self.colorize(newItem)
            if not self.latest and item['watched']==0 and not self.downloading:
                if item['downloaded']>0: # alternatively you can just check for downloaded here. it won't really catch failed to dl errors though.
                    self.latest=newItem
                    self.latestDownloaded=item['episode']
                else:
                    self.downloading=item['episode']
                    self.downloadPercent=item['download_percent']
        # if we are up to date, set latest to be the latest watched
        if not self.latest and not self.downloading:
            first=self.data[self.title][-1]
            if first:
                self.latestEpisode=first['episode']
                if first['downloaded'] and first['watched']:
                    self.latest=self.listWidget.item(0)
##                self.upToDate=1
        
        self.listWidget.setMaximumHeight(self.listWidget.sizeHintForRow(0)*self.listWidget.count())
##        self.listWidget.setMinimumWidth(self.listWidget.sizeHintForColumn(0))

        self.listWidget.setMinimumSize(self.listWidget.sizeHintForColumn(0),self.listWidget.sizeHintForRow(0)*self.listWidget.count())
    def colorize(self,item):
        from PyQt4.QtCore import Qt
        data = item.data(Qt.UserRole).toPyObject()[0]
        if data['downloaded']==0:
            item.setForeground(COLORSCHEME['notdownloadedfg'])
            item.setBackground(COLORSCHEME['notdownloaded'])
            if data['watched']:
                item.setForeground(COLORSCHEME['forcewatchedfg'])
                item.setBackground(COLORSCHEME['forcewatched'])
        elif data['watched']==0:
            item.setForeground(COLORSCHEME['downloadedfg'])
            item.setBackground(COLORSCHEME['downloaded'])
        else:
            item.setForeground(COLORSCHEME['watchedfg'])
            item.setBackground(COLORSCHEME['watched'])
    
    def headerClicked(self):
        if self.latest:
            self.play(self.latest)
            
    def markSeriesWatched(self):
        self.seriesManager.SQL.forceWatched(title = self.title)

    def markEpisodeWatched(self):
        from PyQt4.QtCore import Qt
        torrent = self.listWidget.currentItem().data(Qt.UserRole).toPyObject()[0]['torrent_url']
        self.seriesManager.SQL.forceWatched(torrenturl = torrent)
        
    def episodeSelected(self):
        return not self.listWidget.currentItem()==None

    def selectedEpisodeName(self):
        from PyQt4.QtCore import Qt
        return self.listWidget.currentItem().data(Qt.UserRole).toPyObject()[0]['file_name']
        
    def hideSeries(self):
        self.seriesManager.SQL.hideSeries(self.title)
        
        
    def setTitle(self):
        if self.series:
            if self.latestEpisode:
                self.series.setTitle(self.title + ' ['+str(self.latestEpisode)+']')
            elif self.latest:
                self.series.setTitle(self.title + ' '+ str(self.latestDownloaded))
            elif self.downloading:
                self.series.setTitle(self.title + ' ('+ str(self.downloading)+')')
            else:
                self.series.setTitle(self.title)
            self.series.setStatus(self.latestDownloaded,self.downloading,self.downloadPercent)
            
class SettingsDialog(QtGui.QDialog):
    def __init__(self,initialSettings, parent=None):
        from PyQt4.QtCore import Qt
        super(SettingsDialog, self).__init__(parent)
        self.result=None
        self.setWindowTitle(self.tr("User Settings"))
        self.setWindowFlags(self.windowFlags() &~ Qt.WindowContextHelpButtonHint)
##        self.setSizeGripEnabled(True)
##        self.setAttribute(Qt.WA_DeleteOnClose)

        mainLayout = QtGui.QVBoxLayout()
##        mainLayout.addStretch(1)

        mainLayout.setAlignment(Qt.AlignCenter)

        optionsLayout = QtGui.QFormLayout()
        confirmLayout = QtGui.QGridLayout()

        top=QtGui.QWidget()
        bottom=QtGui.QWidget()
        top.setLayout(optionsLayout)
        bottom.setLayout(confirmLayout)


        optionsLayout.addRow("<b>Required Settings:</b>",None)

        self.options = {}

        self.options['RSS Feed'] = QtGui.QLineEdit()
        self.options['RSS Feed'].setPlaceholderText("Paste your private RSS feed here.")
        optionsLayout.addRow("Private RSS Feed",self.options['RSS Feed'])

        
        fileSelect=QtGui.QWidget()
        fileSelectLayout=QtGui.QGridLayout()
        fileSelect.setLayout(fileSelectLayout)

        self.options['Download Directory']=QtGui.QLineEdit()
        self.options['Download Directory'].setPlaceholderText("Source Directory")
        self.dlBrowse=QtGui.QPushButton('&Browse')

        self.connect(self.dlBrowse,SIGNAL("released()"),lambda:self.folderSelect(self.options['Download Directory']))
        
        fileSelectLayout.addWidget(self.options['Download Directory'],0,0)
        fileSelectLayout.addWidget(self.dlBrowse,0,1)
        optionsLayout.addRow("Download Directory",fileSelect)

        fileSelectLayout.setContentsMargins(0, 0, 0, 0)
        fileSelect.setContentsMargins(0, 0, 0, 0)


        fileSelect=QtGui.QWidget()
        fileSelectLayout=QtGui.QGridLayout()
        fileSelect.setLayout(fileSelectLayout)

        self.options['Save Directory']=QtGui.QLineEdit()
        self.options['Save Directory'].setPlaceholderText("Destination Directory")
        self.stBrowse=QtGui.QPushButton('&Browse')

        self.connect(self.stBrowse,SIGNAL("released()"),lambda:self.folderSelect(self.options['Save Directory']))
        
        fileSelectLayout.addWidget(self.options['Save Directory'],0,0)
        fileSelectLayout.addWidget(self.stBrowse,0,1)
        optionsLayout.addRow("Storage Directory",fileSelect)

        fileSelectLayout.setContentsMargins(0, 0, 0, 0)
        fileSelect.setContentsMargins(0, 0, 0, 0)

        optionsLayout.addRow("<b>Optional Settings:</b>",None)
        self.options['anidb Username'] = QtGui.QLineEdit()
        optionsLayout.addRow("anidb Username",self.options['anidb Username'])

        self.options['anidb Password'] = QtGui.QLineEdit()
        self.options['anidb Password'].setEchoMode(QtGui.QLineEdit.Password)
        optionsLayout.addRow("anidb Password",self.options['anidb Password'])

        self.options['Shana Project Username'] = QtGui.QLineEdit()
        optionsLayout.addRow("Shana Project Username",self.options['Shana Project Username'])

        self.options['Shana Project Password'] = QtGui.QLineEdit()
        self.options['Shana Project Password'].setEchoMode(QtGui.QLineEdit.Password)
        optionsLayout.addRow("Shana Project Password",self.options['Shana Project Password'])

##        optionsLayout.addRow("<b>Unreliable without an anidb account:</b>",None)
        self.options['Season Sort']=QtGui.QCheckBox('Sort Episodes by Season')
        optionsLayout.addRow(self.options['Season Sort'])

        self.options['Poster Icons']=QtGui.QCheckBox('Use Poster Art for Folder Icons (Windows Only)')
        if os.name!='nt':
                self.options['Poster Icons'].setDisabled(True)
        optionsLayout.addRow(self.options['Poster Icons'])

        self.options['Auto Hide Old']=QtGui.QCheckBox('Automatically Hide Older Series (~1 month old)')
        optionsLayout.addRow(self.options['Auto Hide Old'])

        self.saveButton=QtGui.QPushButton('Save')
        self.cancelButton=QtGui.QPushButton('Cancel')
        
        confirmLayout.addWidget(self.saveButton,0,0)
        confirmLayout.addWidget(self.cancelButton,0,1)
        
        self.connect(self.cancelButton,SIGNAL("released()"),self.close)
        self.connect(self.saveButton,SIGNAL("released()"),self.saveValues)

        mainLayout.addWidget(top)
        mainLayout.addWidget(bottom)
        self.setLayout(mainLayout)

        for key in initialSettings:
                if isinstance(self.options[key], QtGui.QCheckBox):
                        self.options[key].setCheckState(initialSettings[key])
                else:
                        self.options[key].setText(initialSettings[key])
                        
    def getValues(self):
        return self.result

    def folderSelect(self,destInput):
        folder = QtGui.QFileDialog.getExistingDirectory(self, "Open Directory",
                                                   ".",
                                                   QtGui.QFileDialog.ShowDirsOnly|
                                                   QtGui.QFileDialog.DontResolveSymlinks)
        if folder:
            destInput.setText(folder)

    def saveValues(self):
        self.result={}
        for key in self.options:
                if isinstance(self.options[key], QtGui.QCheckBox):
                        self.result[key] = self.options[key].checkState()
                else:
                        self.result[key] = str(self.options[key].text())# or None
        self.close()
        
class StillRunningDialog(QtGui.QDialog):
    def __init__(self, parent=None):
        from PyQt4.QtCore import Qt
        super(StillRunningDialog, self).__init__(parent)
        self.result=0
        self.setWindowTitle(self.tr("Application is still running!"))
        self.setWindowFlags(self.windowFlags() &~ Qt.WindowContextHelpButtonHint)
##        self.setSizeGripEnabled(True)
##        self.setAttribute(Qt.WA_DeleteOnClose)

##        mainLayout = QtGui.QGridLayout()
        mainLayout = QtGui.QVBoxLayout()
##        mainLayout.addStretch(1)

        mainLayout.setAlignment(Qt.AlignCenter)

        optionsLayout = QtGui.QFormLayout()
        confirmLayout = QtGui.QGridLayout()

        top=QtGui.QWidget()
        bottom=QtGui.QWidget()
        top.setLayout(optionsLayout)
        bottom.setLayout(confirmLayout)
        mainLayout.setAlignment(Qt.AlignCenter)

        optionsLayout.addRow('Alastore is still running, double click on the tray icon to show the main window again.\nRight click the tray icon to exit completely.',None)
        self.dontshow=QtGui.QCheckBox('Don\'t show this message again.')
        optionsLayout.addRow(self.dontshow)
        
        self.saveButton=QtGui.QPushButton('OK')
##        confirmLayout.addWidget(QtGui.QSpacerItem(),0,0)
        confirmLayout.addWidget(self.saveButton,0,1)
        mainLayout.addWidget(top)
        mainLayout.addWidget(bottom)
        self.setLayout(mainLayout)

        self.connect(self.saveButton,SIGNAL("released()"),self.saveValues)
        
    def getValues(self):
        return self.result

    def saveValues(self):
        self.result=self.dontshow.checkState()
        self.close()
        
from qtrayico import Systray
class trayIcon(Systray):
    def __init__(self,window,seriesManager):
        super(trayIcon,self).__init__(window)
        self.seriesManager=seriesManager
        
    def createActions(self):
        self.actions=[]

        self.updateAction= QtGui.QAction(self.tr("&Refresh"), self)
        self.connect(self.updateAction, QtCore.SIGNAL("triggered()"),self.refresh)
        
        self.configAction= QtGui.QAction(self.tr("&Config"), self)
        self.connect(self.configAction, QtCore.SIGNAL("triggered()"),self.showConfig)
        
        self.helpAction= QtGui.QAction(self.tr("&Help"), self)
        self.connect(self.helpAction, QtCore.SIGNAL("triggered()"),
                     lambda:QtGui.QMessageBox.information(self,
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
<dt>Removing Series/Marking as Watched:</dt>
        <dd>Right click any series to show a context menu with two options.</dd><ul>
        <li>If you choose to hide a series it will reappear if a new episode appears in your
        RSS. If you want a series to be permanently hidden please also remove it from your
        RSS feed.</li><li>
        Marking a series as watched will mark all episodes of the series as having
        been watched. The only reason to do this is if you have previously watched
        episodes elsewhere and you want Alastore to keep you up to date on the
        latest episode without having to download/watch the previous ones.
        Note that there is (currently) no way to undo either of these actions.</li></ul>

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
''')
                     )
                
        self.quitAction = QtGui.QAction(self.tr("&Quit"), self)
        QtCore.QObject.connect(self.quitAction, QtCore.SIGNAL("triggered()"),
        QtGui.qApp, QtCore.SLOT("quit()"))
        
        self.actions.append(self.updateAction)
        self.actions.append(self.configAction)
        self.actions.append(self.helpAction)
        self.actions.append(self.quitAction)

    def refresh(self):
        self.main_window.centralWidget().quickUpdate()
        
    def showConfig(self):
        settings = self.seriesManager.SQL.getSettings(1)
        d=SettingsDialog(settings,self)
        d.exec_()
        if d.getValues():
            settings = d.getValues()
            self.seriesManager.SQL.saveSettings(*[settings[key] for key in self.seriesManager.SQL.COLUMN_NAMES])
            self.refresh()
        d.deleteLater()
        

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
        def closeEvent(self,event):
                super(HideableWithDialog,self).closeEvent(event)
                self.centralWidget().queueShowAgain()
                        

import series
if __name__ == '__main__':
    # chdir to the correct directory to ensure configs, etc. are loaded correctly.
    import os,sys
    try:
        sys._MEIPASS
        os.chdir(os.path.dirname(sys.argv[0]))
    except:
        os.chdir(os.path.dirname(os.path.realpath(__file__)))
        
    from PyQt4.QtGui import QApplication
    import sys

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)#AAAAAAAAAA
    #app.setStyle( 'Plastique' )
    a=series.SeriesList()
    main=HideableWithDialog()#QtGui.QMainWindow()

    main.setWindowTitle('Alastore')
    main.setWindowIcon(QtGui.QIcon(resource_path("book.ico")))
    tray = trayIcon(main,a)
    dlg = AccordianWidget(a,main)
    dlg.populate(a)

    main.setCentralWidget(dlg)
##    main.move(QtCore.QPoint(main.pos().x(),0))
    main.resize(main.sizeHint())

##        dlg.show()
    if '-q' not in sys.argv and '/q' not in sys.argv and '/silent' not in sys.argv:
        main.show()
##    d=SettingsDialog(main)
##    d.exec_()


    sys.exit(app.exec_())

