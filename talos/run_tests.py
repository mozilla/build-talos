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

import filter
import optparse
import os
import re
import string
import sys
import time
import traceback
import urlparse
import yaml
import PerfConfigurator
import utils
import urllib
from utils import talosError
import post_file
from ttest import TTest
from results import PageloaderResults
import mozinfo

# directory of this file
here = os.path.dirname(os.path.realpath(__file__))

def shortName(name):
  names = {"Working Set": "memset",
           "% Processor Time": "%cpu",
           "Private Bytes": "pbytes",
           "RSS": "rss",
           "XRes": "xres",
           "Modified Page List Bytes": "modlistbytes",
           "Main_RSS": "main_rss",
           "Content_RSS": "content_rss"}
  return names.get(name, name)

def isMemoryMetric(resultName):
  memory_metric = ['memset', 'rss', 'pbytes', 'xres', 'modlistbytes', 'main_rss', 'content_rss'] #measured in bytes
  return bool([ i for i in memory_metric if i in resultName])

def filesizeformat(bytes):
  """
  Format the value like a 'human-readable' file size (i.e. 13 KB, 4.1 MB, 102
  bytes, etc).
  """
  bytes = float(bytes)
  formats = ('B', 'KB', 'MB')
  for f in formats:
    if bytes < 1024:
      return "%.1f%s" % (bytes, f)
    bytes /= 1024
  return "%.1fGB" % bytes #has to be GB

def process_Request(post):
  links = ""
  lines = post.split('\n')
  for line in lines:
    if line.find("RETURN\t") > -1:
        line = line.replace("RETURN\t", "")
        links +=  line+ '\n'
    utils.debug("process_Request line: " + line)
  if not links:
    raise talosError("send failed, graph server says:\n" + post)
  return links

def responsiveness_Metric(val_list):
  s = sum([int(x)*int(x) / 1000000.0 for x in val_list])
  return str(round(s))

def construct_results(machine, testname, browser_config, date, vals, amo):
  """
  Creates string formated for the collector script of the graph server
  Returns the completed string
  """
  branch = browser_config['branch_name']
  sourcestamp = browser_config['sourcestamp']
  buildid = browser_config['buildid']
  #machine_name,test_name,branch_name,sourcestamp,buildid,date_run
  info_format = "%s,%s,%s,%s,%s,%s\n"
  data_string = ""
  data_string += "START\n"
  if amo:
    data_string += "AMO\n"
    #browser_name,browser_version,addon_id
    amo_format= "%s,%s,%s\n"
    data_string += amo_format % (browser_config['browser_name'], browser_config['browser_version'], browser_config['addon_id'])
  elif 'responsiveness' in testname:
    data_string += "AVERAGE\n"
  else:
    data_string += "VALUES\n"
  data_string += info_format % (machine, testname, branch, sourcestamp, buildid, date)
  #add the data to the file
  if 'responsiveness' in testname:
    data_string += "%s\n" % (responsiveness_Metric([val for (val, page) in vals]))
  else:
    i = 0
    for val, page in vals:
      data_string += "%d,%.2f,%s\n" % (i,float(val), page)
      i += 1
  data_string += "END"
  return data_string

def getRunOptions(browser, test):
  # XXX should use simplejson/json to serialize
  # https://bugzilla.mozilla.org/show_bug.cgi?id=744405
  options = []
  test_options = ['rss', 'tpchrome', 'tpmozafterpaint', 'tpcycles', 'tppagecycles', 'tprender', 'tpdelay', 'responsiveness', 'shutdown']
  for option in test_options:
    if option not in test:
      continue
    if test[option] == True or test[option] == False:
      options.append('"%s": %s' % (option, str(test[option]).lower()))
    else:
      options.append('"%s": "%s"' % (option, test[option]))
  return "{%s}" % ', '.join(options)

