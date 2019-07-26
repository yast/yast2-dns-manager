from yast import import_module
import_module('SambaToolDnsAPI')
from yast import SambaToolDnsAPI
from samba.netcmd import CommandError

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

    def records(self, selection):
        if selection in self._forward or selection in self._reverse:
            return SambaToolDnsAPI.query(self.server, selection, '@', 'ALL', self.creds.get_username(), self.creds.get_password())
        else:
            zone = self.match_zone(selection)
            if not zone:
                return {}
            return SambaToolDnsAPI.query(self.server, zone, selection, 'ALL', self.creds.get_username(), self.creds.get_password())

    def add_record(self, parent, name, rtype, data):
        zone = self.match_zone(parent)
        if not zone:
            return 'Zone does not exist; record could not be added.'
        fqdn = '%s.%s' % (name, parent)
        return SambaToolDnsAPI.add_record(self.server, zone, fqdn, rtype, data, self.creds.get_username(), self.creds.get_password())

    def delete_record(self, name, rtype, data):
        zone = self.match_zone(name)
        if not zone:
            return 'Zone does not exist; record could not be deleted.'
        return SambaToolDnsAPI.delete_record(self.server, zone, name, rtype, data, self.creds.get_username(), self.creds.get_password())
