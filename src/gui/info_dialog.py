from .info_dialog_ui import InfoDialogUi


class InfoDialog(InfoDialogUi):

    def __init__(self, parent):
        super().__init__(parent)
    

    def show_modal_dialog(self, text: str):
        self.ui_set_text(text)
        super().ui_show_modal()
