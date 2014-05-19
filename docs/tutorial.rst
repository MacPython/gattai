================
 Gattai Tutorial
================

Introduction
===============

Gattai works by reading and processing JSON formatted files known as 'recipes'. These recipes contain the data needed for Gattai to download, build and install all the pieces of whatever software it is that you're building.

To "run" a recipe, invoke gattai on the command line::

  gatai the_recipe.gattai

Recipes
==========

Gattai recipes are a JSON dictionary with two main sections, a 'settings' section that is used to specify any settings you'd like to apply to all packages you're building, and 'packages', which contains a list of specific packages to build along with any specific instructions that package needs.

Let's look at an example file, a Gattai recipe for building wxWebKit dependencies, which we'll proceed to break down.

wxWebkitExample::

	{
	    'settings' : {
	        'darwin' : {
	            'archs': ['ppc', 'i386'],
	            'min-version': '10.5',
	        },
	        'install_dir': '%(RECIPEDIR)s/../../WebKitLibraries/%(PLATFORM)s',
	    },
	    'packages' : [
	    {
	        'name': 'icu',
	        'version': '3.4.1',
	        'source_dir': 'icu',
	        'build_dir': 'source',
	        'prebuild_cmds': [
	            "chmod +x '%(BLDDIR)s/configure' '%(BLDDIR)s/install-sh'",
	        ],
	        'configure_args': ['--disable-extras'],
	        'win32': {
	            'prebuild_cmds': [],
	        },
	        'source': 'ftp://ftp.software.ibm.com/software/globalization/icu/3.4.1/icu-3.4.1.tgz',
	    },
	    {
	        'name': 'libjpeg',
	        'version':'v8d',
	        'source_dir': 'jpeg-8d',
	        'source': 'http://www.ijg.org/files/jpegsrc.v8d.tar.gz',
	    },
	    {
	        'name': 'libpng',
	        'version': '1.5.9',
	        'source': 'http://sourceforge.net/projects/libpng/files/libpng15/1.5.9/libpng-1.5.9.tar.gz/download',
	    },
	    {
	        'name': 'curl',
	        'version': '7.19.6',
	        'source': 'http://curl.haxx.se/download/curl-7.19.6.tar.gz',
	    },

	    ],
	}

``settings``
-------------


In ``settings``, specific specific architectures and a min version of OS X to use are specified when building on Mac. Notice that all settings specific to one platform should be placed inside a key with the platform name. We also set an installation directory. These settings are applied to all packages. Any setting you can specify in ``settings`` can also be specified for a specific package, and always package-specific settings will override global settings.


``settings`` options
......................
The available options for settings are: (Note that these can be overidden in specific packages as well)

``install_dir``
    directory in which to install the package -- this maps to the usual 

``virtualenv``
    path to the virtual env you want to use -- for python packages, if you want to build/install into a virtualenv.

``include_dirs``

``lib_dirs``

``env_vars``
    dictionary of environment variables to set --  these are likely to go in a platform-specific settings block or package-specific block.

``project_file``
    name of project file -- use if it's not the standard "Makefile".

``format``
    format for the makefile -- options are 'msvc', 'gnumake'

``configure_args``
    list of arguments to pass to the ``./configure`` command -- the same way they ar passed on the command line : ['--disable-extras', '--with-png=\usr\local\lib']

``ignore_install_errors``
    whether to ignore install errors, 'True' or 'False' (False is default)


OS-X specific settings
.......................

settings specific to OS-X are put in the ``darwin`` section.

``archs``
    list of the the architectures you want support. options are ``ppc`` ``i386`` ``ppc64`` ``x86_64``. IN common use, these days this would be ``['i386', 'x86_64']``, or maybe one of those. These are passed to the compiler with the ``arch`` flag.

``min-version``
   minimum version of OS-X that you want to support -- this maps to MAC_OSX_DEPLOYMENT_TARGET


