from yast import ycpbuiltins
import sys, traceback
sys.path.append(sys.path[0]+"/../include/samba-internal-dns-manager")
from wizards import DNSSequence

if __name__ == "__main__":
    try:
        DNSSequence()
    except:
        ycpbuiltins.y2error(traceback.format_exc())

