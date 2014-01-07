#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

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
import json

from results import TalosResults
from ttest import TTest
from utils import talosError, talosCrash, talosRegression

# directory of this file
here = os.path.dirname(os.path.realpath(__file__))

# global variable used to track results uploaded via mozhttpd
results_log = ""

def browserInfo(browser_config, devicemanager=None):
  """Get the buildid and sourcestamp from the application.ini (if it exists)"""
  # XXX this should probably be moved to PerfConfigurator.py

  config = ConfigParser.RawConfigParser()
  appIniFileName = "application.ini"
  appIniPath = os.path.join(os.path.dirname(browser_config['browser_path']), appIniFileName)

  # keys for various browser info
  keys = {'buildid': ('App', 'BuildID'),
          'repository': ('App', 'SourceRepository'),
          'sourcestamp': ('App', 'SourceStamp'),
          'browser_name': ('App', 'Name'),
          'browser_version': ('App', 'Version')}

  # defaults (of 'NULL') for browser_info keys
  # XXX https://bugzilla.mozilla.org/show_bug.cgi?id=769082
  defaults = {'repository': 'NULL', 'sourcestamp': 'NULL'}

  # fetch application.ini from remote
  if devicemanager:
    if not os.path.isfile('remoteapp.ini'):
      if browser_config['browser_path'].startswith('org.mozilla.f'): # mobile Firefox/fennec
        remoteAppIni = '/data/data/%s/%s' % (browser_config['browser_path'], appIniFileName)
      else:
        remoteAppIni = '/%s/%s' % (browser_config['deviceroot'], appIniFileName)
      devicemanager.getFile(remoteAppIni, 'remoteapp.ini')
    appIniPath = 'remoteapp.ini'

  if os.path.isfile(appIniPath):

    # read from application.ini
    config.read(appIniPath)

    # fill out browser_config data
    for key in keys:
      value = browser_config.get(key)
      if ((key in defaults and value == defaults[key])
          or (key not in defaults and not value)):
        browser_config[key] = config.get(*keys[key])
        utils.info("Reading '%s' from %s => %s", key, appIniPath, browser_config[key])
  else:
    utils.info("browserInfo: '%s' does not exist", appIniPath)

  # ensure these values are set
  # XXX https://bugzilla.mozilla.org/show_bug.cgi?id=769082
  for key, default in defaults.items():
    browser_config.setdefault(key, default)

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
  # mandatory options: tpmanifest, tpcycles
  if test['tpcycles'] not in range(1, 1000):
    raise talosError('pageloader cycles must be int 1 to 1,000')
  if test.get('tpdelay') and test['tpdelay'] not in range(1, 10000):
    raise talosError('pageloader delay must be int 1 to 10,000')
  if 'tpmanifest' not in test:
    raise talosError("tpmanifest not found in test: %s" % test)
    # TODO: should probably check if the tpmanifest exists

  # build pageloader command from options
  url = ['-tp', test['tpmanifest']]
  CLI_bool_options = ['tpchrome', 'tpmozafterpaint', 'tpnoisy', 'rss', 'tprender', 'tploadaboutblank']
  CLI_options = ['tpcycles', 'tppagecycles', 'tpdelay']
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

def print_logcat():
    if os.path.exists('logcat.log'):
        f = open('logcat.log')
        data = f.read()
        f.close()
        for l in data.split('\r'):
            # Buildbot will mark the job as failed if it finds 'ERROR'.
            print l.replace('RROR', 'RR_R')

def collectResults(request):
  """
    mozhttpd hander to accept results from a test
    currently this accepts a post in the format of a json object and writes it to a file
  """
  params = '?'.join(request.uri.split('?')[1:])
  params = urllib.unquote(params).decode('utf-8')
  data = json.loads(params)
  begin_time_stamp = int(time.time()*1000)
  with open(results_log, 'w') as fhandle:
      fhandle.write("__start_report\n")
      for item in data:
          if item == 'BEGIN_TIME_STAMP':
              begin_time_stamp = int(data[item])
          else:
              fhandle.write("%s,%s\n" % (item, data[item]))
      fhandle.write("__end_report\n")
      fhandle.write('__startTimestamp%s__endTimestamp\n' % begin_time_stamp)

      #TODO(jmaher): figure out this in more detail - I want it to be more accurate
      fhandle.write("__startBeforeLaunchTimestamp%d__endBeforeLaunchTimestamp\n" % int(time.time()*1000))
      fhandle.write("__startAfterTerminationTimestamp%d__endAfterTerminationTimestamp\n" % int(time.time()*1000))

  return (200, { 'called': 1,
                 'data': {},
                 'query': request.query })

