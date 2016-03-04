#! /usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import getopt
import textwrap
from time import sleep
from random import randrange
from ola.ClientWrapper import ClientWrapper
from ola.OlaClient import OLADNotRunningException
from PyQt5.QtCore import QThread, QAbstractTableModel, Qt, QVariant, pyqtSignal, QModelIndex, \
                         QAbstractListModel, QFileInfo, QCoreApplication
from PyQt5.QtWidgets import QApplication, QGroupBox, QVBoxLayout, QGridLayout, QVBoxLayout, \
                            QTableView, QCheckBox, QSpinBox, QLabel, QMainWindow, QLineEdit, QListView, \
                            QPushButton, QToolBar, QMenu, QFrame, QHeaderView, QAction, QRadioButton
from PyQt5.QtGui import QColor, QBrush, QFont, QIcon

debug = 1


class OLA(QThread):
    universeChanged = pyqtSignal()
    universesList = pyqtSignal()
    """Separate Thread that run OLA client"""
    def __init__(self):
        QThread.__init__(self)
        self.client = None
        # start the thread
        self.start()
        if debug:
            print 'try to connecto to OLA'

    def __del__(self):
        self.wait()

    def universes_request(self, request, universes):
        self.universes_list = universes
        self.universesList.emit()

    def run(self):
        """the running thread"""
        try:
            self.wrapper = ClientWrapper()
            self.client = self.wrapper.Client()
            if debug:
                print 'connected to OLA server'
            self.wrapper.Run()
        except OLADNotRunningException:
            if debug:
                print 'cannot connect to OLA'

    def stop(self):
        """stop the OLA client wrapper"""
        if self.client:
            self.wrapper.Stop()
            if debug:
                print 'connection to OLA is closed'


class UniversesModel(QAbstractListModel):
    """List Model of univeses available in OLA"""
    def __init__(self, parent):
        super(UniversesModel, self).__init__(parent)
        self.universes_list = []
        self.parent = parent

    def rowCount(self, index=QModelIndex()):
        """return the number of universes present"""
        return len(self.universes_list)

    def object(self, row):
        """return object for an index"""   
        return  self.universes_list[row]

    def data(self, index, role=Qt.DisplayRole):
        """return the name of the universe"""
        if index.isValid():
            row = index.row()
            if role == Qt.DisplayRole:
                try:
                    value = self.universes_list[row].name
                    return QVariant(value)
                except IndexError:
                    if debug:
                        # these cells does not exists
                        print(row, 'is out of universes list')
                        return QVariant()
            else:
                return QVariant()
        else:
            return QVariant()

    def update_universes_list(self, RequestStatus, universes):
        """receive the dmx_list when ola sends new data"""
        if RequestStatus.Succeeded():
            if universes:
                self.universes_list = []
                for index, universe in enumerate(universes):
                    self.universes_list.append(universe)
                self.parent.ola.universesList.emit()


