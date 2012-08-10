#!/usr/bin/env python
# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is standalone Firefox Windows performance test.
#
# The Initial Developer of the Original Code is Google Inc.
# Portions created by the Initial Developer are Copyright (C) 2006
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Annie Sullivan <annie.sullivan@gmail.com> (original author)
#   Alice Nodelman <anodelman@mozilla.com>
#   retornam <mozbugs.retornam+bz@gmail.com>
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****

__author__ = 'annie.sullivan@gmail.com (Annie Sullivan)'

import ConfigParser
import filter
import optparse
import os
import PerfConfigurator
import post_file
import sys
import time
import traceback
import urllib
import urlparse
import utils

from results import TalosResults
from ttest import TTest
from utils import talosError

# directory of this file
here = os.path.dirname(os.path.realpath(__file__))

def browserInfo(browser_config, devicemanager=None):
  """Get the buildid and sourcestamp from the application.ini (if it exists)
  """
  config = ConfigParser.RawConfigParser()
  appIniFileName = "application.ini"
  appIniPath = os.path.join(os.path.dirname(browser_config['browser_path']), appIniFileName)
  if os.path.isfile(appIniPath) or devicemanager != None:
    if (devicemanager != None):
      if (browser_config['browser_path'].startswith('org.mozilla.f')):
        remoteAppIni = '/data/data/' + browser_config['browser_path'] + '/' + appIniFileName
      else:
        remoteAppIni = browser_config['deviceroot'] + '/' + appIniFileName
      if not os.path.isfile('remoteapp.ini'):
        devicemanager.getFile(remoteAppIni, 'remoteapp.ini')
      config.read('remoteapp.ini')
    else:
      config.read(appIniPath)

    if not browser_config.get('buildid'):
      browser_config['buildid'] = config.get('App', 'BuildID')
    if browser_config.get('repository', 'NULL') == 'NULL':
      browser_config['repository'] = config.get('App', 'SourceRepository')
    if browser_config.get('sourcestamp', 'NULL') == 'NULL':
      browser_config['sourcestamp'] = config.get('App', 'SourceStamp')
    if not browser_config.get('browser_name'):
      browser_config['browser_name'] = config.get('App', 'Name')
    if not browser_config.get('browser_version'):
      browser_config['browser_version'] = config.get('App', 'Version')
  if ('repository' in browser_config) and ('sourcestamp' in browser_config):
    print 'RETURN:<a href = "' + browser_config['repository'] + '/rev/' + browser_config['sourcestamp'] + '">rev:' + browser_config['sourcestamp'] + '</a>'
  else:
    browser_config['repository'] = 'NULL'
    browser_config['sourcestamp'] = 'NULL'
  return browser_config

def useBaseTestDefaults(base, tests):
  for test in tests:
    for item in base:
      if not item in test:
        test[item] = base[item]
        if test[item] is None:
          test[item] = ''
  return tests

def buildCommandLine(test):
  """build firefox command line options for tp tests"""

  # sanity check pageloader values
  # mandatory options: tpmanifest, tpcycles, tpformat
  if test['tpcycles'] not in range(1, 1000):
    raise talosError('pageloader cycles must be int 1 to 1,000')
  available_formats = ('js', 'jsfull', 'text', 'tinderbox')
  if test['tpformat'] not in available_formats:
    raise talosError('pageloader format not recognized. valid formats are %s' % ', '.join(available_formats))
  if test.get('tpdelay') and test['tpdelay'] not in range(1, 10000):
    raise talosError('pageloader delay must be int 1 to 10,000')
  if 'tpmanifest' not in test:
    raise talosError("tpmanifest not found in test: %s" % test)
    # TODO: should probably check if the tpmanifest exists

  # build pageloader command from options
  url = ['-tp', test['tpmanifest']]
  CLI_bool_options = ['tpchrome', 'tpmozafterpaint', 'tpnoisy', 'rss', 'tprender']
  CLI_options = ['tpformat', 'tpcycles', 'tppagecycles', 'tpdelay']
  for key in CLI_bool_options:
      if test.get(key):
          url.append('-%s' % key)
  for key in CLI_options:
      value = test.get(key)
      if value:
          url.extend(['-%s' % key, str(value)])

  # XXX we should actually return the list but since we abuse
  # the url as a command line flag to pass to firefox all over the place
  # will just make a string for now
  return ' '.join(url)

def setup_webserver(webserver):
  """use mozhttpd to setup a webserver"""

  scheme = "http://"
  if (webserver.startswith('http://') or
      webserver.startswith('chrome://') or
      webserver.startswith('file:///')):
    scheme = ""
  elif (webserver.find('://') >= 0):
    print "Unable to parse user defined webserver: '%s'" % (webserver)
    sys.exit(2)

  url = urlparse.urlparse('%s%s' % (scheme, webserver))
  port = url.port

  if port:
    import mozhttpd
    return mozhttpd.MozHttpd(host=url.hostname, port=int(port), docroot=here)
  else:
    print "WARNING: unable to start web server without custom port configured"
    return None

