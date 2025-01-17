Name: lua-gd
Version: 2.0.33r3
Release: 1
Summary: gd bindings for the Lua programming language
Summary(pt_BR): Bindings da biblioteca gd para a linguagem Lua
Packager: Alexandre Erwin Ittner <alexandre@ittner.com.br>
License: MIT
Group: Libraries
Group(pt_BR): Bibliotecas
Source0: %{name}-%{version}.tar.gz
URL: http://lua-gd.luaforge.net/
BuildRoot: %{_tmppath}/%{name}-%{version}-root
Requires: lua >= 5.1
Requires: libgd2 >= 2.0.33
BuildRequires: lua-devel
BuildRequires: libgd-devel >= 2.0.33
Prefix: /usr
Provides: luagd

%description
Lua-GD is a library that allows you to use the gd graphic library from
programs written in the Lua programming language.


%description -l pt_BR
Lua-GD é uma biblioteca que permite usar a biblioteca gráfica gd em
programas escritos na linguagem Lua.


%prep
%setup -q

%build
make

%install
mkdir -p $RPM_BUILD_ROOT%{_libdir}
cp *.so $RPM_BUILD_ROOT%{_libdir}

%clean
rm -rf %{buildroot} $RPM_BUILD_ROOT $RPM_BUILD_DIR/%{name}-%{version}

%post
/sbin/ldconfig

%postun
/sbin/ldconfig

%files
%defattr(-,root,root)
%doc README COPYING doc/* demos
%{_libdir}/*.so*

%changelog
* Sun Aug 28 2005 Alexandre Erwin Ittner <aittner@netuno.com.br>
- First version of this package.
* Sun Apr 30 2006 Alexandre Erwin Ittner <aittner@netuno.com.br>
- New version. License update.


