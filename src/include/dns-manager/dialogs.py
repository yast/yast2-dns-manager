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
from ipaddress import ip_address, IPv4Address, IPv6Address, ip_network
from socket import getaddrinfo, gaierror
from complex import dns_type_flag, dns_type_name, format_data

class NameServer:
    def __init__(self, name='', ips=[]):
        self.name = name
        self.ips = ips

    def __new(self):
        items = [Item(ip) for ip in self.ips]
        return MinSize(56, 22, HBox(HSpacing(3), VBox(
                VSpacing(1),
                Left(Label('Enter a server name and one or more IP addresses. Both are required to identify the name server.')),
                Left(Label('Server fully qualified domain name (FQDN):')),
                HBox(
                    HWeight(5, VBox(
                        Left(TextEntry(Id('hostname'), '', self.name)),
                    )),
                    HWeight(1, VBox(
                        Right(PushButton(Id('resolve'), 'Resolve')),
                    )),
                ),
                Left(Label('IP Addresses of this NS record:')),
                HBox(
                    HWeight(5, VBox(
                        Table(Id('ips'), Header('IP Address'), items),
                    )),
                    HWeight(1, VBox(
                        Right(PushButton(Id('delete'), 'Delete')),
                    )),
                ),
                Bottom(Right(HBox(
                    Right(PushButton(Id('ok'), 'OK')),
                    Right(PushButton(Id('cancel'), 'Cancel')),
                ))),
                VSpacing(1),
            ), HSpacing(3)))

    def Show(self):
        UI.SetApplicationTitle('New Name Server Record')
        UI.OpenDialog(self.__new())
        result = None
        while True:
            ret = UI.UserInput()
            if ret == 'abort' or ret == 'cancel':
                result = None
                break
            elif ret == 'resolve':
                self.name = UI.QueryWidget('hostname', 'Value')
                try:
                    resp = getaddrinfo(self.name, None)
                except gaierror as e:
                    resp = None
                if resp:
                    self.ips = list(set([r[-1][0] for r in resp]))
                    UI.ChangeWidget('ips', 'Items', [Item(ip) for ip in self.ips])
                    result = (self.name, self.ips)
            elif ret == 'delete':
                selection = UI.QueryWidget('ips', 'CurrentItem')
                self.ips = [ip for ip in self.ips if ip != selection]
                UI.ChangeWidget('ips', 'Items', [Item(ip) for ip in self.ips])
                result = (self.name, self.ips)
            elif ret == 'ok':
                break
        UI.CloseDialog()
        return result

