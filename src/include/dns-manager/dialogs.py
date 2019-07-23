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

class ConnectionDialog:
    def __init__(self):
        self.lp = LoadParm()
        self.creds = Credentials()
        self.creds.guess(self.lp)
        self.server = None
        self.conn = None

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
        if mtype and mtype in ['top', 'zones', 'zone', 'folder', 'object']:
            menus.append({'title': 'Action', 'id': 'action', 'type': 'Menu'})
        if mtype and mtype == 'top':
            menus.append({'title': 'Connect to DNS Server...', 'id': 'connect', 'type': 'MenuEntry', 'parent': 'action'})
        elif mtype and mtype == 'zones':
            menus.append({'title': 'New Zone...', 'id': 'new_zone', 'type': 'MenuEntry', 'parent': 'action'})
        elif mtype and mtype == 'zone':
            menus.append({'title': 'Reload', 'id': 'reload', 'type': 'MenuEntry', 'parent': 'action'})
        if mtype and mtype in ['zone', 'folder']:
            menus.append({'title': 'New Host (A or AAAA)...', 'id': 'new_host', 'type': 'MenuEntry', 'parent': 'action'})
            menus.append({'title': 'New Alias (CNAME)...', 'id': 'new_alias', 'type': 'MenuEntry', 'parent': 'action'})
            menus.append({'title': 'New Mail Exchanger (MX)...', 'id': 'new_mx', 'type': 'MenuEntry', 'parent': 'action'})
            menus.append({'title': 'New Domain...', 'id': 'new_domain', 'type': 'MenuEntry', 'parent': 'action'})
            menus.append({'title': 'New Delegation...', 'id': 'new_delegation', 'type': 'MenuEntry', 'parent': 'action'})
            menus.append({'title': 'Other New Records...', 'id': 'other_new_records', 'type': 'MenuEntry', 'parent': 'action'})
        if mtype and mtype in ['folder', 'object']:
            menus.append({'title': 'Delete', 'id': 'delete', 'type': 'MenuEntry', 'parent': 'action'})
        if mtype and mtype == 'object':
            menus.append({'title': 'Properties', 'id': 'properties', 'type': 'MenuEntry', 'parent': 'action'})
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
                UI.ReplaceWidget('dns_tree_repl', self.__dns_tree())
            elif ret == 'dns_tree':
                choice = UI.QueryWidget('dns_tree', 'Value')
                if choice not in ['dns_edit', 'server', 'forward', 'reverse']:
                    records = self.conn.records(choice)
                    if records:
                        UI.ReplaceWidget('rightPane', self.__rightpane(records, choice))
                    if choice in self.conn.forward_zones() or choice in self.conn.reverse_zones():
                        self.__setup_menus(mtype='zone')
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
                choice = UI.QueryWidget('items', 'Value')
                if choice == '(same as parent folder)':
                    choice = ''
                result = self.conn.records(top)
                record = result[choice] if result and choice in result else None
                if record and 'dwChildCount' in record and record['dwChildCount'] > 0:
                    if event['EventReason'] == 'Activated':
                        nchoice = '%s.%s' % (choice, top)
                        records = self.conn.records(nchoice)
                        self.__tree_select(nchoice)
                        UI.ReplaceWidget('rightPane', self.__rightpane(records, nchoice))
                        UI.SetFocus('items')
                    self.__setup_menus(mtype='folder')
                elif record:
                    if event['EventReason'] == 'Activated':
                        pass
                    else:
                        self.__setup_menus(mtype='object')
            UI.SetApplicationTitle('DNS Manager')
        return ret

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
            items = [Item(Id(zone), zone, '', '') for zone in self.conn.forward_zones()]
        elif zone_type == 'reverse':
            items = [Item(Id(zone), zone, '', '') for zone in self.conn.reverse_zones()]
        return Table(Id('items'), Opt('notify', 'immediate', 'notifyContextMenu'), Header('Name', 'Type', 'Status'), items)

    def __rightpane(self, records, parent):
        prepend = ''
        m = re.match('(\d+\.\d+\.\d+)\.in\-addr\.arpa', parent)
        if m:
            prepend = '.'.join(reversed(m.group(1).split('.'))) + '.'
        items = []
        for name in records.keys():
            if len(records[name]['records']) > 0:
                items.extend([Item('%s%s' % (prepend, name) if name else '(same as parent folder)', self.__dns_type_name(int(r['type'])), r['data'] if 'data' in r else '', '') for r in records[name]['records']])
            else:
                items.append(Item('%s%s' % (prepend, name) if name else '(same as parent folder)', '', '', ''))
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