class UniverseModel(QAbstractTableModel):
    """Table Model of a DMX universe (512 values 0/255)"""
    def __init__(self, parent):
        super(UniverseModel, self).__init__(parent)
        self.columns = 32
        self.rows = (512/self.columns)
        if int(self.rows)*self.columns < 512:
            self.rows = self.rows + 1
        self.dmx_list = []
        for row in range(self.rows):
            self.dmx_list.append([0 for i in range(self.columns)])
            if self.rows-1 == row:
                delta = self.columns * self.rows
                delta = delta - 512
                delta = self.columns - delta
                self.dmx_list[row] = self.dmx_list[row][:delta]
        self.parent = parent

    def rowCount(self, index=QModelIndex()):
        """return the size of the list"""
        return self.rows

    def columnCount(self, index=QModelIndex()):
        """return the number of columns per row"""
        return self.columns

    def data(self, index, role=Qt.DisplayRole):
        """return value for an index"""
        rows = index.row()
        columns = index.column()
        index_number = rows - 1
        index_number = index_number * columns
        index_number = index_number + columns
        if index.isValid():
            if role == Qt.DisplayRole:
                try:
                    value = self.dmx_list[rows][columns]
                    if value == 255:
                        value = 'FF'
                    elif value == 0:
                        value = ''
                    return QVariant(value)
                except IndexError:
                    if debug:
                        # these cells does not exists
                        print(rows,columns,'is out of dmx_list')
            elif role == Qt.BackgroundRole:
                try:
                    value =  self.dmx_list[rows][columns]
                    green = 255 - value
                    color = QColor(green,255,green)
                    return QBrush(color)
                except IndexError:
                    # these cells does not exists
                    return QVariant()
            elif role == Qt.FontRole:
                try:
                    font = QFont()
                    font.setFamily('Helvetica')
                    #font.setStretch('UltraCondensed')
                    font.setFixedPitch(True)
                    font.setPointSize(10)
                    return font
                except:
                    return QVariant()
            else:
                return QVariant()
        else:
            return QVariant()

    def new_frame(self, data):
        """receive the dmx_list when ola sends new data"""
        if debug:
        	print 'new frame received :', len(data), data
        # if data: does not work because the data list can be empty when fetching DMX
        if data != None:
            for index,value in enumerate(data):
                column = index%self.columnCount()
                row = int(index/self.columnCount())
                self.dmx_list[row][column] = value
                self.model_index = self.index(row, column)
                if value != self.model_index.data:
                    # yes : value has changed
                    self.setData(self.model_index, value)
                else:
                    pass
            # if value is 0, OLA does not send the value
            if len(data) < 512:
                for index in range(len(data),512):
                    column = index%self.columns
                    row = int(index/self.columns)
                    self.dmx_list[row][column] = 0
                    self.model_index = self.index(row, column)
                    if self.model_index.data != 0:
                        self.setData(self.model_index, 0)
            # this is send only once for a dmx_list
            # This is where the update is send to the GUI
            self.parent.ola.universeChanged.emit()


