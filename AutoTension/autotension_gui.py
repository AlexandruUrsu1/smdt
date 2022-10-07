# Updated tensioner program to work with the motorized tension setup
# Paul Johnecheck
# April 2022
#
# Modifications:
# 2022-06, Reinhard: separate 400 and 320 tensioning, new target for 320 is 325
#
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
# 2022-08, Alexandru: Major gui update, created seperate autotension and "manual tension" screens
#                     Screens update and operate seperatly, not connected at all
#                     Main processes take place in autotension tab (intended/preferred tab)
#                     Everything extra placed in manual tab, only to use if something goes wrong in autotension tab
#                     Improved the feedback to the user when using "Get Tension" to clear up confusion
#
# 2022-09, Alexandru: Made the autotension process pickier about final tension values in order to improve precision
#                     "Increase" and "Decrease" tension buttons/processes should be more effective and cause the stepper motor to
#                     osciallte back and forth much less frequently
#                     Added an "Import" button next to the tube ID text box on the manual tensioning page, It "imports" the tube
#                     ID from the autotension tab if manual tensioning is still required after the autotension process
#                     New "Truer" overtension value?
#                     Get tension clarified some more
#

import sys
import os
import datetime
import time
import win32gui

pyside_version = None
try:
    from PySide6 import QtCore, QtWidgets, QtGui
    from PySide6.QtWidgets import QMessageBox, QComboBox, QTabWidget, QWidget
    pyside_version = 6
