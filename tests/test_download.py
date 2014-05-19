#!/usr/bin/env python

"""
test_download.py

tests the downloading method

"""


import os, shutil, time

import gattai

def cleanup_downloads():
    """
    deletes various stuff that gets downloaded by the tests
    """

    files_to_delete = ['./py_gd-master.zip',
                       'gattai.log',
                       'junk1',
                       'junk2',
                       ]
    dirs_to_delete = ['py_gd-master',
                      'junk_dir']

    for name in files_to_delete:
        try:
            os.remove(name)
        except OSError:
            pass
    for name in dirs_to_delete:
        try:
            shutil.rmtree(name)
        except OSError:
            pass

class RecipeForTesting(gattai.GattaiRecipe):
    """
    ugly hack for a recipe that doesn't load from JSON 

    lets you test methods more easily
    
    essentially a un-initialized recipe
    """
    def __init__(self):
        pass

class DepForTesting(gattai.Dependency):
    """
    ugly hack for a Dependency that doesn't load from JSON 

    lets you test methods more easily
    
    essentially a un-initialized Dependency
    """
    def __init__(self):
        pass


def test_get_filename():
    dep = DepForTesting()

    filename = dep.get_filename_from_url("https://github.com/NOAA-ORR-ERD/py_gd/archive/master.zip")

    assert filename == "py_gd-master.zip"

def test_is_newer():
    """
    check if the modifaction time chekc works
    """
    dep = DepForTesting()

    cleanup_downloads()
    # create a couple files:
    open("junk1", 'w')
    time.sleep(1) # time delay to make sure they have a slightly different mod time.
    open("junk2", 'w')

    assert dep.is_newer("junk2", "junk1")
    assert not dep.is_newer("junk1", "junk2")

    #modify the first:
    time.sleep(1) # time delay to make sure they have a slightly different mod time.
    open("junk1", 'a').write('soemthing')

    assert not dep.is_newer("junk2", "junk1")
    assert dep.is_newer("junk1", "junk2")

    #try with directories:
    os.mkdir("junk_dir")
    assert dep.is_newer("junk_dir", "junk2")
    assert not dep.is_newer("junk2", "junk_dir")

def test_download_source():
    """
    tests that download_source ties to download a file that already exists
    """
    assert False




# def test_download_from_github():

#     url = "https://github.com/NOAA-ORR-ERD/py_gd/archive/master.zip"

#     cleanup_downloads()

#     recipe = gattai.GattaiRecipe("test_recipe.gattai")

#     dep = gattai.Dependency(recipe, recipe.deps[0])

#     dep.download_file(url)

#     assert os.path.exists('./py_gd-master.zip')

# def test_download_source_zip_github():

#     cleanup_downloads()

#     recipe = gattai.GattaiRecipe("test_recipe.gattai")

#     dep = gattai.Dependency(recipe, recipe.deps[0])

#     dep.download_source()

#     print "download_source worked"
#     assert os.path.exists("py_gd-master")







