#!/usr/bin/env python

# Copyright (c) 2012, Kevin Ollivier
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met: 
# 
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer. 
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution. 
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# 
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies, 
# either expressed or implied, of the Gattai Project.

import commands
import distutils.sysconfig
import json as json_loader
import logging
import os
import subprocess
import sys
import types
import urllib
import zipfile

logging.basicConfig(level=logging.INFO)

__version__ = "1.0.1"

def get_user_home_dir():
    home = None
    if "HOME" in os.environ:
        home = os.environ["HOME"]
    elif "HOMEDRIVE" in os.environ and "HOMEPATH" in os.environ:
        home = os.environ["HOMEDRIVE"] + os.environ["HOMEPATH"]

    if home is None or not os.path.exists(home):
        logging.warning("Unable to determine the home directory on this system. Some operations may fail.")
    return home

from distutils.dep_util  import newer

script_dir = os.path.abspath(os.path.dirname(__file__))

GATTAI_DIR = script_dir

import builder
    
deps_builder = None
        
# Dependency JSON format:
# A liar of dependencies ordered in the proper order needed to build the project
# These should be listed in the proper build order

def perform_substitutions(value, subs=locals()):
    if isinstance(value, dict):
        for key in value:
            value[key] = perform_substitutions(value[key], subs)
    elif isinstance(value, list):
        result = []
        for item in value:
            result.append(perform_substitutions(item, subs))
        return result
    elif isinstance(value, str) or isinstance(value, unicode):
        return value % subs
    return value

def run_in_venv(venv_dir, cmd):
    activate_script = None
    if os.path.exists(venv_dir):
        activate_script = os.path.join(venv_dir, "bin", "activate")
        win = sys.platform.startswith('win')
        if win:
            activate_script = os.path.join(venv_dir, "Scripts", "activate.bat")
        
    final_cmd = cmd
    if activate_script is not None and os.path.exists(activate_script):
        final_cmd = "%s && %s" % (activate_script, cmd)
        if not win:
            final_cmd = "source %s" % final_cmd

    logging.info("Running command: %s" % final_cmd)
    return subprocess.call(final_cmd, shell=True)
    
