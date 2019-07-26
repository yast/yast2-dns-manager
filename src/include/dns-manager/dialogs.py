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
import re
from samba.dcerpc import dnsp
from ipaddress import ip_address, IPv4Address, IPv6Address

class NewDialog:
    def __init__(self, obj_type, parent):
        self.obj = {}
        self.obj_type = obj_type
        self.parent = parent
        self.title = None
        if self.obj_type in ['cname', 'ptr']:
            self.title = 'Resource Record'
        self.dialog_seq = 0
        self.dialog = None

    def __new(self):
        pane = self.__fetch_pane()
        return MinSize(56, 22, HBox(HSpacing(3), VBox(
                VSpacing(1),
                ReplacePoint(Id('new_pane'), pane),
                VSpacing(1),
            ), HSpacing(3)))

    def __fetch_pane(self):
        if not self.dialog:
            if strcmp(self.obj_type, 'host'):
                self.dialog = self.__host_dialog()
            elif strcmp(self.obj_type, 'cname'):
                self.dialog = self.__cname_dialog()
            elif strcmp(self.obj_type, 'ptr'):
                self.dialog = self.__ptr_dialog()
            else:
                self.dialog = self.__other_dialog()
        return self.dialog[self.dialog_seq][0]

    def __other_dialog(self):
        return [
            [VBox(
                Bottom(Right(HBox(
                    PushButton(Id('finish'), 'Add %s' % self.obj_type.capitalize()),
                    PushButton(Id('cancel'), 'Cancel')
                ))),
            ),
            [], # known keys
            [], # required keys
            None, # dialog hook
            ],
        ]

    def __ptr_dialog(self):
        def fqdn_hook():
            name = UI.QueryWidget('name', 'Value')
            if re.match('[\d+\.]+in\-addr\.arpa', self.parent):
                UI.ChangeWidget('fqdn', 'Value', '%s.%s' % ('.'.join(reversed(name.split('.'))), self.parent))
            elif re.match('[\w+\.]+ip6\.arpa', self.parent):
                UI.ChangeWidget('fqdn', 'Value', '%s.%s' % ('.'.join(reversed(''.join(name.split(':')))), self.parent))
        name = ''
        m = re.match('([\d+\.]+)(in\-addr)\.arpa', self.parent)
        if not m:
            m = re.match('([\w+\.]+)(ip6)\.arpa', self.parent)
        if m:
            if m.group(2) == 'in-addr':
                name = '%s.' % '.'.join(reversed(m.group(1)[:-1].split('.')))
            else: # ip6
                rev = ''.join(reversed(m.group(1)[:-1].split('.')))
                name = '%s:' % ':'.join([rev[x-4:x] for x in range(4, len(rev)+4, 4)])
        return [
            [VBox(
                Left(Label(Id('name_label'), 'Host IP Address:')),
                HBox(
                    HWeight(1, Left(TextEntry(Opt('disabled'), '', name))),
                    HWeight(2, Left(TextEntry(Id('name'), Opt('notify', 'immediate'), ''))),
                ),
                Left(Label('Fully qualified domain name (FQDN):')),
                Left(TextEntry(Id('fqdn'), Opt('disabled'), '', self.parent)),
                Left(Label(Id('data_label'), 'Host name:')),
                Left(TextEntry(Id('data'), '')),
                Left(CheckBox(Id('allow_update'), Opt('disabled'), 'Allow any authenticated user to update all DNS records with the same\nname. This setting applies only to DNS records for a new name.')),
                Bottom(Right(HBox(
                    PushButton(Id('finish'), 'OK'),
                    PushButton(Id('cancel'), 'Cancel')
                ))),
            ),
            ['name', 'data', 'allow_update'], # known keys
            ['name', 'data'], # required keys
            fqdn_hook, # dialog hook
            ],
        ]

    def __cname_dialog(self):
        return [
            [VBox(
                Left(Label(Id('name_label'), 'Alias name (uses parent domain if left blank):')),
                Left(TextEntry(Id('name'), '')),
                Left(Label('Fully qualified domain name (FQDN):')),
                Left(TextEntry(Id('fqdn'), Opt('disabled'), '', self.parent)),
                Left(Label(Id('data_label'), 'Fully qualified domain name (FQDN) for target host:')),
                Left(TextEntry(Id('data'), '')),
                Left(CheckBox(Id('allow_update'), Opt('disabled'), 'Allow any authenticated user to update all DNS records with the same\nname. This setting applies only to DNS records for a new name.')),
                Bottom(Right(HBox(
                    PushButton(Id('finish'), 'OK'),
                    PushButton(Id('cancel'), 'Cancel')
                ))),
            ),
            ['name', 'data', 'allow_update'], # known keys
            ['name', 'data'], # required keys
            None, # dialog hook
            ],
        ]

    def __host_dialog(self):
        return [
            [VBox(
                Left(Label(Id('name_label'), 'Name (uses parent domain name if blank):')),
                Left(TextEntry(Id('name'), '')),
                Left(Label('Fully qualified domain name (FQDN):')),
                Left(TextEntry(Id('fqdn'), Opt('disabled'), '', self.parent)),
                Left(Label(Id('data_label'), 'IP address:')),
                Left(TextEntry(Id('data'), '')),
                Left(CheckBox(Id('create_ptr'), 'Create associated pointer (PTR) record')),
                Left(CheckBox(Id('allow_update'), Opt('disabled'), 'Allow any authenticated user to update DNS records with the\nsame owner name')),
                Bottom(Right(HBox(
                    PushButton(Id('finish'), 'Add %s' % self.obj_type.capitalize()),
                    PushButton(Id('cancel'), 'Cancel')
                ))),
            ),
            ['name', 'data', 'create_ptr', 'allow_update'], # known keys
            ['name', 'data'], # required keys
            None, # dialog hook
            ],
        ]

    def __warn_label(self, key):
        label = UI.QueryWidget('%s_label' % key, 'Value')
        if not label:
            label = UI.QueryWidget(key, 'Label')
        if label[-2:] != ' *':
            if not UI.ChangeWidget('%s_label' % key, 'Value', '%s *' % label):
                UI.ChangeWidget(key, 'Label', '%s *' % label)

    def __fetch_values(self, back=False):
        ret = True
        known_value_keys = self.dialog[self.dialog_seq][1]
        for key in known_value_keys:
            value = UI.QueryWidget(key, 'Value')
            if value or type(value) == bool:
                self.obj[key] = value
        required_value_keys = self.dialog[self.dialog_seq][2]
        for key in required_value_keys:
            if not key in self.obj or not self.obj[key]:
                self.__warn_label(key)
                ycpbuiltins.y2error('Missing value for %s' % key)
                ret = False
        return ret

    def __set_values(self):
        for key in self.obj:
            UI.ChangeWidget(key, 'Value', self.obj[key])

    def __dialog_hook(self):
        hook = self.dialog[self.dialog_seq][3]
        if hook:
            hook()

    def Show(self):
        UI.SetApplicationTitle('New %s' % (self.title if self.title else self.obj_type.title()))
        UI.OpenDialog(self.__new())
        while True:
            self.__dialog_hook()
            ret = UI.UserInput()
            if str(ret) == 'abort' or str(ret) == 'cancel':
                ret = None
                break
            elif str(ret) == 'next':
                if self.__fetch_values():
                    self.dialog_seq += 1
                    UI.ReplaceWidget('new_pane', self.__fetch_pane())
                    self.__set_values()
            elif str(ret) == 'back':
                self.__fetch_values(True)
                self.dialog_seq -= 1;
                UI.ReplaceWidget('new_pane', self.__fetch_pane())
                self.__set_values()
            elif str(ret) == 'finish':
                if self.__fetch_values():
                    ret = self.obj
                    break
        UI.CloseDialog()
        return ret

