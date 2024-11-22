
#Tests file for main.py in WhiteboardApplication directory
#Created by Sharon Dong
#Created 11/22/2024
#Last edit: 11/22/2024
from time import sleep

import pytest
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import QPoint
from pytestqt.plugin import qtbot

#import WhiteboardApplication.main
from WhiteboardApplication.main import *
from pytestqt import *









def test_PenButton(qtbot):

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    sleep(2)
    #have to press the button twice for some reason...
    window.tb_actionText.trigger()

    canvas = window.tabWidget.currentWidget().findChild(QtWidgets.QGraphicsView, 'gv_Canvas')
    assert canvas is not None, "Canvas is not found"

    scene = canvas.scene()
    assert scene is not None, "Scene is not found"

    # Allow some time for the GUI to process events
    qtbot.wait(100)

    sleep(2)

    # Assert that a new path was added to the scene
    assert len(scene.items()) > 0, "No items were added to the scene"

    # Verify the tool state if needed (e.g., the active tool is 'pen')
    assert scene.active_tool == "pen", "Pen tool was not activated properly"

