# Deprecated

*These files are deprecated and will be removed in a future release.
Please use CMake instead.*

# Project Notes

DO NOT modify project settings for each configuration and/or platform
on a per-project basis. Use property sheets to set shared configuration
properties. The rule of thumb - if you set same value for the same
property in more than one configuration or platform, you did it wrong.

## libmaxminddb.props

This is the base property sheet for libMaxMindDB project. It contains
settings that are shared between all configurations, such as compiler
warning level, not using link-time code generation, etc.

In order to minimize the number of property sheet files, this propery
sheet also contains settings for Win32 and Debug configurations, which
are overridden by the x64 and Release property sheets described below.

## libmaxminddb-release.props

This property sheet contains all Release settings and is shared between
Win32 and x64 release builds. It must be located higher than the base
property sheet in the property Manager window for each configuration
where it's used (i.e. Release|Win32 and Release|x64).

## libmaxminddb-x64.props

This property sheet contains all x64 settings and is shared between all
Debug and Release x64 configurations. It must be located higher than the
base property sheet in the property Manager window for each configuration
where it's used (i.e. Debug|x64 and Release|x64).

## Adding More Projects

If you want to add more projects into this solution, follow the same logic
and create their own property sheets. Do not use libmaxminddb property
sheets in those projects because it will interfere with their intermediate
directories. Instead, copy and rename libmaxminddb property sheets as a
starting point.

DO NOT add libmaxminddb.lib to the Additional Dependencies box of command
line tools or any other libraries you built, for that matter. This box is
only for standard Windows libraries. Instead, add libmaxminddb as a reference
to all command line tool projects. Do the same for any other library projects
you added to this solutionn.

For external 3rd-party .lib files, create a solution folder called Libraries
and add Debug, Debug64, Release, Release64 subfolders, then drag and drop all
versinos of .lib to their respective folders and use Exclude From Build in
each library file's property to assign them to the proper build confguration.
Unused libraries will be shown with a traffic stop sign in each configuration.
If you have a lot of projects, it might be easier to do this by editing .vcxproj
and .vcxproj.filters in a text editor.

# Tests

To use the tests, you must download the `libtap` and `maxmind-db` submodules.
This can be done by running `git submodule update --init --recursive` from
the Git checkout. Each test source file has a separate project. Once compiled,
the tests must be run from the base directory of the checkout.
