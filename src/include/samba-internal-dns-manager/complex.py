from yast import import_module
import_module('SambaToolDnsAPI')
from yast import SambaToolDnsAPI
from samba.netcmd import CommandError

class Connection:
    def __init__(self, lp, creds, server):
        self.lp = lp
        self.creds = creds
        self.server = server
        self.zones = SambaToolDnsAPI.zonelist(self.server, self.creds.get_username(), self.creds.get_password())
        if len(self.zones.keys()) == 0:
            raise CommandError('Failed to authenticate to list dns zones')
