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


import optparse
import os
import re
import sys
import time
import urlparse
import yaml
import PerfConfigurator
import utils
from utils import talosError
import post_file
from ttest import TTest
from filter import ignore_first, median
from results import PageloaderResults

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
        links += line.replace("RETURN\t", "") + '\n'
    utils.debug("process_Request line: " + line.replace("RETURN\t", ""))
  if not links:
    raise talosError("send failed, graph server says:\n" + post)
  return links

def responsiveness_Metric(val_list):
  s = sum([int(x)*int(x) / 1000000.0 for x in val_list])
  return str(round(s))

def send_to_csv(csv_dir, results):
  import csv
  def avg_excluding_max(val_list):
    """return float rounded to two decimal places, converted to string
       calculates the average value in the list exluding the max value"""
    i = len(val_list)
    total = sum(float(v) for v in val_list)
    maxval = max(float(v) for v in val_list)
    if total > maxval:
      avg = str(round((total - maxval)/(i-1), 2))
    else:
      avg = str(round(total, 2))
    return avg

  for res in results:
    browser_dump, counter_dump, print_format = results[res]
    if csv_dir:
      writer = csv.writer(open(os.path.join(csv_dir, res + '.csv'), "wb"))
    else: #working with stdout
      writer = csv.writer(sys.stdout)
    if print_format == 'tsformat':
      i = 0
      res_list = []
      writer.writerow(['i', 'val'])
      for val in browser_dump:
        val_list = val.split('|')
        for v in val_list:
          writer.writerow([i, v])
          i += 1
          res_list.append(v)
      writer.writerow(['RETURN: ' + res + ': ' + avg_excluding_max(res_list),])
    elif print_format == 'tpformat':
      writer.writerow(['i', 'page', 'median', 'mean', 'min' , 'max', 'runs'])
      for bd in browser_dump:
        bd.rstrip('\n')
        page_results = bd.splitlines()
        i = 0
        res_list = []
        for mypage in page_results:
          r = mypage.split(';')
          #skip this line if it isn't the correct format
          if len(r) == 1:
              continue
          r[1] = r[1].rstrip('/')
          if r[1].find('/') > -1 :
             page = r[1].split('/')[1]
          else:
             page = r[1]
          res_list.append(r[2])
          writer.writerow([i, page, r[2], r[3], r[4], r[5], '|'.join(r[6:])])
          i += 1
        writer.writerow(['RETURN: ' + res + ': ' + avg_excluding_max(res_list), ])
    else:
      raise talosError("Unknown print format in send_to_csv")
    for cd in counter_dump:
      for count_type in cd:
        counterName = res + '_' + shortName(count_type)
        if cd[count_type] == []: #failed to collect any data for this counter
          utils.stamped_msg("No results collected for: " + counterName, "Error")
          continue
        if csv_dir:
          writer = csv.writer(open(os.path.join(csv_dir, counterName + '.csv'), "wb"))
        else:
          writer = csv.writer(sys.stdout)
        writer.writerow(['i', 'value'])
        i = 0
        for val in cd[count_type]:
          writer.writerow([i, val])
          i += 1
        if isMemoryMetric(shortName(count_type)):
          writer.writerow(['RETURN: ' + counterName + ': ' + filesizeformat(avg_excluding_max(cd[count_type])),])
        elif count_type == 'responsiveness':
          writer.writerow(['RETURN: ' + counterName + ': ' + responsiveness_Metric(cd[count_type]),])
        else:
          writer.writerow(['RETURN: ' + counterName + ': ' + avg_excluding_max(cd[count_type]),])

def construct_results (machine, testname, browser_config, date, vals, amo):
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

