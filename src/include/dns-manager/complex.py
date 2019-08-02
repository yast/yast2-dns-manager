from yast import import_module
import_module('SambaToolDnsAPI')
from yast import SambaToolDnsAPI
from samba.netcmd import CommandError
from samba.dcerpc import dnsp

def dns_type_flag(rec_type):
    rtype = rec_type.upper()
    if rtype == 'A':
        record_type = dnsp.DNS_TYPE_A
    elif rtype == 'AAAA':
        record_type = dnsp.DNS_TYPE_AAAA
    elif rtype == 'PTR':
        record_type = dnsp.DNS_TYPE_PTR
    elif rtype == 'NS':
        record_type = dnsp.DNS_TYPE_NS
    elif rtype == 'CNAME':
        record_type = dnsp.DNS_TYPE_CNAME
    elif rtype == 'SOA':
        record_type = dnsp.DNS_TYPE_SOA
    elif rtype == 'MX':
        record_type = dnsp.DNS_TYPE_MX
    elif rtype == 'SRV':
        record_type = dnsp.DNS_TYPE_SRV
    elif rtype == 'TXT':
        record_type = dnsp.DNS_TYPE_TXT
    elif rtype == 'ALL':
        record_type = dnsp.DNS_TYPE_ALL
    else:
        raise Exception('Unknown type of DNS record %s' % rec_type)
    return record_type

def dns_type_name(dns_type, short=False):
    if dns_type == dnsp.DNS_TYPE_TOMBSTONE:
        return 'TOMBSTONE' if short else '(TOMBSTONE)'
    elif dns_type == dnsp.DNS_TYPE_A:
        return 'A' if short else 'Host (A)'
    elif dns_type == dnsp.DNS_TYPE_NS:
        return 'NS' if short else 'Name Server (NS)'
    elif dns_type == dnsp.DNS_TYPE_MD:
        return 'MD' if short else '(MD)'
    elif dns_type == dnsp.DNS_TYPE_MF:
        return 'MF' if short else '(MF)'
    elif dns_type == dnsp.DNS_TYPE_CNAME:
        return 'CNAME' if short else 'Alias (CNAME)'
    elif dns_type == dnsp.DNS_TYPE_SOA:
        return 'SOA' if short else 'Start of Authority (SOA)'
    elif dns_type == dnsp.DNS_TYPE_MB:
        return 'MB' if short else 'Mailbox (MB)'
    elif dns_type == dnsp.DNS_TYPE_MG:
        return 'MG' if short else 'Mail Group (MG)'
    elif dns_type == dnsp.DNS_TYPE_MR:
        return 'MR' if short else 'Renamed Mailbox (MR)'
    elif dns_type == dnsp.DNS_TYPE_NULL:
        return 'NULL' if short else '(NULL)'
    elif dns_type == dnsp.DNS_TYPE_WKS:
        return 'WKS' if short else 'Well Known Services (WKS)'
    elif dns_type == dnsp.DNS_TYPE_PTR:
        return 'PTR' if short else 'Pointer (PTR)'
    elif dns_type == dnsp.DNS_TYPE_HINFO:
        return 'HINFO' if short else 'Host Information (HINFO)'
    elif dns_type == dnsp.DNS_TYPE_MINFO:
        return 'MINFO' if short else 'Mailbox Information (MINFO)'
    elif dns_type == dnsp.DNS_TYPE_MX:
        return 'MX' if short else 'Mail Exchanger (MX)'
    elif dns_type == dnsp.DNS_TYPE_TXT:
        return 'TXT' if short else 'Text (TXT)'
    elif dns_type == dnsp.DNS_TYPE_RP:
        return 'RP' if short else 'Responsible Person (RP)'
    elif dns_type == dnsp.DNS_TYPE_AFSDB:
        return 'AFSDB' if short else 'AFS Database (AFSDB)'
    elif dns_type == dnsp.DNS_TYPE_X25:
        return 'X.25'
    elif dns_type == dnsp.DNS_TYPE_ISDN:
        return 'ISDN'
    elif dns_type == dnsp.DNS_TYPE_RT:
        return 'RT' if short else 'Route Through (RT)'
    elif dns_type == dnsp.DNS_TYPE_SIG:
        return 'SIG' if short else 'Signature (SIG)'
    elif dns_type == dnsp.DNS_TYPE_KEY:
        return 'KEY' if short else 'Public Key (KEY)'
    elif dns_type == dnsp.DNS_TYPE_AAAA:
        return 'AAAA' if short else 'IPv6 Host (AAAA)'
    elif dns_type == dnsp.DNS_TYPE_LOC:
        return 'LOC' if short else '(LOC)'
    elif dns_type == dnsp.DNS_TYPE_NXT:
        return 'NXT' if short else 'Next Domain (NXT)'
    elif dns_type == dnsp.DNS_TYPE_SRV:
        return 'SRV' if short else 'Service Location (SRV)'
    elif dns_type == dnsp.DNS_TYPE_ATMA:
        return 'ATMA' if short else 'ATM Address (ATMA)'
    elif dns_type == dnsp.DNS_TYPE_NAPTR:
        return 'NAPTR' if short else '(NAPTR)'
    elif dns_type == dnsp.DNS_TYPE_DNAME:
        return 'DNAME' if short else '(DNAME)'
    elif dns_type == dnsp.DNS_TYPE_DS:
        return 'DS' if short else '(DS)'
    elif dns_type == dnsp.DNS_TYPE_RRSIG:
        return 'RRSIG' if short else '(RRSIG)'
    elif dns_type == dnsp.DNS_TYPE_NSEC:
        return 'NSEC' if short else '(NSEC)'
    elif dns_type == dnsp.DNS_TYPE_DNSKEY:
        return 'DNSKEY' if short else '(DNSKEY)'
    elif dns_type == dnsp.DNS_TYPE_DHCID:
        return 'DHCID' if short else '(DHCID)'
    elif dns_type == dnsp.DNS_TYPE_ALL:
        return 'ALL' if short else '(ALL)'
    elif dns_type == dnsp.DNS_TYPE_WINS:
        return 'WINS' if short else '(WINS)'
    elif dns_type == dnsp.DNS_TYPE_WINSR:
        return 'WINSR' if short else '(WINSR)'
    else:
        return 'Unknown'

