#
# spec file for package yast2-samba-internal-dns-manager
#
# Copyright (c) 2019 SUSE LINUX GmbH, Nuernberg, Germany.
#
# All modifications and additions to the file contributed by third parties
# remain the property of their copyright owners, unless otherwise agreed
# upon. The license for this file, and modifications and additions to the
# file, is the same license as for the pristine package itself (unless the
# license for the pristine package is not an Open Source License, in which
# case the license is the MIT License). An "Open Source License" is a
# license that conforms to the Open Source Definition (Version 1.9)
# published by the Open Source Initiative.

# Please submit bugfixes or comments via https://bugs.opensuse.org/
#


Name:           yast2-samba-internal-dns-manager
Version:        0.1
Release:        0
Summary:        Samba Internal DNS Manager
License:        GPL-3.0-only
Group:          Productivity/Networking/Samba
Url:            http://www.github.com/yast/yast2-samba-internal-dns-manager
Source:         %{name}-v%{version}.tar.bz2
BuildArch:      noarch
Requires:       krb5-client
Requires:       samba-client
Requires:       samba-python3
Requires:       yast2
Requires:       yast2-python3-bindings >= 4.0.0
Requires:       yast2-adcommon-python
BuildRequires:  autoconf
BuildRequires:  automake
BuildRequires:  perl-XML-Writer
BuildRequires:  python3
BuildRequires:  update-desktop-files
BuildRequires:  yast2
BuildRequires:  yast2-devtools
BuildRequires:  yast2-testsuite

%description
DNS Manager for the Internal Samba Active Directory Domain Controller DNS server.

%prep
%setup -q -n %{name}-v%{version}

%build
%yast_build

%install
%yast_install

%files
%defattr(-,root,root)
%dir %{yast_yncludedir}/samba-internal-dns-manager
%{yast_clientdir}/*.py
%{yast_yncludedir}/samba-internal-dns-manager/*
%{yast_desktopdir}/samba-internal-dns-manager.desktop
%doc %{yast_docdir}
%license COPYING

%changelog