def send_to_graph(results_url, machine, date, browser_config, results, amo):
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
    browser_dump, counter_dump, print_format = results[testname]
    utils.debug("Working with test: " + testname)
    utils.debug("Sending results: " + " ".join(browser_dump))
    utils.stamped_msg("Generating results file: " + testname, "Started")
    if print_format == 'tsformat':
      #non-tpformat results
      for bd in browser_dump:
        vals.extend([[x, 'NULL'] for x in bd.split('|')])
    elif print_format == 'tpformat':
      #tpformat results
      fullname += browser_config['test_name_extension']
      for bd in browser_dump:
        page_results = PageloaderResults(bd)
        if browser_config['ignore_first']:
            newvals = page_results.filter(ignore_first, median)
        else:
            newvals = page_results.median()
        newvals = [[val, page] for val, page in newvals if val > -1]
        vals.extend(newvals)
    else:
      raise talosError("Unknown print format in send_to_graph")
    result_strings.append(construct_results(machine, fullname, browser_config, date, vals, amo))
    result_testnames.append(fullname)

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
    for cd in counter_dump:
      for count_type in cd:
        counterName = testname + '_' + shortName(count_type)
        if cd[count_type] == []: #failed to collect any data for this counter
          utils.stamped_msg("No results collected for: " + counterName, "Error")
          continue
        vals = [[x, 'NULL'] for x in cd[count_type]]
        if print_format == "tpformat":
          counterName += browser_config['test_name_extension']
        utils.stamped_msg("Generating results file: " + counterName, "Started")
        result_strings.append(construct_results(machine, counterName, browser_config, date, vals, amo))
        result_testnames.append(counterName)
        utils.stamped_msg("Generating results file: " + counterName, "Stopped")

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
          links += process_Request(post_file.post_multipart(results_server, results_path, [("key", "value")], [("filename", "data_string", data_string)]))
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

def browserInfo(browser_config, devicemanager = None):
  """Get the buildid and sourcestamp from the application.ini (if it exists)
  """
  appIniFileName = "application.ini"
  appIniPath = os.path.join(os.path.dirname(browser_config['browser_path']), appIniFileName)
  if os.path.isfile(appIniPath) or devicemanager != None:
    if (devicemanager != None):
      if (browser_config['browser_path'].startswith('org.mozilla.f')):
        remoteAppIni = '/data/data/' + browser_config['browser_path'] + '/' + appIniFileName
      else:
        remoteAppIni = browser_config['deviceroot'] + '/' + appIniFileName
      if (not os.path.isfile('remoteapp.ini')):
        devicemanager.getFile(remoteAppIni, 'remoteapp.ini')
      appIni = open('remoteapp.ini')
    else:
      appIni = open(appIniPath)
    appIniContents = appIni.readlines()
    appIni.close()
    reSourceStamp = re.compile('SourceStamp\s*=\s*(.*)$')
    reRepository = re.compile('SourceRepository\s*=\s*(.*)$')
    reBuildID = re.compile('BuildID\s*=\s*(.*)$')
    reName = re.compile('Name\s*=\s*(.*)$')
    reVersion = re.compile('Version\s*=\s*(.*)$')
    for line in appIniContents:
      match = re.match(reBuildID, line)
      if match:
        browser_config['buildid'] = match.group(1)
      match = re.match(reRepository, line)
      if match:
          browser_config['repository'] = match.group(1)
      match = re.match(reSourceStamp, line)
      if match:
          browser_config['sourcestamp'] = match.group(1)
      match = re.match(reName, line)
      if match:
          browser_config['browser_name'] = match.group(1)
      match = re.match(reVersion, line)
      if match:
          browser_config['browser_version'] = match.group(1)
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