class PropertiesDialog:
    def __init__(self, obj_type, name, data):
        self.obj_type = obj_type
        self.name = name
        self.data = self.__fetch_record(data)
        self.dialog_seq = 0
        self.dialog = None

    def __fetch_record(self, data):
        for record in data['records']:
            if self.obj_type == record['type']:
                return record

    def __new(self):
        pane = self.__fetch_pane()
        return MinSize(56, 22, HBox(HSpacing(3), VBox(
                VSpacing(1),
                ReplacePoint(Id('new_pane'), pane),
                VSpacing(1),
            ), HSpacing(3)))

    def __fetch_pane(self):
        if not self.dialog:
            if self.obj_type == dnsp.DNS_TYPE_SRV:
                self.dialog = self.__srv_dialog()
            else:
                self.dialog = self.__other_dialog()
        return self.dialog[self.dialog_seq][0]

    def __other_dialog(self):
        name_keys = {k: ' '.join(re.split('([A-Z][a-z]*)', k)).strip().capitalize() for k in self.data.keys() if k not in ['flags', 'type']}
        items = []
        for k in name_keys.keys():
            if type(self.data[k]) == int:
                items.append(Left(IntField(Id(k), Opt('hstretch'), name_keys[k], 0, 99999, self.data[k])))
            else:
                items.append(Left(TextEntry(Id(k), Opt('hstretch'), name_keys[k], self.data[k])))
        return [
            [VBox(
                *items,
                Bottom(Right(HBox(
                    PushButton(Id('finish'), 'OK'),
                    PushButton(Id('cancel'), 'Cancel'),
                ))),
            ),
            list(name_keys.keys()), # known keys
            list(name_keys.keys()), # required keys
            None, # dialog hook
            ],
        ]

    def __srv_dialog(self):
        return [
            [VBox(
                HBox(
                    HWeight(1, VBox(
                        Left(Label('Domain:')),
                        Left(Label('Service:')),
                        Left(Label('Protocol:')),
                        Left(Label(Id('priority_label'), 'Priority:')),
                        Left(Label(Id('weight_label'), 'Weight:')),
                        Left(Label(Id('port_label'), 'Port number:')),
                    )),
                    HWeight(3, VBox(
                        Left(TextEntry(Opt('disabled', 'hstretch'), '', '.'.join(self.name.split('.')[1:]))),
                        Left(ComboBox(Opt('disabled', 'hstretch'), '', [self.name.split('.')[0]])),
                        Left(ComboBox(Opt('disabled', 'hstretch'), '', [])),
                        Left(IntField(Id('priority'), Opt('hstretch'), '', 0, 99999, self.data['priority'])),
                        Left(IntField(Id('weight'), Opt('hstretch'), '', 0, 99999, self.data['weight'])),
                        Left(IntField(Id('port'), Opt('hstretch'), '', 1, 65535, self.data['port'])),
                    )),
                ),
                Left(Label(Id('nameTarget_label'), 'Host offering this service:')),
                Left(TextEntry(Id('nameTarget'), Opt('hstretch'), '', self.data['nameTarget'])),
                Bottom(Right(HBox(
                    PushButton(Id('finish'), 'OK'),
                    PushButton(Id('cancel'), 'Cancel'),
                ))),
            ),
            ['nameTarget', 'priority', 'weight', 'port'], # known keys
            ['nameTarget', 'priority', 'weight', 'port'], # required keys
            None, # dialog hook
            ],
        ]

    def __warn_label(self, key):
        label = UI.QueryWidget('%s_label' % key, 'Value')
        if not label:
            label = UI.QueryWidget(key, 'Label')
        if label[-2:] != ' *':
            if not UI.ChangeWidget('%s_label' % key, 'Value', '%s *' % label):
                UI.ChangeWidget(key, 'Label', '%s *' % label)

    def __fetch_values(self, back=False):
        ret = True
        known_value_keys = self.dialog[self.dialog_seq][1]
        for key in known_value_keys:
            value = UI.QueryWidget(key, 'Value')
            if value or type(value) == bool:
                self.obj[key] = value
        required_value_keys = self.dialog[self.dialog_seq][2]
        for key in required_value_keys:
            if not key in self.obj or not self.obj[key]:
                self.__warn_label(key)
                ycpbuiltins.y2error('Missing value for %s' % key)
                ret = False
        return ret

    def __set_values(self):
        for key in self.obj:
            UI.ChangeWidget(key, 'Value', self.obj[key])

    def __dialog_hook(self):
        hook = self.dialog[self.dialog_seq][3]
        if hook:
            hook()

    def Show(self):
        UI.SetApplicationTitle('%s Properties' % self.name.split('.')[0])
        UI.OpenDialog(self.__new())
        while True:
            self.__dialog_hook()
            ret = UI.UserInput()
            if str(ret) == 'abort' or str(ret) == 'cancel':
                ret = None
                break
            elif str(ret) == 'next':
                if self.__fetch_values():
                    self.dialog_seq += 1
                    UI.ReplaceWidget('new_pane', self.__fetch_pane())
                    self.__set_values()
            elif str(ret) == 'back':
                self.__fetch_values(True)
                self.dialog_seq -= 1;
                UI.ReplaceWidget('new_pane', self.__fetch_pane())
                self.__set_values()
            elif str(ret) == 'finish':
                if self.__fetch_values():
                    ret = self.obj
                    break
        UI.CloseDialog()
        return ret

