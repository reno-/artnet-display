
import sys
import getopt
import textwrap
from time import sleep
from random import randrange
from ola.ClientWrapper import ClientWrapper
from ola.OlaClient import OLADNotRunningException
from PyQt5.QtCore import QThread, QAbstractListModel, Qt, QVariant, pyqtSignal
from PyQt5.QtWidgets import QListView, QApplication, QGroupBox, QVBoxLayout, QPushButton, QSpinBox, QMainWindow, QFrame

class OLA(QThread):
    universeChanged = pyqtSignal()
    """Separate Thread that run OLA client"""
    def __init__(self):
        QThread.__init__(self)
        self.client = None
        # start the thread
        self.start()

    def __del__(self):
        self.wait()

    def run(self):
        """the running thread"""
        try:
            self.wrapper = ClientWrapper()
            self.client = self.wrapper.Client()
            print 'connected to OLA server'
            self.wrapper.Run()
        except OLADNotRunningException:
            print 'cannot connect to OLA'

    def stop(self):
        """stop the OLA client wrapper"""
        if self.client:
            self.wrapper.Stop()
            print 'connection to OLA is closed'


class UniverseModel(QAbstractListModel):
    """List Model of a DMX universe (512 values 0/255)"""
    def __init__(self, parent):
        super(UniverseModel, self).__init__(parent)
        # fill in the universe with zero (avoid IndexError)
        self.dmx_list = [0 for i in range(512)]
        self.parent = parent

    def rowCount(self, index):
        """return the size of the list"""
        return len(self.dmx_list)

    def data(self, index, role=Qt.DisplayRole):
        """return value for an index"""
        index = index.row()
        if role == Qt.DisplayRole:
            return self.dmx_list[index]
        return QVariant()

    def new_frame(self, data):
        """receive the dmx_list when ola sends new data"""
        for index, value in enumerate(data):
            self.setData(index, value)
        # this is send only once for a dmx_list
        self.parent.ola.universeChanged.emit()

    def setData(self, index, value):
        """set the value for each new value"""
        self.dmx_list[index] = value


class Universe(QGroupBox):
    """docstring for Universe"""
    def __init__(self, parent, ola, universe=1):
        super(Universe, self).__init__()
        self.selector = QSpinBox()
        self.selector.setRange(1,2)
        self.view = QListView()
        self.model = UniverseModel(self)
        self.view.setModel(self.model)
        vbox = QVBoxLayout()
        vbox.addWidget(self.selector)
        vbox.addWidget(self.view)
        self.setLayout(vbox)
        parent.vbox.addWidget(self)
        self.ola = ola
        self.old = None
        self.selector.valueChanged.connect(self.ola_connect)
        self.selector.setValue(1)
        self.ola_connect(1)

    def ola_connect(self, new):
        # NEXT :  HOW to unregister Universe??
        if self.ola.client:
            if self.old:
                # unregister the previous universe (self.old)
                self.ola.client.RegisterUniverse(self.old, self.ola.client.UNREGISTER, self.model.new_frame)
            # register the selected universe (new)
            # ask about universe values, in case no new frame is sent
            self.ola.client.FetchDmx(new, self.refresh)
            self.ola.client.RegisterUniverse(new, self.ola.client.REGISTER, self.model.new_frame)
            self.ola.universeChanged.connect(self.model.layoutChanged.emit)
            self.old = new
            return True
        else:
            return False

    def refresh(self, RequestStatus, universe, dmx_list):
        self.model.new_frame(dmx_list)

class MainWindow(QMainWindow):
    """This is the main window"""
    def __init__(self):
        super(MainWindow, self).__init__()
        # create a button to connect to OLA server
        self.ola_switch = QPushButton('Connect to OLA server')
        self.ola_switch.released.connect(self.ola_connect)
        # create a vertical layout and add widgets
        frame = QFrame()
        self.vbox = QVBoxLayout(frame)
        self.vbox.addWidget(self.ola_switch)
        # set the layout on the groupbox
        self.setCentralWidget(frame)
        self.setWindowTitle("OLA test GUI")
        self.resize(480, 320)
        self.ola = None

    def ola_connect(self):
        print 'connecting to OLA server'
        # meke OLA wrapper running in parallel
        self.ola = OLA()
        # don't know why, but it seems to be necessary with QThread
        sleep(0.5)
        if self.ola.client:
            self.ola_switch.setVisible(False)
            # Create the universe layout (view and model)
            self.universe = Universe(self, self.ola, 1)

    def closeEvent(self, event):
        # why this is happenning twice?
        if self.ola:
            self.ola.stop()



if __name__ == "__main__":
  app = QApplication(sys.argv)
  window = MainWindow()
  window.show()
  sys.exit(app.exec_())