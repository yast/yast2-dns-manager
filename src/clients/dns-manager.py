from yast import ycpbuiltins
import sys, traceback
sys.path.append(sys.path[0]+"/../include/dns-manager")
from wizards import DNSSequence

if __name__ == "__main__":
    try:
        DNSSequence()
    except Exception as e:
        ycpbuiltins.y2error(str(e))
        ycpbuiltins.y2error(traceback.format_exc())