class ConnectionDialog:
    def __init__(self):
        self.lp = LoadParm()
        self.creds = Credentials()
        self.creds.guess(self.lp)
        self.server = None
        self.conn = None
        self.cldap_ret = None

    def __cldap(self, address):
        if not self.cldap_ret:
            net = Net(Credentials())
            try:
                self.cldap_ret = net.finddc(address=address, flags=(nbt.NBT_SERVER_LDAP | nbt.NBT_SERVER_DS))
            except NTSTATUSError:
                pass

    def __fetch_server(self, address):
        self.__cldap(address)
        return self.cldap_ret.pdc_dns_name if self.cldap_ret else None

    def __fetch_domain(self):
        self.__cldap(self.server)
        return self.cldap_ret.dns_domain if self.cldap_ret else None

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
                UI.SetFocus('selection')
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
                ycred = YCreds(self.creds, auto_krb5_creds=False)
                def cred_valid():
                    try:
                        self.conn = Connection(self.lp, self.creds, self.server)
                        return True
                    except Exception as e:
                        ycpbuiltins.y2error(str(e))
                    return False
                ycred.Show(cred_valid)
                if self.conn:
                    break
        UI.CloseDialog()
        return self.conn

class DNS:
    def __init__(self):
        self.__setup_menus(mtype='top')
        self.conn = None

    def __setup_menus(self, mtype=None):
        menus = [{'title': '&File', 'id': 'file', 'type': 'Menu'},
                 {'title': 'Exit', 'id': 'abort', 'type': 'MenuEntry', 'parent': 'file'}]
        if mtype and mtype in ['top', 'zones', 'fzone', 'rzone', 'folder', 'object']:
            menus.append({'title': 'Action', 'id': 'action', 'type': 'Menu'})
        if mtype and mtype == 'top':
            menus.append({'title': 'Connect to DNS Server...', 'id': 'connect', 'type': 'MenuEntry', 'parent': 'action'})
        elif mtype and mtype == 'zones':
            menus.append({'title': 'New Zone...', 'id': 'new_zone', 'type': 'MenuEntry', 'parent': 'action'})
        elif mtype and mtype in ['fzone', 'rzone']:
            menus.append({'title': 'Reload', 'id': 'reload', 'type': 'MenuEntry', 'parent': 'action'})
        if mtype and mtype in ['fzone', 'folder']:
            menus.append({'title': 'New Host (A or AAAA)...', 'id': 'new_host', 'type': 'MenuEntry', 'parent': 'action'})
            menus.append({'title': 'New Alias (CNAME)...', 'id': 'new_alias', 'type': 'MenuEntry', 'parent': 'action'})
            menus.append({'title': 'New Mail Exchanger (MX)...', 'id': 'new_mx', 'type': 'MenuEntry', 'parent': 'action'})
            menus.append({'title': 'New Domain...', 'id': 'new_domain', 'type': 'MenuEntry', 'parent': 'action'})
        if mtype and mtype in ['rzone']:
            menus.append({'title': 'New Pointer (PTR)...', 'id': 'new_pointer', 'type': 'MenuEntry', 'parent': 'action'})
            menus.append({'title': 'New Alias (CNAME)...', 'id': 'new_alias', 'type': 'MenuEntry', 'parent': 'action'})
        if mtype and mtype in ['fzone', 'rzone', 'folder']:
            menus.append({'title': 'New Delegation...', 'id': 'new_delegation', 'type': 'MenuEntry', 'parent': 'action'})
            menus.append({'title': 'Other New Records...', 'id': 'other_new_records', 'type': 'MenuEntry', 'parent': 'action'})
        if mtype and mtype == 'object':
            menus.append({'title': 'Delete', 'id': 'delete', 'type': 'MenuEntry', 'parent': 'action'})
            menus.append({'title': 'Properties', 'id': 'properties', 'type': 'MenuEntry', 'parent': 'action'})
        CreateMenu(menus)

    def Show(self):
        UI.SetApplicationTitle('DNS Manager')
        Wizard.SetContentsButtons('', self.__dns_page(), '', '', '')
        DeleteButtonBox()
        UI.SetFocus('dns_tree')
        current_selection = None
        current_parent = None
        current_dns_type = None
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
                UI.ReplaceWidget('dns_tree_repl', self.__dns_tree())
            elif ret == 'dns_tree':
                choice = UI.QueryWidget('dns_tree', 'Value')
                current_selection = choice
                current_parent = choice
                if choice not in ['dns_edit', 'server', 'forward', 'reverse']:
                    records = self.conn.records(choice)
                    if records:
                        UI.ReplaceWidget('rightPane', self.__rightpane(records, choice))
                    if choice in self.conn.forward_zones():
                        self.__setup_menus(mtype='fzone')
                    if choice in self.conn.reverse_zones():
                        self.__setup_menus(mtype='rzone')
                    else:
                        self.__setup_menus(mtype='folder')
                elif choice in ['forward', 'reverse']:
                    UI.ReplaceWidget('rightPane', self.__rightpane_zones(choice))
                    self.__setup_menus(mtype='zones')
                elif choice == 'dns_edit':
                    UI.ReplaceWidget('rightPane', Empty())
                    self.__setup_menus(mtype='top')
                else:
                    UI.ReplaceWidget('rightPane', Empty())
                    self.__setup_menus()
            elif ret == 'items':
                top = UI.QueryWidget('dns_tree', 'Value')
                choice, dns_type = UI.QueryWidget('items', 'Value').split(':')
                result = self.conn.records(top)
                record = result[choice] if result and choice in result else None
                nchoice = '%s.%s' % (choice, top)
                current_selection = nchoice
                current_dns_type = dns_type
                if record and 'dwChildCount' in record and record['dwChildCount'] > 0:
                    current_parent = nchoice
                    if event['EventReason'] == 'Activated':
                        self.__refresh(nchoice)
                    self.__setup_menus(mtype='folder')
                elif record:
                    if event['EventReason'] == 'Activated':
                        PropertiesDialog(int(dns_type), nchoice, record).Show()
                    self.__setup_menus(mtype='object')
            elif ret == 'properties':
                top = UI.QueryWidget('dns_tree', 'Value')
                record = self.conn.records(current_selection)['']
                if record:
                    PropertiesDialog(int(current_dns_type), current_selection, record).Show()
            elif ret == 'new_host':
                host = NewDialog('host', current_parent).Show()
                if host:
                    msg2 = None
                    try:
                        ipvers = ip_address(host['data'])
                        if type(ipvers) == IPv4Address:
                            msg = self.conn.add_record(current_parent, host['name'], 'A', host['data'])
                            self.__refresh(item=host['name'], dns_type=dnsp.DNS_TYPE_A)
                            if host['create_ptr']:
                                rev = '%s.in-addr.arpa' % '.'.join(list(reversed(host['data'].split('.'))))
                                parent = self.conn.match_zone(rev)
                                if not parent:
                                    msg2 = 'Zone does not exist; record could not be added.'
                                else:
                                    name = '%s.%s' % (host['name'], current_parent)
                                    data = rev.split(parent)[0][:-1]
                                    msg2 = self.conn.add_record(parent, data, 'PTR', name)
                        elif type(ipvers) == IPv6Address:
                            msg = self.conn.add_record(current_parent, host['name'], 'AAAA', host['data'])
                            self.__refresh(item=host['name'], dns_type=dnsp.DNS_TYPE_AAAA)
                            if host['create_ptr']:
                                rev = '%s.ip6.arpa' % '.'.join(list(reversed(list(host['data'].replace(':', '')))))
                                parent = self.conn.match_zone(rev)
                                if not parent:
                                    msg2 = 'Zone does not exist; record could not be added.'
                                else:
                                    name = '%s.%s' % (host['name'], current_parent)
                                    data = rev.split(parent)[0][:-1]
                                    msg2 = self.conn.add_record(parent, data, 'PTR', name)
                    except ValueError as e:
                        msg = str(e)
                    if msg2 and msg2 != 'Record added successfully':
                        self.__message('Warning: The associated pointer (PTR) record cannot be created: %s' % msg2, warn=True, buttons=['ok'])
                    self.__message(msg, buttons=['ok'])
            elif ret == 'new_alias':
                cname = NewDialog('cname', current_parent).Show()
                if cname:
                    msg = self.conn.add_record(current_parent, cname['name'], 'CNAME', cname['data'])
                    self.__refresh(item=cname['name'], dns_type=dnsp.DNS_TYPE_CNAME)
                    self.__message(msg, buttons=['ok'])
            elif ret == 'new_pointer':
                ptr = NewDialog('ptr', current_parent).Show()
                if ptr:
                    msg = self.conn.add_record(current_parent, ptr['name'], 'PTR', ptr['data'])
                    self.__refresh(item=ptr['name'], dns_type=dnsp.DNS_TYPE_PTR)
                    self.__message(msg, buttons=['ok'])
            elif ret == 'delete':
                top = UI.QueryWidget('dns_tree', 'Value')
                choice, dns_type = UI.QueryWidget('items', 'Value').split(':')
                result = self.conn.records(top)
                record = result[choice] if result and choice in result else None
                nchoice = '%s.%s' % (choice, top) if choice else top
                ycpbuiltins.y2error(str(record))
                data = None
                for rec in record['records']:
                    if rec['type'] == int(dns_type):
                        data = rec['data']
                        break
                if data and self.__message('Do you want to delete the record %s from the server?' % (choice if choice else nchoice), title='DNS', warn=True):
                    type_name = self.__dns_type_name(int(dns_type))
                    m = re.match('[\w\s]*\s*\((\w+)\)', type_name)
                    if m:
                        dns_type = m.group(1)
                    else:
                        dns_type = type_name
                    msg = self.conn.delete_record(nchoice, dns_type, data)
                    self.__message(msg, buttons=['ok'])
                    self.__refresh()
            UI.SetApplicationTitle('DNS Manager')
        return Symbol(ret)

    def __refresh(self, top=None, item=None, dns_type=None):
        if not top:
            top = UI.QueryWidget('dns_tree', 'Value')
        records = self.conn.records(top)
        self.__tree_select(top)
        UI.ReplaceWidget('rightPane', self.__rightpane(records, top))
        UI.SetFocus('items')
        if item and dns_type:
            UI.ChangeWidget('items', 'CurrentItem', Symbol('%s:%d' % (item, dns_type)))

    def __message(self, msg, title=None, warn=False, buttons=['yes', 'no']):
        ans = False
        if title:
            UI.SetApplicationTitle(title)
        opts = tuple(['warncolor']) if warn else tuple()
        btns = tuple([PushButton(Id(btn), btn.capitalize()) for btn in buttons])
        UI.OpenDialog(Opt(*opts), HBox(HSpacing(1), VBox(
            VSpacing(.3),
            Label(msg),
            Right(HBox(*btns)),
            VSpacing(.3),
        ), HSpacing(1)))
        ret = UI.UserInput()
        if str(ret) == 'yes':
            ans = True
        elif str(ret) == 'no' or str(ret) == 'abort' or str(ret) == 'cancel':
            ans = False
        else:
            ans = None
        UI.CloseDialog()
        return ans

    def __tree_select(self, choice):
        UI.ReplaceWidget('dns_tree_repl', self.__dns_tree(choice))
        UI.ChangeWidget('dns_tree', 'CurrentItem', Symbol(choice))

    def __dns_type_name(self, dns_type):
        if dns_type == dnsp.DNS_TYPE_TOMBSTONE:
            return '(TOMBSTONE)'
        elif dns_type == dnsp.DNS_TYPE_A:
            return 'Host (A)'
        elif dns_type == dnsp.DNS_TYPE_NS:
            return 'Name Server (NS)'
        elif dns_type == dnsp.DNS_TYPE_MD:
            return '(MD)'
        elif dns_type == dnsp.DNS_TYPE_MF:
            return '(MF)'
        elif dns_type == dnsp.DNS_TYPE_CNAME:
            return 'Alias (CNAME)'
        elif dns_type == dnsp.DNS_TYPE_SOA:
            return 'Start of Authority (SOA)'
        elif dns_type == dnsp.DNS_TYPE_MB:
            return 'Mailbox (MB)'
        elif dns_type == dnsp.DNS_TYPE_MG:
            return 'Mail Group (MG)'
        elif dns_type == dnsp.DNS_TYPE_MR:
            return 'Renamed Mailbox (MR)'
        elif dns_type == dnsp.DNS_TYPE_NULL:
            return '(NULL)'
        elif dns_type == dnsp.DNS_TYPE_WKS:
            return 'Well Known Services (WKS)'
        elif dns_type == dnsp.DNS_TYPE_PTR:
            return 'Pointer (PTR)'
        elif dns_type == dnsp.DNS_TYPE_HINFO:
            return 'Host Information (HINFO)'
        elif dns_type == dnsp.DNS_TYPE_MINFO:
            return 'Mailbox Information (MINFO)'
        elif dns_type == dnsp.DNS_TYPE_MX:
            return 'Mail Exchanger (MX)'
        elif dns_type == dnsp.DNS_TYPE_TXT:
            return 'Text (TXT)'
        elif dns_type == dnsp.DNS_TYPE_RP:
            return 'Responsible Person (RP)'
        elif dns_type == dnsp.DNS_TYPE_AFSDB:
            return 'AFS Database (AFSDB)'
        elif dns_type == dnsp.DNS_TYPE_X25:
            return 'X.25'
        elif dns_type == dnsp.DNS_TYPE_ISDN:
            return 'ISDN'
        elif dns_type == dnsp.DNS_TYPE_RT:
            return 'Route Through (RT)'
        elif dns_type == dnsp.DNS_TYPE_SIG:
            return 'Signature (SIG)'
        elif dns_type == dnsp.DNS_TYPE_KEY:
            return 'Public Key (KEY)'
        elif dns_type == dnsp.DNS_TYPE_AAAA:
            return 'IPv6 Host (AAAA)'
        elif dns_type == dnsp.DNS_TYPE_LOC:
            return '(LOC)'
        elif dns_type == dnsp.DNS_TYPE_NXT:
            return 'Next Domain (NXT)'
        elif dns_type == dnsp.DNS_TYPE_SRV:
            return 'Service Location (SRV)'
        elif dns_type == dnsp.DNS_TYPE_ATMA:
            return 'ATM Address (ATMA)'
        elif dns_type == dnsp.DNS_TYPE_NAPTR:
            return '(NAPTR)'
        elif dns_type == dnsp.DNS_TYPE_DNAME:
            return '(DNAME)'
        elif dns_type == dnsp.DNS_TYPE_DS:
            return '(DS)'
        elif dns_type == dnsp.DNS_TYPE_RRSIG:
            return '(RRSIG)'
        elif dns_type == dnsp.DNS_TYPE_NSEC:
            return '(NSEC)'
        elif dns_type == dnsp.DNS_TYPE_DNSKEY:
            return '(DNSKEY)'
        elif dns_type == dnsp.DNS_TYPE_DHCID:
            return '(DHCID)'
        elif dns_type == dnsp.DNS_TYPE_ALL:
            return '(ALL)'
        elif dns_type == dnsp.DNS_TYPE_WINS:
            return '(WINS)'
        elif dns_type == dnsp.DNS_TYPE_WINSR:
            return '(WINSR)'
        else:
            return 'Unknown'

    def __rightpane_zones(self, zone_type):
        if zone_type == 'forward':
            items = [Item(Id('%s:' % zone), zone, '', '') for zone in self.conn.forward_zones()]
        elif zone_type == 'reverse':
            items = [Item(Id('%s:' % zone), zone, '', '') for zone in self.conn.reverse_zones()]
        return Table(Id('items'), Opt('notify', 'immediate', 'notifyContextMenu'), Header('Name', 'Type', 'Status'), items)

    def __rightpane(self, records, parent):
        prepend = ''
        m = re.match('([\d+\.]+)(in\-addr)\.arpa', parent)
        if not m:
            m = re.match('([\w+\.]+)(ip6)\.arpa', parent)
        if m:
            if m.group(2) == 'in-addr':
                prepend = '.'.join(reversed(m.group(1)[:-1].split('.'))) + '.'
            else: # ipv6
                rev = ''.join(reversed(m.group(1)[:-1].split('.')))
                prepend = ':'.join([rev[x-4:x] for x in range(4, len(rev)+4, 4)]) + ':'
        items = []
        for name in records.keys():
            if len(records[name]['records']) > 0:
                items.extend([Item(Id('%s:%d' % (name, r['type'])), '%s%s' % (prepend if r['type'] == dnsp.DNS_TYPE_PTR else '', name) if name else '(same as parent folder)', self.__dns_type_name(r['type']), r['data'] if 'data' in r else '', '') for r in records[name]['records']])
            elif name:
                items.append(Item(Id('%s:' % name), '%s' % name, '', '', ''))
        return Table(Id('items'), Opt('notify', 'immediate', 'notifyContextMenu'), Header('Name', 'Type', 'Data', 'Timestamp'), items)

    def __tree_children(self, records, parent, expand=None):
        children = []
        if records:
            for child in records.keys():
                if records[child]['dwChildCount'] > 0:
                    cid = '%s.%s' % (child, parent)
                    children.append(Item(Id(cid), child, cid == expand[-len(cid):] if expand else False, self.__tree_children(records[child]['children'], cid, expand)))
        return children

    def __dns_tree(self, expand=None):
        if self.conn:
            forward_zones = self.conn.forward_zones()
            reverse_zones = self.conn.reverse_zones()
            expand_forward = len([z for z in forward_zones if expand[-len(z):] == z]) > 0 if expand else False
            expand_reverse = len([z for z in reverse_zones if expand[-len(z):] == z]) > 0 if expand else False
            forward_items = [Item(Id(zone), zone, zone == expand[-len(zone):] if expand else False, self.__tree_children(self.conn.records(zone), zone, expand)) for zone in forward_zones]
            reverse_items = [Item(Id(zone), zone, zone == expand[-len(zone):] if expand else False, self.__tree_children(self.conn.records(zone), zone, expand)) for zone in reverse_zones]
            tree = [Item(Id('server'), self.conn.server, True, [
                        Item(Id('forward'), 'Forward Lookup Zones', expand_forward, forward_items),
                        Item(Id('reverse'), 'Reverse Lookup Zones', expand_reverse, reverse_items)
                        ])
                    ]
        else:
            tree = []
        return Tree(Id('dns_tree'), Opt('notify', 'immediate', 'notifyContextMenu'), '', [
            Item(Id('dns_edit'), 'DNS', True, tree)
        ])

    def __dns_page(self):
        return HBox(
            HWeight(1, VBox(
                ReplacePoint(Id('dns_tree_repl'), self.__dns_tree()),
            )),
            HWeight(2, ReplacePoint(Id('rightPane'), Empty()))
        )

