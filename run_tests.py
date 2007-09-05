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

"""Runs extension performance tests.

   This file runs Ts (startup time) and Tp (page load time) tests
   for an extension with different profiles.  It was originally
   written for the Google Toolbar for Firefox; to make it work for
   another extension modify get_xpi.py.  To change the preferences
   that are set on the profiles that are tested, edit the arrays in
   the main function below.
"""

__author__ = 'annie.sullivan@gmail.com (Annie Sullivan)'


import time
import yaml
import sys
import urllib 
import tempfile
import os
import string
import socket
socket.setdefaulttimeout(480)

import utils
import config
import post_file
import ttest

def shortNames(name):
  if name == "tp_loadtime":
    return "tp_l"
  elif name == "tp_Percent Processor Time":
    return "tp_%cpu"
  elif name == "tp_Working Set":
    return "tp_memset"
  elif name == "tp_Private Bytes":
    return "tp_pbytes"
  else:
    return name

def process_Request(post):
  str = ""
  lines = post.split('\n')
  for line in lines:
    if line.find("RETURN:") > -1:
        str += line.split(":")[3] + ":" + shortNames(line.split(":")[1]) + ":" + line.split(":")[2] + '\n'
  return str

def send_to_csv(results):
  import csv
  for res in results:
    browser_dump, counter_dump = results[res]
    writer = csv.writer(open(config.CSV_FILE + '_' +  res, "wb"))
    if res == 'ts':
      i = 0
      writer.writerow(['i', 'val'])
      for val in browser_dump:
        writer.writerow([i, val])
        i += 1
    if (res.find('tp') > -1) or (res == 'tdhmtl'):
      writer.writerow(['i', 'page', 'median', 'mean', 'min' , 'max', 'runs'])
      for bd in browser_dump:
        bd.rstrip('\n')
        page_results = bd.splitlines()
        i = 0
        for mypage in page_results[2:]:
          r = mypage.split(';')
          if r[1].find('/') > -1 :
             page = r[1].split('/')[1]
          else:
             page = r[1]
          writer.writerow([i, page, r[2], r[3], r[4], r[5], '|'.join(r[6:])])
          i += 1
    for cd in counter_dump:
      for count_type in cd:
        writer = csv.writer(open(config.CSV_FILE + '_' + res + '_' + count_type, "wb"))
        writer.writerow(['i', 'value'])
        i = 0
        for val in cd[count_type]:
          writer.writerow([i, val])
          i += 1

def post_chunk(id, filename):
  tmpf = open(filename, "r")
  file_data = tmpf.read()
  while True:
    try:
      ret = post_file.post_multipart(config.RESULTS_SERVER, config.RESULTS_LINK, [("key", "value")], [("filename", filename, file_data)])
    except IOError:
      print "FAIL: IOError on sending data to the graph server"
    else:
      break
  links = process_Request(ret)
  utils.debug(id + ": sent results")
  return links

def chunk_list(val_list):
  """ 
    divide up a list into manageable chunks
    currently set at length 500 
    this is for a failure on mac os x with python 2.4.4 
  """
  chunks = []
  end = 500
  while (val_list != []):
    chunks.append(val_list[0:end])
    val_list = val_list[end:len(val_list)]
  return chunks