packages
-------------
In the packages section, we define the specific packages we want to build. Notice that for many packages, all you need to do is define the package's name, version, and the location of the source tar ball. So long as the package adheres to common conventions for directory names, makefile names, etc., Gattai will not need any extra information to build.

When there are exceptions, like in the cases of icu and libjpeg above, you simply need to provide Gattai with the information needed to build. For both packages, you need to tell it the source_dir, as it doesn't follow the typical convention most packages use. With icu, we must also tell it the subdirectory to build, as we do not build from the source directory as we do with other packages. We can also, as shown above, pass configure arguments, specify prebuild/postinstall_cmds, and other properties.

NOTE: packages are built/installed in the order you give them in the recipe -- so if one depends on the others, be sure to put them in the right order.


``packages`` options
......................

The available options for packages. (Recall that most of the setting options can be used here, and they will override the ones in ``settings``.

``ignore``
    if ignore is set to something other than "False", this package will be ignored -- helpful for testing / debugging recipes.

``name``
   name of the package

``version``
    version string for the package -- example: '1.2.1'

``exact_version_only``
    whether only that exact version will be accepted. if left out, ``version`` is considered the minimum version

``source``
    url of the source tarball or zip file (or git url). Example: ``http://netcdf4-python.googlecode.com/files/netCDF4-1.0.4.tar.gz``

``source_dir``
    name of the directory the source will be in -- this will default to the file name (without the .tar.gz or .zip) from the source url -- but if it's not the same, you can specify it here. You can also specify a source dir on your system, and if it's there, it won't try to download anything [I think]

``build_type``
    type of package this is. Options are: 'python', 'cxx' ('cxx' works for C too). default is 'cxx'


``installer_requires_admin``
    whether the installer requires admin privileges (sudo will be used if it does) -- only used with dmg installers on OS-X

``dmg``
    url of a dmg installer (OS-X only) -- it will get installed directly, rather than trying to build it.

``binary``
    url of a binary installer. example, an `*.exe` on Windows.

``installer``
     the file inside the binary package that must be run to install the package, relative to the package root. Use with "dmg" or "binary"

``install_check_cmd``
    command used to check the install -- i.e. 'make check'

``prebuild_cmds``
    list of commands to run before the build is started. Example: ``["chmod +x '%(BLDDIR)s/configure' '%(BLDDIR)s/install-sh'"]``

``postinstall_script``
    script to run after the install

``postinstall_cmds``
    list of commands to run after the install

python package settings
.........................

``easy_install``
    whether to run easy_install to install a python package.

``alt_setup.py``
    name of alternate setup.py script -- the common convention is to use "setup.py", but it could be names anything. If it has a different name, specify it with this property.

Substitutions
===============

Gattai includes a handful of handy substitution values that can be used to insert standard values into property values in a recipe. These values will be replaced by the appropriate value when the JSON is read. To use a substitution, wrap it in python style formatting spec: %(THEVALUE)s. 

Example: "include_dirs": ["%(HOMEDIR)s/Temp/include"]

ROOTDIR
    the root of the recipe -- defaults to current working dir.

HOMEDIR
    the users home directory
    
PYTHON
    the python command -- defaults to "python"

Tips for Developing Recipes
=============================


Use the ``ignore`` property
-----------------------------

Recipes often involve multiple packages as dependencies. While debugging, it can be quite annoying to have to wait for a whole bunch to build, before finding the issue at hand with one package. To force gattai to only build the ones you want to use at the moment, you can set the ``ignore`` property on all the packages you don't want built while testing.

Example::

    ...
    "packages" : [
        {
            "ignore": "TRUE",
            "name": "libpng",
            "version": "1.6.3",
    ...

Use the ``targets`` flag at the command line
----------------------------------------------

If you only want to build one, or a couple, of the packages, you can pass in the ones you want to build on the gattai command line::
    gattai --targets=a_package  a_recipe.gattai


  





