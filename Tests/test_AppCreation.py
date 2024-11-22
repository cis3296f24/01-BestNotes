#Tests file for main.py in WhiteboardApplication directory
#Created by Riviera Sperduto
#Created 11/19/2024
#Last edit: 11/20/2024
from time import sleep

import pytest
from pytestqt.plugin import qtbot

#import WhiteboardApplication.main
from WhiteboardApplication.main import *
from pytestqt import *




def test_AppCreation(qtbot):
    print("Hello World")


    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    sleep(2)

    assert window is not None