def send_to_graph(title, date, browser_config, results):
  tbox = title
  url_format = "http://%s/%s"
  link_format= "<a href = \"%s\">%s</a>"
  #value, testname, tbox, timeval, date, branch, buildid, type, data
  result_format = "%.2f,%s,%s,%d,%d,%s,%s,%s,%s,\n"
  result_format2 = "%.2f,%s,%s,%d,%d,%s,%s,%s,\n"
  links = ''

  for res in results:
    filename = tempfile.mktemp()
    tmpf = open(filename, "w")
    browser_dump, counter_dump = results[res]
    filename = tempfile.mktemp()
    tmpf = open(filename, "w")
    if res == 'ts':
       i = 0
       for val in browser_dump:
         tmpf.write(result_format % (float(val), res, tbox, i, date, browser_config['branch'], browser_config['buildid'], "discrete", "ms"))
         i += 1
    if (res.find('tp') > -1)  or (res == 'tdhtml'):
       # each line of the string is of the format i;page_name;median;mean;min;max;time vals\n
      for bd in browser_dump:
        bd.rstrip('\n')
        page_results = bd.splitlines()
        i = 0
        for mypage in page_results[2:]:
          r = mypage.split(';')
          if r[1].find('/') > -1 :
             page = r[1].split('/')[1]
          else:
             page = r[1]
          try:
            val = float(r[2])
          except ValueError:
            print 'WARNING: value error for median in tp'
            val = 0
          tmpf.write(result_format % (val, res + '_loadtime', tbox, i, date, browser_config['branch'], browser_config['buildid'], "discrete", page))
          i += 1
    tmpf.flush()
    tmpf.close()
    links += post_chunk(res, filename)
    os.remove(filename)
    for cd in counter_dump:
      for count_type in cd:
        val_list = cd[count_type]
        chunks = chunk_list(val_list)
        chunk_link = ''
        i = 0
        for chunk in chunks:
          filename = tempfile.mktemp()
          tmpf = open(filename, "w")
          for val in chunk:
              tmpf.write(result_format2 % (float(val), res + "_" + count_type.replace("%", "Percent"), tbox, i, date, browser_config['branch'], browser_config['buildid'], "discrete"))
              i += 1
          tmpf.flush()
          tmpf.close()
          chunk_link = post_chunk('%s_%s (%d values)' % (res, count_type, len(chunk)), filename)
          os.remove(filename)
        links += chunk_link
    
  lines = links.split('\n')
  for line in lines:
    if line == "":
      continue
    values = line.split(":")
    linkName = values[1]
    if float(values[2]) > 0:
      linkName += "_T: " + values[2]
    else:
      linkName += "_1"
    url = url_format % (config.RESULTS_SERVER, values[0],)
    link = link_format % (url, linkName,)
    print "RETURN: " + link

def test_file(filename):
  """Runs the Ts and Tp tests on the given config file and generates a report.
  
  Args:
    filename: the name of the file to run the tests on
  """
  
  browser_config = []
  tests = []
  title = ''
  testdate = ''
  results = {}
  
  # Read in the profile info from the YAML config file
  config_file = open(filename, 'r')
  yaml_config = yaml.load(config_file)
  config_file.close()
  for item in yaml_config:
    if item == 'title':
      title = yaml_config[item]
    elif item == 'testdate':
      testdate = yaml_config[item]
  browser_config = {'preferences'  : yaml_config['preferences'],
                    'extensions'   : yaml_config['extensions'],
                    'firefox'      : yaml_config['firefox'],
                    'branch'       : yaml_config['branch'],
                    'buildid'      : yaml_config['buildid'],
                    'profile_path' : yaml_config['profile_path'],
                    'env'          : yaml_config['env'],
                    'dirs'         : yaml_config['dirs']}
  tests = yaml_config['tests']
  config_file.close()
  if (testdate != ''):
    date = int(time.mktime(time.strptime(testdate, '%a, %d %b %Y %H:%M:%S GMT')))
  else:
    date = int(time.time()) #TODO get this into own file
  utils.debug("using testdate: %d" % date)
  utils.debug("actual date: %d" % int(time.time()))

  for test in tests:
    print "Running test: " + test
    res, browser_dump, counter_dump = ttest.runTest(browser_config, tests[test])
    if not res:
      print 'FAIL: failure to complete test: ' + test
      sys.exit(0)
    results[test] = [browser_dump, counter_dump]
    print "Completed test: " + test

  #process the results
  if config.TO_GRAPH_SERVER:
    #send results to the graph server
    send_to_graph(title, date, browser_config, results)
  if config.TO_CSV:
    send_to_csv(results)
  
if __name__=='__main__':

  # Read in each config file and run the tests on it.
  for i in range(1, len(sys.argv)):
    utils.debug("running test file " + sys.argv[i])
    test_file(sys.argv[i])

