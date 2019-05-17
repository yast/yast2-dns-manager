from adcommon.strings import strcmp
from yast import import_module
import_module('Wizard')
import_module('UI')
from yast import *
from adcommon.ui import CreateMenu, DeleteButtonBox

class DNS:
    def __init__(self):
        self.__setup_menus()

    def __setup_menus(self):
        menus = [{'title': '&File', 'id': 'file', 'type': 'Menu'},
                 {'title': 'Exit', 'id': 'abort', 'type': 'MenuEntry', 'parent': 'file'}]
        CreateMenu(menus)

    def Show(self):
        UI.SetApplicationTitle('DNS Manager')
        Wizard.SetContentsButtons('', self.__dns_page(), '', '', '')
        DeleteButtonBox()
        UI.SetFocus('dns_tree')
        while True:
            event = UI.WaitForEvent()
            if 'WidgetID' in event:
                ret = event['WidgetID']
            elif 'ID' in event:
                ret = event['ID']
            else:
                raise Exception('ID not found in response %s' % str(event))
            if ret == 'abort' or ret == 'cancel':
                break
            UI.SetApplicationTitle('DNS Manager')
        return ret

    def __dns_page(self):
        return HBox(
            HWeight(1, VBox(
                ReplacePoint(Id('dns_tree'), Empty()),
            )),
            HWeight(2, ReplacePoint(Id('rightPane'), Empty()))
        )

