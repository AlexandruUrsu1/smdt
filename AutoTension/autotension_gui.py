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
# 2022-07, Alexandru: Checks for valid name and tube id, program no longer initializes with a name
#                     Added lots of code to make the program run smoother, though excess code may create longer load times
#                     Calculate tension multiple times to accomodate for program sometimes being "off" on initial calculation
#                     Rewrote chunks of program in attempt to concise code
#                     First chunk of gui update, simple color coding to make certain info more apparent, especially for new users
#                     Some QoL improvments
#

import sys
import os
import datetime
import time
import win32gui

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

        layout0 = QtWidgets.QVBoxLayout()
        layout2 = QtWidgets.QVBoxLayout()
        layout3 = QtWidgets.QGridLayout()
        layout4 = QtWidgets.QVBoxLayout()

        layout1.addLayout(layout0)
        layout1.addLayout(layout2)
        layout1.addLayout(layout3)
        layout1.addLayout(layout4)

        self.user_edit = ""
        self.ID_edit = QtWidgets.QLineEdit()
        self.ID_edit.returnPressed.connect(self.final_tension)
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

        layout0.addLayout(form_layout0)

        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow("ID:", self.ID_edit)
        form_layout.addRow("External Sensor Tension:", self.ext_tension)
        form_layout.addRow("Internal Frequency Magnet Tension:", self.int_tension)

        layout2.addLayout(form_layout)

        self.overtension_button = QtWidgets.QPushButton()
        self.overtension_button.setText("Over-Tension (400)")
        layout3.addWidget(self.overtension_button, 0, 0)

        self.release_button = QtWidgets.QPushButton()
        self.release_button.setText("Release Tension (0)")
        layout3.addWidget(self.release_button, 0, 1)

        self.final_tension_button = QtWidgets.QPushButton()
        self.final_tension_button.setText("Final Tension (320)")
        layout3.addWidget(self.final_tension_button, 0, 2)

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

        self.overtension_button.setAutoDefault(True)

        self.overtension_button.clicked.connect(self.overtension)
        
        self.release_button.clicked.connect(self.release)
        
        self.final_tension_button.clicked.connect(self.final_tension)

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
        space1.setText("----------------------------------------------------------------------------------------------")
        note1.setText("|                           1st Tension: 311.97 - 322.57 |  2nd Tension: 336.99 - 362.97                           |")
        note2.setText("|                                         Press Esc key to cancel tensioning process                                       |")
        space2.setText("----------------------------------------------------------------------------------------------")
        space1.setAlignment(QtCore.Qt.AlignCenter)
        note1.setAlignment(QtCore.Qt.AlignCenter)
        note2.setAlignment(QtCore.Qt.AlignCenter)
        space2.setAlignment(QtCore.Qt.AlignCenter)
        label.setText("Status:" + (" " * 111))
        self.addName_button.setText("Add Name")
        layout4.addWidget(space1)
        layout4.addWidget(note1)
        layout4.addWidget(note2)
        layout4.addWidget(space2)

        form_layout2 = QtWidgets.QFormLayout()
        form_layout2.addRow(label, self.addName_button)
        
        layout4.addLayout(form_layout2)

        self.addName_button.clicked.connect(self.openFile)

        self.status = QtWidgets.QLineEdit()
        self.status.setReadOnly(True)
        self.status.setText("Not Started")
        self.status.setStyleSheet('background-color: lightgrey; color: black')
        layout4.addWidget(self.status)
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

    def update_username(self):
        self.user_edit = str(self.combo.currentText())

    def avg(self, x):
        return sum(x)/len(x)

    def openFile(self):
        os.startfile("Python_program_names.txt")

    def stepper_device(self):
        n_samp = 1
        stepper = Stepper(
            noise_reduction=self.avg,
            stride=28,
            n_samp=n_samp,
            plotter=Plotter(self.plot_title, self.plot_x_label, self.plot_y_label))
        return stepper

    def tube_tension_record(self, tension, frequency):
        self.update_username()
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
        return newTube

    def variable_reset(self):
        self.increase = 10
        self.decrease = 10

    def measuring_tension(self, string):
        self.update_status(string)
        tension, frequency =  self.tension_device.get_tension()
        self.update_int_tension(tension)
        return tension, frequency

    def reset(self):
        self.int_tension.setText("Not yet measured")
        self.int_tension.setStyleSheet('background-color: lightgrey')
        self.status.setStyleSheet('background-color: lightgrey')

    def name_error(self):
        self.ID_edit.setStyleSheet('background-color: white')
        self.update_status("Please select a valid name")
        self.status.setStyleSheet('background-color: lightred')

    def ID_error(self):
        self.ID_edit.setStyleSheet('background-color: lightred')
        self.update_status("Please enter a valid tube ID")
        self.status.setStyleSheet('background-color: lightred')

    def tension_pass(self):
        self.int_tension.setStyleSheet('background-color: lightgreen')
        self.status.setStyleSheet('background-color: lightgreen')
        self.update_status("Done")

    def red(self):
        self.int_tension.setStyleSheet('background-color: red')
        self.status.setStyleSheet('background-color: red')

    def yellow(self):
        self.ID_edit.setStyleSheet('background-color: white')
        self.status.setStyleSheet('background-color: yellow')

    def overtension(self):
        self.variable_reset()
        self.tension_device = FourierTension()
        stepper = self.stepper_device()

        self.reset()
        if(str(self.combo.currentText()) != "-Please Select A Name-"):
            if(len(self.ID_edit.text()) == 8):
                if( (self.ID_edit.text()[0:3] == "MSU") and (self.ID_edit.text()[3:8].isdigit() == True) ):
                    self.yellow()
                    self.update_status("Tensioning to 400")
                    result = stepper.step_to(400, 5, callback=self.update_ext_tension)
                    stepper.pause()
                    if(result == 1):
                        tension, frequency = self.measuring_tension("Measuring internal tension")

                        if(( tension > 350) and (tension < 450) ):
                            self.db.add_tube(self.tube_tension_record(tension, frequency))
                            self.tension_pass()
                        else:
                            tension, frequency = self.measuring_tension("Recalculating...")
                            if(( tension > 350) and (tension < 450) ):
                                self.db.add_tube(self.tube_tension_record(tension, frequency))
                                self.tension_pass()
                            else:
                                self.red()
                                self.update_status("Invalid overtension, check battery or try again")
                    else:
                        self.update_status("Overtension cancelled, no tube data saved")
                        self.reset()
                else:
                    self.ID_error()
            else:
                self.ID_error()
        else:
            self.name_error()

        self.ID_edit.setFocus()
        self.ID_edit.selectAll()

    def release(self):
        self.variable_reset()
        stepper = self.stepper_device()

        self.reset()
        if(str(self.combo.currentText()) != "-Please Select A Name-"):
            if(len(self.ID_edit.text()) == 8):
                if( (self.ID_edit.text()[0:3] == "MSU") and (self.ID_edit.text()[3:8].isdigit() == True) ):
                    self.yellow()
                    self.update_status("Releasing tension")
                    result = stepper.step_to(0, 10, callback=self.update_ext_tension)
                    stepper.pause()
                    if(result == 1):
                        self.tension_pass()
                    else:
                        self.update_status("Release tension cancelled")
                        self.reset()
                else:
                    self.ID_error()
            else:
                self.ID_error()
        else:
            self.name_error()

        self.ID_edit.setFocus()
        self.ID_edit.selectAll()

    def final_tension(self):
        self.variable_reset()
        self.tension_device = FourierTension()
        stepper = self.stepper_device()

        self.reset()
        if(str(self.combo.currentText()) != "-Please Select A Name-"):
            if(len(self.ID_edit.text()) == 8):
                if( (self.ID_edit.text()[0:3] == "MSU") and (self.ID_edit.text()[3:8].isdigit() == True) ):
                    self.yellow()
                    self.update_status("Tensioning to 320")
                    result = stepper.step_to(320, 5, callback=self.update_ext_tension)
                    stepper.pause()
                    if(result == 1):
                        tension, frequency = self.measuring_tension("Measuring internal tension")

                        if( (tension > 200) and (tension < 400) ):
                            tension, frequency = self.measuring_tension("Double checking tension")
                            self.db.add_tube(self.tube_tension_record(tension, frequency))
                            self.tension_pass()
                        else:
                            tension, frequency = self.measuring_tension("Error, recalculating...")
                            if( (tension > 200) and (tension < 400) ):
                                self.db.add_tube(self.tube_tension_record(tension, frequency))
                                self.tension_pass()
                            else:
                                self.red()
                                self.update_status("Invalid final tension, press \"Get Tension\" or check battery")
                    else:
                        self.update_status("Final tension cancelled, no tube data saved")
                        self.reset()
                else:
                    self.ID_error()
            else:
                self.ID_error()
        else:
            self.name_error()

        self.ID_edit.setFocus()
        self.ID_edit.selectAll()

    def get_tension(self):
        self.tension_device = FourierTension()

        self.reset()
        if(str(self.combo.currentText()) != "-Please Select A Name-"):
            if(len(self.ID_edit.text()) == 8):
                if( (self.ID_edit.text()[0:3] == "MSU") and (self.ID_edit.text()[3:8].isdigit() == True) ):
                    self.ID_edit.setStyleSheet('background-color: white')
                    tension, frequency = self.measuring_tension("Measuring internal tension")

                    if( (tension > 200) and (tension < 500) ):
                        self.db.add_tube(self.tube_tension_record(tension, frequency))
                        self.int_tension.setStyleSheet('background-color: lightgreen')
                        self.update_status("Done. Internal tension is "+str(tension))
                        self.status.setStyleSheet('background-color: lightgreen')
                    else:
                        tension, frequency = self.measuring_tension("Error, recalculating...")
                        if(tension <= 200):
                            self.db.add_tube(self.tube_tension_record(tension, frequency))
                            self.red()
                            self.update_status("Done. Internal tension low. Wire snap? Check battery?")
                        elif(tension >= 500):
                            self.red()
                            self.update_status("Invalid tension, check battery?")
                        else:
                            self.db.add_tube(self.tube_tension_record(tension, frequency))
                            self.int_tension.setStyleSheet('background-color: lightgreen')
                            self.update_status("Done. Internal tension is "+str(tension))
                            self.status.setStyleSheet('background-color: lightgreen')
                else:
                    self.ID_error()
            else:
                self.ID_error()
        else:
            self.name_error()

        self.ID_edit.setFocus()
        self.ID_edit.selectAll()

    def tension_up(self):
        target = 322 + self.increase - self.decrease
        self.tension_device = FourierTension()
        stepper = self.stepper_device()

        self.reset()
        if(str(self.combo.currentText()) != "-Please Select A Name-"):
            if(len(self.ID_edit.text()) == 8):
                if( (self.ID_edit.text()[0:3] == "MSU") and (self.ID_edit.text()[3:8].isdigit() == True) ):
                    self.increase += 10
                    self.yellow()
                    self.update_status("Increasing Tension")
                    result = stepper.step_to(target, 5, callback=self.update_ext_tension)
                    stepper.pause()
                    if(result == 1):
                        tension, frequency = self.measuring_tension("Measuring internal tension")

                        if( (tension > 280.00) and (tension < 350.00) ):
                            tension, frequency = self.measuring_tension("Double checking tension")
                            self.db.add_tube(self.tube_tension_record(tension, frequency))
                            self.tension_pass()
                        else:
                            self.red()
                            self.update_status("Invalid tension, make sure you are near correct tension range, check battery, or try again")
                    else:
                        self.update_status("Increase tension cancelled, no tube data saved")
                        self.reset()
                else:
                    self.ID_error()
            else:
                self.ID_error()
        else:
            self.name_error()

        self.ID_edit.setFocus()
        self.ID_edit.selectAll()

    def tension_down(self):
        target = 322 + self.increase - self.decrease
        self.tension_device = FourierTension()
        stepper = self.stepper_device()

        self.reset()
        if(str(self.combo.currentText()) != "-Please Select A Name-"):
            if(len(self.ID_edit.text()) == 8):
                if( (self.ID_edit.text()[0:3] == "MSU") and (self.ID_edit.text()[3:8].isdigit() == True) ):
                    self.decrease += 10
                    self.yellow()
                    self.update_status("Decreasing Tension")
                    result = stepper.step_to(target, 5, callback=self.update_ext_tension)
                    stepper.pause()
                    if(result == 1):
                        tension, frequency = self.measuring_tension("Measuring internal tension")

                        if( (tension > 280.00) and (tension < 350.00) ):
                            tension, frequency = self.measuring_tension("Double checking tension")
                            self.db.add_tube(self.tube_tension_record(tension, frequency))
                            self.tension_pass()
                        else:
                            self.red()
                            self.update_status("Invalid tension, make sure you are near correct tension range, or check battery and try again")
                    else:
                        self.update_status("Decrease tension cancelled, no tube data saved")
                        self.reset()
                else:
                    self.ID_error()
            else:
                self.ID_error()
        else:
            self.name_error()

        self.ID_edit.setFocus()
        self.ID_edit.selectAll()

    def autotension(self):
        check = 0
        check1 = 0
        self.variable_reset()
        target = 319 + self.increase - self.decrease
        self.tension_device = FourierTension()
        stepper = self.stepper_device()

        self.reset()
        if(str(self.combo.currentText()) != "-Please Select A Name-"):
            if(len(self.ID_edit.text()) == 8):
                if( (self.ID_edit.text()[0:3] == "MSU") and (self.ID_edit.text()[3:8].isdigit() == True) ):
                    self.yellow()
                    self.update_status("Tensioning to 400")
                    result = stepper.step_to(410, 10, callback=self.update_ext_tension)
                    if(result == 1):
                        self.update_status("Holding at 400")
                        result = stepper.hold(410, 20, hold_time=10, callback=self.update_ext_tension)
                        if(result == 1):
                            self.update_status("Tensioning to 0")
                            result = stepper.step_to(0, 5, callback=self.update_ext_tension)
                            if(result == 1):
                                self.update_status("Tensioning to 315")
                                result = stepper.step_to(319, 5, callback=self.update_ext_tension)
                                if(result == 1):
                                    self.update_status("Holding at 315")
                                    result = stepper.hold(319, 10, hold_time=2, callback=self.update_ext_tension)
                                    stepper.pause()
                                    if(result == 1):
                                        tension, frequency = self.measuring_tension("Measuring internal tension")

                                        if( (tension > 200) and (tension < 500) ):
                                            check = 0
                                        else:
                                            tension, frequency = self.measuring_tension("Error, recalculating...")
                                            if( ( tension > 200) and (tension < 500) ):
                                                check = 0
                                            else:
                                                check1 = 2
                                                self.red()
                                                self.update_status("Invalid tension, check battery or try again")

                                        while(check == 0):
                                            if( (tension > 322.57) and (tension < 350.00) ):
                                                self.decrease += 10
                                                target = 319 - self.decrease + self.increase
                                                self.update_status("Decreasing Tension")
                                                result = stepper.step_to(target, 5, callback=self.update_ext_tension)
                                                stepper.pause()
                                                if(result == 1):
                                                    tension, frequency = self.measuring_tension("Measuring internal tension")
                                                else:
                                                    check = 1
                                                    self.update_status("Autotension cancelled, no tube data saved")
                                                    self.reset()
                                            elif( (tension > 280.00) and (tension < 311.97) ):
                                                self.increase += 10
                                                target = 319 - self.decrease + self.increase
                                                self.update_status("Increasing Tension")
                                                result = stepper.step_to(target, 5, callback=self.update_ext_tension)
                                                stepper.pause()
                                                if(result == 1):
                                                    tension, frequency = self.measuring_tension("Measuring internal tension")
                                                else:
                                                    check = 1
                                                    self.update_status("Autotension cancelled, no tube data saved")
                                                    self.reset()
                                            else:
                                                check = 1

                                        if(result == 1):
                                            if(check1 != 2):
                                                if( (tension > 200) and (tension < 500) ):
                                                    tension, frequency = self.measuring_tension("Double checking tension")
                                                    self.db.add_tube(self.tube_tension_record(tension, frequency))
                                                    self.tension_pass()
                                                    win32gui.SetForegroundWindow(win32gui.FindWindow(None, "AutoTension"))
                                                    self.ID_edit.setFocus()
                                                    self.ID_edit.selectAll()
                                                else:
                                                    self.red()
                                                    self.update_status("Invalid tension, check battery or try again")
                                        else:
                                            self.update_status("Autotension cancelled, no tube data saved")
                                            self.reset()
                                    else:
                                        self.update_status("Autotension cancelled, no tube data saved")
                                        self.reset()
                                else:
                                    self.update_status("Autotension cancelled, no tube data saved")
                                    self.reset()
                            else:
                                self.update_status("Autotension cancelled, no tube data saved")
                                self.reset()
                        else:
                            self.update_status("Autotension cancelled, no tube data saved")
                            self.reset()
                    else:
                        self.update_status("Autotension cancelled, no tube data saved")
                        self.reset()
                else:
                    self.ID_error()
            else:
                self.ID_error()
        else:
            self.name_error()

if __name__ == "__main__":
    app = QtWidgets.QApplication()
    w = MainWindow()
    if pyside_version == 2:
        sys.exit(app.exec_())
    elif pyside_version == 6:
        sys.exit(app.exec())
