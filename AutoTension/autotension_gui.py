#
# Updated tensioner program to work with the motorized tension setup
# Paul Johnecheck
# April 2022
#
# Modifications:
# 2022-06, Reinhard: separate 400 and 320 tensioning, new target for 320 is 325
#          Alexandru: Implement buttons for increase tension and decreas tension
#                     Add text that "Escape" button interrupts tensioning process.
#                     Re-added full autotension process button
#                     Added tension ranges information
#                     Added name dropdown and button to allow more names to be added
#                     AI increase/decrease tension added
#                     Changed requirements for saving data to database for less "false" data
#

import sys
import os
import datetime

pyside_version = None
try:
    from PySide6 import QtCore, QtWidgets, QtGui
    from PySide6.QtWidgets import QMessageBox, QComboBox
    pyside_version = 6
except ImportError:
    from PySide2 import QtCore, QtWidgets, QtGui
    from PySide2.QtWidgets import QMessageBox, QComboBox
    pyside_version = 2

from stepper import Stepper, Plotter
from freq_tension import FourierTension

DROPBOX_DIR = os.path.dirname(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(DROPBOX_DIR)

from sMDT import db, tube
from sMDT.data.tension import Tension, TensionRecord

class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)

        self.plot_title = "Tension v. Time"
        self.plot_x_label = "Time (s)"
        self.plot_y_label = "Tension (g)"

        self.db = db.db()

        self.setWindowTitle("AutoTension")

        layout1 = QtWidgets.QVBoxLayout()

        #layout0 = QtWidgets.QGridLayout()
        layout0 = QtWidgets.QVBoxLayout()
        layout2 = QtWidgets.QVBoxLayout()
        layout3 = QtWidgets.QGridLayout()
        layout4 = QtWidgets.QVBoxLayout()

        layout1.addLayout(layout0)
        layout1.addLayout(layout2)
        layout1.addLayout(layout3)
        layout1.addLayout(layout4)

        #self.user_edit = QtWidgets.QLineEdit()
        self.user_edit = ""
        self.ID_edit = QtWidgets.QLineEdit()
        self.ID_edit.returnPressed.connect(self.retension)
        self.ext_tension = QtWidgets.QLineEdit()
        self.ext_tension.setReadOnly(True)
        self.ext_tension.setText("Not yet measured")
        self.ext_tension.setStyleSheet('background-color: lightgrey; color: black')
        self.int_tension = QtWidgets.QLineEdit()
        self.int_tension.setReadOnly(True)
        self.int_tension.setText("Not yet measured")
        self.int_tension.setStyleSheet('background-color: lightgrey; color: black')

        names = []
        file = open("Python_program_names.txt", "r")
        file.readline()
        file.readline()
        for line in file:
            line = line.rstrip()
            names.append(line)
        file.close()

        name = QtWidgets.QLabel()
        name.setText("Name: " + (" " * 50))
        self.combo = QComboBox()
        self.combo.addItems(names)
        self.user_edit = str(self.combo.currentText())

        form_layout0 = QtWidgets.QFormLayout()
        form_layout0.addRow(name, self.combo)
        #layout0.addWidget(name, 0, 0)
        #layout0.addWidget(combo, 0, 1)

        layout0.addLayout(form_layout0)

        form_layout = QtWidgets.QFormLayout()
        #form_layout.addRow("Name:", self.user_edit)
        form_layout.addRow("ID:", self.ID_edit)
        form_layout.addRow("External Sensor Tension:", self.ext_tension)
        form_layout.addRow("Internal Frequency Magnet Tension:", self.int_tension)

        layout2.addLayout(form_layout)

        self.first_tension_button = QtWidgets.QPushButton()
        self.first_tension_button.setText("Over-Tension (400)")
        layout3.addWidget(self.first_tension_button, 0, 0)

        self.release_button = QtWidgets.QPushButton()
        self.release_button.setText("Release Tension (0)")
        layout3.addWidget(self.release_button, 0, 1)

        self.retension_button = QtWidgets.QPushButton()
        self.retension_button.setText("Final Tension (320)")
        layout3.addWidget(self.retension_button, 0, 2)

        self.get_tension_button = QtWidgets.QPushButton()
        self.get_tension_button.setText("\nGet Tension\n")
        layout3.addWidget(self.get_tension_button, 0, 3, 2, 1)

        self.autotension_button = QtWidgets.QPushButton()
        self.autotension_button.setText("Auto-Tension")
        layout3.addWidget(self.autotension_button, 1, 0)

        self.tension_up_button = QtWidgets.QPushButton()
        self.tension_up_button.setText("Increase Tension")
        layout3.addWidget(self.tension_up_button, 1, 1)

        self.tension_down_button = QtWidgets.QPushButton()
        self.tension_down_button.setText("Decrease Tension")
        layout3.addWidget(self.tension_down_button, 1, 2)

        self.first_tension_button.setAutoDefault(True)

        self.first_tension_button.clicked.connect(self.first_tension)
        
        self.release_button.clicked.connect(self.release)
        
        self.retension_button.clicked.connect(self.retension)

        self.get_tension_button.clicked.connect(self.get_tension)

        self.autotension_button.clicked.connect(self.autotension)

        self.tension_up_button.clicked.connect(self.tension_up)

        self.tension_down_button.clicked.connect(self.tension_down)

        note1 = QtWidgets.QLabel()
        note2 = QtWidgets.QLabel()
        space1 = QtWidgets.QLabel()
        space2 = QtWidgets.QLabel()
        label = QtWidgets.QLabel()
        self.addName_button = QtWidgets.QPushButton()
        note3 = QtWidgets.QLabel()
        note4 = QtWidgets.QLabel()
        space1.setText("----------------------------------------------------------------------------------------------")
        note1.setText("Acceptable 1st Tension: 305.00 - 326.15 | Yields 2nd Tension: 336.99 - 362.97")
        note2.setText("Optimal      1st Tension: 311.97 - 319.02 | Yields 2nd Tension: 348.00 - 355.45")
        space2.setText("----------------------------------------------------------------------------------------------")
        label.setText("Status:" + (" " * 111))
        self.addName_button.setText("Add Name")
        layout4.addWidget(space1)
        layout4.addWidget(note1)
        layout4.addWidget(note2)
        layout4.addWidget(space2)
        #layout4.addWidget(label)

        form_layout2 = QtWidgets.QFormLayout()
        form_layout2.addRow(label, self.addName_button)

        layout4.addLayout(form_layout2)

        self.addName_button.clicked.connect(self.openFile)

        self.status = QtWidgets.QLineEdit()
        self.status.setReadOnly(True)
        self.status.setText("Not Started")
        self.status.setStyleSheet('background-color: lightgrey; color: black')
        layout4.addWidget(self.status)
        note3.setText("***Press Esc key to cancel the tension process (may require multiple key presses!)")
        note4.setText("**Program will freeeze momentarily after cancellation")
        layout4.addWidget(note3)
        layout4.addWidget(note4)
        widget = QtWidgets.QWidget()
        widget.setLayout(layout1)
        self.setCentralWidget(widget)
        
        self.show()

        self.increase = 10
        self.decrease = 10

    def update_ext_tension(self, tension):
        self.ext_tension.setText(str(tension))

    def update_int_tension(self, tension):
        self.int_tension.setText(str(tension))

    def update_status(self, status):
        self.status.setText(status)

    def avg(self, x):
        return sum(x)/len(x)

    def openFile(self):
        if sys.platform == 'linux2':
            subprocess.call(["xdg-open", "Python_program_names.txt"])
        else:
            os.startfile("Python_program_names.txt")

    def first_tension(self):
        self.increase = 10
        self.decrease = 10

        self.tension_device = FourierTension()
        n_samp = 1
        stepper = Stepper(
            noise_reduction=self.avg,
            stride=28,
            n_samp=n_samp,
            plotter=Plotter(self.plot_title, self.plot_x_label, self.plot_y_label))

        self.update_status("Tensioning to 400")
        stepper.resume()
        result = stepper.step_to(350, 10, callback=self.update_ext_tension)
        stride = 5
        result = stepper.step_to(400, 5, callback=self.update_ext_tension)
        stride = 28
        stepper.pause()
        self.update_status("Measuring internal tension")
        tension, frequency =  self.tension_device.get_tension()
        self.update_int_tension(tension)

        if(result == 1):
            if( (tension > 100) and (tension < 1000) ):
                self.user_edit = str(self.combo.currentText())
                newTube = tube.Tube()
                newTube.set_ID(self.ID_edit.text().strip())
                newTube.tension.add_record(
                    TensionRecord(
                        tension=tension,
                        frequency=frequency,
                        date=datetime.datetime.now(),
                        user=self.user_edit.strip()
                        )
                    )
                self.db.add_tube(newTube)
                self.update_status("Done")
            else:
                self.update_status("Invalid tension, press \"Get Tension\"")
        else:
            self.update_status("Cancelled, no tension saved")

        self.ID_edit.setFocus()

    def release(self):
        self.increase = 10
        self.decrease = 10

        n_samp = 1
        stepper = Stepper(
            noise_reduction=self.avg,
            stride=28,
            n_samp=n_samp,
            plotter=Plotter(self.plot_title, self.plot_x_label, self.plot_y_label))

        self.update_status("Releasing tension")
        stepper.resume()
        stepper.step_to(0, 10, callback=self.update_ext_tension)

    def retension(self):
        self.increase = 10
        self.decrease = 10

        self.tension_device = FourierTension()
        n_samp = 1
        stepper = Stepper(
            noise_reduction=self.avg,
            stride=28,
            n_samp=n_samp,
            plotter=Plotter(self.plot_title, self.plot_x_label, self.plot_y_label))

        self.update_status("Tensioning to 322")
        stepper.resume()
        result = stepper.step_to(300, 10, callback=self.update_ext_tension)
        stride = 5
        result = stepper.step_to(322, 5, callback=self.update_ext_tension)
        stride = 28
        stepper.pause()
        self.update_status("Measuring internal tension")
        tension, frequency =  self.tension_device.get_tension()
        self.update_int_tension(tension)

        if(result == 1):
            if( (tension > 100) and (tension < 1000) ):
                self.user_edit = str(self.combo.currentText())
                newTube = tube.Tube()
                newTube.set_ID(self.ID_edit.text().strip())
                newTube.tension.add_record(
                    TensionRecord(
                        tension=tension,
                        frequency=frequency,
                        date=datetime.datetime.now(),
                        user=self.user_edit.strip()
                        )
                    )
                self.db.add_tube(newTube)
                self.update_status("Done")
            else:
                self.update_status("Invalid tension, press \"Get Tension\"")
        else:
            self.update_status("Cancelled, no tension saved")

        self.ID_edit.setFocus()

    def get_tension(self):
        self.tension_device = FourierTension()
        self.update_status("Measuring internal tension")
        tension, frequency =  self.tension_device.get_tension()
        self.update_int_tension(tension)

        if( (tension > 100) and (tension < 1000) ):
            self.user_edit = str(self.combo.currentText())
            newTube = tube.Tube()
            newTube.set_ID(self.ID_edit.text().strip())
            newTube.tension.add_record(
                TensionRecord(
                    tension=tension,
                    frequency=frequency,
                    date=datetime.datetime.now(),
                    user=self.user_edit.strip()
                    )
                )
            self.db.add_tube(newTube)

        self.update_status("Done. Internal tension is "+str(tension))
        self.ID_edit.setFocus()
        self.ID_edit.selectAll()

    def tension_up(self):
        target = 322 + 10 + self.increase - self.decrease
        
        self.tension_device = FourierTension()
        n_samp = 1
        stepper = Stepper(
            noise_reduction=self.avg,
            stride=28,
            n_samp=n_samp,
            plotter=Plotter(self.plot_title, self.plot_x_label, self.plot_y_label))

        self.update_status("Increasing Tension")
        stepper.resume()
        stride = 5
        result = stepper.step_to(300, 10, callback=self.update_ext_tension)
        result = stepper.step_to(target, 5, callback=self.update_ext_tension)
        stepper.pause()
        self.update_status("Measuring internal tension")
        tension, frequency =  self.tension_device.get_tension()
        self.update_int_tension(tension)

        if(result == 1):
            if( (tension > 100) and (tension < 1000) ):
                self.user_edit = str(self.combo.currentText())
                newTube = tube.Tube()
                newTube.set_ID(self.ID_edit.text().strip())
                newTube.tension.add_record(
                    TensionRecord(
                        tension=tension,
                        frequency=frequency,
                        date=datetime.datetime.now(),
                        user=self.user_edit.strip()
                        )
                    )
                self.db.add_tube(newTube)
                self.update_status("Done")
            else:
                self.update_status("Invalid tension, press \"Get Tension\"")
        else:
            self.update_status("Cancelled, no tension saved")

        self.ID_edit.setFocus()

        self.increase += 10

    def tension_down(self):
        target = 322 - 10 + self.increase - self.decrease
        
        self.tension_device = FourierTension()
        n_samp = 1
        stepper = Stepper(
            noise_reduction=self.avg,
            stride=28,
            n_samp=n_samp,
            plotter=Plotter(self.plot_title, self.plot_x_label, self.plot_y_label))

        self.update_status("Decreasing Tension")
        stepper.resume()
        stride = 5
        result = stepper.step_to(300, 10, callback=self.update_ext_tension)
        result = stepper.step_to(target, 5, callback=self.update_ext_tension)
        stepper.pause()
        self.update_status("Measuring internal tension")
        tension, frequency =  self.tension_device.get_tension()
        self.update_int_tension(tension)

        if(result == 1):
            if( (tension > 100) and (tension < 1000) ):
                self.user_edit = str(self.combo.currentText())
                newTube = tube.Tube()
                newTube.set_ID(self.ID_edit.text().strip())
                newTube.tension.add_record(
                    TensionRecord(
                        tension=tension,
                        frequency=frequency,
                        date=datetime.datetime.now(),
                        user=self.user_edit.strip()
                        )
                    )
                self.db.add_tube(newTube)
                self.update_status("Done")
            else:
                self.update_status("Invalid tension, press \"Get Tension\"")
        else:
            self.update_status("Cancelled, no tension saved")

        self.ID_edit.setFocus()

        self.decrease += 10

    def autotension(self):
        self.increase = 10
        self.decrease = 10

        self.tension_device = FourierTension()
        n_samp = 1
        stepper = Stepper(
            noise_reduction=self.avg,
            stride=28,
            n_samp=n_samp,
            plotter=Plotter(self.plot_title, self.plot_x_label, self.plot_y_label))

        self.update_status("Beginning at zero")
        stepper.resume()
        result = stepper.step_to(0, 10, callback=self.update_ext_tension)
        self.update_status("Increasing Tension")
        result = stepper.step_to(350, 10, callback=self.update_ext_tension)
        stride = 5
        result = stepper.step_to(400, 5, callback=self.update_ext_tension)
        stride = 28
        stepper.pause()
        self.update_status("Holding at 400")
        result = stepper.hold(400, 5, hold_time=7, callback=self.update_ext_tension)
        stepper.resume()
        self.update_status("Tensioning to 0")
        result = stepper.step_to(0, 10, callback=self.update_ext_tension)
        self.update_status("Tensioning to 322")
        result = stepper.step_to(300, 10, callback=self.update_ext_tension)
        stride = 5
        result = stepper.step_to(319, 5, callback=self.update_ext_tension)
        stepper.pause()
        self.update_status("Holding at 322")
        result = stepper.hold(319, 5, hold_time=2, callback=self.update_ext_tension)
        self.update_status("Measuring internal tension")
        tension, frequency =  self.tension_device.get_tension()
        self.update_int_tension(tension)

        if(result == 1):
            while(True):
                if( (tension > 1000) or (tension < 100) ):
                    self.update_status("Recalculating...")
                    tension, frequency =  self.tension_device.get_tension()
                    self.update_int_tension(tension)
                else:
                    break

        if(result == 1):
            if(tension > 322.00):
                self.update_status("Decreasing Tension")
                stepper.resume()
                stride = 5
                result = stepper.step_to(300, 10, callback=self.update_ext_tension)
                result = stepper.step_to(312, 5, callback=self.update_ext_tension)
                stepper.pause()
                self.update_status("Measuring internal tension")
                tension, frequency =  self.tension_device.get_tension()
                self.update_int_tension(tension)
            elif(tension < 309.00):
                self.update_status("Increasing Tension")
                stepper.resume()
                stride = 5
                result = stepper.step_to(300, 10, callback=self.update_ext_tension)
                result = stepper.step_to(332, 5, callback=self.update_ext_tension)
                stepper.pause()
                self.update_status("Measuring internal tension")
                tension, frequency =  self.tension_device.get_tension()
                self.update_int_tension(tension)
            else:
                pass

        if(result == 1):
            if( (tension > 100) and (tension < 1000) ):
                self.user_edit = str(self.combo.currentText())
                newTube = tube.Tube()
                newTube.set_ID(self.ID_edit.text().strip())
                newTube.tension.add_record(
                    TensionRecord(
                        tension=tension,
                        frequency=frequency,
                        date=datetime.datetime.now(),
                        user=self.user_edit.strip()
                        )
                    )
                self.db.add_tube(newTube)
                self.update_status("Done")
            else:
                self.update_status("Invalid tension, press \"Get Tension\"")
        else:
            self.update_status("Cancelled, no tension saved")

        self.ID_edit.setFocus()

if __name__ == "__main__":
    app = QtWidgets.QApplication()
    w = MainWindow()
    if pyside_version == 2:
        sys.exit(app.exec_())
    elif pyside_version == 6:
        sys.exit(app.exec())