class Universe(QGroupBox):
    """docstring for Universe"""
    def __init__(self, parent):
        super(Universe, self).__init__()
        # make it available for the whole instance
        self.ola = parent.ola
		# intialize variable used in ola_connect method
        self.old = None
        # Create 
        self.id_label = QLabel('Universe ID')
        self.id = QSpinBox()
        self.name_label = QLabel('Name')
        self.name = QLineEdit()
        self.name.setFixedWidth(200)
        self.merge_mode_label = QLabel('Merge Mode')
        self.merge_mode_htp_label = QLabel('HTP')
        self.merge_mode_htp = QRadioButton()
        self.merge_mode_ltp_label = QLabel('LTP')
        self.merge_mode_ltp = QRadioButton()
        self.inputs = QPushButton('Inputs')
        self.outputs = QPushButton('Outputs')
        self.inputsMenu = QMenu()
        self.outputsMenu = QMenu()
        self.inputs.setMenu(self.inputsMenu)
        self.outputs.setMenu(self.outputsMenu)
        #self.merge_mode = QCheckBox()
        # Create the view to display values
        self.view = QTableView()
        self.model = UniverseModel(self)
        self.view.setModel(self.model)
        # set up headers of the QTableView
        v_headers = QHeaderView(Qt.Vertical)
        self.view.setVerticalHeader(v_headers)
        h_headers = QHeaderView(Qt.Horizontal)
        self.view.setHorizontalHeader(h_headers)
        if debug : 
        	print 'how many lines : ', v_headers.count()
        	print 'how many columns : ', h_headers.count()
        # set up rows and columns
        for col in range(self.model.columnCount()):
            self.view.setColumnWidth(col, 28)
        for row in range(self.model.rowCount()):
            self.view.setRowHeight(row, 20)
        # Add the previous UI stuffs to a layout
        grid = QGridLayout()
        grid.addWidget(self.id, 0, 0, 1, 1)
        grid.addWidget(self.name, 0, 1, 1, 1)
        grid.addWidget(self.merge_mode_htp_label, 0, 2, 1, 1)
        grid.addWidget(self.merge_mode_htp, 0, 3, 1, 1)
        grid.addWidget(self.merge_mode_ltp_label, 0, 4, 1, 1)
        grid.addWidget(self.merge_mode_ltp, 0, 5, 1, 1)
        grid.addWidget(self.inputs, 0, 7, 1, 1)
        grid.addWidget(self.outputs, 0, 9, 1, 1)
        grid.addWidget(self.view,1, 0, 15, 10)
        # Create the settings Layout
        self.settings = QLabel('Some Widgets to patch universes inputs & outputs')
        self.settings.setVisible(False)
        grid.addWidget(self.settings)
        self.setLayout(grid)
        parent.vbox.addWidget(self)

    def connect(self, universe):
        if self.ola.client:
            if universe.id != self.old:
                if self.old:
                    # unregister the previous universe (self.old)
                    if debug:
                        print 'disconnect universe :', self.old
                    self.ola.client.RegisterUniverse(self.old, self.ola.client.UNREGISTER, self.model.new_frame)
                # register the selected universe (new)
                # ask about universe values, in case no new frame is sent
                if debug:
                    print 'connect universe :', universe.id
                self.ola.client.RegisterUniverse(universe.id, self.ola.client.REGISTER, self.model.new_frame)
                self.ola.universeChanged.connect(self.model.layoutChanged.emit)
                self.ola.client.FetchDmx(universe.id, self.refresh)
                self.display_properties(universe)
                self.old = universe.id
                return True
            else:
                # ola wants to connect again to the universe it's already binding to
                if debug:
	        		print 'universe already connected'
                return False
        else:
            return False

    def display_properties(self, universe):
        self.id.setValue(universe.id)
        self.name.setText(universe.name)
        if universe.merge_mode == 1:
            self.merge_mode_htp.setChecked(True)
            self.merge_mode_ltp.setChecked(False)
        else:
            self.merge_mode_htp.setChecked(False)
            self.merge_mode_ltp.setChecked(True)

    def refresh(self, RequestStatus, universe, dmx_list):
    	if debug:
    		print 'refresh universe', universe
        self.model.new_frame(dmx_list)