def setup_webserver(webserver):
  """use mozhttpd to setup a webserver"""

  scheme = "http://"
  if (webserver.startswith('http://') or
      webserver.startswith('chrome://') or
      webserver.startswith('file:///')):
    scheme = ""
  elif '://' in webserver:
    print "Unable to parse user defined webserver: '%s'" % (webserver)
    sys.exit(2)

  url = urlparse.urlparse('%s%s' % (scheme, webserver))
  port = url.port

  if port:
    import mozhttpd
    return mozhttpd.MozHttpd(host=url.hostname, port=int(port), docroot=here, 
                                                  urlhandlers = [{'method': 'GET',
                                                    'path': '/results',
                                                    'function': collectResults }])
  else:
    print "WARNING: unable to start web server without custom port configured"
    return None

def run_tests(configurator):
  """Runs the talos tests on the given configuration and generates a report.

  Args:
    config: dictionary of configuration, as generated by PerfConfigurator
  """
  global results_log

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

  paths = ['profile_path', 'tpmanifest', 'extensions', 'setup', 'cleanup']
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
    test['url'] = utils.interpolatePath(test['url'])
    test['setup'] = utils.interpolatePath(test['setup'])
    test['cleanup'] = utils.interpolatePath(test['cleanup'])

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

  # Bug 940690 - Get existing metrofx talos tests running on release/project
  # branches:
  #    Identify when we do a win8 metro talos run, and a non metro run.  We do
  #    this so we can differentiate results in datazilla and graph server.
  #    Below will append a '.m' suffix to the title. The title will be used in
  #    datazilla via DatazillaOutput.test_machine() and graph server will match
  #    the title against an associated machine name in the graphserver sql database.
  if 'metrotestharness' in browser_config['browser_path'] and not title.endswith(".m"):
    # we are running this with win 8 metro
    title = "%s.m" % (title,)

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
  utils.debug("using testdate: %d", date)
  utils.debug("actual date: %d", int(time.time()))

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
  talos_results = TalosResults(title=title,
                               date=date,
                               browser_config=browser_config,
                               filters=filters,
                               remote=browser_config['remote'],
                               test_name_extension=browser_config['test_name_extension'])

  # results links
  results_urls, results_options = configurator.output_options()
  talos_results.check_output_formats(results_urls, **results_options)

  results_log = browser_config['results_log']

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
    test['browser_log'] = browser_config['browser_log']
    utils.stamped_msg("Running test " + testname, "Started")

    if os.path.exists('logcat.log'):
        os.unlink('logcat.log')

    try:
      mytest = TTest(browser_config['remote'])
      if mytest:
        talos_results.add(mytest.runTest(browser_config, test))
      else:
        utils.stamped_msg("Error found while running %s" % testname, "Error")
    except talosRegression, tr:
      utils.stamped_msg("Detected a regression for " + testname, "Stopped")
      print_logcat()
      if httpd:
        httpd.stop()
      # by returning 1, we report an orange to buildbot
      # http://docs.buildbot.net/latest/developer/results.html
      return 1
    except (talosCrash, talosError):
      # NOTE: if we get into this condition, talos has an internal problem and cannot continue
      #       this will prevent future tests from running
      utils.stamped_msg("Failed %s" % testname, "Stopped")
      talosError_tb = sys.exc_info()
      traceback.print_exception(*talosError_tb)
      print_logcat()
      if httpd:
        httpd.stop()
      # indicate a failure to buildbot, turn the job red
      return 2

    utils.stamped_msg("Completed test " + testname, "Stopped")
    print_logcat()

  elapsed = utils.stopTimer()
  print "cycle time: " + elapsed
  utils.stamped_msg(title, "Stopped")

  # stop the webserver if running
  if httpd:
    httpd.stop()

  # output results
  if results_urls:
    talos_results.output(results_urls, **results_options)

  # we will stop running tests on a failed test, or we will return 0 for green
  return 0

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
                    help="DEPRECATED: this is now the default")
  options, args = parser.parse_args(args)

  # set variables
  level = 'info'
  if options.debug:
    level = 'debug'
  utils.startLogger(level)
  sys.exit(run_tests(parser))

if __name__=='__main__':
  main()