def test_file(filename, options, parsed):
  """Runs the talos tests on the given config file and generates a report.

  Args:
    filename: the name of the file to run the tests on
    options: TalosOptions from command line parser
    defaults: defaults supplied by command line parser
  """

  # Read in the profile info from the YAML config file
  config_file = open(filename, 'r')
  yaml_config = yaml.load(config_file)
  config_file.close()
  tests = yaml_config['tests']
  tests = useBaseTestDefaults(yaml_config.get('basetest', []), tests)

  # Override yaml_config if options are provided
  options = options.__dict__
  yaml_config.update(dict([(i,j) for i, j in options.items() if i in parsed]))

  # set defaults
  title = yaml_config.get('title', '')
  testdate = yaml_config.get('testdate', '')
  results_url = yaml_config.get('results_url', '')
  csv_dir = yaml_config.get('csv_dir', '')

  # markup data
  if csv_dir:
    csv_dir = os.path.normpath(csv_dir)
    if not os.path.exists(csv_dir):
      print 'FAIL: path "%s" does not exist' % csv_dir
      sys.exit(1)
  if results_url:
    results_url_split = urlparse.urlsplit(results_url)
    results_scheme, results_server, results_path, _, _ = results_url_split
    if results_scheme in ('http', 'https') and not post_file.link_exists(results_server, results_path):
      print 'WARNING: graph server link does not exist'

  # set browser_config
  required = ['preferences', 'extensions',
              'browser_path', 'browser_log', 'browser_wait',
              'process', 'extra_args', 'branch', 'buildid', 'env', 'init_url'
              ]
  optional = {'addon_id': 'NULL',
              'bcontroller_config': 'bcontroller.yml',
              'bundles': {},
              'branch_name': '',
              'child_process': 'plugin-container',
              'develop': False,
              'deviceroot': '',
              'dirs': {},
              'host': yaml_config.get('deviceip', ''), # XXX names should match!
              'port': yaml_config.get('deviceport', ''), # XXX names should match!
              'remote': False,
              'fennecIDs': '',
              'repository': 'NULL',
              'source_stamp': 'NULL',
              'symbols_path': None,
              'test_name_extension': '',
              'test_timeout': 1200,
              'webserver': '',
              'xperf_path': None,
              'ignore_first': False
              }
  browser_config = dict(title=title)
  browser_config.update(dict([(i, yaml_config[i]) for i in required]))
  browser_config.update(dict([(i, yaml_config.get(i, j)) for i, j in optional.items()]))

  # get device manager if specified
  dm = None
  if browser_config['remote'] == True:
    if browser_config['port'] == -1:
        from mozdevice import devicemanagerADB
        dm = devicemanagerADB.DeviceManagerADB(browser_config['host'], browser_config['port'])
    else:
        from mozdevice import devicemanagerSUT
        dm = devicemanagerSUT.DeviceManagerSUT(browser_config['host'], browser_config['port'])

  #normalize paths to work accross platforms
  browser_config['browser_path'] = os.path.normpath(browser_config['browser_path'])
  for dir in browser_config['dirs']:
    browser_config['dirs'][dir] = os.path.normpath(browser_config['dirs'][dir])
  for bname in browser_config['bundles']:
    browser_config['bundles'][bname] = os.path.normpath(browser_config['bundles'][bname])

  # get test date in seconds since epoch
  if testdate:
    date = int(time.mktime(time.strptime(testdate, '%a, %d %b %Y %H:%M:%S GMT')))
  else:
    date = int(time.time())
  utils.debug("using testdate: %d" % date)
  utils.debug("actual date: %d" % int(time.time()))

  #pull buildid & sourcestamp from browser
  browser_config = browserInfo(browser_config, devicemanager = dm)

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
      httpd = mozhttpd.MozHttpd(host=url.hostname, port=int(port), docroot=os.path.split(os.path.realpath(__file__))[0])
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
      results[testname] = [browser_dump, counter_dump, print_format]
      # If we're doing CSV, write this test immediately (bug 419367)
      if csv_dir:
        send_to_csv(csv_dir, {testname : results[testname]})
      if options["to_screen"] or options["amo"]:
        send_to_csv(None, {testname : results[testname]})
    except talosError, e:
      utils.stamped_msg("Failed " + testname, "Stopped")
      print 'FAIL: Busted: ' + testname
      print 'FAIL: ' + e.msg.replace('\n','\nRETURN:')
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
      links = send_to_graph(results_url, title, date, browser_config, results, options["amo"])
      results_from_graph(links, results_server, options["amo"])
      utils.stamped_msg("Completed sending results", "Stopped")
    except talosError, e:
      utils.stamped_msg("Failed sending results", "Stopped")
      #failed to send results, just print to screen and then report graph server error
      for test in tests:
        testname = test['name']
        send_to_csv(None, {testname : results[testname]})
      print '\nFAIL: ' + e.msg.replace('\n', '\nRETURN:')
      raise e

def main(args=sys.argv[1:]):

  # parse command line options
  parser = PerfConfigurator.TalosOptions()
  parser.add_option('-d', '--debug', dest='debug',
                    action='store_true', default=False,
                    help="enable debug")
  parser.add_option('-n', '--noisy', dest='noisy',
                    action='store_true', default=False,
                    help="enable noisy output")
  parser.add_option('-s', '--screen', dest='to_screen',
                    action='store_true', default=False,
                    help="set screen")

  options, args = parser.parse_args(args)

  # set variables
  if options.debug:
    print 'setting debug'
    utils.setdebug(1)
  if options.noisy:
    utils.setnoisy(1)

  # Read in each config file and run the tests on it.
  for arg in args:
    utils.debug("running test file " + arg)
    test_file(arg, options, parser.parsed)

if __name__=='__main__':
  main()
