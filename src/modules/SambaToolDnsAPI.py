from yast import ycpbuiltins
from io import StringIO
from samba.getopt import SambaOptions, CredentialsOptions
from optparse import OptionParser
from yast import Declare
from samba.netcmd import dns
from samba.netcmd import CommandError
import re
from samba.dcerpc import dnsp

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

results = None
@Declare('map', 'string', 'string', 'string', 'string', 'string', 'string')
def query(server, zone, name, rtype, username, password):
    global results
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
    cmd = dns.cmd_query()
    def fetch_dnsrecords(_, records):
        global results
        results = records
    dns.print_dnsrecords = fetch_dnsrecords
    try:
        cmd.run(server, zone, name, rtype, sambaopts=sambaopts, credopts=credopts)
    except CommandError:
        return {}
    records = {}
    for rec in results.rec:
        records[rec.dnsNodeName.str] = {}
        records[rec.dnsNodeName.str]['records'] = []
        if rec.dwChildCount > 0:
            records[rec.dnsNodeName.str]['children'] = query(server, zone, '%s.%s' % (rec.dnsNodeName.str, name if name != '@' else '%s.' % zone), rtype, username, password)
        for dns_rec in rec.records:
            record = {}
            if dns_rec.wType in [dnsp.DNS_TYPE_A, dnsp.DNS_TYPE_AAAA]:
                record = {'data': dns_rec.data}
            elif dns_rec.wType in [dnsp.DNS_TYPE_PTR, dnsp.DNS_TYPE_NS, dnsp.DNS_TYPE_CNAME]:
                record = {'data': dns_rec.data.str}
            elif dns_rec.wType == dnsp.DNS_TYPE_SOA:
                record = {'serial': dns_rec.data.dwSerialNo, 'refresh': dns_rec.data.dwRefresh, 'retry': dns_rec.data.dwRetry, 'expire': dns_rec.data.dwExpire, 'minttl': dns_rec.data.dwMinimumTtl, 'ns': dns_rec.data.NamePrimaryServer.str, 'email': dns_rec.data.ZoneAdministratorEmail.str}
            elif dns_rec.wType == dnsp.DNS_TYPE_MX:
                record = {'nameExchange': dns_rec.data.nameExchange.str, 'preference': dns_rec.data.wPreference}
            elif dns_rec.wType == dnsp.DNS_TYPE_SRV:
                record = {'nameTarget': dns_rec.data.nameTarget.str, 'port': dns_rec.data.wPort, 'priority': dns_rec.data.wPriority, 'weight': dns_rec.data.wWeight}
            elif dns_rec.wType == dnsp.DNS_TYPE_TXT:
                record = {'data': [name.str for name in dns_rec.data.str]}
            record.update({'type': dns_rec.wType, 'flags': dns_rec.dwFlags, 'serial': dns_rec.dwSerial, 'ttl': dns_rec.dwTtlSeconds})
            records[rec.dnsNodeName.str]['records'].append(record)
    return records
