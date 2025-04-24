%global python_interp python3
%global srcname oomkiller

Name:           %{srcname}
Version:        1.0.0
Release:        2%{?dist}
Summary:        A guardian of memory space.

License:        MIT
URL:            https://github.com/marsway/oomkiller
Source:         %{srcname}-%{version}.tar.gz
Source1:        %{srcname}.conf
Source2:        %{srcname}.service

BuildArch:      noarch

BuildRequires:  %{python_interp}
BuildRequires:  %{python_interp}-pip
BuildRequires:  %{python_interp}-setuptools
BuildRequires:  systemd-units

Requires:       %{python_interp}
Requires:       %{python_interp}-psutil

Requires(post):    systemd-units
Requires(preun):   systemd-units
Requires(postun):  systemd-units

%description
%{summary}.
A guardian of memory space.

%prep
%autosetup -n %{name}-%{version} -p1

%build
%{python_interp} setup.py build

%install
%{python_interp} setup.py install --skip-build --root %{buildroot}

install -Dm 644 %{SOURCE1} %{buildroot}%{_sysconfdir}/oomkiller/%{srcname}.conf
install -Dm 644 %{SOURCE2} %{buildroot}%{_unitdir}/%{srcname}.service

%post
%systemd_post %{srcname}.service
systemctl start %{srcname}.service > /dev/null 2>&1 || :
systemctl enable %{srcname}.service > /dev/null 2>&1 || :

%preun
%systemd_preun %{srcname}.service

%postun
%systemd_postun_with_restart %{srcname}.service

%files
%exclude %{python3_sitelib}/__pycache__
%{_bindir}/%{srcname}-daemon
%{python3_sitelib}/*.egg-info
%{python3_sitelib}/%{srcname}.py
%config(noreplace) %{_sysconfdir}/oomkiller/%{srcname}.conf
%{_unitdir}/%{srcname}.service

%changelog
* Thu Apr 24 2025 Li Wei <liwei@marsway.red>- 1.0.1-1
- Initial RPM packaging