#!/usr/bin/env python

"""
create a talos.zip appropriate for testing
"""

import os
import re
import shutil
import subprocess
import sys
import tarfile
import urllib2
import zipfile

# globals
here = os.path.dirname(os.path.abspath(__file__))
dest = os.path.join(here, 'talos')

# mozbase dependencies
mozbase_src = 'https://raw.github.com/mozilla/mozbase/master/'
mozbase_files = [('mozhttpd/mozhttpd/mozhttpd.py', 'mozhttpd.py'),
                 ('mozhttpd/mozhttpd/iface.py', 'iface.py'),
                 ('mozinfo/mozinfo/mozinfo.py', 'mozinfo.py'),
                 ('mozdevice/mozdevice/__init__.py', 'mozdevice/__init__.py'),
                 ('mozdevice/mozdevice/devicemanager.py', 'mozdevice/devicemanager.py'),
                 ('mozdevice/mozdevice/devicemanagerADB.py', 'mozdevice/devicemanagerADB.py'),
                 ('mozdevice/mozdevice/devicemanagerSUT.py', 'mozdevice/devicemanagerSUT.py'),
                 ('mozdevice/mozdevice/droid.py', 'mozdevice/droid.py')]
mozbase = [(mozbase_src + src, destination) for src, destination in mozbase_files]

# PyYAML dependency
yaml_src = 'http://pyyaml.org/export/360/pyyaml/trunk/lib/yaml/'
yaml_files = ['composer.py',
              'constructor.py',
              'cyaml.py',
              'dumper.py',
              'emitter.py',
              'error.py',
              'events.py',
              '__init__.py',
              'loader.py',
              'nodes.py',
              'parser.py',
              'reader.py',
              'representer.py',
              'resolver.py',
              'scanner.py',
              'serializer.py',
              'tokens.py']
yaml = [(yaml_src + f, 'yaml/%s' % f) for f in yaml_files]

# simplejson dependency:
# https://bugzilla.mozilla.org/show_bug.cgi?id=744405
simplejson_src = 'https://raw.github.com/simplejson/simplejson/ef460026417ab8cd9d8fae615d4e9b9cc784ccf1'
simplejson_files = ['decoder.py',
                    'encoder.py',
                    '__init__.py',
                    'ordered_dict.py',
                    'scanner.py',
                    'tool.py']
simplejson = [('%s/simplejson/%s' % (simplejson_src, f), 'simplejson/%s' % f)
              for f in simplejson_files]

# all dependencies
manifest = mozbase + yaml + simplejson

def download(*resources):
    """
    download resources: (url, destination)
    the destination is relative to the 'talos' subdirectory
    returns new directory names
    """

    newdirs = []
    for url, destination in resources:
        filename = os.path.join(dest, destination)
        dirname = os.path.dirname(filename)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
            newdirs.append(dirname)
        try:
            contents = urllib2.urlopen(url).read()
        except:
            print url
            raise
        f = file(filename, 'w')
        f.write(contents)
        f.close()
    return newdirs

def ignore(filename, patterns):
    """
    returns whether a file should be ignored or not
    - filename: name of file
    - patterns
    """
    for pattern in patterns:
        if pattern.search(filename):
            return True
    return False

def main(args=sys.argv[1:]):

    # list of patterns to ignore
    hgignore = os.path.join(here, '.hgignore')
    assert os.path.exists(hgignore), '.hgignore not found in %s' % here
    ignore_patterns = [re.compile(i)
                       for i in file(hgignore).read().splitlines()
                       if not i.startswith('#') and i.strip()]

    # get the files
    newdirs = download(*manifest)
    newfiles = [filename for _,filename in manifest]

    # get the filename
    filename = 'talos.zip'
    process = subprocess.Popen(['hg', 'id', '-i'], cwd=here, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    if process.returncode: # failure
        print >> sys.stderr, "Failed to find the changeset hash"
    filename = 'talos.%s.zip' % stdout.strip()

    # make the talos.zip file
    zip = zipfile.ZipFile(filename, mode='w', compression=zipfile.ZIP_DEFLATED)
    talosdir = os.path.abspath(os.path.join(here, 'talos'))
    for dirpath, dirnames, filenames in os.walk(talosdir):
        filenames = [i for i in filenames if not i.endswith('.pyc')]
        for f in filenames:
            try:
                fullname = os.path.join(dirpath, f)
                truncname = fullname[len(talosdir):].strip(os.path.sep)
                arcname = os.path.join('talos', truncname)
                if truncname in newfiles or not ignore(arcname, ignore_patterns):
                    # do not package files that are in .hgignore
                    # except the new files
                    zip.write(fullname, arcname=arcname)
            except:
                print fullname, truncname
                raise
    zip.close()

    # cleanup: remove downloaded files
    for path in newfiles:
        path = os.path.join(dest, path)
        assert os.path.exists(path), "'%s' not found" % path
        os.remove(path)
    for newdir in newdirs:
        shutil.rmtree(newdir)

    # output the path to the zipfile
    print os.path.abspath(filename)

if __name__ == '__main__':
    main()
