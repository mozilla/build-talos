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

mozhttpd_src = 'https://raw.github.com/mozilla/mozbase/mozhttpd-0.5/'
mozhttpd_files = [('mozhttpd/mozhttpd/mozhttpd.py', 'mozhttpd.py'),
                  ('mozhttpd/mozhttpd/iface.py', 'iface.py')]
mozhttpd = [(mozhttpd_src + src, destination) for src, destination in mozhttpd_files]

mozinfo_src = 'https://raw.github.com/mozilla/mozbase/mozinfo-0.4/mozinfo/mozinfo/mozinfo.py'
mozinfo = [(mozinfo_src, 'mozinfo.py')]

mozcrash_src = 'https://raw.github.com/mozilla/mozbase/mozcrash-0.9/mozcrash/mozcrash/mozcrash.py'
mozcrash = [(mozcrash_src, 'mozcrash.py')]

mozfile_src = 'https://raw.github.com/mozilla/mozbase/mozfile-0.3/mozfile/mozfile/mozfile.py'
mozfile = [(mozfile_src, 'mozfile.py')]

mozlog_src = 'https://raw.github.com/mozilla/mozbase/master/mozlog/mozlog/logger.py'
mozlog = [(mozlog_src, 'mozlog.py')]

mozdevice_src = 'https://raw.github.com/mozilla/mozbase/mozdevice-0.26/'
mozdevice_files = [('mozdevice/mozdevice/__init__.py', 'mozdevice/__init__.py'),
                   ('mozdevice/mozdevice/Zeroconf.py', 'mozdevice/Zeroconf.py'),
                   ('mozdevice/mozdevice/devicemanager.py', 'mozdevice/devicemanager.py'),
                   ('mozdevice/mozdevice/devicemanagerADB.py', 'mozdevice/devicemanagerADB.py'),
                   ('mozdevice/mozdevice/devicemanagerSUT.py', 'mozdevice/devicemanagerSUT.py'),
                   ('mozdevice/mozdevice/droid.py', 'mozdevice/droid.py')]
mozdevice = [(mozdevice_src + src, destination) for src, destination in mozdevice_files]

mozprocess_src = 'https://raw.github.com/mozilla/mozbase/mozprocess-0.13/'
mozprocess_files = [('mozprocess/mozprocess/__init__.py', 'mozprocess/__init__.py'),
                    ('mozprocess/mozprocess/pid.py', 'mozprocess/pid.py'),
                    ('mozprocess/mozprocess/processhandler.py', 'mozprocess/processhandler.py'),
                    ('mozprocess/mozprocess/qijo.py', 'mozprocess/qijo.py'),
                    ('mozprocess/mozprocess/winprocess.py', 'mozprocess/winprocess.py'),
                    ('mozprocess/mozprocess/wpk.py', 'mozprocess/wpk.py')]
mozprocess = [(mozprocess_src + src, destination) for src, destination in mozprocess_files]

# datazilla client dependency
datazilla_client = [('https://raw.github.com/mozilla/datazilla_client/master/dzclient/client.py',
                     'dzclient.py')]

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
manifest = mozhttpd + mozinfo + mozcrash + mozfile + mozlog + mozdevice + datazilla_client + yaml + simplejson + oauth2 + httplib2_oauth2 + mozprocess
manifest = [(url, destination.replace('/', os.path.sep)) for url, destination in manifest]

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
    # Error out on Windows until bug 829690 is fixed.
    if os.name == 'nt':
        sys.exit("This script fails to set permissions properly for the packaged breakpad "
                 "binaries when run on Windows (bug 829690), which causes failures when "
                 "processing crashes. For now please run on another platform.")

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
        if os.path.exists(newdir):
            shutil.rmtree(newdir)

    # output the path to the zipfile
    print os.path.abspath(filename)

if __name__ == '__main__':
    main()