def format_data(data):
    if data['type'] in [dnsp.DNS_TYPE_CNAME, dnsp.DNS_TYPE_PTR, dnsp.DNS_TYPE_A, dnsp.DNS_TYPE_AAAA]:
        return data['data']
    elif data['type'] == dnsp.DNS_TYPE_TXT:
        return data['text']
    elif data['type'] == dnsp.DNS_TYPE_MX:
        return '%s %s' % (data['nameExchange'], data['preference'])
    elif data['type'] == dnsp.DNS_TYPE_SOA:
        return '%s %s %d %d %d %d %d' % (data['ns'], data['email'], data['serial'], data['refresh'], data['retry'], data['expire'], data['minttl'])
    elif data['type'] == dnsp.DNS_TYPE_SRV:
        return '%s %d %d %d' % (data['nameTarget'], data['port'], data['priority'], data['weight'])

class Connection:
    def __init__(self, lp, creds, server):
        self.lp = lp
        self.creds = creds
        self.server = server
        self.__refresh_zones()

    def __refresh_zones(self):
        self.zones = SambaToolDnsAPI.zonelist(self.server, self.creds.get_username(), self.creds.get_password())
        self._forward = {zone: self.zones[zone] for zone in self.zones.keys() if 'DNS_RPC_ZONE_REVERSE' not in self.zones[zone]['Flags']}
        self._reverse = {zone: self.zones[zone] for zone in self.zones.keys() if 'DNS_RPC_ZONE_REVERSE' in self.zones[zone]['Flags']}
        if len(self.zones.keys()) == 0:
            raise CommandError('Failed to authenticate to list dns zones')

    def forward_zones(self):
        return self._forward

    def reverse_zones(self):
        return self._reverse

    def match_zone(self, selection):
        matching_zones = [zone for zone in list(self._forward.keys()) + list(self._reverse.keys()) if selection[-len(zone):] == zone]
        return max(matching_zones, key=len) if len(matching_zones) > 0 else None

    def records(self, zone, selection):
        return SambaToolDnsAPI.query(self.server, zone, selection, 'ALL', self.creds.get_username(), self.creds.get_password())

    def add_record(self, zone, parent, name, rtype, data):
        fqdn = '%s.%s' % (name, parent)
        return SambaToolDnsAPI.add_record(self.server, zone, fqdn, rtype, data, self.creds.get_username(), self.creds.get_password())

    def delete_record(self, zone, name, rtype, data):
        return SambaToolDnsAPI.delete_record(self.server, zone, name, rtype, data, self.creds.get_username(), self.creds.get_password())

    def delete_zone(self, zone):
        ret = SambaToolDnsAPI.delete_zone(self.server, zone, self.creds.get_username(), self.creds.get_password())
        self.__refresh_zones()
        return ret

    def create_zone(self, zone):
        ret = SambaToolDnsAPI.create_zone(self.server, zone, self.creds.get_username(), self.creds.get_password())
        self.__refresh_zones()
        return ret

    def update_record(self, zone, parent, name, rtype, newdata):
        fqdn = '%s.%s' % (name, parent)
        olddata = format_data(SambaToolDnsAPI.query(self.server, zone, fqdn, rtype, self.creds.get_username(), self.creds.get_password())['']['records'][0])
        return SambaToolDnsAPI.update_record(self.server, zone, fqdn, rtype, olddata, newdata, self.creds.get_username(), self.creds.get_password())