class MainWindow(QMainWindow):
    """This is the main window"""
    def __init__(self):
        super(MainWindow, self).__init__()
        # initialize to None just to know if a universe has ever been seleted
        self.universe = None
		# create a vertical layout in a frame to add widgets
        frame = QFrame()
        self.vbox = QVBoxLayout(frame)
        self.setCentralWidget(frame)
        # create a status bar
        self.status("Ready", 0)
        # create a ToolBar
        self.createToolBar()
		# set up the window
        self.setWindowTitle("OLA GUI")
        self.setFixedWidth(1086)
        self.setFixedHeight(459)
        self.move(0, 0)
        # initialize ola to be sure it exists
        self.ola = None
        if debug:
            print 'main window created'
            print 'make a ola_connection request'
        # When creating the app, there is no universe selected
        self.universe_selected = None
        # Try tp create OLA client
        self.ola_create()

    def debug_sw(self, state):
    	global debug
    	debug = state

    def status(self, message, timeout=2000):
        if timeout == 0:
            timeout = 999999999
        self.statusBar().showMessage(message, timeout)

    def createToolBar(self):
        self.createActions()
        mytoolbar = QToolBar()
        # temporary debug UI toggle
        debug_UI = QCheckBox('Debug')
        global debug
        debug_UI.setChecked(debug)
        debug_UI.stateChanged.connect(self.debug_sw)
        mytoolbar.addWidget(debug_UI)
        self.ola_connection = QCheckBox('OLA')
        self.ola_connection.released.connect(self.ola_create)
        mytoolbar.addWidget(self.ola_connection)
        # I MUST MOVE SETTINGS PANEL FOR SELECTED UNIVERS IN tHE UNIVERSE GROUPBOX
        #mytoolbar.addAction(self.settingsAct)
        mytoolbar.addAction(self.displayAct)
        self.settingsAct.setVisible(True)
        self.displayAct.setVisible(False)
        mytoolbar.setMovable(False)
        mytoolbar.setFixedWidth(110)
        self.addToolBar(Qt.LeftToolBarArea, mytoolbar)
        self.toolbar = mytoolbar

    def createActions(self):
        """create all actions"""
        root = QFileInfo(__file__).absolutePath()

        self.settingsAct = QAction(QIcon(root + '/images/settings.svg'), "Settings", self,
                                  statusTip="Settings panel for the selected universe",
                                  triggered=self.openSettingsPanel)

        self.displayAct = QAction(QIcon(root + '/images/display.svg'),"Display", self,
                                  statusTip="Display value for the selected universe",
                                  triggered=self.openDisplayPanel)

    def openSettingsPanel(self):
        """switch to the settings editor"""
        if debug:
            print 'switch to the settings view'
        self.displayAct.setVisible(True)
        self.settingsAct.setVisible(False)
        self.universe.view.setVisible(False)
        self.universe.settings.setVisible(True)

    def openDisplayPanel(self):
        """switch to the universe display panel"""
        if debug:
            print 'switch to the display view'
        self.displayAct.setVisible(False)
        self.settingsAct.setVisible(True)
        self.universe.view.setVisible(True)
        self.universe.settings.setVisible(False)

    def create_universe(self):
        print 'TODO : create a new universe'

    def ola_create(self):
        # check if there is not already a OLA client
        if not self.ola:
            # create a OLA client
            ola = OLA()
            sleep(0.5)
            if ola.client:
                self.ola = ola
                self.ola_connection.setEnabled(False)
                self.status("connected to OLA")
                self.ola_connection.setChecked(True)
                # create a button to add a new universe
                new_universe = QPushButton('new universe')
                new_universe.released.connect(self.create_universe)
                self.toolbar.addWidget(new_universe)
                refresh_universes = QPushButton('refresh list')
                self.toolbar.addWidget(refresh_universes)
                # create the panel to display universe
                self.create_universe_panel()
                # please update universes list
                self.universes_refresh()
                refresh_universes.released.connect(self.universes_refresh)
                
            else:
                self.status("can't connect to OLA. Is it running?", 0)
                self.ola_connection.setChecked(False)

    def universes_refresh(self):
        if debug:
            print 'refresh universe list'
        self.ola.client.FetchUniverses(self.list_model.update_universes_list)

    def create_universe_panel(self):
        self.toolbar.addSeparator()
        self.selectorGroup = QGroupBox()
        self.selectorLayout = QVBoxLayout()
        self.selectorGroup.setLayout(self.selectorLayout)
        self.toolbar.addWidget(self.selectorGroup)
        model = UniversesModel(self)
        self.list_model = model
        self.list_view = QListView()
        self.list_view.setModel(model)
        self.selectorLayout.addWidget(self.list_view)
        self.ola.universesList.connect(self.list_model.layoutChanged.emit)
        # Universe Selected Change
        self.list_view.selectionModel().selectionChanged.connect(self.universe_selection_changed)

    def universe_selection_changed(self, universe):
        """
        Universe Selection has changed
        This method will display Universe attributes
        such as Id, Name, MergeMode and dmx_list
        """
        row = universe.indexes()[0].row()
        universe = universe.indexes()[0].model().object(row)
        if not self.universe:
            # there is no universe interface created. Please do it
            # MAYBE WE CAN DO THIS WHEN CREATING THE MAIN WINDOW?
            self.universe = Universe(self)
        # Fill in the universe_selected variable
        self.universe_selected = universe
        if debug:
            print 'selected universe :', universe
        self.universe.connect(self.universe_selected)

    def closeEvent(self, event):
        # why this is happenning twice?
        if self.ola:
            self.ola.stop()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())