def send_to_graph(results_url, machine, date, browser_config, results, amo, filters):
  """send the results to a graphserver or file URL"""

  links = ''
  result_strings = []
  result_testnames = []

  # parse the results url
  results_url_split = urlparse.urlsplit(results_url)
  results_scheme, results_server, results_path, _, _ = results_url_split

  #construct all the strings of data, one string per test and one string  per counter
  for testname in results:
    vals = []
    fullname = testname
    browser_dump, counter_dump, print_format, test_config = results[testname]
    utils.debug("Working with test: " + testname)
    utils.debug("Sending results: " + " ".join(browser_dump))
    utils.stamped_msg("Generating results file: " + testname, "Started")

    # TODO: add this for other formats
    raw_values = '"results": {}'
    if print_format == 'tsformat':
      #non-tpformat results
      raw_vals = []
      for bd in browser_dump:
        vals.extend([[x, 'NULL'] for x in bd.split('|')])
        raw_vals.extend([float(x) for x in bd.split('|')])
        raw = []
        # TODO: make the startup tests report the pagename, for now I use the 'testname'
        raw.append('"%s": %s' % (testname, raw_vals))
        raw_values = '"results": {%s}' % ', '.join(raw)
    elif print_format == 'tpformat':
      #tpformat results
      fullname += browser_config['test_name_extension']
      for bd in browser_dump:
        page_results = PageloaderResults(bd)

        # filter the data
        _filters = filters
        if 'filters' in test_config:
            # test specific filters
            try:
                _filters = filter.filters_args(test_config['filters'])
            except AssertionError, e:
                raise talosError(str(e))
        newvals = page_results.filter(*_filters)

        newvals = [[val, page] for val, page in newvals if val > -1]
        vals.extend(newvals)

        rv = page_results.raw_values()
        raw = []
        for page in rv.keys():
          raw.append('"%s": %s' % (page, rv[page]))
        raw_values = '"results": {%s}' % ', '.join(raw)
    else:
      raise talosError("Unknown print format in send_to_graph")
    result_strings.append(construct_results(machine, fullname, browser_config, date, vals, amo))
    result_testnames.append(fullname)
    options = getRunOptions(browser_config, test_config)
    if browser_config['remote']:
      # TODO: figure out how to not hardcode this, specifically the version !!
      raw_machine = '"test_machine": {"name": "%s", "os": "%s", "osversion": "%s", "platform": "%s"}' % \
                     (machine, "Android", "4.0.3", "arm")
    else:
      raw_machine = '"test_machine": {"name": "%s", "os": "%s", "osversion": "%s", "platform": "%s"}' % \
                     (machine, mozinfo.info["os"], mozinfo.info["version"], mozinfo.info["processor"])
    raw_build = '"test_build": {"name": "%s", "version": "%s", "revision": "%s", "branch":  "%s", "id": "%s"}' % \
                  (browser_config["browser_name"], browser_config["browser_version"], browser_config["sourcestamp"], browser_config["branch_name"], browser_config["buildid"])
    raw_testrun = '"testrun": {"date": "%s", "suite": "Talos %s", "options": %s}' % \
                   (date, testname, options)

    #TODO: do we only test ts, if not, can we ensure that we are not trying to uplaod ts_rss, etc...
    if amo and testname == 'ts':
      from amo.amo_api import upload_amo_results
      upload_amo_results(browser_config['addon_id'],
                         browser_config['browser_version'],
                         browser_config['process'],
                         testname,
                         [val for val,page in vals])

    utils.stamped_msg("Generating results file: " + testname, "Stopped")
    #counters collected for this test
    aux = []
    for cd in counter_dump:
      for count_type in cd:
        counterName = testname + '_' + shortName(count_type)
        if cd[count_type] == []: #failed to collect any data for this counter
          utils.stamped_msg("No results collected for: " + counterName, "Error")
          continue
        adata = '"'+shortName(count_type)+'": %s' % [str(x) for x in cd[count_type]]
        aux.append(adata.replace('\'', '"'))
        vals = [[x, 'NULL'] for x in cd[count_type]]
        if print_format == "tpformat":
          counterName += browser_config['test_name_extension']
        utils.stamped_msg("Generating results file: " + counterName, "Started")
        result_strings.append(construct_results(machine, counterName, browser_config, date, vals, amo))
        result_testnames.append(counterName)
        utils.stamped_msg("Generating results file: " + counterName, "Stopped")

    raw_counters = '"results_aux": {%s}' % ', '.join(aux)
    raw_results = "{%s, %s, %s, %s, %s}" % (raw_machine, raw_build, raw_testrun, raw_values, raw_counters)
    try:
        post_file.post_multipart("http://10.8.73.29", "/views/api/load_test", fields=[("data", urllib.quote(raw_results))])
        print "done posting raw results to staging server"
    except:
        # This is for posting to a staging server, we can ignore the error
        print "was not able to post raw results to staging server"

  #send all the strings along to the graph server
  for data_string, testname in zip(result_strings, result_testnames):
    RETRIES = 5
    wait_time = 5
    times = 0
    msg = ""
    while times < RETRIES:
      try:
        utils.stamped_msg("Transmitting test: " + testname, "Started")
        if results_scheme in ('http', 'https'):
          links += process_Request(post_file.post_multipart(results_server, results_path, files=[("filename", "data_string", data_string)]))
        elif results_scheme == 'file':
          f = file(results_path, 'a')
          f.write(data_string)
          f.close()
        else:
          raise NotImplementedError("results_url: %s - only http://, https://, and file:// supported" % results_url)
        break
      except talosError, e:
        msg = e.msg
      except Exception, e:
        msg = str(e)
      times += 1
      time.sleep(wait_time)
      wait_time += wait_time
    else:
      raise talosError("Graph server unreachable (%d attempts)\n%s" % (RETRIES, msg))
    utils.stamped_msg("Transmitting test: " + testname, "Stopped")

  return links