except ImportError:
    from PySide2 import QtCore, QtWidgets, QtGui
    from PySide2.QtWidgets import QMessageBox, QComboBox, QTabWidget, QWidget
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

        names = []
        file = open("Python_program_names.txt", "r")
        file.readline()
        file.readline()
        for line in file:
            line = line.rstrip()
            names.append(line)
        file.close()

        self.setWindowTitle("AutoTension")

        layout1 = QtWidgets.QVBoxLayout()

        tab = QTabWidget()
        auto_tab = QWidget()
        manual_tab = QWidget()
        
        auto_layout = QtWidgets.QVBoxLayout()
        auto_layout0 = QtWidgets.QVBoxLayout()
        auto_layout2 = QtWidgets.QVBoxLayout()
        auto_layout3 = QtWidgets.QGridLayout()
        auto_layout4 = QtWidgets.QVBoxLayout()

        auto_layout.addLayout(auto_layout0)
        auto_layout.addLayout(auto_layout2)
        auto_layout.addLayout(auto_layout3)
        auto_layout.addLayout(auto_layout4)

        self.auto_user_edit = ""
        self.auto_ID_edit = QtWidgets.QLineEdit()
        self.auto_ID_edit.returnPressed.connect(self.auto_get_tension)
        self.auto_ext_tension = QtWidgets.QLineEdit()
        self.auto_ext_tension.setReadOnly(True)
        self.auto_ext_tension.setText("Not yet measured")
        self.auto_ext_tension.setStyleSheet('background-color: lightgrey; color: black')
        self.auto_ext_tension.returnPressed.connect(self.auto_get_tension)
        self.auto_int_tension = QtWidgets.QLineEdit()
        self.auto_int_tension.setReadOnly(True)
        self.auto_int_tension.setText("Not yet measured")
        self.auto_int_tension.setStyleSheet('background-color: lightgrey; color: black')

        auto_name = QtWidgets.QLabel()
        auto_name.setText("Name: " + (" " * 50))
        self.auto_combo = QComboBox()
        self.auto_combo.addItems(names)
        self.auto_user_edit = str(self.auto_combo.currentText())

        auto_form_layout0 = QtWidgets.QFormLayout()
        auto_form_layout0.addRow(auto_name, self.auto_combo)

        auto_layout0.addLayout(auto_form_layout0)

        auto_form_layout = QtWidgets.QFormLayout()
        auto_form_layout.addRow("ID:", self.auto_ID_edit)
        auto_form_layout.addRow("External Sensor Tension:", self.auto_ext_tension)
        auto_form_layout.addRow("Internal Frequency Magnet Tension:", self.auto_int_tension)

        auto_layout2.addLayout(auto_form_layout)

        self.autotension_button = QtWidgets.QPushButton()
        self.autotension_button.setText("\nAuto-Tension\n")
        auto_layout3.addWidget(self.autotension_button, 0, 0, 1, 1)

        self.auto_get_tension_button = QtWidgets.QPushButton()
        self.auto_get_tension_button.setText("\nGet Tension\n")
        auto_layout3.addWidget(self.auto_get_tension_button, 0, 1, 1, 1)

        self.autotension_button.clicked.connect(self.autotension)

        self.auto_get_tension_button.clicked.connect(self.auto_get_tension)

        auto_note1 = QtWidgets.QLabel()
        auto_note2 = QtWidgets.QLabel()
        auto_space1 = QtWidgets.QLabel()
        auto_space2 = QtWidgets.QLabel()
        auto_label = QtWidgets.QLabel()
        self.auto_addName_button = QtWidgets.QPushButton()
        auto_space1.setText("----------------------------------------------------------------------------------------------")
        auto_note1.setText("|                           1st Tension: 315.48 - 322.57 |  2nd Tension: 336.99 - 362.97                           |")
        auto_note2.setText("|                                         Press Esc key to cancel tensioning process                                       |")
        auto_space2.setText("----------------------------------------------------------------------------------------------")
        auto_space1.setAlignment(QtCore.Qt.AlignCenter)
        auto_note1.setAlignment(QtCore.Qt.AlignCenter)
        auto_note2.setAlignment(QtCore.Qt.AlignCenter)
        auto_space2.setAlignment(QtCore.Qt.AlignCenter)
        auto_label.setText("Status:" + (" " * 111))
        self.auto_addName_button.setText("Add Name")
        auto_layout4.addWidget(auto_space1)
        auto_layout4.addWidget(auto_note1)
        auto_layout4.addWidget(auto_note2)
        auto_layout4.addWidget(auto_space2)

        auto_form_layout2 = QtWidgets.QFormLayout()
        auto_form_layout2.addRow(auto_label, self.auto_addName_button)
        
        auto_layout4.addLayout(auto_form_layout2)

        self.auto_addName_button.clicked.connect(self.openFile)

        self.auto_status = QtWidgets.QLineEdit()
        self.auto_status.setReadOnly(True)
        self.auto_status.setText("Not Started")
        self.auto_status.setStyleSheet('background-color: lightgrey; color: black')
        auto_layout4.addWidget(self.auto_status)

        auto_tab.setLayout(auto_layout)

        tab.addTab(auto_tab, "Autotension")

        manual_layout = QtWidgets.QVBoxLayout()
        manual_layout0 = QtWidgets.QVBoxLayout()
        manual_layout1 = QtWidgets.QHBoxLayout()
        manual_layout2 = QtWidgets.QVBoxLayout()
        manual_layout3 = QtWidgets.QGridLayout()
        manual_layout4 = QtWidgets.QVBoxLayout()

        manual_layout.addLayout(manual_layout0)
        manual_layout.addLayout(manual_layout1)
        manual_layout.addLayout(manual_layout2)
        manual_layout.addLayout(manual_layout3)
        manual_layout.addLayout(manual_layout4)

        self.manual_user_edit = ""
        self.manual_ID_edit = QtWidgets.QLineEdit()
        self.manual_ID_edit.returnPressed.connect(self.final_tension)
        self.manual_ext_tension = QtWidgets.QLineEdit()
        self.manual_ext_tension.setReadOnly(True)
        self.manual_ext_tension.setText("Not yet measured")
        self.manual_ext_tension.setStyleSheet('background-color: lightgrey; color: black')
        self.manual_int_tension = QtWidgets.QLineEdit()
        self.manual_int_tension.setReadOnly(True)
        self.manual_int_tension.setText("Not yet measured")
        self.manual_int_tension.setStyleSheet('background-color: lightgrey; color: black')

        manual_name = QtWidgets.QLabel()
        manual_name.setText("Name: " + (" " * 50))
        self.manual_combo = QComboBox()
        self.manual_combo.addItems(names)
        self.manual_user_edit = str(self.manual_combo.currentText())

        manual_form_layout0 = QtWidgets.QFormLayout()
        manual_form_layout0.addRow(manual_name, self.manual_combo)

        manual_layout0.addLayout(manual_form_layout0)

        manual_note0 = QtWidgets.QLabel()
        manual_note0.setText("ID:        " + (" " * 50))
        self.import_button = QtWidgets.QPushButton()
        self.import_button.setText("Import")
        manual_layout1.addWidget(manual_note0)
        manual_layout1.addWidget(self.manual_ID_edit)
        manual_layout1.addWidget(self.import_button)

        self.import_button.clicked.connect(self.import_auto_ID)
        
        manual_form_layout = QtWidgets.QFormLayout()
        manual_form_layout.addRow("External Sensor Tension:", self.manual_ext_tension)
        manual_form_layout.addRow("Internal Frequency Magnet Tension:", self.manual_int_tension)

        manual_layout2.addLayout(manual_form_layout)

        self.overtension_button = QtWidgets.QPushButton()
        self.overtension_button.setText("Over-Tension (400)")
        self.overtension_button.setStyleSheet("font-size: 13px;");
        manual_layout3.addWidget(self.overtension_button, 0, 0)

        self.release_button = QtWidgets.QPushButton()
        self.release_button.setText("Release Tension (0)")
        self.release_button.setStyleSheet("font-size: 13px;");
        manual_layout3.addWidget(self.release_button, 0, 1)

        self.final_tension_button = QtWidgets.QPushButton()
        self.final_tension_button.setText("Final Tension (320)")
        self.final_tension_button.setStyleSheet("font-size: 13px;");
        manual_layout3.addWidget(self.final_tension_button, 0, 2)

        self.manual_get_tension_button = QtWidgets.QPushButton()
        self.manual_get_tension_button.setText("Get Tension")
        manual_layout3.addWidget(self.manual_get_tension_button, 1, 2)

        self.tension_up_button = QtWidgets.QPushButton()
        self.tension_up_button.setText("Increase Tension")
        manual_layout3.addWidget(self.tension_up_button, 1, 0)

        self.tension_down_button = QtWidgets.QPushButton()
        self.tension_down_button.setText("Decrease Tension")
        manual_layout3.addWidget(self.tension_down_button, 1, 1)

        self.overtension_button.setAutoDefault(True)

        self.overtension_button.clicked.connect(self.overtension)
        
        self.release_button.clicked.connect(self.release)
        
        self.final_tension_button.clicked.connect(self.final_tension)

        self.manual_get_tension_button.clicked.connect(self.manual_get_tension)

        self.tension_up_button.clicked.connect(self.tension_up)

        self.tension_down_button.clicked.connect(self.tension_down)

        manual_note1 = QtWidgets.QLabel()
        manual_note2 = QtWidgets.QLabel()
        manual_space1 = QtWidgets.QLabel()
        manual_space2 = QtWidgets.QLabel()
        manual_label = QtWidgets.QLabel()
        self.manual_addName_button = QtWidgets.QPushButton()
        manual_space1.setText("----------------------------------------------------------------------------------------------")
        manual_note1.setText("|                           1st Tension: 315.48 - 322.57 |  2nd Tension: 336.99 - 362.97                           |")
        manual_note2.setText("|                                         Press Esc key to cancel tensioning process                                       |")
        manual_space2.setText("----------------------------------------------------------------------------------------------")
        manual_space1.setAlignment(QtCore.Qt.AlignCenter)
        manual_note1.setAlignment(QtCore.Qt.AlignCenter)
        manual_note2.setAlignment(QtCore.Qt.AlignCenter)
        manual_space2.setAlignment(QtCore.Qt.AlignCenter)
        manual_label.setText("Status:" + (" " * 111))
        self.manual_addName_button.setText("Add Name")
        manual_layout4.addWidget(manual_space1)
        manual_layout4.addWidget(manual_note1)
        manual_layout4.addWidget(manual_note2)
        manual_layout4.addWidget(manual_space2)

        manual_form_layout2 = QtWidgets.QFormLayout()
        manual_form_layout2.addRow(manual_label, self.manual_addName_button)
        
        manual_layout4.addLayout(manual_form_layout2)

        self.manual_addName_button.clicked.connect(self.openFile)

        self.manual_status = QtWidgets.QLineEdit()
        self.manual_status.setReadOnly(True)
        self.manual_status.setText("Not Started")
        self.manual_status.setStyleSheet('background-color: lightgrey; color: black')
        manual_layout4.addWidget(self.manual_status)

        manual_tab.setLayout(manual_layout)

        tab.addTab(manual_tab, "Manual Tension")

        layout1.addWidget(tab)

        widget = QtWidgets.QWidget()
        widget.setLayout(layout1)
        self.setCentralWidget(widget)

        self.show()

        self.increase = 10
        self.decrease = 10

    def update_auto_ext_tension(self, tension):
        self.auto_ext_tension.setText(str(tension))

    def update_manual_ext_tension(self, tension):
        self.manual_ext_tension.setText(str(tension))

    def update_auto_int_tension(self, tension):
        self.auto_int_tension.setText(str(tension))

    def update_manual_int_tension(self, tension):
        self.manual_int_tension.setText(str(tension))

    def update_auto_status(self, status):
        self.auto_status.setText(status)

    def update_manual_status(self, status):
        self.manual_status.setText(status)

    def update_auto_username(self):
        self.auto_user_edit = str(self.auto_combo.currentText())

    def update_manual_username(self):
        self.manual_user_edit = str(self.manual_combo.currentText())

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

    def stepper_device_small(self):
        n_samp = 1
        stepper = Stepper(
            noise_reduction=self.avg,
            stride=1,
            n_samp=n_samp,
            plotter=Plotter(self.plot_title, self.plot_x_label, self.plot_y_label))
        return stepper

    def auto_tube_tension_record(self, tension, frequency):
        self.update_auto_username()
        newTube = tube.Tube()
        newTube.set_ID(self.auto_ID_edit.text().strip())
        newTube.tension.add_record(
            TensionRecord(
                tension=tension,
                frequency=frequency,
                date=datetime.datetime.now(),
                user=self.auto_user_edit.strip()
                )
            )
        return newTube

    def manual_tube_tension_record(self, tension, frequency):
        self.update_manual_username()
        newTube = tube.Tube()
        newTube.set_ID(self.manual_ID_edit.text().strip())
        newTube.tension.add_record(
            TensionRecord(
                tension=tension,
                frequency=frequency,
                date=datetime.datetime.now(),
                user=self.manual_user_edit.strip()
                )
            )
        return newTube

    def variable_reset(self):
        self.increase = 10
        self.decrease = 10

    def measuring_auto_tension(self, string):
        self.update_auto_status(string)
        tension, frequency =  self.tension_device.get_tension()
        self.update_auto_int_tension(tension)
        return tension, frequency

    def measuring_manual_tension(self, string):
        self.update_manual_status(string)
        tension, frequency =  self.tension_device.get_tension()
        self.update_manual_int_tension(tension)
        return tension, frequency

    def auto_reset(self):
        self.auto_int_tension.setText("Not yet measured")
        self.auto_int_tension.setStyleSheet('background-color: lightgrey')
        self.auto_status.setStyleSheet('background-color: lightgrey')

    def manual_reset(self):
        self.manual_int_tension.setText("Not yet measured")
        self.manual_int_tension.setStyleSheet('background-color: lightgrey')
        self.manual_status.setStyleSheet('background-color: lightgrey')

    def auto_reset_plus_status(self, string):
        self.auto_int_tension.setText("Not yet measured")
        self.auto_int_tension.setStyleSheet('background-color: lightgrey')
        self.auto_status.setStyleSheet('background-color: lightgrey')
        self.update_auto_status(string)

    def manual_reset_plus_status(self, string):
        self.manual_int_tension.setText("Not yet measured")
        self.manual_int_tension.setStyleSheet('background-color: lightgrey')
        self.manual_status.setStyleSheet('background-color: lightgrey')
        self.update_manual_status(string)

    def auto_name_error(self):
        self.auto_ID_edit.setStyleSheet('background-color: white')
        self.update_auto_status("Please select a valid name")
        self.auto_status.setStyleSheet('background-color: red')

    def manual_name_error(self):
        self.manual_ID_edit.setStyleSheet('background-color: white')
        self.update_manual_status("Please select a valid name")
        self.manual_status.setStyleSheet('background-color: red')

    def auto_ID_error(self):
        self.auto_ID_edit.setStyleSheet('background-color: red')
        self.update_auto_status("Please enter a valid tube ID")
        self.auto_status.setStyleSheet('background-color: red')

    def manual_ID_error(self):
        self.manual_ID_edit.setStyleSheet('background-color: red')
        self.update_manual_status("Please enter a valid tube ID")
        self.manual_status.setStyleSheet('background-color: red')

    def auto_tension_pass(self, string):
        self.auto_int_tension.setStyleSheet('background-color: lightgreen')
        self.auto_status.setStyleSheet('background-color: lightgreen')
        self.update_auto_status(string)

    def manual_tension_pass(self, string):
        self.manual_int_tension.setStyleSheet('background-color: lightgreen')
        self.manual_status.setStyleSheet('background-color: lightgreen')
        self.update_manual_status(string)

    def auto_red(self, string):
        self.auto_int_tension.setStyleSheet('background-color: red')
        self.auto_status.setStyleSheet('background-color: red')
        self.update_auto_status(string)

    def manual_red(self, string):
        self.manual_int_tension.setStyleSheet('background-color: red')
        self.manual_status.setStyleSheet('background-color: red')
        self.update_manual_status(string)

    def auto_yellow(self):
        self.auto_ID_edit.setStyleSheet('background-color: white')
        self.auto_status.setStyleSheet('background-color: yellow')

    def manual_yellow(self):
        self.manual_ID_edit.setStyleSheet('background-color: white')
        self.manual_status.setStyleSheet('background-color: yellow')

    def auto_focus(self):
        self.auto_ID_edit.setFocus()
        self.auto_ID_edit.selectAll()

    def manual_focus(self):
        self.manual_ID_edit.setFocus()
        self.manual_ID_edit.selectAll()

    def import_auto_ID(self):
        self.manual_ID_edit.setText(self.auto_ID_edit.text())

    def overtension(self):
        self.variable_reset()
        self.tension_device = FourierTension()
        stepper = self.stepper_device()

        self.manual_reset()
        if(str(self.manual_combo.currentText()) != "-Please Select A Name-"):
            if(len(self.manual_ID_edit.text()) == 8):
                if( (self.manual_ID_edit.text()[0:3] == "MSU") and (self.manual_ID_edit.text()[3:8].isdigit() == True) ):
                    self.manual_yellow()
                    self.update_manual_status("Tensioning to 400")
                    result = stepper.step_to(400, 5, callback=self.update_manual_ext_tension)
                    stepper.pause()
                    if(result == 1):
                        tension, frequency = self.measuring_manual_tension("Measuring internal tension")

                        if(( tension > 350) and (tension < 450) ):
                            self.db.add_tube(self.manual_tube_tension_record(tension, frequency))
                            self.manual_tension_pass("Overtension complete")
                        else:
                            tension, frequency = self.measuring_manual_tension("Recalculating...")
                            if(( tension > 350) and (tension < 450) ):
                                self.db.add_tube(self.manual_tube_tension_record(tension, frequency))
                                self.manual_tension_pass("Overtension complete")
                            else:
                                self.manual_red("Invalid overtension, check battery or try again")
                    else:
                        self.manual_reset_plus_status("Overtension cancelled, no tube data saved")
                else:
                    self.manual_ID_error()
                    self.manual_focus()
            else:
                self.manual_ID_error()
                self.manual_focus()
        else:
            self.manual_name_error()

    def release(self):
        self.variable_reset()
        stepper = self.stepper_device()

        self.manual_reset()
        if(str(self.manual_combo.currentText()) != "-Please Select A Name-"):
            if(len(self.manual_ID_edit.text()) == 8):
                if( (self.manual_ID_edit.text()[0:3] == "MSU") and (self.manual_ID_edit.text()[3:8].isdigit() == True) ):
                    self.manual_yellow()
                    self.update_manual_status("Releasing tension")
                    result = stepper.step_to(0, 10, callback=self.update_manual_ext_tension)
                    stepper.pause()
                    if(result == 1):
                        self.manual_tension_pass("Released tension")
                    else:
                        self.manual_reset_plus_status("Release tension cancelled")
                else:
                    self.manual_ID_error()
                    self.manual_focus()
            else:
                self.manual_ID_error()
                self.manual_focus()
        else:
            self.manual_name_error()

    def final_tension(self):
        self.variable_reset()
        self.tension_device = FourierTension()
        stepper = self.stepper_device()

        self.manual_reset()
        if(str(self.manual_combo.currentText()) != "-Please Select A Name-"):
            if(len(self.manual_ID_edit.text()) == 8):
                if( (self.manual_ID_edit.text()[0:3] == "MSU") and (self.manual_ID_edit.text()[3:8].isdigit() == True) ):
                    self.manual_yellow()
                    self.update_manual_status("Tensioning to 320")
                    result = stepper.step_to(320, 5, callback=self.update_manual_ext_tension)
                    stepper.pause()
                    if(result == 1):
                        tension, frequency = self.measuring_manual_tension("Measuring internal tension")

                        if( (tension > 311.97) and (tension < 326.15) ):
                            self.db.add_tube(self.manual_tube_tension_record(tension, frequency))
                            self.manual_tension_pass("Final tension complete, "+(self.manual_ID_edit.text().strip())+" tube tension added to database")
                            self.manual_focus()
                        else:
                            tension, frequency = self.measuring_manual_tension("Error, recalculating...")
                            if( (tension > 315.48) and (tension < 322.57) ):
                                self.db.add_tube(self.manual_tube_tension_record(tension, frequency))
                                self.manual_tension_pass("Final tension complete, tube tension added to database")
                                win32gui.SetForegroundWindow(win32gui.FindWindow(None, "AutoTension"))
                                self.manual_focus()
                            elif( (tension > 200) and (tension < 315.48) ):
                                self.db.add_tube(self.manual_tube_tension_record(tension, frequency))
                                self.manual_red("Final tension low, need increase")
                            elif( (tension > 322.57) and (tension < 400) ):
                                self.db.add_tube(self.manual_tube_tension_record(tension, frequency))
                                self.manual_red("Final tension high, need decrease")
                            elif(tension < 200):
                                self.db.ad4d_tube(self.manual_tube_tension_record(tension, frequency))
                                self.manual_red("Final tension very low, check battery or try again?")
                            else:
                                self.manual_red("Invalid final tension, check battery")
                    else:
                        self.manual_reset_plus_status("Final tension cancelled, no tube data saved")
                else:
                    self.manual_ID_error()
                    self.manual_focus()
            else:
                self.manual_ID_error()
                self.manual_focus()
        else:
            self.manual_name_error()

    def auto_get_tension(self):
        self.tension_device = FourierTension()

        self.auto_reset()
        if(str(self.auto_combo.currentText()) != "-Please Select A Name-"):
            if(len(self.auto_ID_edit.text()) == 8):
                if( (self.auto_ID_edit.text()[0:3] == "MSU") and (self.auto_ID_edit.text()[3:8].isdigit() == True) ):
                    self.auto_ID_edit.setStyleSheet('background-color: white')
                    tension, frequency = self.measuring_auto_tension("Measuring internal tension")

                    if( (tension > 335) and (tension < 365) ):
                        self.db.add_tube(self.auto_tube_tension_record(tension, frequency))
                        self.auto_tension_pass((self.auto_ID_edit.text().strip())+" Done. Internal tension is "+str(tension))
                    elif( (tension > 200) and (tension < 315) ):
                        self.db.add_tube(self.auto_tube_tension_record(tension, frequency))
                        self.auto_red("Done. Tension low.")
                    elif( (tension > 315) and (tension < 335) ):
                        self.db.add_tube(self.auto_tube_tension_record(tension, frequency))
                        self.auto_red("Done. If 1st tension, good. If 2nd tension, low.")
                        #self.auto_yellow()
                        #self.auto_int_tension.setStyleSheet('background-color: yellow')
                        #self.update_auto_status("Done. If 1st tension, good. If 2nd tension, low.")
                    elif( (tension > 365) and (tension < 500) ):
                        self.db.add_tube(self.auto_tube_tension_record(tension, frequency))
                        self.auto_red("Done. Tension high.")
                    else:
                        tension, frequency = self.measuring_auto_tension("Error, recalculating...")
                        if(tension <= 200):
                            self.db.add_tube(self.auto_tube_tension_record(tension, frequency))
                            self.auto_red("Done. Internal tension low. Wire snap? Check battery?")
                        elif( (tension > 200) and (tension < 315) ):
                            self.db.add_tube(self.auto_tube_tension_record(tension, frequency))
                            self.auto_red("Done. Tension low.")
                        elif( (tension > 315) and (tension < 335) ):
                            self.db.add_tube(self.auto_tube_tension_record(tension, frequency))
                            self.auto_red("Done. If 1st tension, good. If 2nd tension, low.")
                            #self.auto_yellow()
                            #self.auto_int_tension.setStyleSheet('background-color: yellow')
                            #self.update_auto_status("Done. If 1st tension, good. If 2nd tension, low.")
                        elif( (tension > 335) and (tension < 365) ):
                            self.db.add_tube(self.auto_tube_tension_record(tension, frequency))
                            self.auto_tension_pass("Done. Internal tension is "+str(tension))
                        elif( (tension > 365) and (tension < 500) ):
                            self.db.add_tube(self.auto_tube_tension_record(tension, frequency))
                            self.auto_red("Done. Tension high.")
                        else:
                            self.auto_red("Invalid tension, very high, check battery?")
                else:
                    self.auto_ID_error()
            else:
                self.auto_ID_error()
        else:
            self.auto_name_error()

        self.auto_focus()

    def manual_get_tension(self):
        self.tension_device = FourierTension()

        self.manual_reset()
        if(str(self.manual_combo.currentText()) != "-Please Select A Name-"):
            if(len(self.manual_ID_edit.text()) == 8):
                if( (self.manual_ID_edit.text()[0:3] == "MSU") and (self.manual_ID_edit.text()[3:8].isdigit() == True) ):
                    self.manual_ID_edit.setStyleSheet('background-color: white')
                    tension, frequency = self.measuring_manual_tension("Measuring internal tension")

                    if( (tension > 335) and (tension < 365) ):
                        self.db.add_tube(self.manual_tube_tension_record(tension, frequency))
                        self.manual_tension_pass((self.manual_ID_edit.text().strip())+" Done. Internal tension is "+str(tension))
                    elif( (tension > 200) and (tension < 315) ):
                        self.db.add_tube(self.manual_tube_tension_record(tension, frequency))
                        self.manual_red("Done. Tension low.")
                    elif( (tension > 315) and (tension < 335) ):
                        self.db.add_tube(self.manual_tube_tension_record(tension, frequency))
                        self.manual_yellow()
                        self.manual_int_tension.setStyleSheet('background-color: yellow')
                        self.update_manual_status("Done. If 1st tension, good. If 2nd tension, low.")
                    elif( (tension > 365) and (tension < 500) ):
                        self.db.add_tube(self.manual_tube_tension_record(tension, frequency))
                        self.manual_red("Done. Tension high.")
                    else:
                        tension, frequency = self.measuring_manual_tension("Error, recalculating...")
                        if(tension <= 200):
                            self.db.add_tube(self.manual_tube_tension_record(tension, frequency))
                            self.manual_red("Done. Internal tension low. Wire snap? Check battery?")
                        elif( (tension > 200) and (tension < 315) ):
                            self.db.add_tube(self.manual_tube_tension_record(tension, frequency))
                            self.manual_red("Done. Tension low.")
                        elif( (tension > 315) and (tension < 335) ):
                            self.db.add_tube(self.manual_tube_tension_record(tension, frequency))
                            self.manual_yellow()
                            self.manual_int_tension.setStyleSheet('background-color: yellow')
                            self.update_manual_status("Done. If 1st tension, good. If 2nd tension, low.")
                        elif( (tension > 335) and (tension < 365) ):
                            self.db.add_tube(self.manual_tube_tension_record(tension, frequency))
                            self.manual_tension_pass("Done. Internal tension is "+str(tension))
                        elif( (tension > 365) and (tension < 500) ):
                            self.db.add_tube(self.manual_tube_tension_record(tension, frequency))
                            self.manual_red("Done. Tension high.")
                        else:
                            self.manual_red("Invalid tension, very high, check battery?")
                else:
                    self.manual_ID_error()
            else:
                self.manual_ID_error()
        else:
            self.manual_name_error()

        self.manual_focus()

    def tension_up(self):
        external_text = ""
        external_float = 0.0
        external_int = 0
        target = 0
        self.variable_reset()
        self.tension_device = FourierTension()
        stepper = self.stepper_device_small()

        self.manual_reset()
        if(str(self.manual_combo.currentText()) != "-Please Select A Name-"):
            if(len(self.manual_ID_edit.text()) == 8):
                if( (self.manual_ID_edit.text()[0:3] == "MSU") and (self.manual_ID_edit.text()[3:8].isdigit() == True) ):
                    external_text = self.manual_ext_tension.text()
                    external_float = float(external_text)
                    external_int = int(external_float)
                    self.increase += 10
                    target = external_int + self.increase - self.decrease
                    self.manual_yellow()
                    self.update_manual_status("Increasing Tension")
                    result = stepper.step_to(target, 5, callback=self.update_manual_ext_tension)
                    stepper.pause()
                    if(result == 1):
                        tension, frequency = self.measuring_manual_tension("Measuring internal tension")

                        if( (tension > 280.00) and (tension < 350.00) ):
                            tension, frequency = self.measuring_manual_tension("Double checking tension")
                            self.db.add_tube(self.manual_tube_tension_record(tension, frequency))
                            self.manual_tension_pass("Tension increased")
                        else:
                            self.manual_red("Invalid tension, make sure you are near correct tension range, check battery, or try again")
                    else:
                        self.manual_reset_plus_status("Increase tension cancelled, no tube data saved")
                else:
                    self.manual_ID_error()
                    self.manual_focus()
            else:
                self.manual_ID_error()
                self.manual_focus()
        else:
            self.manual_name_error()

    def tension_down(self):
        self.manual_ext_tension.setText(self.auto_ext_tension.text())
        external_text = ""
        external_float = 0.0
        external_int = 0
        target = 0
        self.variable_reset()
        self.tension_device = FourierTension()
        stepper = self.stepper_device_small()

        self.manual_reset()
        if(str(self.manual_combo.currentText()) != "-Please Select A Name-"):
            if(len(self.manual_ID_edit.text()) == 8):
                if( (self.manual_ID_edit.text()[0:3] == "MSU") and (self.manual_ID_edit.text()[3:8].isdigit() == True) ):
                    external_text = self.manual_ext_tension.text()
                    external_float = float(external_text)
                    external_int = int(external_float)
                    self.decrease += 10
                    target = external_int + self.increase - self.decrease
                    self.manual_yellow()
                    self.update_manual_status("Decreasing Tension")
                    result = stepper.step_to(target, 5, callback=self.update_manual_ext_tension)
                    stepper.pause()
                    if(result == 1):
                        tension, frequency = self.measuring_manual_tension("Measuring internal tension")

                        if( (tension > 280.00) and (tension < 350.00) ):
                            tension, frequency = self.measuring_manual_tension("Double checking tension")
                            self.db.add_tube(self.manual_tube_tension_record(tension, frequency))
                            self.manual_tension_pass("Tension decreased")
                        else:
                            self.manual_red("Invalid tension, make sure you are near correct tension range, or check battery and try again")
                    else:
                        self.manual_reset_plus_status("Decrease tension cancelled, no tube data saved")
                else:
                    self.manual_ID_error()
                    self.manual_focus()
            else:
                self.manual_ID_error()
                self.manual_focus()
        else:
            self.manual_name_error()

    def autotension(self):
        check = 1
        check1 = 1
        external_text = ""
        external_float = 0.0
        external_int = 0
        target = 0
        self.variable_reset()
        self.tension_device = FourierTension()
        n_samp = 1
        stepper = Stepper(
            noise_reduction=self.avg,
            stride=28,
            n_samp=n_samp,
            plotter=Plotter(self.plot_title, self.plot_x_label, self.plot_y_label))

        self.auto_reset()
        if(str(self.auto_combo.currentText()) != "-Please Select A Name-"):
            if(len(self.auto_ID_edit.text()) == 8):
                if( (self.auto_ID_edit.text()[0:3] == "MSU") and (self.auto_ID_edit.text()[3:8].isdigit() == True) ):
                    self.auto_yellow()
                    self.update_auto_status("Tensioning to 400")
                    result = stepper.step_to(410, 10, callback=self.update_auto_ext_tension)
                    if(result == 1):
                        self.update_auto_status("Holding at 400")
                        result = stepper.hold(400, 20, hold_time=9, callback=self.update_auto_ext_tension)
                        if(result == 1):
                            self.update_auto_status("Tensioning to 0")
                            result = stepper.step_to(0, 11, callback=self.update_auto_ext_tension)
                            if(result == 1):
                                self.update_auto_status("Holding at 0")
                                result = stepper.hold(1, 21, hold_time=9, callback=self.update_auto_ext_tension)
                                if(result == 1):
                                    self.update_auto_status("Tensioning to 319")
                                    result = stepper.step_to(319, 5, callback=self.update_auto_ext_tension)
                                    if(result == 1):
                                        self.update_auto_status("Holding at 319")
                                        result = stepper.hold(319, 10, hold_time=2, callback=self.update_auto_ext_tension)
                                        stepper.pause()
                                        if(result == 1):
                                            tension, frequency = self.measuring_auto_tension("Measuring internal tension")

                                            if( (tension > 200) and (tension < 500) ):
                                                check = 0
                                            else:
                                                tension, frequency = self.measuring_auto_tension("Error, recalculating...")
                                                if( ( tension > 200) and (tension < 450) ):
                                                    check = 0
                                                else:
                                                    check1 = 2
                                                    self.auto_red("Invalid tension, check battery or try again")

                                            external_text = self.auto_ext_tension.text()
                                            external_float = float(external_text)
                                            external_int = int(external_float)
                                            while(check == 0):
                                                tension, frequency = self.measuring_auto_tension("Double checking tension...")
                                                if( (tension > 322.57) and (tension < 350.00) ):
                                                    self.decrease += 10
                                                    target = external_int - self.decrease + self.increase
                                                    self.update_auto_status("Decreasing Tension")
                                                    stride = 1
                                                    result = stepper.step_to(target, 5, callback=self.update_auto_ext_tension)
                                                    stride = 28
                                                    stepper.pause()
                                                    if(result == 1):
                                                        tension, frequency = self.measuring_auto_tension("Measuring internal tension")
                                                    else:
                                                        check = 1
                                                        self.auto_reset_plus_status("Autotension cancelled, no tube data saved")
                                                        check1 = 2
                                                elif( (tension > 280.00) and (tension < 315.48) ):
                                                    self.increase += 10
                                                    target = external_int - self.decrease + self.increase
                                                    self.update_auto_status("Increasing Tension")
                                                    stride = 1
                                                    result = stepper.step_to(target, 5, callback=self.update_auto_ext_tension)
                                                    stride = 28
                                                    stepper.pause()
                                                    if(result == 1):
                                                        tension, frequency = self.measuring_auto_tension("Measuring internal tension")
                                                    else:
                                                        check = 1
                                                        self.auto_reset_plus_status("Autotension cancelled, no tube data saved")
                                                        check1 = 2
                                                elif( (tension >= 350.00) and (tension < 450) ):
                                                    self.decrease += 50
                                                    target = external_int - self.decrease + self.increase
                                                    self.update_auto_status("Decreasing Tension")
                                                    stride = 1
                                                    result = stepper.step_to(target, 5, callback=self.update_auto_ext_tension)
                                                    stride = 28
                                                    stepper.pause()
                                                    if(result == 1):
                                                        tension, frequency = self.measuring_auto_tension("Measuring internal tension")
                                                    else:
                                                        check = 1
                                                        self.auto_reset_plus_status("Autotension cancelled, no tube data saved")
                                                        check1 = 2
                                                elif( (tension > 200.00) and (tension <= 280.00) ):
                                                    self.increase += 50
                                                    target = external_int - self.decrease + self.increase
                                                    self.update_auto_status("Increasing Tension")
                                                    stride = 1
                                                    result = stepper.step_to(target, 5, callback=self.update_auto_ext_tension)
                                                    stride = 28
                                                    stepper.pause()
                                                    if(result == 1):
                                                        tension, frequency = self.measuring_auto_tension("Measuring internal tension")
                                                    else:
                                                        check = 1
                                                        self.auto_reset_plus_status("Autotension cancelled, no tube data saved")
                                                        check1 = 2
                                                else:
                                                    check = 1

                                            if(result == 1):
                                                if(check1 != 2):
                                                    if( (tension > 200) and (tension < 450) ):
                                                        tension, frequency = self.measuring_auto_tension("Double checking tension...")
                                                        self.db.add_tube(self.auto_tube_tension_record(tension, frequency))
                                                        self.auto_tension_pass("Done")
                                                        win32gui.SetForegroundWindow(win32gui.FindWindow(None, "AutoTension"))
                                                        self.auto_focus()
                                                    else:
                                                        self.auto_red("Invalid tension, check battery or try again")
                                                else:
                                                    check1 = 1
                                            else:
                                                self.auto_reset_plus_status("Autotension cancelled, no tube data saved")
                                        else:
                                            self.auto_reset_plus_status("Autotension cancelled, no tube data saved")
                                    else:
                                        self.auto_reset_plus_status("Autotension cancelled, no tube data saved")
                                else:
                                    self.auto_reset_plus_status("Autotension cancelled, no tube data saved")
                            else:
                                self.auto_reset_plus_status("Autotension cancelled, no tube data saved")
                        else:
                            self.auto_reset_plus_status("Autotension cancelled, no tube data saved")
                    else:
                        self.auto_reset_plus_status("Autotension cancelled, no tube data saved")
                else:
                    self.auto_ID_error()
                    self.auto_focus()
            else:
                self.auto_ID_error()
                self.auto_focus()
        else:
            self.auto_name_error()

if __name__ == "__main__":
    app = QtWidgets.QApplication()
    w = MainWindow()
    if pyside_version == 2:
        sys.exit(app.exec_())
    elif pyside_version == 6:
        sys.exit(app.exec())