class Dependency(object):
    def __init__(self, recipe, props):
        """
        This class manages build dependencies. The basic design goal behind
        this class is that it will contain first a common 'recipe' that performs
        the most common build steps, but can be subclassed for dependencies
        needing custom operations.
        
        """
        
        self.recipe = recipe
        self.name = props['name']
        self.props = props
        self.platform_props = {}
        if sys.platform in self.props:
            self.props.update(self.props[sys.platform])
            
        self.SRCDIR = self.source_dir().replace('\\', '/')
        self.BLDDIR = self.build_dir().replace('\\', '/')
        
    def source_dir(self, dir=None):
        if dir is None:
            dir = self.recipe.ROOTDIR
        fullname = "%s-%s" % (self.name, self.props['version'])
        default = os.path.join(dir, fullname)
        result = self.get_prop('source_dir', default=default, perform_substitutions=False)

        source = self.abs_path_for_path(result)
        # source_dir is not guaranteed to exist, so if no paths exist, we should return
        # a path relative to dir. However, if a path does exist relative to the recipe dir
        # we return that instead.
        recipe_dir = os.path.dirname(self.recipe.filename)
        for name in [fullname, self.name]:
            fullpath = os.path.join(recipe_dir, name)
            if os.path.exists(fullpath):
                source = fullpath
        
        return source
        
    def abs_path_for_path(self, filename, dir=None):
        if dir is None:
            dir = self.recipe.ROOTDIR
        source = os.path.abspath(filename)
        if not os.path.exists(source):
            source = os.path.join(dir, filename)
        
        # In addition to checking for it in the root dir, check the recipe dir too
        recipe_dir = os.path.dirname(self.recipe.filename)
        if not os.path.exists(source):
            source = os.path.join(recipe_dir, filename)
            
        # if we can't find the file anywhere, just return the abspath of the file passed in.
        if not os.path.exists(source):
            source = os.path.abspath(filename)
        
        return source

    def build_dir(self, dir=None):
        if dir is None:
            dir = self.recipe.ROOTDIR
        result = self.get_prop('build_dir', default=self.source_dir(dir), perform_substitutions=False)
        abspath = os.path.abspath(result)
        if os.path.exists(abspath):
            return abspath
        else:
            return os.path.abspath(os.path.join(self.source_dir(dir), result))

    def get_filename_from_url(self, url):
        """
        figures out the filename of the file that will be downlaoed by a url

        usually obvious, but there are some special cases
        """
        filename = url.split("/")[-1]
        if filename == 'download': # special SF.net hack
            filename = url.split("/")[-2]
        elif 'github.com' in url and 'archive' in url: #special github hack
             url_parts = url.split("/")
             filename = url_parts[-3]+'-'+ url_parts[-1]      

        # strip off any args after the name.
        filename = filename.split("#")[0]

        return filename


    def download_file(self, url, dir=None):
        if dir is None:
            dir = self.recipe.ROOTDIR
        filename = self.get_filename_from_url(url)

        dirname = os.path.dirname(os.path.abspath(filename))

        logging.debug("Dirname = %s" % dirname)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        try:
            # FIXME: Write a download callback handler that shows progress
            logging.info("File for %s not found, downloading from %s, this may take time..." % (self.name, url))
            class MyURLopener(urllib.FancyURLopener):
                def http_error_default(self, url, fp, errcode, errmsg, headers):
                    # handle errors the way you'd like to
                    logging.error("Error downloading file.")
                    logging.error("Error code: %r" % errcode)
                    logging.error("Error message:")
                    logging.error(errmsg)
                    raise Exception("Unable to download file.")
            MyURLopener().retrieve(url, filename=filename)
        except:
            logging.error("Unable to download file for dependency.")
            sys.exit(1)
        if not os.path.exists(filename):
            logging.error("Unable to find downloaded file %s" % os.path.abspath(filename))
            sys.exit(1)
        return filename

    def valid_version(self, version_str):
        valid = False
        req_version = self.get_prop('version')
        needs_exact_match = self.get_prop('exact_version_only')
        if version_str == req_version or version_str.find(req_version) != -1:
            valid = True
        elif not needs_exact_match:
            version_tuple = version_str.split('.')
            req_version_tuple = req_version.split('.')
            # Future major versions are sometimes not compatible, so we will only accept
            # exact matches for the major version for now.
            # Also, use a try block so that if the version isn't purely numbers,
            # we will just gracefully fail the check.  
            try:
                if int(version_tuple[0]) == int(req_version_tuple[0]):
                    if int(version_tuple[1]) > int(req_version_tuple[1]):
                        valid = True
                    elif int(version_tuple[1]) == int(req_version_tuple[1]):
                        valid = (int(version_tuple[2] >= int(req_version_tuple[2])))
            except:
                logging.warning("Unable to compare versions for %r." % self.name)
                logging.warning("Assuming incompatible version.")
        return valid
    
    def is_newer(self, path1, path2):
        """
        compared the mod time of the two files or directories

        returns true if the mod time of filename1 is newer than the modtie mof filename2

        used to see if somethign need to re-built, etc.

        FIXME: maybe no point -- I though this might get more complicated!
        """
        t1 = os.path.getmtime(path1)
        t2 = os.path.getmtime(path2)
        return t1 > t2


    def installed(self):
        is_installed = False
        cmd_version = None
        check_cmd = self.get_prop('install_check_cmd')
        if check_cmd:
            return subprocess.call(check_cmd) == 0
        else:
            name = self.get_prop('name')
            if self.get_prop('program_name'):
                name = self.get_prop('program_name')
            version = self.get_prop('version')
            if self.get_prop('build_type') == 'python':
                try:
                    cmd_version = subprocess.check_output('python -c "import %s; return %s.__VERSION__"')
                except:
                    pass
            
            cmds = [
                        [name, '--version'],
                        ['%s-config' % name, '--version'],
                        ['pkg-config', '--version', name],
                    ]
            
            for cmd in cmds:
                try:
                    cmd_version = subprocess.check_output(cmd)
                    break
                except:
                    pass
        
        if cmd_version is not None:
            is_installed = self.valid_version(cmd_version)
        return is_installed
            
    def run_installer(self, dir=None):
        if dir == None:
            dir = self.recipe.ROOTDIR
        filename = None
        result = False
        dmg = self.get_prop('dmg')
        binary = self.get_prop('binary')
        if dmg:
            filename = self.download_file(dmg)
            logging.info("Downloaded disk image to %s" % filename)
            if not filename:
                return False
            cmd = 'hdiutil mount %s' % os.path.abspath(filename)
            logging.info("Running %s" % cmd)
            status, output = commands.getstatusoutput(cmd)
            if status == 0:
                lines = output.split('\n')
                last_line = lines[-1].split('\t')
                logging.info(last_line)
                mountpoint = last_line[0].strip()
                volume = last_line[2].strip()
                installer = os.path.join(volume, self.get_prop('installer'))
                sudo = ''
                if self.get_prop('installer_requires_admin', False):
                    sudo = 'sudo '
                result = run_in_venv(self.recipe.ROOTDIR, sudo + '/usr/sbin/installer -verbose -pkg "%s" -target /' % installer) == 0
                run_in_venv(self.recipe.ROOTDIR, 'hdiutil detach %s -force' % mountpoint)
                logging.info("Installer is %s" % installer)
            else:
                logging.error("Unaable to mount disk image. Error message is:")
                logging.error(output)
                return False
        elif binary:
            filename = self.download_file(binary)
            if not filename:
                return False
            if sys.platform.startswith('win'):
                result = run_in_venv(self.recipe.ROOTDIR, filename)
                if result != 0:
                    return False
            else:
                status, output = commands.getstatusoutput(filename)
                if status != 0:
                    return False
        else:
            logging.error("Could not find disk image or executable for binary package.")
            return False
        return True
        
    def download_source(self, dir=None):
        if dir is None:
            dir = self.recipe.ROOTDIR
        if self.get_prop('source'):
            filename = self.get_filename_from_url(self.get_prop('source'))
            if not os.path.exists(filename):
                filename = self.download_file(self.get_prop('source'))
            
            self.extract_archive(filename)
            if filename is None:
                return

    def extract_archive(self, filename):
        """
        extracts the given archive -- usually used for source archives.

        supports zip, tar, gz, bz2

        """
        base, ext = os.path.splitext(filename)
        format = 'zip'
        if base.endswith('.tar') or ext == '.tgz':
            if ext == '.gz' or ext == '.tgz':
                format = 'tar.gz'
            elif ext == '.bz2':
                format = 'tar.bz2'
            else:
                format = 'tar'
        else:
            format = ext[1:]
        
        if format.startswith('tar'):
            mode = 'r'
            if format.endswith('gz'):
                mode += ':gz'
            elif format.endswith('bz2'):
                mode += ':bz2'
                            
            import tarfile
            tarball = tarfile.open(filename, mode=mode)
            tarball.extractall()
        elif format == 'git':
            run_in_venv(self.recipe.ROOTDIR, 'git clone %s %s-%s' % (self.get_prop('source'), self.name, self.get_prop('version')))
        elif format == 'zip':
            zip = zipfile.ZipFile(filename)
            zip.extractall()


    def source_exists(self, dir=None):
        """
        Checks whether an unpacked source or binary version of the dependency
        exists in the given location
        """
        if dir is None:
            dir = self.recipe.ROOTDIR
        dirname = self.source_dir(dir)
        if os.path.exists(dirname) and os.path.dirname(dirname):
            return True
        else:
            self.download_source(dir)
        
        dirname = self.source_dir(dir)
        # run the test again after attempting to download
        if not os.path.exists(dirname) or not os.path.dirname(dirname):
            logging.error("Unable to locate directory %s" % dirname)
            logging.error("Could not find or retrieve %s" % self.name)
            if 'optional' in self.props and self.props['optional'] == True:
                return False
            else:
                sys.exit(1)
                
        return True

    def perform_substitutions(self, value, dir=None):
        if dir is None:
            dir = self.recipe.ROOTDIR
        BLDDIR = self.BLDDIR
        SRCDIR = self.SRCDIR
        ROOTDIR = dir
        HOMEDIR = get_user_home_dir()
        PYTHON = self.recipe.PYTHON

        return perform_substitutions(value, locals())

    def build(self, dir=None, args=[]):
        """
        Build the software, which is located in the specified base dir.
        """
        if dir is None:
            dir = self.recipe.ROOTDIR
            
        self.SRCDIR = self.source_dir(dir).replace('\\', '/')
        self.BLDDIR = self.build_dir(dir).replace('\\', '/')

        env_vars = {}
        if 'env_vars' in self.recipe.settings and self.recipe.settings['env_vars'] is not None:
            env_vars.update(self.recipe.settings['env_vars'])
        
        if 'env_vars' in self.props:
            env_vars.update(self.props['env_vars'])
        
        old_env = {}
        for env in env_vars:
            env_value = env_vars[env]
            if env in os.environ:
                old_env[env] = os.environ[env]
                
            for key in os.environ:
                # do env substitutions
                if sys.platform.startswith('win'):
                    env_value = env_value.replace('%' + key + '%', os.environ[key])
                else:
                    env_value = env_value.replace('$' + key, os.environ[key])
            env_value = self.perform_substitutions(env_value)
            
            os.environ[env] = env_value

        if not "clean" in args:
            if self.installed(): # if we're already installed and using proper version, exit
                logging.info("%s is installed and up-to-date, skipping..." % self.get_prop('name'))
                return True

        if self.get_prop('ignore', False):
            logging.info("Ignoring %s"%self.props['name'])
            return True

        needs_built = True
        success = True
        if not 'clean' in args and self.get_prop('installer'):
            logging.info("Running installer...")
            success = self.run_installer(dir)
            needs_built = False
            
        if self.get_prop('easy_install'):
            logging.info("Running easy_install...")
            success = self.run_easy_install(args)
            needs_built = False
        
        if needs_built and not self.source_exists(dir):
            logging.error("Source not found.")
            return False

        olddir = os.getcwd()
        if needs_built:
            os.chdir(self.SRCDIR)

        pre_cmds = []
        if not "clean" in args: 
            pre_cmds.extend(self.get_prop('prebuild_cmds', default=[]))
        
        for cmd in pre_cmds:
            if sys.platform.startswith('win'):
                cmd = cmd.replace('/', '\\\\')
            if cmd.startswith('cd '):
                os.chdir(cmd.replace('cd ', ''))
            elif run_in_venv(self.recipe.ROOTDIR, cmd) != 0:
                logging.error("pre-build command '%s' failed, exiting..." % cmd)
                sys.exit(1)


        if needs_built:
            logging.info("Building %s" % self.get_prop('name'))
            build_type = 'cxx'
            if 'build_type' in self.props:
                build_type = self.props['build_type']

            success = eval("self.%s_build(dir, args=args)" % build_type)
        
        if success:
            olddir2 = os.getcwd()
            if needs_built:
                os.chdir(self.SRCDIR)
            success = self.postinstall(dir, args)
            os.chdir(olddir2)
            
        for env in old_env:
            os.environ[env] = old_env[env]

        os.chdir(olddir)
        return success

    def postinstall(self, dir=None, args=[]):
        if dir is None:
            dir = self.recipe.ROOTDIR
        
        post_cmds = []
        script_filename = None
        if not "clean" in args:
            script_filename = self.get_prop('postinstall_script', default=None)
            if script_filename is None:
                post_cmds.extend(self.get_prop('postinstall_cmds', default=[]))
        
        if script_filename is not None:
            filename = self.abs_path_for_path(script_filename)
            if os.path.exists(filename):
                script = open(filename, 'r').read()
                script = self.perform_substitutions(script)
                exec(script)
        
        for cmd in post_cmds:
            if cmd.startswith('cd '):
                os.chdir(cmd.replace('cd ', ''))
            elif run_in_venv(self.recipe.ROOTDIR, cmd) != 0:
                logging.error("'%s' failed, exiting..." % cmd)
                sys.exit(1)

        return True
        
    def get_prop(self, propname, default=None, perform_substitutions=True):
        """
        For string properties, we return the highest priority override, starting from platform-specific
        local, and finally returning cross-platform global.
        """
        
        result = default
        if propname in self.recipe.settings:
            result = self.recipe.settings[propname]
        if propname in self.props:
            result = self.props[propname]
        
        if result == "TRUE":
            result = True
        if result == "FALSE":
            result = False
            
        if perform_substitutions:
            result = self.perform_substitutions(result)
        return result

    def cxx_build(self, dir=None, args=[]):
        if dir is None:
            dir = self.recipe.ROOTDIR
        
        format = 'autoconf'
        if sys.platform.startswith('win'):
            format = 'msvc'
            
        format = self.get_prop('format', format)

        import builder
        dep_builder = None
        cxx_args = []
        include_dirs = [os.path.abspath(path) for path in  self.get_prop('include_dirs', default=[]) ]
        lib_dirs = [os.path.abspath(path) for path in self.get_prop('lib_dirs', default=[]) ]
        inc_flags = []
        ld_flags = []
        
        extra_cflags = []
        extra_ldflags = []
        
        project_file = None
        if format == 'msvc':
            # project file needs to be the first argument
            project_file = 'makefile.vc'
            
            if 'project_file' in self.platform_props:
                project_file = self.platform_props['project_file']

            if os.path.splitext(project_file)[1] == ".vc":
                dep_builder = builder.MSVCBuilder()
            else:
                dep_builder = builder.MSVCProjectBuilder()
        
        elif format == 'gnumake':
            project_file = self.get_prop('project_file', default=None)
            dep_builder = builder.GNUMakeBuilder()
        elif format == 'autoconf':
            dep_builder = builder.AutoconfBuilder()
    
        if format != 'msvc':
            for inc in include_dirs:
                inc_flags.append("-I%s" % inc)
            extra_cflags.extend(inc_flags)

            for ldir in lib_dirs:
                ld_flags.append("-L%s" % ldir)
            extra_ldflags.extend(ld_flags)
            
        if not dep_builder:
            logging.error("Unable to initialize dependency builder. Exiting.")
            return
        
        if 'build_args' in self.props:
            cxx_args.extend(self.props['build_args'])
        
        if 'build_args' in self.platform_props:
            cxx_args.extend(self.platform_props['build_args'])
                
        if 'clean' in args:
            logging.info("Cleaning %r" % self.name)
            dep_builder.clean(self.build_dir(dir))
        else:
            install_dir = os.path.abspath(self.get_prop('install_dir', default=os.path.abspath(dir)))
            configure_args = ['--prefix="%s"' % install_dir]
            configure_args.extend(self.get_prop('configure_args', default=[]))
            
            # Extra flags to be placed on CFLAGS and CXXFLAGS to be passed
            # through configure.  There seems to be no other way to specify
            # custom CFLAGS
            if 'extra_cflags' in self.props:
                extra_cflags.extend(self.props['extra_cflags'])
            
            if 'extra_cflags' in self.platform_props:
                extra_cflags.extend(self.platform_props['extra_cflags'])
                    
            if sys.platform.startswith('darwin'):
                archs = self.get_prop('archs', default=None)
                if archs is not None:
                    configure_args.append('--disable-dependency-tracking')
                    for arch in archs:
                        archflag = ['-arch', arch]
                        extra_cflags.extend(archflag)
                        extra_ldflags.extend(archflag)
                    
                min_version = self.get_prop('min-version', default=None)
                if min_version:
                    sdkdir = '/Developer/SDKs/MacOSX%s.sdk' % min_version
                    if os.path.exists(sdkdir):
                        extra_cflags.extend(['-isysroot', sdkdir])
                        extra_ldflags.extend(['-isysroot', sdkdir])

                    extra_cflags.append("-mmacosx-version-min=%s" % min_version)
                    extra_ldflags.append("-mmacosx-version-min=%s" % min_version)

            if not sys.platform.startswith('win'):
                cxx_args.append('CFLAGS="%s"' % ' '.join(extra_cflags))
                cxx_args.append('CXXFLAGS="%s"' % ' '.join(extra_cflags))
                cxx_args.append('LDFLAGS="%s"' % ' '.join(extra_ldflags))

            result = 0
            cxx_args.append('prefix="%s"' % install_dir)
            sdir = self.build_dir(dir)
            dependencies = [ os.path.join(sdir, 'Makefile.in'),
                os.path.join(sdir, 'configure'),
            ]
            if project_file is not None:
                dependencies.append(os.path.join(sdir, project_file))
            for dep in dependencies:
                makefile = os.path.join(sdir, "Makefile")
            if True: # not os.path.exists(dep) or not os.path.exists(makefile) or newer(dep, makefile):
                final_args = []
                for a in configure_args + cxx_args:
                    final_args.append(self.perform_substitutions(a))
                result = dep_builder.configure(self.build_dir(dir), options=final_args)
            
            if result == 0:
                logging.debug("Project file: %r" % project_file)
                result = dep_builder.build(self.build_dir(dir), projectFile=project_file, options=cxx_args)
            if result == 0:
                inst_result = dep_builder.install(self.build_dir(dir), projectFile=project_file, options=cxx_args)
                # sometimes there are expected errors that can be ignored, so handle that case here.
                if not self.get_prop('ignore_install_errors', default=False):
                    result = inst_result
            
            if result != 0:
                if 'optional' in self.props and self.props['optional'] == True:
                    return False
                else:
                    sys.exit(1)
        
        return True
    
    def run_easy_install(self, args=[]):
        easy_install = self.get_prop('easy_install', default=None)
        if easy_install:
            if 'clean' in args:
                return run_in_venv(self.recipe.ROOTDIR, 'easy_install -m %s' % self.name)
            else:
                return run_in_venv(self.recipe.ROOTDIR, 'easy_install %s' % easy_install)
    
    def python_build(self, dir=None, args=[]):
        if dir is None:
            dir = self.recipe.ROOTDIR
        setup_cmd = self.get_prop('alt_setup.py', default='setup.py')
        py_args = [self.recipe.PYTHON, setup_cmd]
        
        if 'clean' in args:
            py_args.append('clean')
        else:
            py_args.extend(['build', 'install'])

        py_args.extend(self.get_prop('build_args', default=[]))
            
        return run_in_venv(self.recipe.ROOTDIR, ' '.join(py_args)) == 0