def results_from_graph(links, results_server, amo):
  if amo:
    #only get a pass/fail back from the graph server
    lines = links.split('\n')
    for line in lines:
      if line == "":
        continue
      if line.lower() in ('success',):
        print 'RETURN:addon results inserted successfully'

  else:
    #take the results from the graph server collection script and put it into a pretty format for the waterfall
    url_format = "http://%s/%s"
    link_format= "<a href=\'%s\'>%s</a>"
    first_results = 'RETURN:<br>'
    last_results = ''
    full_results = '\nRETURN:<p style="font-size:smaller;">Details:<br>'
    lines = links.split('\n')
    for line in lines:
      if not line:
        continue
      linkvalue = -1
      linkdetail = ""
      values = line.split("\t")
      linkName = values[0]
      if len(values) == 2:
        linkdetail = values[1]
      else:
        linkvalue = float(values[1])
        linkdetail = values[2]
      if linkvalue > -1:
        if isMemoryMetric(linkName):
          linkName += ": " + filesizeformat(linkvalue)
        else:
          linkName += ": " + str(linkvalue)
        url = url_format % (results_server, linkdetail)
        link = link_format % (url, linkName)
        first_results = first_results + "\nRETURN:" + link + "<br>"
      else:
        url = url_format % (results_server, linkdetail)
        link = link_format % (url, linkName)
        last_results = last_results + '| ' + link + ' '
    full_results = first_results + full_results + last_results + '|</p>'
    print full_results

def browserInfo(browser_config, devicemanager=None):
  """Get the buildid and sourcestamp from the application.ini (if it exists)
  """
  import ConfigParser
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

    if not 'buildid' in browser_config or not browser_config['buildid']:
      browser_config['buildid'] = config.get('App', 'BuildID')
    if not 'repository' in browser_config or browser_config['repository'] == 'NULL':
      browser_config['repository'] = config.get('App', 'SourceRepository')
    if not 'sourcestamp' in browser_config or browser_config['sourcestamp'] == 'NULL':
      browser_config['sourcestamp'] = config.get('App', 'SourceStamp')
    if not 'browser_name' in browser_config or not browser_config['browser_name']:
      browser_config['browser_name'] = config.get('App', 'Name')
    if not 'browser_version' in browser_config or not browser_config['browser_version']:
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

