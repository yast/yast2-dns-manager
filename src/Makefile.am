# Makefile.am for samba-internal-dns-manager

client_DATA = \
	clients/samba-internal-dns-manager.py

yncludedir = @yncludedir@/samba-internal-dns-manager
ynclude_DATA = \
	include/samba-internal-dns-manager/wizards.py \
	include/samba-internal-dns-manager/dialogs.py

desktop_DATA = \
	desktop/yast2-samba-internal-dns-manager.desktop

EXTRA_DIST = $(client_DATA) $(ynclude_DATA) $(module_DATA) $(desktop_DATA)

include $(top_srcdir)/Makefile.am.common
