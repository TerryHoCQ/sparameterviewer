from .settings import Settings
from lib import is_windows, AppPaths
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *
import logging
import pathlib
from typing import Callable, Optional, Union



class QtHelper:


    @staticmethod
    def set_dialog_icon(dialog: Union[QDialog,QMainWindow]):
        if is_windows():
            images_to_try = ['sparamviewer.ico']
        else:
            images_to_try = ['sparamviewer.png', 'sparamviewer.xbm']
        for image in images_to_try:
            try:
                icon_path = pathlib.Path(AppPaths.get_resource_dir()) / image
                dialog.setWindowIcon(QtGui.QIcon(str(icon_path)))
                return
            except Exception as ex:
                logging.debug(f'Cannot load icon <{image}>, trying next')
        logging.debug(f'Unable to set window icon')


    @staticmethod
    def make_label(text: str, *, font: Optional[QFont] = None, stretch: bool = False) -> QLabel:
        label = QLabel()
        label.setText(text)
        if font:
            label.setFont(font)
        if not stretch:
            label.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed, QSizePolicy.ControlType.Label))
        return label


    @staticmethod
    def make_font(*, base: QFont = None, family: str = None, bold: bool = None, underline: bool = None, strikethru: bool = None, rel_size: float = None) -> QFont:
        if base:
            font = QFont(base)
        else:
            font = QFont()
        if family:
            font.setFamily(family)
        if bold is not None:
            font.setBold(bold)
        if rel_size is not None:
            font.setPointSizeF(font.pointSizeF() * rel_size)
        if underline is not None:
            font.setUnderline(bold)
        if strikethru is not None:
            font.setStrikeOut(strikethru)
        return font


    @staticmethod
    def make_image(path: str, placeholder: str = 'Placeholder') -> QLabel:
        image = QLabel()
        try:
            pixmap = QPixmap(path)
            if pixmap.isNull():
                raise RuntimeError('QPixmap is null')
            image.setPixmap(pixmap)
            image.adjustSize()
        except Exception as ex:
            logging.error('Unable to create QPixmap from <{path}>')
            logging.exception(ex)
            image.setText(placeholder)
        return image


    @staticmethod
    def make_button(text: str, action: Callable = None) -> QPushButton:
        button = QPushButton()
        button.setText(text)
        if action:
            button.clicked.connect(action)
        return button


    @staticmethod
    def make_spring() -> QSpacerItem:
        return QSpacerItem(0, 0, QSizePolicy.Policy.Expanding)


    @staticmethod
    def make_hspace(width: int) -> QSpacerItem:
        return QSpacerItem(width, 0, QSizePolicy.Policy.Fixed)


    @staticmethod
    def make_vspace(height: int) -> QSpacerItem:
        return QSpacerItem(0, height, QSizePolicy.Policy.Fixed)


    @staticmethod
    def add_submenu(parent, menu: QMenu, text: str, visible: bool = True) -> QMenu:
        submenu = QMenu(text, parent)
        if not visible:
            submenu.setVisible(False)
        menu.addMenu(submenu)
        return submenu


    @staticmethod
    def add_menuitem(menu: QMenu, text: str, action: Callable, *, shortcut: str = '', visible: bool = True, checkable: bool = False) -> QAction:
        item = QAction(text)
        if action:
            item.triggered.connect(action)
        if shortcut:
            item.setShortcut(QKeySequence(shortcut))
        if checkable:
            item.setCheckable(True)
        if not visible:
            item.setVisible(False)
        menu.addAction(item)
        return item


    @staticmethod
    def get_monospace_font() -> str:
        try:
            preferred_fonts = ['Fira Code', 'DejaVu Mono', 'Liberation Mono', 'Consolas', 'Courier New', 'Lucida Sans Typewriter']
            if Settings.editor_font in preferred_fonts:
                return Settings.editor_font
            
            available_fonts = QtGui.QFontDatabase.families()
            for preferred_font in preferred_fonts:
                if preferred_font in available_fonts:
                    Settings.editor_font = preferred_font
                    return preferred_font
        except:
            pass
        
        return QFont().family()  # fallback


    @staticmethod
    def indicate_error(widget: QWidget, indicate_error: bool = True):
        if indicate_error:
            base_color = widget.palette().color(widget.palette(). ColorRole.Base)
            is_light = base_color.lightnessF() >= 0.5
            if is_light:
                bg_color = QColor.fromHsvF(0.0, 0.3, 0.95)
                fg_color = QColor.fromHsvF(0.0, 0.0, 0.0)
            else:
                bg_color = QColor.fromHsvF(0.0, 0.7, 0.7)
                fg_color = QColor.fromHsvF(0.0, 0.0, 1.0)
            style = f'background-color:{bg_color.name()};color:{fg_color.name()};'
        else:
            style = ''
        widget.setStyleSheet(style)


    @staticmethod
    def _box_layout(layout: QBoxLayout, direction: str, *items):
        for item in items:
            if item is ...:
                layout.addStretch()
            elif isinstance(item, QLayoutItem):
                layout.addLayout(item)
            elif isinstance(item, str):
                layout.addWidget(QtHelper.make_label(item))
            elif isinstance(item, int):
                if direction=='h':
                    layout.addLayout(QtHelper.make_hspace(item))
                elif direction=='v':
                    layout.addLayout(QtHelper.make_vspace(item))
                else:
                    raise ValueError()
            else:
                layout.addWidget(item)
        return layout


    @staticmethod
    def layout_h(*items):
        return QtHelper._box_layout(QHBoxLayout(), 'h', *items)


    @staticmethod
    def layout_v(*items):
        return QtHelper._box_layout(QVBoxLayout(), 'v', *items)


    @staticmethod
    def layout_grid(items_rows_then_columns):
        layout = QGridLayout()
        for i_row,columns in enumerate(items_rows_then_columns):
            for i_col,item in enumerate(columns):
                if item is None:
                    continue
                elif isinstance(item, QLayoutItem):
                    widget = QWidget()
                    widget.setLayout(item)
                    layout.addWidget(widget, i_row, i_col)
                elif isinstance(item, str):
                    layout.addWidget(QtHelper.make_label(item), i_row, i_col)
                else:
                    layout.addWidget(item, i_row, i_col)
        return layout


    @staticmethod
    def layout_widget_h(*items):
        widget = QWidget()
        widget.setLayout(QtHelper.layout_h(*items))
        return widget


    @staticmethod
    def layout_widget_v(*items):
        widget = QWidget()
        widget.setLayout(QtHelper.layout_v(*items))
        return widget


    @staticmethod
    def layout_widget_grid(widgets_rows_then_columns):
        widget = QWidget()
        widget.setLayout(QtHelper.layout_grid(*widgets_rows_then_columns))
        return widget