class GattaiRecipe(object):
    def __init__(self, filename):
        self.json = json_loader.load(open(filename))
        self.settings = self.json['settings']
        if sys.platform in self.settings:
            self.settings.update(self.settings[sys.platform])
        self.deps = self.json['packages']
        self.filename = os.path.abspath(filename)
        
        self.ROOTDIR = os.getcwd()
        self.PYTHON = 'python'
        self.HOMEDIR = get_user_home_dir()
        
        self.setup_venv()
        fh = logging.FileHandler('gattai.log')
        logging.getLogger().addHandler(fh)
        
        for setting in self.settings:
            sub_value = self.perform_substitutions(self.settings[setting])
            self.settings[setting] = sub_value

    def perform_substitutions(self, value):
        ROOTDIR = self.ROOTDIR
        PYTHON = self.PYTHON
        HOMEDIR = self.HOMEDIR
        
        return perform_substitutions(value, locals())

    def setup_venv(self):
        venv = None
        setting_name = "virtualenv"
        if setting_name in self.settings:
            venv = self.perform_substitutions(self.settings[setting_name])
        
        if venv is not None:
            if not os.path.exists(venv):
                root = distutils.sysconfig.PREFIX
                result = subprocess.call(['virtualenv', venv])
                if result != 0:
                    logging.error("ERROR: Unable to set up virtualenv. Exiting...")
                    sys.exit(1)
    
            self.ROOTDIR = venv
            logging.info("ROOTDIR = %s" % self.ROOTDIR)
            os.chdir(venv)
        else:
            # if they're not using a virtualenv, or the user has set one up themselves,
            # make sure we use whatever python they chose to run the scripts instead
            logging.info("No virtualenv set.")
            self.PYTHON = sys.executable
        
        return venv

    def list_targets(self):
        return ", ".join( [dep["name"] for dep in self.deps] )
        
    def build_deps(self, targets=["all"], arguments=[]):
        if sys.platform.startswith("win"):
            has_nmake = False
            try:
                has_nmake = subprocess.call(['nmake', '/?'], stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0
            except:
                pass
        
            if not has_nmake:
                logging.error('Cannot run nmake, have you run "%VS90COMNTOOLS%vsvars32.bat"?')
                sys.exit(1)
    
        for dep in self.deps:
            builder = Dependency(self, dep)
            args = []
            action = "Getting"
            target_name = builder.name + '-' + builder.props['version']
            if dep["name"] in targets or "all" in targets:
                if 'clean' in arguments:
                    args.append('clean')
                    action = "Cleaning"
            
                logging.info(action + " %s" % target_name)
                if not builder.build(args=args):
                    logging.error("Build failed for %s. Exiting..." % builder.name)
                    sys.exit(1)
            else:
                logging.info("Skipping %s" % target_name)

if __name__ == '__main__':
    main()
    

