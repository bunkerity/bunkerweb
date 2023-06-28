Nginx Auto Lib Core
===================

Nginx Auto Lib Core is a generic external library-handler that has been designed to
facilitate the inclusion of external libraries in modules for the Nginx web server.
It has been written both for the benefit of Nginx module developers and for the end
users of those Nginx modules, and can provide a consistent, intelligent, flexible
cross-platform way to include external libraries.

Any developers of Nginx modules are encouraged to use Auto Lib Core to handle library
dependencies for their modules rather than writing their own custom handler from scratch.

Note : The latest version can be found [here](https://github.com/simplresty/ngx_auto_lib).


Information for end users
=========================

To include external libraries using Auto Lib to you may need or wish to export some
variables before you run configure. e.g.

$ export MOZJS=/path/to/mozjs
$ export MOZJS_SHARED=NO
$ ./configure ...

In all cases below [PFX] should be replaced with the name of the library (e.g. MOZJS). The
specific value for [PFX] should be mentioned in the README file for the module that
uses Auto Lib Core.


Search order for paths
----------------------

(1) [PFX]_INC and [PFX]_LIB
(2) [PFX] (source or install dir)
(3) any dirs under [PFX]_BASE (see below)
(4) any dirs under the parent directory of the Nginx source dir beginning with '[pfx]-'
(5) standard system paths (including /usr/local, /usr, /opt/local, /opt, /usr/pkg)

If any of 1-3 are specified, then any set values will be searched, and the the Nginx
source's parent directory and system paths are not searched unless [PFX]_SEARCH_[PLACE]
variable is set to YES, where PLACE ::= PARENT | SYSTEM. e.g.

$ export OPENSSL_LIB=/path/to/openssl/lib
$ export OPENSSL_INC=/path/to/openssl/inc
$ ./configure

will search only in the lib and include paths specified, and

$ export OPENSSL_LIB=/path/to/openssl/lib
$ export OPENSSL_INC=/path/to/openssl/inc
$ export OPENSSL_BASE=/path/to/openssl/base
$ export OPENSSL_SEARCH_PARENT=YES
$ ./configure --with-openssl=/path/to/openssl

will search first in the lib & inc dirs specified, then in /path/to/openssl, then will
look for directories in /path/to/openssl/base and then in the Nginx source parent
directory, but will skip checking the system paths.

Note : apart from system paths, all dirs are checked as both source and install directories,
so static versions of installed OpenSSL, PCRE, Zlib etc libraries can be used with Nginx
if desired.


Specifying a path to find a library
-----------------------------------

If the version of a library you wish to include is in any of the standard paths (e.g.
/usr/local, /usr ...), you will not need to specify a path to include the library.

If you do wish to specify a specific path, in most cases just specifying
[PFX]=/path/to/library will be sufficient. e.g.

$ export MOZJS=/path/to/mozjs
$ ./configure ...

The path can be either a source directory or an install directory. Auto Lib will search


Searching under base paths
--------------------------

Rather than specifying a specific path to find new libraries in non-standard locations,
you may wish to specify a base path (or just let Auto Lib search the directory that the
Nginx source is located in). This will then automatically find the most recent versions
of libraries and check them before older versions.

e.g.

You have installations

/openssl/version/0.9.8m
/openssl/version/1.0.0a
...

$ export OPENSSL_BASE=/openssl/version
$ ./configure ...

Any directories under /openssl/version will be searched IN REVERSE ORDER, i.e. most recent
version first. Here /openssl/version/1.0.0a would be searched before /openssl/version/0.9.8m.

If [PFX]_BASE_SEARCH_PREFIX=YES, then only directories beginning with '[pfx]-' are searched.
If [PFX]_BASE_SEARCH_PREFIX=something, then only directories beginning with 'something' are
searched.

When searching under [PFX]_BASE no prefix is added to the search, but when searching under
the directory that the Nginx source is located in, the prefix [pfx]- is automatically added.

Note : there is currently a minor bug (due to the implementation of the 'sort' command)
means versions that include hyphens (e.g. 1.0.0-beta5) are checked before versions like
1.0.0a. This will be fixed soon, and searching of -build folders before normal source ones
will be added too.



Shared or static?
-----------------

The default for most libraries is to look for shared libraries, though this can be overridden
by the user by setting [PFX]_SHARED=NO.

In the near future the default action will be to look for shared libraries then to look
for static libraries in each directory searched unless one of [PFX]_SHARED and/or
[PFX]_STATIC = NO. If both are set to NO, then Auto Lib will not be used at all.



Variables that users can set to help find libraries
---------------------------------------------------

[PFX]                   Location of dir where the library can be found      (PATH, see below)
[PFX]_INC               Include dir for library headers                     (PATH)
[PFX]_LIB               Lib dir for library archive/shared objects          (PATH)
[PFX]_BASE              Base dir under which to search for other dirs       (PATH)
[PFX]_SEARCH_LIB_INC    Search in [PFX]_INC and [PFX]_LIB if set            (YES|NO, def=YES)
[PFX]_SEARCH_DIR        Search [PFX] if set                                 (YES|NO, def=YES)
[PFX]_SEARCH_BASE       Search under [PFX]_BASE if set                      (YES|NO, def=YES)
[PFX]_SEARCH_PARENT     Search under the dir that the Nginx source is in    (YES|NO, see above)
[PFX]_SEARCH_SYSTEM     Search in standard system paths                     (YES|NO, see above)
[PFX]_SHARED            Use shared library rather than static               (YES|NO, def=YES)
[PFX]_SYSTEM_DIRS       System dirs to search in (PATHS, space-separated, overrides the defaults)
USE_[PFX]               Whether or not to install the library               (YES|NO, def=YES)


Note : for libraries that have configure options (e.g. --with-openssl=/path), the [PFX]
variable is set automatically by configure, so will not be used if exported.



Information for module developers
=================================

How Auto Lib Core works
-----------------------

Auto Lib Core works as an interface layer between the module and the auto/feature part of
the Nginx source. This is the file that results in the 'checking for ...' lines that you
see when you call ./configure.

auto/feature works by using a few key variables (see below) to generate some C code, trying
to compile it to see if it works and optionally running the code. This output file is called
autotest.c (located under the objs/ directory whilst configure is running, but is deleted
after each call to auto/feature).

Normally, whenever an external library is required, a module developer will write a number
of calls to auto/feature manually in their config files - e.g. to check under a range of
different possible locations to find a library. Apart from being tedious, this is obviously
potentially error-prone.

Auto Lib Core will automatically generate all the calls to auto/feature for you, and will
take into account different operating systems etc in a consistent way, 'intelligent' way.


Including Nginx Auto Lib Core with custom modules
-------------------------------------------------

Option 1 :

- include ngx_auto_lib_core in the same directory that your module config file is
  located
- add the following line to your config file

  . $ngx_addon_dir/ngx_auto_lib_core

NOTE : if you want to include the file in a different directory to your config
file, you will need to change both the include line in your config file AND
the line in the ngx_auto_lib_core file that points to the file (it's the line that
has $ngx_addon_dir/ngx_auto_lib_core in it)

Option 2 :

- make the Nginx Development Kit (github.com/simpl-it/ngx_devel_kit) a dependency
  for your module (Auto Lib Core is included automatically with it)


Recommended way of including Auto Lib Core
------------------------------------------

If the Nginx Development Kit (NDK) is already a dependency for your module, then you do
not need to do anything - just follow the 'using Auto Lib Core' instructions below.

If the NDK is not a dependency for your module, then it is recommended to include a
copy of ngx_auto_lib_core with your module, but to recommend to users of your module
to include the NDK when compiling. If the module is not required for anything else, this
will not make any difference to the Nginx binary that they compile, but will mean they
will get the latest version of Auto Lib Core (which probably won't change much anyway,
but you never know).

You will also probably want to include a copy of this readme file for Auto Lib Core
(at least the user section), and mention what the relevant [PFX] you use for your module
is in your module's readme file so that users will know what to write for any variables
that they might use to control the search paths for libraries (see above user section).


Using Auto Lib Core
-------------------

To use Auto Lib Core, you should do the following in your config file for each
external library that you want to include :

1 - Call ngx_auto_lib_init
2 - Define any variables used for testing
3 - Define any hooks (custom functions)
4 - Call ngx_auto_lib_run


Calling ngx_auto_lib_init() and ngx_auto_lib_run()
--------------------------------------------------

You can pass either one or two variables to ngx_auto_lib_init(). The first is the name of
the library as it will appear when running ./configure, the second is the prefix that is
used for internal variables and looking for directory prefixes. If the second is not
specified, it defaults to the first.

The init function resets all key variables and functions, so it must be called before
setting any other variables or functions that are to be used as hooks (see the notes below).

ngx_auto_lib_run() should be called in the config files after all the variables and hooks
have been defined. This will then run through all the tests to try to find the external
library.


Variables you can set in your config files
------------------------------------------

All the variables that you set in Auto Lib Core are similar to the ones you set for
including libraries in the normal way.

       name                           description
----------------------------------------------------------------------------------------

core variables (i.e. the ones in the core Nginx source)

ngx_feature_inc_path                CFLAGS and include path info (including -I)
ngx_feature_incs                    Include/define code inserted before main() in autotest.c
ngx_feature_libs                    External libraries to add (see below)
ngx_feature_path                    Space-separated include path
ngx_feature_run                     Whether to run the autotest binary (default = no)
ngx_feature_test                    C-code inserted inside main() in autotest.c

extended variables (only work in NALC) :

ngx_feature_add_libs                Add libraries (but do not add include files)
ngx_feature_add_path                Add extra directories to include path
ngx_feature_build_dirs              Sub dirs that builds might be found
ngx_feature_build_inc_dirs          Sub dirs that include files might be found
ngx_feature_build_lib_dirs          Sub dirs that lib files might be found
ngx_feature_check_macros_defined    Lib required only if one of these macros is defined
ngx_feature_check_macros_non_zero   Lib required only if one of these macros is non-zero
ngx_feature_defines                 Define these macros if the library is found
ngx_feature_deps                    Deps to add (e.g. to CORE_DEPS) if the library is found
ngx_feature_exit_if_not_found       Quit configure if the library is not found
ngx_feature_haves                   Set these macros to 1 if the library is found
ngx_feature_inc_names               Names for include files (not including the .h)
ngx_feature_lib_files               Add these files under the lib dir for static inclusions
ngx_feature_lib_names               Names for lib files (not including -l or .a)
ngx_feature_modules                 Modules to add if the library is found
ngx_feature_srcs                    Sources to add (e.g. to ADDON_SRCS) if the lib is found
ngx_feature_shared                  If set to 'no', then only use static lib versions
ngx_feature_test_libs               Add these libs when testing, but not to the final binary
ngx_feature_variables               Set these variables if the library is found

standard variables that are completely over-written (i.e. they won't work with NALC) :

ngx_feature_name                    Message that is displayed after 'checking for' in configure


Using these variables
---------------------

You do not need to set most of these variables, since 'intelligent' guesses are made that
will work for most cases. With the exception of ngx_feature_test, you should generally use
the extended variables rather than the core ones, since sensible core variables will be
automatically generated from them, and will work for both static and shared libraries.


Variable defaults
-----------------

ngx_feature_incs            for i in $ngx_feature_inc_names { #include <$i.h> }
ngx_feature_libs            for l in $ngx_feature_lib_names { -l$l or $LIB/lib$l.a }
                            + $ngx_feature_add_libs
ngx_feature_inc_names       $ngx_feature_lib_names
ngx_feature_lib_names       $pfx
pfx                         str_to_lower (if two variables are passed to ngx_auto_lib_init, then
                            then $2, otherwise, $1)

The easiest way to understand how all the defaults work is probably to look at the source code
of ngx_auto_lib_test_setup() and to look at the examples in the standard Nginx Auto Lib module
which has code for OpenSSL, PCRE, Zlib, MD5 and SHA1.


Hooks
-----

To facilitate using Auto Lib Core in a flexible way, a number of 'hooks' have been
placed in the testing cycle. These hooks are implemented as functions that you define
in your config file which are called if required by the core library. In the core
library they are left as empty functions that return either 0 or 1. Any functions
you write will

Note : ngx_auto_lib_init() resets the variables and functions each time it is called, so
you must DEFINE HOOKS AFTER YOU CALL ngx_auto_lib_init.

Note : an update on what hooks are available will be added later. To see what hooks are
available, just look in the source code of ngx_auto_lib_core for any functions that just
return 0 or 1.

See the MD5 and SHA1 libraries of Nginx Auto Lib module for examples.



Checking that a library is required
-----------------------------------

Although in most cases Auto Lib Core will be used where external libraries are
definitely required (for a module to work), this may not always be the case. In the
standard Nginx Auto Lib module (github.com/simpl-it/ngx_auto_lib) - which is designed
to improve the inclusion of OpenSSL, PCRE and Zlib libraries and increase compilation
speed where possible - the libraries are not always required, so checks are made to
see if it is necessary.



How Auto Lib Core checks if a library is required - ngx_auto_lib_check_require()
------------------------------------------------------------------------------------

- search for USE_[PFX]=YES (it is set to YES by default for most modules)
- search for any external libraries that have been included in the CORE_LIBS or ADDON_LIBS
  variables that use the same lib name as any set in ngx_feature_lib_names
- search for any macros that have been defined either in the CFLAGS variable or using
  auto/have or auto/define as set in the ngx_feature_check_macros_defined and
  ngx_feature_ngx_macros_non_zero variables
- any custom checks implemented by creating an ngx_auto_lib_check hook function (which
  should return 0 if the library is required and return 1 at the end if the module is
  not required)



Guaranteeing that the correct version of a shared library is linked at run time
-------------------------------------------------------------------------------

Sometimes users will want to use shared libraries that are in non-standard locations
that the linker may have a problem in locating at run time - even if the correct
linker path (-L/path/to/lib) is supplied when checking. To make sure that the linker
can find the library at run time, and to make sure that the linker will use the correct
version of a library if the library is also located in a standard directory, a run path
is added to the linker flags (using -Wl,--rpath -Wl,/path/to/lib/dir). In most cases this
will guarantee that the correct library is used when linking - though care should be taken
by any users specifying specific paths for libraries that the correct version of the
library has been linked at run time (e.g. using ldd etc).

As an additional check when running auto/feature, as well as the compilation of the
autotest.c file, a check is made by ldd to see that the path of the shared library
that the linker links to is the same as the one specified. This is done because


To do
-----

- Change how library paths are searched to include both shared and static libraries
- Touch up documentation


License
-------

    BSD


Copyright
---------

    [Marcus Clyne](https://github.com/mclyne) (c) 2010