def run_tests(config):
  """Runs the talos tests on the given configuration and generates a report.

  Args:
    config: dictionary of configuration, as generated by PerfConfigurator
  """

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

  # set defaults
  title = config.get('title', '')
  testdate = config.get('testdate', '')
  results_url = config.get('results_url', '')
  amo = config.get('amo', False)

  # ensure results_url link exists
  if results_url:
    results_url_split = urlparse.urlsplit(results_url)
    results_scheme, results_server, results_path, _, _ = results_url_split
    if results_scheme in ('http', 'https') and not post_file.link_exists(results_server, results_path):
      print 'WARNING: graph server link does not exist'

  # set browser_config
  required = ['preferences', 'extensions',
              'browser_path', 'browser_log', 'browser_wait',
              'extra_args', 'buildid', 'env', 'init_url'
              ]
  optional = {'addon_id': 'NULL',
              'bcontroller_config': 'bcontroller.yml',
              'branch_name': '',
              'child_process': 'plugin-container',
              'develop': False,
              'deviceroot': '',
              'dirs': {},
              'host': config.get('deviceip', ''), # XXX names should match!
              'port': config.get('deviceport', ''), # XXX names should match!
              'process': '',
              'remote': False,
              'fennecIDs': '',
              'repository': 'NULL',
              'sourcestamp': 'NULL',
              'symbols_path': None,
              'test_name_extension': '',
              'test_timeout': 1200,
              'webserver': '',
              'xperf_path': None,
              }
  browser_config = dict(title=title)
  browser_config.update(dict([(i, config[i]) for i in required]))
  browser_config.update(dict([(i, config.get(i, j)) for i, j in optional.items()]))

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

  #pull buildid & sourcestamp from browser
  try:
    browser_config = browserInfo(browser_config, devicemanager = dm)
  except:
    if not browser_config['develop']:
      raise

  if browser_config['remote'] == True:
    procName = browser_config['browser_path'].split('/')[-1]
    if dm.processExist(procName):
      dm.killProcess(procName)

  # setup a webserver, if --develop is specified to PerfConfigurator.py
  httpd = None
  if browser_config['develop'] == True:
    scheme = "http://"
    if (browser_config['webserver'].startswith('http://') or
        browser_config['webserver'].startswith('chrome://') or
        browser_config['webserver'].startswith('file:///')):
      scheme = ""
    elif (browser_config['webserver'].find('://') >= 0):
      print "Unable to parse user defined webserver: '%s'" % (browser_config['webserver'])
      sys.exit(2)

    url = urlparse.urlparse('%s%s' % (scheme, browser_config['webserver']))
    port = url.port

    if port:
      import mozhttpd
      httpd = mozhttpd.MozHttpd(host=url.hostname, port=int(port), docroot=here)
      httpd.start()
    else:
      print "WARNING: unable to start web server without custom port configured"

  # run the tests
  results = {}
  utils.startTimer()
  utils.stamped_msg(title, "Started")
  for test in tests:
    testname = test['name']
    utils.stamped_msg("Running test " + testname, "Started")

    try:
      mytest = TTest(browser_config['remote'])
      browser_dump, counter_dump, print_format = mytest.runTest(browser_config, test)
      utils.debug("Received test results: " + " ".join(browser_dump))
      results[testname] = [browser_dump, counter_dump, print_format, test]
    except talosError, e:
      utils.stamped_msg("Failed " + testname, "Stopped")
      print 'FAIL: Busted: ' + testname
      print 'FAIL: ' + e.msg.replace('\n','\nRETURN:')
      talosError_tb = sys.exc_info()
      traceback.print_exception(*talosError_tb)
      if browser_config['develop'] == True and httpd:
        httpd.stop()
      raise e
    utils.stamped_msg("Completed test " + testname, "Stopped")
  elapsed = utils.stopTimer()
  print "RETURN: cycle time: " + elapsed + "<br>"
  utils.stamped_msg(title, "Stopped")

  # stop the webserver if running
  if browser_config['develop'] == True and httpd:
    httpd.stop()

  #process the results
  if results_url:
    #send results to the graph server
    try:
      utils.stamped_msg("Sending results", "Started")
      links = send_to_graph(results_url, title, date, browser_config, results, amo, filters)
      results_from_graph(links, results_server, amo)
      utils.stamped_msg("Completed sending results", "Stopped")
    except talosError, e:
      utils.stamped_msg("Failed sending results", "Stopped")
      send_to_graph('file://%s' % os.path.join(os.getcwd(), 'results.out'), title, date, browser_config, results, amo, filters)
      print '\nFAIL: ' + e.msg.replace('\n', '\nRETURN:')
      raise e

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
  run_tests(parser.config)

if __name__=='__main__':
  main()
