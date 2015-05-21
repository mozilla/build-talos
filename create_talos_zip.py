#!/usr/bin/env python

"""
create a talos.zip appropriate for testing
"""

import StringIO
import gzip
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib2
import zipfile

# globals
here = os.path.dirname(os.path.abspath(__file__))
dest = os.path.join(here, 'talos')

mozbase_packages = [ ('mozcrash', '0.13'),
                     ('mozdevice', '0.40'),
                     ('mozfile', '1.1'),
                     ('mozhttpd', '0.5'),
                     ('mozinfo', '0.7'),
                     ('mozlog', '2.6'),
                     ('moznetwork', '0.24'),
                     ('mozprocess', '0.21'),
                     ('mozversion', '0.8'),
                     ('manifestparser', '1.0'),  # required by mozprofile
                     ('mozprofile', '0.23'),
]

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

# oauth2 dependency:
# https://bugzilla.mozilla.org/show_bug.cgi?id=774480
#oauth2_src = 'https://raw.github.com/simplegeo/python-oauth2/master/oauth2'
# oauth2 is incompatible with python 2.4 as we use on windows, so point to
# a vendor branch until upstream is fixed
# https://bugzilla.mozilla.org/show_bug.cgi?id=792989
oauth2_src = 'https://raw.github.com/k0s/python-oauth2/master/oauth2'
oauth2_files = [
#    'clients/__init__.py', # clients subdirectory is not needed and is incompatible with create_talos_zip.py hackiness
#    'clients/imap.py',
#    'clients/smtp.py',
    '__init__.py',
    '_version.py']
oauth2 = [('%s/%s' % (oauth2_src, f), 'oauth2/%s' % f)
          for f in oauth2_files]

# httplib2 dependency
httplib2_src = 'http://httplib2.googlecode.com/hg/python2/httplib2'
httplib2_files = ['__init__.py',
                  'cacerts.txt',
                  'iri2uri.py',
                  'socks.py']
httplib2_oauth2 = [('%s/%s' % (httplib2_src, f), 'oauth2/httplib2/%s' % f)
                   for f in httplib2_files]

# all dependencies
manifest = yaml + oauth2 + httplib2_oauth2
manifest = [(url, destination.replace('/', os.path.sep)) for url, destination in manifest]

def unpack_pypi_module(modulename, version, destdir):
    url = 'http://pypi.python.org/packages/source/%s/%s/%s-%s.tar.gz' % (
        modulename[0], modulename, modulename, version)
    print url
    contents = urllib2.urlopen(url).read()
    c = StringIO.StringIO(contents)
    c.seek(0)
    os.mkdir(os.path.join(destdir, modulename))
    key = '%s-%s/%s/' % (modulename, version, modulename)
    with tarfile.TarFile(fileobj=gzip.GzipFile(fileobj=c)) as tar:
        for tar_member in tar.getmembers():
            if tar_member.name.startswith(key):
                if tar_member.isfile():
                    destpath = tar_member.name[len(key):]
                    module_destdir = os.path.join(destdir, modulename,
                                                  os.path.dirname(destpath))
                    if not os.path.exists(module_destdir):
                        os.makedirs(module_destdir)
                    destfilename = os.path.join(module_destdir, os.path.basename(destpath))
                    print destfilename
                    with open(destfilename, 'w') as f:
                        f.write(tar.extractfile(tar_member).read())

def download(destdir, *resources):
    """
    download resources: (url, destination)
    the destination is relative to the 'talos' subdirectory
    returns new directory names
    """
    for url, destination in resources:
        filename = os.path.join(destdir, destination)
        dirname = os.path.dirname(filename)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        try:
            contents = urllib2.urlopen(url).read()
        except:
            print url
            raise
        with open(filename, 'w') as f:
            f.write(contents)

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
    # Error out on Windows until bug 829690 is fixed.
    if os.name == 'nt':
        sys.exit("This script fails to set permissions properly for the packaged breakpad "
                 "binaries when run on Windows (bug 829690), which causes failures when "
                 "processing crashes. For now please run on another platform.")

    tempdir = tempfile.mkdtemp()

    temp_talos_dir = os.path.join(tempdir, 'talos')
    os.mkdir(temp_talos_dir)

    # get mozbase packages
    for (packagename, version) in mozbase_packages:
        unpack_pypi_module(packagename, version, temp_talos_dir)

    # get the other packages
    download(temp_talos_dir, *manifest)

    # list of patterns to ignore
    hgignore = os.path.join(here, '.hgignore')
    assert os.path.exists(hgignore), '.hgignore not found in %s' % here
    ignore_patterns = [re.compile(i)
                       for i in file(hgignore).read().splitlines()
                       if not i.startswith('#') and i.strip()]

    # copy talos itself
    talosdir = os.path.abspath(os.path.join(here, 'talos'))
    for dirpath, dirnames, filenames in os.walk(talosdir):
        filenames = [i for i in filenames if not i.endswith('.pyc')]
        for f in filenames:
            try:
                fullname = os.path.join(dirpath, f)
                truncname = fullname[len(talosdir):].strip(os.path.sep)
                arcname = os.path.join('talos', truncname)
                if not ignore(arcname, ignore_patterns):
                    # do not package files that are in .hgignore
                    destname = os.path.join(tempdir, arcname)
                    destdirname = os.path.dirname(destname)
                    if not os.path.exists(destdirname):
                        os.makedirs(destdirname)
                    shutil.copyfile(fullname, destname)
                    shutil.copymode(fullname, destname)
            except:
                print fullname, truncname
                raise

    # get the filename
    filename = 'talos.zip'
    process = subprocess.Popen(['hg', 'id', '-i'], cwd=here, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    if process.returncode: # failure
        print >> sys.stderr, "Failed to find the changeset hash"
    filename = 'talos.%s.zip' % stdout.strip()

    # make the talos.zip file
    with zipfile.ZipFile(filename, mode='w', compression=zipfile.ZIP_DEFLATED) as zip:
        for dirpath, dirnames, filenames in os.walk(tempdir):
            for f in filenames:
                srcname = os.path.join(tempdir, dirpath, f)
                print srcname
                zip.write(srcname, arcname=os.path.join(dirpath, f)[len(tempdir):])
                
    # cleanup: remove temporary staging location
    shutil.rmtree(tempdir)

    # output the path to the zipfile
    print os.path.abspath(filename)

if __name__ == '__main__':
    main()
