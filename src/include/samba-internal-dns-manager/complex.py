from yast import import_module
import_module('SambaToolDnsAPI')
from yast import SambaToolDnsAPI

class Connection:
    def __init__(self, lp, creds, server):
        self.lp = lp
        self.creds = creds
        self.server = server
        self.zones = SambaToolDnsAPI.zonelist(self.server, self.creds.get_username(), self.creds.get_password())

