import os
import sys

try:
    # try to use setuptools to get develop mode.
    from setuptools import setup, find_packages
    ## if we have setuptools, use find_packages:
    packages = find_packages('src')
except ImportError:
    from distutils.core import setup
    packages = ['gattai'],


NAME = 'gattai'
BUILD = '2'
VERSION = '1.0'
FULL_VERSION = '%s.%s' % (VERSION, BUILD)

PYTHON = sys.executable
PYTHON_DIR = os.path.dirname(PYTHON)

scripts = ['bin/gattai']
if sys.platform.startswith('win'):
    win_bat = """
    @echo off

    "%s" "%s" %%1 %%2 %%3 %%4 %%5 %%6 %%7 %%8 %%9
    """ % (PYTHON, os.path.join(PYTHON_DIR, "Scripts", "gattai"))

    f = open("bin/gattai.bat", "w")
    f.write(win_bat)
    f.close()

    scripts.append('bin/gattai.bat')

setup(name = NAME,
      version = FULL_VERSION,
      author = "Kevin Ollivier",
      author_email = "kevino@theolliviers.com",
      scripts = scripts,
      package_dir = { '': 'src' },
      packages = packages,
      )

