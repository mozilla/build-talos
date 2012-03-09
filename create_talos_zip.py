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
manifest = [('https://raw.github.com/mozilla/mozbase/master/mozhttpd/mozhttpd/mozhttpd.py', 'mozhttpd.py'),
            ('https://raw.github.com/mozilla/mozbase/master/mozinfo/mozinfo/mozinfo.py', 'mozinfo.py'),
            ('https://raw.github.com/mozilla/mozbase/master/mozdevice/mozdevice/__init__.py', 'mozdevice/__init__.py'),
            ('https://raw.github.com/mozilla/mozbase/master/mozdevice/mozdevice/devicemanager.py', 'mozdevice/devicemanager.py'),
            ('https://raw.github.com/mozilla/mozbase/master/mozdevice/mozdevice/devicemanagerADB.py', 'mozdevice/devicemanagerADB.py'),
            ('https://raw.github.com/mozilla/mozbase/master/mozdevice/mozdevice/devicemanagerSUT.py', 'mozdevice/devicemanagerSUT.py'),
            ('http://pyyaml.org/export/360/pyyaml/trunk/lib/yaml/composer.py', 'yaml/composer.py'),
            ('http://pyyaml.org/export/360/pyyaml/trunk/lib/yaml/constructor.py', 'yaml/constructor.py'),
            ('http://pyyaml.org/export/360/pyyaml/trunk/lib/yaml/cyaml.py', 'yaml/cyaml.py'),
            ('http://pyyaml.org/export/360/pyyaml/trunk/lib/yaml/dumper.py', 'yaml/dumper.py'),
            ('http://pyyaml.org/export/360/pyyaml/trunk/lib/yaml/emitter.py', 'yaml/emitter.py'),
            ('http://pyyaml.org/export/360/pyyaml/trunk/lib/yaml/error.py', 'yaml/error.py'),
            ('http://pyyaml.org/export/360/pyyaml/trunk/lib/yaml/events.py', 'yaml/events.py'),
            ('http://pyyaml.org/export/360/pyyaml/trunk/lib/yaml/__init__.py', 'yaml/__init__.py'),
            ('http://pyyaml.org/export/360/pyyaml/trunk/lib/yaml/loader.py', 'yaml/loader.py'),
            ('http://pyyaml.org/export/360/pyyaml/trunk/lib/yaml/nodes.py', 'yaml/nodes.py'),
            ('http://pyyaml.org/export/360/pyyaml/trunk/lib/yaml/parser.py', 'yaml/parser.py'),
            ('http://pyyaml.org/export/360/pyyaml/trunk/lib/yaml/reader.py', 'yaml/reader.py'),
            ('http://pyyaml.org/export/360/pyyaml/trunk/lib/yaml/representer.py', 'yaml/representer.py'),
            ('http://pyyaml.org/export/360/pyyaml/trunk/lib/yaml/resolver.py', 'yaml/resolver.py'),
            ('http://pyyaml.org/export/360/pyyaml/trunk/lib/yaml/scanner.py', 'yaml/scanner.py'),
            ('http://pyyaml.org/export/360/pyyaml/trunk/lib/yaml/serializer.py', 'yaml/serializer.py'),
            ('http://pyyaml.org/export/360/pyyaml/trunk/lib/yaml/tokens.py', 'yaml/tokens.py')]

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
                       if not i.startswith('#')]

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
            fullname = os.path.join(dirpath, f)
            truncname = fullname[len(talosdir):].strip(os.path.sep)
            if truncname in newfiles or not ignore(truncname, ignore_patterns):
                # do not package files that are in .hgignore
                # except the new files
                zip.write(fullname, arcname=os.path.join('talos', truncname))
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
