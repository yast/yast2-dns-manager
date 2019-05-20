from adcommon.strings import strcmp
from yast import import_module
import_module('Wizard')
import_module('UI')
from yast import *
from adcommon.ui import CreateMenu, DeleteButtonBox
from adcommon.creds import YCreds
from samba.credentials import Credentials
from samba.param import LoadParm
from samba.net import Net
from samba.dcerpc import nbt
from samba import NTSTATUSError
from complex import Connection

class ConnectionDialog:
    def __init__(self):
        self.lp = LoadParm()
        self.creds = Credentials()
        self.creds.guess(self.lp)
        self.server = None

    def __fetch_server(self, address):
        net = Net(Credentials())
        try:
            cldap_ret = net.finddc(address=address, flags=(nbt.NBT_SERVER_LDAP | nbt.NBT_SERVER_DS))
        except NTSTATUSError:
            return None
        return cldap_ret.pdc_dns_name if cldap_ret else None

    def __fetch_domain(self):
        net = Net(Credentials())
        cldap_ret = net.finddc(address=self.server, flags=(nbt.NBT_SERVER_LDAP | nbt.NBT_SERVER_DS))
        return cldap_ret.dns_domain if cldap_ret else None

    def __new(self):
        return MinSize(56, 8, HBox(HSpacing(3), VBox(
                VSpacing(1),
                Left(Label('The DNS server is running on:')),
                RadioButtonGroup(VBox(
                    Left(RadioButton(Id('this'), Opt('notify'), 'This computer', True)),
                    Left(RadioButton(Id('select'), Opt('notify'), 'The following computer:', False)),
                    Left(InputField(Id('selection'), Opt('hstretch', 'disabled'), '', ''))
                )),
                Bottom(Right(HBox(
                    PushButton(Id('ok'), 'OK'),
                    PushButton(Id('cancel'), 'Cancel'),
                ))),
                VSpacing(1),
            ), HSpacing(3)))

    def Show(self):
        UI.SetApplicationTitle('Connect to DNS Server')
        UI.OpenDialog(self.__new())
        while True:
            ret = UI.UserInput()
            if str(ret) == 'abort' or str(ret) == 'cancel':
                break
            elif ret == 'select':
                UI.ChangeWidget('selection', 'Enabled', True)
            elif ret == 'this':
                UI.ChangeWidget('selection', 'Enabled', False)
            elif ret == 'ok':
                if UI.QueryWidget('this', 'Value'):
                    self.server = self.__fetch_server('localhost')
                else:
                    self.server = self.__fetch_server(UI.QueryWidget('selection', 'Value'))
                if self.server:
                    self.lp.set('realm', self.__fetch_domain().upper())
                else:
                    continue
                ycred = YCreds(self.creds)
                ycred.Show()
                break
        UI.CloseDialog()
        return Connection(self.lp, self.creds, self.server)

class DNS:
    def __init__(self):
        self.__setup_menus(mtype='top')
        self.conn = None

    def __setup_menus(self, mtype=None):
        menus = [{'title': '&File', 'id': 'file', 'type': 'Menu'},
                 {'title': 'Exit', 'id': 'abort', 'type': 'MenuEntry', 'parent': 'file'}]
        if mtype and mtype == 'top':
            menus.append({'title': 'Action', 'id': 'action', 'type': 'Menu'})
            menus.append({'title': 'Connect to DNS Server...', 'id': 'connect', 'type': 'MenuEntry', 'parent': 'action'})
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
            elif ret == 'connect':
                self.conn = ConnectionDialog().Show()
            UI.SetApplicationTitle('DNS Manager')
        return ret

    def __dns_page(self):
        return HBox(
            HWeight(1, VBox(
                ReplacePoint(Id('dns_tree'), Empty()),
            )),
            HWeight(2, ReplacePoint(Id('rightPane'), Empty()))
        )