def run_tests(configurator):
  """Runs the talos tests on the given configuration and generates a report.

  Args:
    config: dictionary of configuration, as generated by PerfConfigurator
  """
  config=configurator.config
  # data filters
  filters = config['filters']
  try:
      filters = filter.filters_args(filters)
  except AssertionError, e:
      raise talosError(str(e))

  # get the test data
  tests = config['tests']
  tests = useBaseTestDefaults(config.get('basetest', {}), tests)

  paths = ['profile_path', 'tpmanifest']
  for test in tests:

    # Check for profile_path, tpmanifest and interpolate based on Talos root
    # https://bugzilla.mozilla.org/show_bug.cgi?id=727711
    # Build command line from config
    for path in paths:
      if test.get(path):
        test[path] = utils.interpolatePath(test[path])
    if test.get('tpmanifest'):
      test['tpmanifest'] = os.path.normpath('file:/%s' % (urllib.quote(test['tpmanifest'], '/\\t:\\')))
    if not test.get('url'):
      # build 'url' for tptest
      test['url'] = buildCommandLine(test)

    # ensure test-specific filters are valid
    if 'filters' in test:
      try:
        filter.filters_args(test['filters'])
      except AssertionError, e:
        raise talosError(str(e))
      except IndexError, e:
        raise talosError(str(e))


  # set browser_config
  browser_config=configurator.browser_config()
  
  #set defaults
  title = config.get('title', '')
  testdate = config.get('testdate', '')

  # get the process name from the path to the browser
  if not browser_config['process']:
      browser_config['process'] = os.path.basename(browser_config['browser_path'])

  # fix paths to substitute
  # `os.path.dirname(os.path.abspath(__file__))` for ${talos}
  # https://bugzilla.mozilla.org/show_bug.cgi?id=705809
  browser_config['extensions'] = [utils.interpolatePath(i)
                                  for i in browser_config['extensions']]
  browser_config['dirs'] = dict([(i, utils.interpolatePath(j))
                                    for i,j in browser_config['dirs'].items()])
  browser_config['bcontroller_config'] = utils.interpolatePath(browser_config['bcontroller_config'])

  # get device manager if specified
  dm = None
  if browser_config['remote'] == True:
    if browser_config['port'] == -1:
        from mozdevice import devicemanagerADB
        dm = devicemanagerADB.DeviceManagerADB(browser_config['host'], browser_config['port'])
    else:
        from mozdevice import devicemanagerSUT
        dm = devicemanagerSUT.DeviceManagerSUT(browser_config['host'], browser_config['port'])

  # normalize browser path to work across platforms
  browser_config['browser_path'] = os.path.normpath(browser_config['browser_path'])

  # get test date in seconds since epoch
  if testdate:
    date = int(time.mktime(time.strptime(testdate, '%a, %d %b %Y %H:%M:%S GMT')))
  else:
    date = int(time.time())
  utils.debug("using testdate: %d" % date)
  utils.debug("actual date: %d" % int(time.time()))

  # pull buildid & sourcestamp from browser
  try:
    browser_config = browserInfo(browser_config, devicemanager=dm)
  except:
    if not browser_config['develop']:
      raise

  if browser_config['remote']:
    procName = browser_config['browser_path'].split('/')[-1]
    if dm.processExist(procName):
      dm.killProcess(procName)

  # results container
  talos_results = TalosResults(filters=filters,
                               title=title,
                               date=date,
                               remote=browser_config['remote'],
                               browser_config=browser_config,
                               test_name_extension=browser_config['test_name_extension'])

  # results links
  outputs = ['results_urls', 'datazilla_urls']
  results_urls = dict([(key, config[key]) for key in outputs
                       if key in config])
  talos_results.check_output_formats(**results_urls)

  # setup a webserver, if --develop is specified to PerfConfigurator.py
  httpd = None
  if browser_config['develop'] == True:
    httpd = setup_webserver(browser_config['webserver'])
    if httpd:
      httpd.start()

  # run the tests
  utils.startTimer()
  utils.stamped_msg(title, "Started")
  for test in tests:
    testname = test['name']
    utils.stamped_msg("Running test " + testname, "Started")

    try:
      mytest = TTest(browser_config['remote'])
      talos_results.add(mytest.runTest(browser_config, test))
    except talosError, e:
      utils.stamped_msg("Failed " + testname, "Stopped")
      print 'FAIL: Busted: ' + testname
      print 'FAIL: ' + e.msg.replace('\n','\nRETURN:')
      talosError_tb = sys.exc_info()
      traceback.print_exception(*talosError_tb)
      if httpd:
        httpd.stop()
      raise e
    utils.stamped_msg("Completed test " + testname, "Stopped")
  elapsed = utils.stopTimer()
  print "RETURN: cycle time: " + elapsed + "<br>"
  utils.stamped_msg(title, "Stopped")

  # stop the webserver if running
  if httpd:
    httpd.stop()

  # output results
  if results_urls:
    talos_results.output(**results_urls)

def main(args=sys.argv[1:]):

  # parse command line options
  usage = "%prog [options] manifest.yml [manifest.yml ...]"
  parser = PerfConfigurator.PerfConfigurator(usage=usage)
  parser._dump = False # disable automatic dumping
  parser.add_option('-d', '--debug', dest='debug',
                    action='store_true', default=False,
                    help="enable debug")
  parser.add_option('-n', '--noisy', dest='noisy',
                    action='store_true', default=False,
                    help="enable noisy output")
  options, args = parser.parse_args(args)

  # set variables
  if options.debug:
    print 'setting debug'
    utils.setdebug(1)
  if options.noisy:
    utils.setnoisy(1)

  # run tests
  run_tests(parser)

if __name__=='__main__':
  main()