class ObjDialog:
    def __init__(self, obj_type, parent, name=None, record=None):
        self.obj_type = obj_type.lower()
        if record and name is not None:
            self.update = True
            self.obj = self.__fetch_record(record)
            self.obj['name'] = name
        else:
            self.update = False
            self.obj = {}
        self.parent = parent
        self.title = None
        self.subtitle = None
        self.space = (3, 1)
        if self.obj_type in ['a', 'aaaa']:
            self.subtitle = dns_type_name(dns_type_flag(self.obj_type))
            self.obj_type = 'host'
        if self.obj_type == 'ns' and self.update:
            self.subtitle = 'Name Servers'
        if self.obj_type == 'soa':
            self.subtitle = dns_type_name(dns_type_flag(self.obj_type))
        if self.obj_type == 'host':
            self.title = 'Host'
        if self.obj_type in ['cname', 'ptr', 'mx', 'srv', 'txt']:
            self.title = 'Resource Record'
            self.subtitle = dns_type_name(dns_type_flag(self.obj_type))
            self.obj['type'] = dns_type_flag(obj_type)
        if self.obj_type == 'ns':
            self.title = 'Delegation Wizard'
        if self.obj_type == 'zone':
            self.title = 'Zone Wizard'
        if self.obj_type == 'other':
            self.title = 'Resource Record Type'
        self.dialog_seq = 0
        self.dialog = None

    def __fetch_record(self, data):
        obj_type = dns_type_flag(self.obj_type)
        if obj_type == dnsp.DNS_TYPE_NS:
            ret = {'data' : []}
            for record in data['records']:
                if obj_type == record['type']:
                    ips = []
                    try:
                        resp = getaddrinfo(record['data'], None)
                    except gaierror as e:
                        resp = None
                    if resp:
                        ips = list(set([r[-1][0] for r in resp]))
                    ret['data'].append((record['data'], ips))
            return ret
        for record in data['records']:
            if obj_type == record['type']:
                return record

    def __subtitle(self, dialog):
        if self.subtitle:
            return DumbTab([self.subtitle], HBox(HSpacing(3), VBox(
                VSpacing(1),
                dialog,
                VSpacing(1),
            ), HSpacing(3)))
        else:
            return dialog

    def __new(self):
        if self.subtitle:
            self.space = (0, 0)
        pane = self.__fetch_pane()
        return MinSize(56, 22, HBox(HSpacing(self.space[0]), VBox(
                VSpacing(self.space[1]),
                self.__subtitle(ReplacePoint(Id('new_pane'), pane)),
                VSpacing(self.space[1]),
            ), HSpacing(self.space[0])))

    def __fetch_pane(self):
        if not self.dialog:
            if strcmp(self.obj_type, 'host'):
                self.dialog = self.__host_dialog()
            elif strcmp(self.obj_type, 'cname'):
                self.dialog = self.__cname_dialog()
            elif strcmp(self.obj_type, 'ptr'):
                self.dialog = self.__ptr_dialog()
            elif strcmp(self.obj_type, 'mx'):
                self.dialog = self.__mx_dialog()
            elif strcmp(self.obj_type, 'ns') and not self.update:
                self.dialog = self.__ns_dialog()
            elif strcmp(self.obj_type, 'ns') and self.update:
                self.dialog = self.__ns_properties_dialog()
            elif strcmp(self.obj_type, 'zone'):
                self.dialog = self.__zone_dialog()
            elif strcmp(self.obj_type, 'srv'):
                self.dialog = self.__srv_dialog()
            elif strcmp(self.obj_type, 'txt'):
                self.dialog = self.__txt_dialog()
            elif strcmp(self.obj_type, 'soa'):
                self.dialog = self.__soa_dialog()
            elif not self.update:
                self.dialog = self.__other_dialog()
            else:
                self.dialog = self.__other_properties_dialog()
        if len(self.dialog)-1 < self.dialog_seq:
            self.dialog_seq -= 1
        return self.dialog[self.dialog_seq][0]() if callable(self.dialog[self.dialog_seq][0]) else self.dialog[self.dialog_seq][0]

    def __soa_dialog(self):
        return [
            [VBox(
                Left(Label(Id('serial_label'), 'Serial number:')),
                Left(IntField(Id('serial'), '', 0, 99999, self.obj['serial'])),
                VSpacing(1),
                Left(Label(Id('ns_label'), 'Primary server:')),
                Left(TextEntry(Id('ns'), '', self.obj['ns'])),
                VSpacing(1),
                Left(Label(Id('email_label'), 'Responsible person:')),
                Left(TextEntry(Id('email'), '', self.obj['email'])),
                VSpacing(1),
                HBox(
                    VBox(
                        Left(Label(Id('refresh_label'), 'Refresh interval:')),
                        Left(Label(Id('retry_label'), 'Retry interval:')),
                        Left(Label(Id('expire_label'), 'Expires after:')),
                        Left(Label(Id('minttl_label'), 'Minimum (default) TTL:')),
                        Left(Label(Id('ttl_label'), 'TTL for this record:')),
                    ),
                    VBox(
                        Left(IntField(Id('refresh'), '', 0, 99999, self.obj['refresh'])),
                        Left(IntField(Id('retry'), '', 0, 99999, self.obj['retry'])),
                        Left(IntField(Id('expire'), '', 0, 99999, self.obj['expire'])),
                        Left(IntField(Id('minttl'), '', 0, 99999, self.obj['minttl'])),
                        Left(IntField(Id('ttl'), '', 0, 99999, self.obj['ttl'])),
                    ),
                    VBox(
                        Left(Label('seconds')),
                        Left(Label('seconds')),
                        Left(Label('seconds')),
                        Left(Label('seconds')),
                        Left(Label('seconds')),
                    ),
                ),
                VSpacing(1),
                Bottom(Right(HBox(
                    PushButton(Id('finish'), 'OK'),
                    PushButton(Id('cancel'), 'Cancel'),
                ))),
            ),
            [], # known keys
            [], # required keys
            None, # dialog hook
            ],
        ]

    def __ns_properties_dialog(self):
        self.obj['type'] = dnsp.DNS_TYPE_NS
        def name_servers_hook(ret):
            if 'data' not in self.obj:
                self.obj['data'] = []
            if ret == 'add':
                server = NameServer().Show()
                if server:
                    self.obj['data'].append(server)
                    items = [Item(Id(server[0]), server[0], ' '.join(['[%s*]' % ip for ip in server[1]])) for server in self.obj['data']]
                    UI.ChangeWidget('items', 'Items', items)
            elif ret == 'edit':
                selection = UI.QueryWidget('items', 'CurrentItem')
                found = None
                for server in self.obj['data']:
                    if server[0] == selection:
                        found = server
                        break
                server = None
                if found:
                    server = NameServer(found[0], found[1]).Show()
                if server:
                    self.obj['data'] = [s for s in self.obj['data'] if s[0] != selection]
                    self.obj['data'].append(server)
                    items = [Item(Id(server[0]), server[0], ' '.join(['[%s*]' % ip for ip in server[1]])) for server in self.obj['data']]
                    UI.ChangeWidget('items', 'Items', items)
            elif ret == 'remove':
                selection = UI.QueryWidget('items', 'CurrentItem')
                if selection:
                    self.obj['data'] = [s for s in self.obj['data'] if s[0] != selection]
                    items = [Item(Id(server[0]), server[0], ' '.join(['[%s*]' % ip for ip in server[1]])) for server in self.obj['data']]
                    UI.ChangeWidget('items', 'Items', items)
        items = [Item(Id(server[0]), server[0], ' '.join(['[%s*]' % ip for ip in server[1]])) for server in self.obj['data']]
        return [
            [VBox(
                Left(Label('To add name servers to the list, click Add.')),
                VSpacing(1),
                Left(Label('Name servers:')),
                Table(Id('items'), Header('Server Fully Qualified Domain Name (FQDN)', 'IP Address'), items),
                Left(HBox(
                    PushButton(Id('add'), 'Add...'),
                    PushButton(Id('edit'), 'Edit...'),
                    PushButton(Id('remove'), 'Remove'),
                )),
                Left(Label('* represents an IP address retrieved as the result of a DNS query and may\nnot represent actual records stored on this server.')),
                Bottom(Right(HBox(
                    PushButton(Id('finish'), 'OK'),
                    PushButton(Id('cancel'), 'Cancel'),
                ))),
            ),
            [], # known keys
            [], # required keys
            name_servers_hook, # dialog hook
            ],
        ]

    def __other_properties_dialog(self):
        name_keys = {k: ' '.join(re.split('([A-Z][a-z]*)', k)).strip().capitalize() for k in self.obj.keys() if k not in ['flags', 'type']}
        items = []
        for k in name_keys.keys():
            if type(self.obj[k]) == int:
                items.append(Left(IntField(Id(k), Opt('disabled', 'hstretch'), name_keys[k], 0, 99999, self.obj[k])))
            else:
                items.append(Left(TextEntry(Id(k), Opt('disabled', 'hstretch'), name_keys[k], self.obj[k])))
        return [
            [VBox(
                *items,
                Bottom(Right(HBox(
                    PushButton(Id('finish'), Opt('disabled'), 'OK'),
                    PushButton(Id('cancel'), 'Cancel'),
                ))),
            ),
            list(name_keys.keys()), # known keys
            list(name_keys.keys()), # required keys
            None, # dialog hook
            ],
        ]

    def __other_dialog(self):
        self.obj['objs'] = []
        self.selection = 'cname'
        def selection_hook(ret):
            if ret == 'types':
                self.selection = UI.QueryWidget('types', 'CurrentItem')
            elif ret == 'next':
                obj = ObjDialog(self.selection, self.parent).Show()
                if obj:
                    self.obj['objs'].append(obj)
                UI.SetApplicationTitle('New Resource Record Type')
        def other_dialog():
            items = [Item(Id('cname'), dns_type_name(dns_type_flag('cname')), self.selection == 'cname'),
                     Item(Id('host'), 'Host (A or AAAA)', self.selection == 'host')]
            items.extend([Item(Id(dns_type), dns_type_name(dns_type_flag(dns_type)), self.selection == dns_type) for dns_type in ['mx', 'ptr', 'srv', 'txt']])
            buttons = [HBox(
                           PushButton(Id('next'), 'Create Record...'),
                           PushButton(Id('cancel'), 'Cancel'),
                       ),
                       HBox(
                           PushButton(Id('next'), 'Create Record...'),
                           PushButton(Id('finish'), 'Done'),
                       )]
            return VBox(
                Left(Label('Select a resource record type:')),
                Left(SelectionBox(Id('types'), Opt('notify', 'immediate'), '', items)),
                Bottom(Right(HBox(
                    buttons[self.dialog_seq],
                ))),
            )
        return [
            [other_dialog,
            [], # known keys
            [], # required keys
            selection_hook, # dialog hook
            ],
            [other_dialog,
            [], # known keys
            [], # required keys
            selection_hook, # dialog hook
            ],
        ]

    def __txt_dialog(self):
        def txt_hook(ret):
            if ret == 'name':
                name = UI.QueryWidget('name', 'Value')
                UI.ChangeWidget('fqdn', 'Value', '%s.%s' % (name, self.parent))
            elif ret == 'data':
                data = UI.QueryWidget('data', 'Value')
                UI.ChangeWidget('data', 'Value', re.sub(r'[^a-zA-Z0-9\s]', '', data))
        return [
            [VBox(
                Left(Label('Record name (uses parent domain if left blank):')),
                Left(TextEntry(Id('name'), Opt('disabled') if self.update else Opt('notify', 'hstretch'), self.obj['name'] if self.update else '')),
                Left(Label('Fully qualified domain name (FQDN):')),
                Left(TextEntry(Id('fqdn'), Opt('disabled'), '', '%s.%s' % (self.obj['name'], self.parent) if self.update else self.parent)),
                Left(Label(Id('data_label'), 'Text:')),
                Left(TextEntry(Id('data'), Opt('notify'), '', ' '.join(self.obj['data']) if self.update else '')),
                Bottom(Right(HBox(
                    PushButton(Id('finish'), 'OK'),
                    PushButton(Id('cancel'), 'Cancel')
                ))),
            ),
            ['name', 'data'], # known keys
            ['name', 'data'], # required keys
            txt_hook, # dialog hook
            ],
        ]

    def __srv_dialog(self):
        service_items = [self.obj['name']] if self.update else ['', '_finger', '_ftp', '_http', '_kerberos', '_ldap', '_msdcs', '_nntp', '_telnet', '_whois']
        def srv_hook(ret):
            if ret == 'name':
                selection = UI.QueryWidget('name', 'Value')
                if selection == '_finger':
                    UI.ChangeWidget('port', 'Value', 79)
                    UI.ChangeWidget('protocol', 'Items', ['_tcp', '_udp'])
                elif selection == '_ftp':
                    UI.ChangeWidget('port', 'Value', 21)
                    UI.ChangeWidget('protocol', 'Items', ['_tcp', '_udp'])
                elif selection == '_http':
                    UI.ChangeWidget('port', 'Value', 80)
                    UI.ChangeWidget('protocol', 'Items', ['_tcp', '_udp'])
                elif selection == '_kerberos':
                    UI.ChangeWidget('port', 'Value', 88)
                    UI.ChangeWidget('protocol', 'Items', ['_tcp', '_udp'])
                elif selection in ['_ldap', '_msdcs']:
                    UI.ChangeWidget('port', 'Value', 389)
                    UI.ChangeWidget('protocol', 'Items', ['_tcp', '_udp'])
                elif selection == '_nntp':
                    UI.ChangeWidget('port', 'Value', 119)
                    UI.ChangeWidget('protocol', 'Items', ['_tcp', '_udp'])
                elif selection == '_telnet':
                    UI.ChangeWidget('port', 'Value', 23)
                    UI.ChangeWidget('protocol', 'Items', ['_tcp', '_udp'])
                elif selection == '_whois':
                    UI.ChangeWidget('port', 'Value', 43)
                    UI.ChangeWidget('protocol', 'Items', ['_tcp'])
        disable_opt = ('disabled',) if self.update else tuple()
        protocols = [self.parent.split('.')[0]] if self.update else ['_tcp', '_udp']
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
                        Left(TextEntry(Opt('disabled', 'hstretch'), '', self.parent)),
                        Left(ComboBox(Id('name'), Opt('editable', 'notify', 'hstretch', *disable_opt), '', service_items)),
                        Left(ComboBox(Id('protocol'), Opt('editable', 'hstretch', *disable_opt), '', protocols)),
                        Left(IntField(Id('priority'), Opt('hstretch'), '', 0, 99999, self.obj['priority'] if self.update else 0)),
                        Left(IntField(Id('weight'), Opt('hstretch'), '', 0, 99999, self.obj['weight'] if self.update else 0)),
                        Left(IntField(Id('port'), Opt('hstretch'), '', 1, 65535, self.obj['port'] if self.update else 1)),
                    )),
                ),
                Left(Label(Id('nameTarget_label'), 'Host offering this service:')),
                Left(TextEntry(Id('nameTarget'), Opt('hstretch'), '', self.obj['nameTarget'] if self.update else '')),
                Empty() if self.update else Left(CheckBox(Id('allow_update'), Opt('disabled'), 'Allow any authenticated user to update all DNS records with the same\nname. This setting applies only to DNS records for a new name.')),
                Bottom(Right(HBox(
                    PushButton(Id('finish'), 'OK'),
                    PushButton(Id('cancel'), 'Cancel')
                ))),
            ),
            ['name', 'protocol', 'priority', 'weight', 'port', 'nameTarget'], # known keys
            ['name', 'protocol', 'priority', 'weight', 'port', 'nameTarget'], # required keys
            srv_hook, # dialog hook
            ],
        ]

    def __zone_dialog(self):
        if self.parent == 'forward':
            return [[VBox(
                Left(Label('The zone name specifies the portion of the DNS namespace for which this server is\n' \
                           'authoritative. It might be your organization\'s domain name or a portion of the\n' \
                           'domain name. The zone name is not the name of the DNS server.')),
                Left(Label(Id('name_label'), 'Zone name:')),
                Left(TextEntry(Id('name'), '')),
                Bottom(Right(HBox(
                    PushButton(Id('finish'), 'Finish'),
                    PushButton(Id('cancel'), 'Cancel')
                ))),
            ),
            ['name'], # known keys
            ['name'], # required keys
            None, # dialog hook
            ]]
        elif self.parent == 'reverse':
            def ip_hook(ret):
                if ret in ['id1', 'id2', 'id3']:
                    name = 'in-addr.arpa'
                    id1 = UI.QueryWidget('id1', 'Value')
                    id1 = re.sub('[^0-9]','', id1)
                    UI.ChangeWidget('id1', 'Value', id1)
                    id2 = UI.QueryWidget('id2', 'Value')
                    id2 = re.sub('[^0-9]','', id2)
                    UI.ChangeWidget('id2', 'Value', id2)
                    id3 = UI.QueryWidget('id3', 'Value')
                    id3 = re.sub('[^0-9]','', id3)
                    UI.ChangeWidget('id3', 'Value', id3)
                    if id1:
                        name = '%s.%s' % (id1, name)
                        if id2:
                            name = '%s.%s' % (id2, name)
                            if id3:
                                name = '%s.%s' % (id3, name)
                    UI.ChangeWidget('name', 'Value', name)
                elif ret == 'netid':
                    UI.ChangeWidget('name', 'Enabled', False)
                    UI.ChangeWidget('id1', 'Enabled', True)
                    UI.ChangeWidget('id2', 'Enabled', True)
                    UI.ChangeWidget('id3', 'Enabled', True)
                    UI.SetFocus('id1')
                elif ret == 'zone_name':
                    UI.ChangeWidget('name', 'Enabled', True)
                    UI.ChangeWidget('id1', 'Enabled', False)
                    UI.ChangeWidget('id2', 'Enabled', False)
                    UI.ChangeWidget('id3', 'Enabled', False)
                    UI.SetFocus('name')
                if ret == 'prefix':
                    prefix = UI.QueryWidget('prefix', 'Value')
                    name = ''
                    try:
                        network = ip_network(prefix)
                    except:
                        network = None
                    if network:
                        UI.ChangeWidget('name', 'Value', network.network_address.reverse_pointer[int(2*(128-network.prefixlen)/4):])
                    else:
                        UI.ChangeWidget('name', 'Value', '')
            def ip_dialog():
                if 'ipv4' in self.obj and self.obj['ipv4']:
                    return VBox(
                        Left(Label('To identify the reverse lookup zone, type the network ID or the name of the zone.')),
                        RadioButtonGroup(VBox(
                            Left(RadioButton(Id('netid'), Opt('notify', 'immediate'), 'Network ID:', True)),
                            HBox(
                                TextEntry(Id('id1'), Opt('notify'), ''),
                                Label('.'),
                                TextEntry(Id('id2'), Opt('notify'), ''),
                                Label('.'),
                                TextEntry(Id('id3'), Opt('notify'), ''),
                                Label('.'),
                                TextEntry(Opt('disabled'), ''),
                            ),
                            Left(Label('The network ID is the portion of the IP addresses that belongs to this zone. Enter the\nnetwork ID in its normal (not reversed) order.')),
                            Left(Label('If you use a zero in the network ID, it will appear in the zone name. For example,\nnetwork ID 10 would create zone 10.in-addr.arpa, and network ID 10.0 would create\nzone 0.10.in-addr.arpa.')),
                            Left(RadioButton(Id('zone_name'), Opt('notify', 'immediate'), 'Reverse lookup zone name:')),
                            Left(TextEntry(Id('name'), Opt('disabled'), '')),
                        )),
                        Bottom(Right(HBox(
                            PushButton(Id('finish'), 'Finish'),
                            PushButton(Id('cancel'), 'Cancel')
                        ))),
                    )
                elif 'ipv6' in self.obj and self.obj['ipv6']:
                    return VBox(
                        Left(Label('To name the reverse lookup zone, enter an IPv6 address prefix to auto generate the\nzone name.')),
                        Left(Label(Id('name_label'), 'IPv6 Address Prefix:')),
                        Left(TextEntry(Id('prefix'), Opt('notify'), '')),
                        Left(Label('Reverse Lookup Zone')),
                        Left(TextEntry(Id('name'), Opt('disabled'), '')),
                        Bottom(Right(HBox(
                            PushButton(Id('finish'), 'Finish'),
                            PushButton(Id('cancel'), 'Cancel')
                        ))),
                    )
                else:
                    return Empty()
            return [
                [VBox(
                    Left(Label('Choose whether you want to create a reverse lookup zone for IPv4 addresses or IPv6\naddresses.')),
                    RadioButtonGroup(VBox(Id('ip'),
                        Left(RadioButton(Id('ipv4'), 'IPv4 Reverse Lookup Zone', True)),
                        Left(RadioButton(Id('ipv6'), 'IPv6 Reverse Lookup Zone')),
                    )),
                    Bottom(Right(HBox(
                        PushButton(Id('next'), 'Next >'),
                        PushButton(Id('cancel'), 'Cancel')
                    ))),
                ),
                ['ipv4', 'ipv6'], # known keys
                [], # required keys
                None, # dialog hook
                ],
                [ip_dialog,
                ['name'], # known keys
                ['name'], # required keys
                ip_hook, # dialog hook
                ],
            ]

    def __ns_dialog(self):
        def fqdn_hook(ret):
            name = UI.QueryWidget('name', 'Value')
            UI.ChangeWidget('fqdn', 'Value', '%s.%s' % (name, self.parent))
        def name_servers_hook(ret):
            if 'data' not in self.obj:
                self.obj['data'] = []
            if ret == 'add':
                server = NameServer().Show()
                if server:
                    self.obj['data'].append(server)
                    items = [Item(Id(server[0]), server[0], '[%s]' % '] ['.join(server[1])) for server in self.obj['data']]
                    UI.ChangeWidget('items', 'Items', items)
            elif ret == 'edit':
                selection = UI.QueryWidget('items', 'CurrentItem')
                found = None
                for server in self.obj['data']:
                    if server[0] == selection:
                        found = server
                        break
                server = None
                if found:
                    server = NameServer(found[0], found[1]).Show()
                if server:
                    self.obj['data'] = [s for s in self.obj['data'] if s[0] != selection]
                    self.obj['data'].append(server)
                    items = [Item(Id(server[0]), server[0], '[%s]' % '] ['.join(server[1])) for server in self.obj['data']]
                    UI.ChangeWidget('items', 'Items', items)
            elif ret == 'remove':
                selection = UI.QueryWidget('items', 'CurrentItem')
                if selection:
                    self.obj['data'] = [s for s in self.obj['data'] if s[0] != selection]
                    items = [Item(Id(server[0]), server[0], '[%s]' % '] ['.join(server[1])) for server in self.obj['data']]
                    UI.ChangeWidget('items', 'Items', items)
        return [
            [VBox(
                Left(Label('Specify the name of the DNS domain you want to delegate.')),
                Left(Label(Id('name_label'), 'Delegated domain:')),
                Left(TextEntry(Id('name'), Opt('notify'), '')),
                Left(Label('Fully qualified domain name (FQDN):')),
                Left(TextEntry(Id('fqdn'), Opt('disabled'), '', self.parent)),
                Bottom(Right(HBox(
                    PushButton(Id('next'), 'Next >'),
                    PushButton(Id('cancel'), 'Cancel')
                ))),
            ),
            ['name'], # known keys
            ['name'], # required keys
            fqdn_hook, # dialog hook
            ],
            [VBox(
                Left(Label('Specify the names and IP addresses of the DNS servers you want to have host the\ndelegated zone.')),
                Left(Label('Name servers:')),
                Table(Id('items'), Header('Server Fully Qualified Domain Name (FQDN)', 'IP Address'), []),
                Left(HBox(
                    PushButton(Id('add'), 'Add...'),
                    PushButton(Id('edit'), 'Edit...'),
                    PushButton(Id('remove'), 'Remove'),
                )),
                Bottom(Right(HBox(
                    PushButton(Id('back'), '< Back'),
                    PushButton(Id('finish'), 'Finish'),
                    PushButton(Id('cancel'), 'Cancel')
                ))),
            ),
            [], # known keys
            [], # required keys
            name_servers_hook, # dialog hook
            ],
        ]

    def __mx_dialog(self):
        def fqdn_hook(ret):
            name = UI.QueryWidget('name', 'Value')
            UI.ChangeWidget('fqdn', 'Value', '%s.%s' % (name, self.parent))
        disable_opt = ('disabled',) if self.update else tuple()
        return [
            [VBox(
                Left(Label(Id('name_label'), 'Host or child domain:')),
                Left(TextEntry(Id('name'), Opt('notify', *disable_opt), '', self.obj['name'] if self.update else '')),
                Left(Label('By default, DNS uses the parent domain name when creating a Mail\nExchange record. You can specify a host or child name, but in most\ndeployments, the above field is left blank.')),
                Left(Label('Fully qualified domain name (FQDN):')),
                Left(TextEntry(Id('fqdn'), Opt('disabled'), '', '%s.%s' % (self.obj['name'], self.parent) if self.update else self.parent)),
                Left(Label(Id('nameExchange_label'), 'Fully qualified domain name (FQDN) of mail server:')),
                Left(TextEntry(Id('nameExchange'), '', self.obj['nameExchange'] if self.update else '')),
                Left(Label(Id('preference_label'), 'Mail server priority:')),
                Left(IntField(Id('preference'), '', 0, 99999, self.obj['preference'] if self.update else 10)),
                Bottom(Right(HBox(
                    PushButton(Id('finish'), 'OK'),
                    PushButton(Id('cancel'), 'Cancel')
                ))),
            ),
            ['name', 'nameExchange', 'preference'], # known keys
            ['name', 'nameExchange', 'preference'], # required keys
            fqdn_hook, # dialog hook
            ],
        ]

    def __ptr_dialog(self):
        def fqdn(name):
            if re.match('[\d+\.]+in\-addr\.arpa', self.parent):
                return '%s.%s' % ('.'.join(reversed(name.split('.'))), self.parent)
            elif re.match('[\w+\.]+ip6\.arpa', self.parent):
                return '%s.%s' % ('.'.join(reversed(''.join(name.split(':')))), self.parent)
        def fqdn_hook(ret):
            name = UI.QueryWidget('name', 'Value')
            UI.ChangeWidget('fqdn', 'Value', fqdn(name))
        name = ''
        m = re.match('([\d+\.]+)(in\-addr)\.arpa', self.parent)
        if not m:
            m = re.match('([\w+\.]+)(ip6)\.arpa', self.parent)
        if m:
            if m.group(2) == 'in-addr':
                name = '%s.' % '.'.join(reversed(m.group(1)[:-1].split('.')))
                name = ('%s%s' % (name, self.obj['name'])) if self.update else name
            else: # ip6
                rev = ''.join(reversed(m.group(1)[:-1].split('.')))
                name = '%s:' % ':'.join([rev[x-4:x] for x in range(4, len(rev)+4, 4)])
                name = ('%s%s' % (name, self.obj['name'])) if self.update else name
        return [
            [VBox(
                Left(Label(Id('name_label'), 'Host IP Address:')),
                HBox(
                    HWeight(1, Left(TextEntry(Id('ip'), Opt('disabled'), '', name))),
                    Empty() if self.update else HWeight(2, Left(TextEntry(Id('name'), Opt('notify'), ''))),
                ),
                Left(Label('Fully qualified domain name (FQDN):')),
                Left(TextEntry(Id('fqdn'), Opt('disabled'), '', fqdn(self.obj['name']) if self.update else self.parent)),
                Left(Label(Id('data_label'), 'Host name:')),
                Left(TextEntry(Id('data'), '', self.obj['data'] if self.update else '')),
                Empty() if self.update else Left(CheckBox(Id('allow_update'), Opt('disabled'), 'Allow any authenticated user to update all DNS records with the same\nname. This setting applies only to DNS records for a new name.')),
                Bottom(Right(HBox(
                    PushButton(Id('finish'), 'OK'),
                    PushButton(Id('cancel'), 'Cancel')
                ))),
            ),
            ['name', 'data', 'allow_update'], # known keys
            ['name', 'data'], # required keys
            None if self.update else fqdn_hook, # dialog hook
            ],
        ]

    def __cname_dialog(self):
        def fqdn_hook(ret):
            name = UI.QueryWidget('name', 'Value')
            UI.ChangeWidget('fqdn', 'Value', '%s.%s' % (name, self.parent))
        return [
            [VBox(
                Left(Label(Id('name_label'), 'Alias name (uses parent domain if left blank):')),
                Left(TextEntry(Id('name'), Opt('disabled') if self.update else Opt('notify'), '', self.obj['name'] if self.update else '')),
                Left(Label('Fully qualified domain name (FQDN):')),
                Left(TextEntry(Id('fqdn'), Opt('disabled'), '', '%s.%s' % (self.obj['name'], self.parent) if self.update else self.parent)),
                Left(Label(Id('data_label'), 'Fully qualified domain name (FQDN) for target host:')),
                Left(TextEntry(Id('data'), '', self.obj['data'] if self.update else '')),
                Empty() if self.update else Left(CheckBox(Id('allow_update'), Opt('disabled'), 'Allow any authenticated user to update all DNS records with the same\nname. This setting applies only to DNS records for a new name.')),
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

    def __host_dialog(self):
        def fqdn_hook(ret):
            if ret == 'name':
                name = UI.QueryWidget('name', 'Value')
                UI.ChangeWidget('fqdn', 'Value', '%s.%s' % (name, self.parent))
            elif ret == 'data':
                try:
                    ipvers = ip_address(UI.QueryWidget('data', 'Value'))
                    if type(ipvers) == IPv4Address:
                        self.obj['type'] = dnsp.DNS_TYPE_A
                    elif type(ipvers) == IPv6Address:
                        self.obj['type'] = dnsp.DNS_TYPE_AAAA
                    self.obj['reverse_pointer'] = ipvers.reverse_pointer
                except ValueError:
                    self.obj['type'] = None
        return [
            [VBox(
                Left(Label(Id('name_label'), 'Name (uses parent domain name if blank):')),
                Left(TextEntry(Id('name'), Opt('disabled') if self.update else Opt('notify'), '', self.obj['name'] if self.update else '')),
                Left(Label('Fully qualified domain name (FQDN):')),
                Left(TextEntry(Id('fqdn'), Opt('disabled'), '', '%s.%s' % (self.obj['name'], self.parent) if self.update else self.parent)),
                Left(Label(Id('data_label'), 'IP address:')),
                Left(TextEntry(Id('data'), Opt('notify'), '', self.obj['data'] if self.update else '')),
                Left(CheckBox(Id('create_ptr'), '%s associated pointer (PTR) record' % ('Update' if self.update else 'Create'))),
                Empty() if self.update else Left(CheckBox(Id('allow_update'), Opt('disabled'), 'Allow any authenticated user to update DNS records with the\nsame owner name')),
                Bottom(Right(HBox(
                    PushButton(Id('finish'), 'OK' if self.update else 'Add %s' % self.obj_type.capitalize()),
                    PushButton(Id('cancel'), 'Cancel')
                ))),
            ),
            ['name', 'data', 'create_ptr', 'allow_update'], # known keys
            ['name', 'data'], # required keys
            fqdn_hook, # dialog hook
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
            if value or type(value) == bool or type(value) == int:
                self.obj[key] = value
        required_value_keys = self.dialog[self.dialog_seq][2]
        for key in required_value_keys:
            if not key in self.obj or self.obj[key] == '':
                self.__warn_label(key)
                ycpbuiltins.y2error('Missing value for %s' % key)
                ret = False
        return ret

    def __set_values(self):
        for key in self.obj:
            UI.ChangeWidget(key, 'Value', self.obj[key])

    def __dialog_hook(self, ret):
        hook = self.dialog[self.dialog_seq][3]
        if hook:
            hook(ret)

    def Show(self):
        UI.SetApplicationTitle(('%s Properties' % (self.obj['name'] if self.obj['name'] else self.parent)) if self.update else 'New %s' % self.title)
        UI.OpenDialog(self.__new())
        ret = None
        while True:
            self.__dialog_hook(ret)
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
        #elif mtype and mtype in ['fzone', 'rzone']:
        #    menus.append({'title': 'Reload', 'id': 'reload', 'type': 'MenuEntry', 'parent': 'action'})
        if mtype and mtype in ['fzone', 'folder']:
            menus.append({'title': 'New Host (A or AAAA)...', 'id': 'new_host', 'type': 'MenuEntry', 'parent': 'action'})
            menus.append({'title': 'New Alias (CNAME)...', 'id': 'new_alias', 'type': 'MenuEntry', 'parent': 'action'})
            menus.append({'title': 'New Mail Exchanger (MX)...', 'id': 'new_mx', 'type': 'MenuEntry', 'parent': 'action'})
            #menus.append({'title': 'New Domain...', 'id': 'new_domain', 'type': 'MenuEntry', 'parent': 'action'})
        if mtype and mtype in ['rzone']:
            menus.append({'title': 'New Pointer (PTR)...', 'id': 'new_pointer', 'type': 'MenuEntry', 'parent': 'action'})
            menus.append({'title': 'New Alias (CNAME)...', 'id': 'new_alias', 'type': 'MenuEntry', 'parent': 'action'})
        if mtype and mtype in ['fzone', 'rzone', 'folder']:
            menus.append({'title': 'New Delegation...', 'id': 'new_delegation', 'type': 'MenuEntry', 'parent': 'action'})
            menus.append({'title': 'Other New Records...', 'id': 'other_new_records', 'type': 'MenuEntry', 'parent': 'action'})
        if mtype and mtype in ['object', 'fzone', 'rzone']:
            menus.append({'title': 'Delete', 'id': 'delete', 'type': 'MenuEntry', 'parent': 'action'})
        if mtype and mtype in ['zones', 'fzone', 'rzone', 'folder']:
            menus.append({'title': 'Refresh', 'id': 'refresh', 'type': 'MenuEntry', 'parent': 'action'})
        if mtype and mtype == 'object':
            menus.append({'title': 'Properties', 'id': 'properties', 'type': 'MenuEntry', 'parent': 'action'})
        CreateMenu(menus)

    def __open_context_menu(self, mtype=None):
        menus = []
        if mtype and mtype == 'top':
            menus.append(Item(Id('connect'), 'Connect to DNS Server...'))
        elif mtype and mtype == 'zones':
            menus.append(Item(Id('new_zone'), 'New Zone...'))
        if mtype and mtype in ['fzone', 'folder']:
            menus.append(Item(Id('new_host'), 'New Host (A or AAAA)...'))
            menus.append(Item(Id('new_alias'), 'New Alias (CNAME)...'))
            menus.append(Item(Id('new_mx'), 'New Mail Exchanger (MX)...'))
        if mtype and mtype in ['rzone']:
            menus.append(Item(Id('new_pointer'), 'New Pointer (PTR)...'))
            menus.append(Item(Id('new_alias'), 'New Alias (CNAME)...'))
        if mtype and mtype in ['fzone', 'rzone', 'folder']:
            menus.append(Item(Id('new_delegation'), 'New Delegation...'))
            menus.append(Item(Id('other_new_records'), 'Other New Records...'))
        if mtype and mtype in ['object', 'fzone', 'rzone']:
            menus.append(Item(Id('delete'), 'Delete'))
        if mtype and mtype in ['zones', 'fzone', 'rzone', 'folder']:
            menus.append(Item(Id('refresh'), 'Refresh'))
        if mtype and mtype == 'object':
            menus.append(Item(Id('properties'), 'Properties'))
        self.menu_open = True
        UI.OpenContextMenu(Term('menu', menus))

    def Show(self):
        UI.SetApplicationTitle('DNS Manager')
        Wizard.SetContentsButtons('', self.__dns_page(), '', '', '')
        DeleteButtonBox()
        UI.SetFocus('dns_tree')
        current_selection = None
        current_parent = None
        current_dns_type = None
        current_zone = None
        self.menu_open = False
        while True:
            event = UI.WaitForEvent()
            if 'WidgetID' in event:
                ret = event['WidgetID']
            elif 'ID' in event:
                ret = event['ID']
            else:
                raise Exception('ID not found in response %s' % str(event))
            if ret != 'abort' and ret != 'cancel':
                self.menu_open = False
            if (ret == 'abort' or ret == 'cancel') and self.menu_open:
                self.menu_open = False
            elif ret == 'abort' or ret == 'cancel':
                break
            elif ret == 'connect':
                self.conn = ConnectionDialog().Show()
                UI.ReplaceWidget('dns_tree_repl', self.__dns_tree())
            elif ret == 'dns_tree':
                zone, choice = UI.QueryWidget('dns_tree', 'Value').split(':')
                current_selection = choice
                current_parent = choice
                current_zone = zone
                if choice not in ['dns_edit', 'server', 'forward', 'reverse']:
                    records = self.conn.records(zone, choice)
                    if records:
                        UI.ReplaceWidget('rightPane', self.__rightpane(records, choice))
                    if choice in self.conn.forward_zones():
                        self.__setup_menus(mtype='fzone')
                        if event['EventReason'] == 'ContextMenuActivated':
                            self.__open_context_menu(mtype='fzone')
                    elif choice in self.conn.reverse_zones():
                        self.__setup_menus(mtype='rzone')
                        if event['EventReason'] == 'ContextMenuActivated':
                            self.__open_context_menu(mtype='rzone')
                    else:
                        self.__setup_menus(mtype='folder')
                        if event['EventReason'] == 'ContextMenuActivated':
                            self.__open_context_menu(mtype='folder')
                elif choice in ['forward', 'reverse']:
                    UI.ReplaceWidget('rightPane', self.__rightpane_zones(choice))
                    self.__setup_menus(mtype='zones')
                    if event['EventReason'] == 'ContextMenuActivated':
                        self.__open_context_menu(mtype='zones')
                elif choice == 'dns_edit':
                    UI.ReplaceWidget('rightPane', Empty())
                    self.__setup_menus(mtype='top')
                    if event['EventReason'] == 'ContextMenuActivated':
                        self.__open_context_menu(mtype='top')
                else:
                    UI.ReplaceWidget('rightPane', Empty())
                    self.__setup_menus()
            elif ret == 'items':
                zone, top = UI.QueryWidget('dns_tree', 'Value').split(':')
                choice, dns_type = UI.QueryWidget('items', 'Value').split(':')
                result = self.conn.records(zone, top)
                record = result[choice] if result and choice in result else None
                nchoice = '%s.%s' % (choice, top)
                current_selection = nchoice
                current_dns_type = dns_type
                current_zone = zone
                if (record and 'dwChildCount' in record and record['dwChildCount'] > 0) or not dns_type:
                    current_parent = nchoice
                    if event['EventReason'] == 'Activated':
                        self.__refresh(zone=zone, top=nchoice)
                    self.__setup_menus(mtype='folder')
                    if event['EventReason'] == 'ContextMenuActivated':
                        self.__open_context_menu(mtype='folder')
                elif record:
                    if event['EventReason'] == 'Activated':
                        obj = ObjDialog(dns_type_name(int(dns_type), short=True), top, choice, record).Show()
                        if obj:
                            self.__update_record(zone, top, obj)
                    self.__setup_menus(mtype='object')
                    if event['EventReason'] == 'ContextMenuActivated':
                        self.__open_context_menu(mtype='object')
            elif ret == 'properties':
                zone, top = UI.QueryWidget('dns_tree', 'Value').split(':')
                choice, dns_type = UI.QueryWidget('items', 'Value').split(':')
                result = self.conn.records(zone, top)
                record = result[choice] if result and choice in result else None
                if record:
                    obj = ObjDialog(dns_type_name(int(dns_type), short=True), top, choice, record).Show()
                    if obj:
                        self.__update_record(zone, top, obj)
            elif ret == 'new_host':
                host = ObjDialog('host', current_parent).Show()
                if host:
                    self.__add_record(current_zone, current_parent, host)
            elif ret == 'new_alias':
                cname = ObjDialog('cname', current_parent).Show()
                if cname:
                    self.__add_record(current_zone, current_parent, cname)
            elif ret == 'new_pointer':
                ptr = ObjDialog('ptr', current_parent).Show()
                if ptr:
                    self.__add_record(current_zone, current_parent, ptr)
            elif ret == 'new_mx':
                mx = ObjDialog('mx', current_parent).Show()
                if mx:
                    self.__add_record(current_zone, current_parent, mx)
            elif ret == 'new_delegation':
                ns = ObjDialog('ns', current_parent).Show()
                if ns:
                    for server in ns['data']:
                        self.conn.add_record(current_zone, current_parent, ns['name'], 'NS', server[0])
                    self.__refresh(zone=current_zone, top='%s.%s' % (ns['name'], current_parent))
            elif ret == 'new_zone':
                zone = ObjDialog('zone', current_parent).Show()
                if zone:
                    msg = self.conn.create_zone(zone['name'])
                    self.__refresh(zone=zone)
                    self.__message(msg, buttons=['ok'])
            elif ret == 'other_new_records':
                objs = ObjDialog('other', current_parent).Show()
                if objs:
                    for obj in objs['objs']:
                        self.__add_record(current_zone, current_parent, obj)
            elif ret == 'delete':
                zone, top = UI.QueryWidget('dns_tree', 'Value').split(':')
                if zone == top and current_selection == zone: # Delete a zone
                    if self.__message('Do you want to delete the zone %s from the server?' % zone, title='DNS', warn=True):
                        msg = self.conn.delete_zone(zone)
                        self.__message(msg, buttons=['ok'])
                        self.__refresh()
                else:
                    choice, dns_type = UI.QueryWidget('items', 'Value').split(':')
                    result = self.conn.records(zone, top)
                    record = result[choice] if result and choice in result else None
                    nchoice = '%s.%s' % (choice, top) if choice else top
                    data = self.__dns_record_to_data(int(dns_type), record)
                    if data and self.__message('Do you want to delete the record %s from the server?' % (choice if choice else nchoice), title='DNS', warn=True):
                        type_name = dns_type_name(int(dns_type))
                        m = re.match('[\w\s]*\s*\((\w+)\)', type_name)
                        if m:
                            dns_type = m.group(1)
                        else:
                            dns_type = type_name
                        msg = self.conn.delete_record(zone, nchoice, dns_type, data)
                        self.__message(msg, buttons=['ok'])
                        self.__refresh()
                    else:
                        self.__message('Deleting record of type %s is not supported' % dns_type_name(int(dns_type)), buttons=['ok'])
            elif ret == 'refresh':
                self.__refresh()
            UI.SetApplicationTitle('DNS Manager')
        return Symbol(ret)

    def __add_record(self, zone, parent, record):
        msg = None
        if record['type'] == dnsp.DNS_TYPE_SRV:
            msg = self.conn.add_record(zone, parent, '%s.%s' % (record['name'], record['protocol']), 'SRV', format_data(record))
            self.__refresh(zone=zone, top='%s.%s' % (record['protocol'], parent), item=record['name'], dns_type=dnsp.DNS_TYPE_SRV)
        elif record['type'] in [dnsp.DNS_TYPE_TXT, dnsp.DNS_TYPE_CNAME, dnsp.DNS_TYPE_PTR, dnsp.DNS_TYPE_MX, dnsp.DNS_TYPE_A, dnsp.DNS_TYPE_AAAA]:
            msg = self.conn.add_record(zone, parent, record['name'], dns_type_name(record['type'], short=True), format_data(record))
            self.__refresh(item=record['name'], dns_type=record['type'])
        if record['type'] == dnsp.DNS_TYPE_A:
            msg2 = None
            if record['create_ptr']:
                ptr_parent = self.conn.match_zone(record['reverse_pointer'])
                if not ptr_parent:
                    msg2 = 'Zone does not exist; record could not be added.'
                else:
                    name = '%s.%s' % (record['name'], parent)
                    data = record['reverse_pointer'].split(ptr_parent)[0][:-1]
                    msg2 = self.conn.add_record(ptr_parent, ptr_parent, data, 'PTR', name)
            if msg2 and msg2 != 'Record added successfully':
                self.__message('Warning: The associated pointer (PTR) record cannot be created: %s' % msg2, warn=True, buttons=['ok'])
        elif record['type'] == dnsp.DNS_TYPE_AAAA:
            msg2 = None
            if record['create_ptr']:
                ptr_parent = self.conn.match_zone(record['reverse_pointer'])
                if not ptr_parent:
                    msg2 = 'Zone does not exist; record could not be added.'
                else:
                    name = '%s.%s' % (record['name'], parent)
                    data = record['reverse_pointer'].split(ptr_parent)[0][:-1]
                    msg2 = self.conn.add_record(ptr_parent, ptr_parent, data, 'PTR', name)
            if msg2 and msg2 != 'Record added successfully':
                self.__message('Warning: The associated pointer (PTR) record cannot be created: %s' % msg2, warn=True, buttons=['ok'])
        if msg:
            self.__message(msg, buttons=['ok'])

    def __update_record(self, zone, parent, record):
        msg = None
        if record['type'] in [dnsp.DNS_TYPE_SRV, dnsp.DNS_TYPE_TXT, dnsp.DNS_TYPE_CNAME, dnsp.DNS_TYPE_PTR, dnsp.DNS_TYPE_MX, dnsp.DNS_TYPE_A, dnsp.DNS_TYPE_AAAA]:
            msg = self.conn.update_record(zone, parent, record['name'], dns_type_name(record['type'], short=True), format_data(record))
            self.__refresh(item=record['name'], dns_type=record['type'])
        if record['type'] == dnsp.DNS_TYPE_A:
            msg2 = None
            if record['create_ptr']:
                ptr_parent = self.conn.match_zone(record['reverse_pointer'])
                if not ptr_parent:
                    msg2 = 'Zone does not exist; record could not be added.'
                else:
                    name = '%s.%s' % (record['name'], parent)
                    data = record['reverse_pointer'].split(ptr_parent)[0][:-1]
                    msg2 = self.conn.add_record(ptr_parent, ptr_parent, data, 'PTR', name)
            if msg2 and msg2 != 'Record added successfully':
                self.__message('Warning: The associated pointer (PTR) record cannot be created: %s' % msg2, warn=True, buttons=['ok'])
        elif record['type'] == dnsp.DNS_TYPE_AAAA:
            msg2 = None
            if record['create_ptr']:
                ptr_parent = self.conn.match_zone(record['reverse_pointer'])
                if not ptr_parent:
                    msg2 = 'Zone does not exist; record could not be added.'
                else:
                    name = '%s.%s' % (record['name'], parent)
                    data = record['reverse_pointer'].split(ptr_parent)[0][:-1]
                    msg2 = self.conn.add_record(ptr_parent, ptr_parent, data, 'PTR', name)
            if msg2 and msg2 != 'Record added successfully':
                self.__message('Warning: The associated pointer (PTR) record cannot be created: %s' % msg2, warn=True, buttons=['ok'])
        elif record['type'] == dnsp.DNS_TYPE_NS:
            if not record['name']:
                name = parent.split('.')[-1]
                parent = '.'.join(parent.split('.')[:-1])
            else:
                name = record['name']
            oldservers = [data['data'] for data in self.conn.records(zone, '%s.%s' % (name, parent))['']['records'] if data['type'] == dnsp.DNS_TYPE_NS]
            newservers = [data[0] for data in record['data']]
            for server in oldservers:
                if server not in newservers:
                    msg2 = self.conn.delete_record(zone, '%s.%s' % (name, parent), 'NS', server)
                    if msg2 != 'Record deleted successfully':
                        self.__message(msg2, buttons=['ok'])
            for server in newservers:
                if server not in oldservers:
                    msg2 = self.conn.add_record(zone, parent, name, 'NS', server)
                    if msg2 != 'Record added successfully':
                        self.__message(msg2, buttons=['ok'])
            self.__refresh(item=name, dns_type=record['type'])
        if msg:
            self.__message(msg, buttons=['ok'])

    def __dns_record_to_data(self, record_type, record):
        srecord = None
        for rec in record['records']:
            if rec['type'] == record_type:
                srecord = rec
                break
        return format_data(srecord)

    def __refresh(self, zone=None, top=None, item=None, dns_type=None):
        if not top:
            zone, top = UI.QueryWidget('dns_tree', 'Value').split(':')
        records = self.conn.records(zone, top)
        self.__tree_select(zone, top)
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

    def __tree_select(self, zone, choice):
        select = '%s:%s' % (zone, choice)
        UI.ReplaceWidget('dns_tree_repl', self.__dns_tree(select))
        UI.ChangeWidget('dns_tree', 'CurrentItem', Symbol(select))

    def __rightpane_zones(self, zone_type):
        if zone_type == 'forward':
            items = [Item(Id('%s:' % zone), zone, '', '') for zone in self.conn.forward_zones()]
        elif zone_type == 'reverse':
            items = [Item(Id('%s:' % zone), zone, '', '') for zone in self.conn.reverse_zones()]
        return Table(Id('items'), Opt('notify', 'immediate', 'notifyContextMenu'), Header('Name', 'Type', 'Status'), items)

    def __flaten_data(self, record):
        if record['type'] in [dnsp.DNS_TYPE_A, dnsp.DNS_TYPE_AAAA, dnsp.DNS_TYPE_PTR, dnsp.DNS_TYPE_CNAME, dnsp.DNS_TYPE_NS]:
            return record['data']
        elif record['type'] == dnsp.DNS_TYPE_MX:
            return '[%d] %s' % (record['preference'], record['nameExchange'])
        elif record['type'] == dnsp.DNS_TYPE_SRV:
            return '[%d][%d][%d] %s' % (record['priority'], record['weight'], record['port'], record['nameTarget'])
        elif record['type'] == dnsp.DNS_TYPE_TXT:
            return ' '.join(record['data'])
        elif record['type'] == dnsp.DNS_TYPE_SOA:
            return '[%d], %s, %s' % (record['serial'], record['ns'], record['email'])
        elif 'data' in record:
            return str(record['data'])
        else:
            return ''

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
                items.extend([Item(Id('%s:%d' % (name, r['type'])), '%s%s' % (prepend if r['type'] == dnsp.DNS_TYPE_PTR else '', name) if name else '(same as parent folder)', dns_type_name(r['type']), self.__flaten_data(r), '') for r in records[name]['records']])
            elif name:
                items.append(Item(Id('%s:' % name), '%s' % name, '', '', ''))
        return Table(Id('items'), Opt('notify', 'immediate', 'notifyContextMenu'), Header('Name', 'Type', 'Data', 'Timestamp'), items)

    def __tree_children(self, zone, records, parent, expand=None):
        children = []
        if records:
            for child in records.keys():
                if records[child]['dwChildCount'] > 0:
                    cid = '%s.%s' % (child, parent)
                    children.append(Item(Id('%s:%s' % (zone, cid)), child, cid == expand[-len(cid):] if expand else False, self.__tree_children(zone, records[child]['children'], cid, expand)))
                elif child and 'type' not in records[child] and not records[child]['records']:
                    cid = '%s.%s' % (child, parent)
                    children.append(Item(Id('%s:%s' % (zone, cid)), child, cid == expand[-len(cid):] if expand else False, []))
        return children

    def __dns_tree(self, expand=None):
        if self.conn:
            forward_zones = self.conn.forward_zones()
            reverse_zones = self.conn.reverse_zones()
            expand_forward = len([z for z in forward_zones if expand[-len(z):] == z]) > 0 if expand else False
            expand_reverse = len([z for z in reverse_zones if expand[-len(z):] == z]) > 0 if expand else False
            forward_items = [Item(Id('%s:%s' % (zone, zone)), zone, zone == expand[-len(zone):] if expand else False, self.__tree_children(zone, self.conn.records(zone, zone), zone, expand)) for zone in forward_zones]
            reverse_items = [Item(Id('%s:%s' % (zone, zone)), zone, zone == expand[-len(zone):] if expand else False, self.__tree_children(zone, self.conn.records(zone, zone), zone, expand)) for zone in reverse_zones]
            tree = [Item(Id(':server'), self.conn.server, True, [
                        Item(Id(':forward'), 'Forward Lookup Zones', expand_forward, forward_items),
                        Item(Id(':reverse'), 'Reverse Lookup Zones', expand_reverse, reverse_items)
                        ])
                    ]
        else:
            tree = []
        return Tree(Id('dns_tree'), Opt('notify', 'immediate', 'notifyContextMenu'), '', [
            Item(Id(':dns_edit'), 'DNS', True, tree)
        ])

    def __dns_page(self):
        return HBox(
            HWeight(1, VBox(
                ReplacePoint(Id('dns_tree_repl'), self.__dns_tree()),
            )),
            HWeight(2, ReplacePoint(Id('rightPane'), Empty()))
        )

