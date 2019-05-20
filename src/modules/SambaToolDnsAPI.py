from yast import ycpbuiltins
from io import StringIO
from samba.getopt import SambaOptions, CredentialsOptions
from optparse import OptionParser
from yast import Declare
from samba.netcmd import dns
from samba.netcmd import CommandError
import re

@Declare('map', 'string', 'string', 'string')
def zonelist(server, username, password):
    parser = OptionParser()
    sambaopts = SambaOptions(parser)
    credopts = CredentialsOptions(parser)
    credopts.creds.parse_string(username)
    credopts.creds.set_password(password)
    credopts.ask_for_password = False
    credopts.machine_pass = False
    lp = sambaopts.get_loadparm()
    lp.set('realm', server)
    lp.set('debug level', '0')
    output = StringIO()
    cmd = dns.cmd_zonelist()
    cmd.outf = output
    try:
        cmd.run(server, 'longhorn', sambaopts=sambaopts, credopts=credopts)
    except CommandError:
        return {}
    res = {}
    for zone in output.getvalue().split('\n\n'):
        if re.match('\d+ zone\(s\) found', zone.strip()):
            continue
        zone_map = {}
        zone_name = None
        for line in zone.split('\n'):
            m = re.match('([^:]+):(.*)', line)
            if m:
                key = m.group(1).strip()
                val = m.group(2).strip()
                if key == 'pszZoneName':
                    zone_name = val
                elif key in ['Flags', 'dwDpFlags']:
                    zone_map[key] = val.split()
                else:
                    zone_map[key] = val
        if zone_name:
            res[zone_name] = zone_map
    return res
