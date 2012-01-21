import calendar
import datetime
import gzip
import re
import socket
import StringIO
import urllib2
import weakref
import yaml


class AutologProduct(object):
  """Class which represents a product, e.g., Firefox"""

  def __init__(self, tree=None, revision=None, branch=None,
               buildtype=None, buildid=None, version=None,
               buildurl=None, productname=None):
    self.tree = tree
    self.revision = revision
    self.branch = branch
    self.buildtype = buildtype
    self.buildid = buildid
    self.version = version
    self.buildurl = buildurl
    self.productname = productname

  def _to_json(self):
    return ({
      'productname': self.productname,
      'tree': self.tree,
      'revision': self.revision,
      'branch': self.branch,
      'buildtype': self.buildtype,
      'buildid': self.buildid,
      'version': self.version,
      'buildurl': self.buildurl,
    })


class AutologTestPass(object):
  """Class which represents a passing test in autolog"""

  def __init__(self, test=None, logurl=None, testgroup_id=None,
               testsuite_id=None, id=None, doc_type=None,
               duration=None):
    self.test = test
    self.logurl = logurl
    self.testgroup_id = testgroup_id
    self.testsuite_id = testsuite_id
    self.dirty = True
    self.id = id
    self.duration = duration
    if doc_type:
      self.doc_type = doc_type
    else:
      self.doc_type = "testpasses"

  def _to_json(self):
    testpass = {
      'test': self.test,
      'testgroup_id': self.testgroup_id,
      'testsuite_id': self.testsuite_id,
    }

    if self.logurl:
      testpass.update({'logurl': self.logurl})

    if self.duration:
      testpass.update({ 'duration': self.duration })

    if self.id:
      testpass.update({ 'testpass_id': self.id })

    return testpass


class AutologPerformanceData(object):
  """Class which represents performance data in autolog"""

  def __init__(self, test=None, testgroup_id=None, testsuite_id=None,
               id=None, doc_type=None, **kwargs):
    self.test = test
    self.testgroup_id = testgroup_id
    self.testsuite_id = testsuite_id
    self.data = []
    self.id = id
    if doc_type:
      self.doc_type = doc_type 
    else:
      self.doc_type = 'perfdata'

    self.add_data(**kwargs)

  def add_data(self, **kwargs):
    self.data.append(dict(kwargs))
    self.dirty = True

  def _to_json(self):
    perfdata = {
      'test': self.test,
      'testgroup_id': self.testgroup_id,
      'testsuite_id': self.testsuite_id,
      'perfdata': self.data,
    }

    if self.id:
      perfdata.update({ 'perfdata_id': self.id })

    return perfdata


class AutologTestFailure(object):
  """Class which represents a test failure in autolog"""

  def __init__(self, test=None, logurl=None, testgroup_id=None,
               testsuite_id=None, id=None, doc_type=None,
               duration=None, **kwargs):
    self.test = test
    self.logurl = logurl
    self.testgroup_id = testgroup_id
    self.testsuite_id = testsuite_id
    self.errors = []
    self.id = id
    self.duration = duration
    if doc_type:
      self.doc_type = doc_type 
    else:
      self.doc_type = "testfailures"
    self.add_error(**kwargs)

  def add_error(self, **kwargs):
    self.errors.append(dict(kwargs))
    self.dirty = True

  def _to_json(self):
    testfailure = {
      'test': self.test,
      'logurl': self.logurl,
      'testgroup_id': self.testgroup_id,
      'testsuite_id': self.testsuite_id,
      'errors': self.errors,
    }

    if self.duration:
      testfailure.update({ 'duration': self.duration })

    if self.id:
      testfailure.update({ 'testfailure_id': self.id })

    return testfailure


class AutologTestSuite(object):
  """Class which represents a test suite in autolog"""

  def __init__(self, cmdline=None, testsuite=None, passed=0,
               failed=0, todo=0, elapsedtime=None, testgroup_id=None,
               id=None, doc_type=None):
    self.testgroup_id = testgroup_id
    self.testfailures = []
    self.perfdata = []
    self.testpasses = []
    self.id = id
    self.cmdline = cmdline
    self.testsuite = testsuite
    self.passed = passed
    self.failed = failed
    self.todo = todo
    self.elapsedtime = elapsedtime
    self.dirty = True
    if doc_type:
      self.doc_type = doc_type
    else:
      self.doc_type = "testsuites"

  def _to_json(self):
    testsuite = {
      'testsuite': self.testsuite,
      'cmdline': self.cmdline,
      'elapsedtime': self.elapsedtime,
      'passed': self.passed,
      'failed': self.failed,
      'todo': self.todo,
      'testgroup_id': self.testgroup_id,
      'testfailure_count': len(self.testfailures),
    }

    if self.id:
      testsuite.update({ 'testsuite_id': self.id })

    return testsuite


class AutologTestGroup(object):
  """Class which represents a test group in autolog"""

  def __init__(self, harness=None, testgroup=None, server=None, machine=None,
               starttime=None, logurl=None, platform=None,
               os=None, testrun=None, pending=False, index='autolog',
               doc_types=None, builder=None, id=None, errors=None,
               restserver=None, logfile=None):
    self._logs = weakref.WeakKeyDictionary()

    # make sure server names are str, not unicode
    if server:
      self.server = str(server) 
    else:
      self.server = 'elasticsearch1.metrics.sjc1.mozilla.com:9200'
    if restserver:
      self.restserver = str(restserver)
    else:
      self.restserver = 'http://brasstacks.mozilla.com/autologserver/'

    self.testsuites = []
    self.total_test_failures = 0
    self.total_perf_records = 0
    self.id = id
    self.harness = harness
    self.testgroup = testgroup
    if machine:
      self.machine = machine
    else:
      self.machine = socket.gethostname()
    self.logurl = logurl
    self.platform = platform
    self.os = os
    self.testrun = testrun
    self.product = None
    self.secondary_products = []
    self.dirty = True
    self._pending = pending
    self.builder = builder
    self.errors = errors
    self._logfile = None

    if isinstance(index, list) and len(index) == 1:
      index = [index[0], index[0]]
    if isinstance(index, basestring):
      index = [index, index]

    self.read_index = index[0]
    self.write_index = index[1]

    if not doc_types:
      self.doc_type = 'testgroups'
      self.testsuite_doc_type = 'testsuites'
      self.testfailure_doc_type = 'testfailures'
    else:
      self.doc_type = doc_types[0]
      self.testsuite_doc_type = doc_types[1]
      self.testfailure_doc_type = doc_types[2]
    self.perfdata_doc_type = 'perfdata'

    if starttime:
      if isinstance(starttime, datetime.datetime):
        self.starttime = calendar.timegm(starttime.timetuple())
      else:
        self.starttime = int(starttime)
    else:
      self.starttime = calendar.timegm(datetime.datetime.utcnow().timetuple())

    self.date = datetime.datetime.utcfromtimestamp(self.starttime).strftime('%Y-%m-%d')

    if not self.platform and self.os:
      self.platform = self.get_platform_from_os(self.os)

    if logfile:
      self.logfile = logfile

  @classmethod
  def get_platform_from_os(cls, os):
    if re.search(r'linux.*64', os, re.I) or \
       re.search(r'fedora.*64', os, re.I):
      return 'linux64'

    if re.search(r'linux', os, re.I) or \
       re.search(r'fedora', os, re.I) or \
       re.search(r'static-analysis', os):
      return 'linux'

    if re.search(r'macosx64', os) or \
       re.search(r'snowleopard', os) or \
       re.search(r'OS\s?X.*10\.6', os):
      return 'macosx64'

    if re.search(r'macosx', os) or \
       re.search(r'leopard', os) or \
       re.search(r'OS\s?X', os):
      return 'macosx'

    if re.search(r'w764', os) or \
       re.search(r'WINNT 6\.1 x64', os, re.I):
      return 'win64'

    if re.search(r'WINNT', os, re.I) or \
       re.search(r'win7', os, re.I) or \
       re.search(r'win32', os) or \
       re.search(r'xp', os):
      return 'win32'

    if re.search(r'android', os, re.I):
      return 'android'

    if re.search(r'Maemo 5', os, re.I) or \
       re.search(r'N8100', os, re.I):
      return 'maemo5'

    if re.search(r'Maemo', os, re.I) or \
       re.search(r'N900', os, re.I):
      return 'maemo4'

    return 'unknown'

  def getlogfile(self):
    return self._logfile

  def setlogfile(self, logfile):
    """Adds the specified logfile to this testgroup"""
    self._logfile = logfile
    self._add_logfile(self, logfile)

  logfile = property(getlogfile, setlogfile)

  def getpending(self):
    return self._pending

  def setpending(self, value):
    if value != self._pending:
      self.dirty = True
    self._pending = value

  pending = property(getpending, setpending)

  def _add_logfile(self, proxy, logfile):
    """Adds a logfile, along with a proxy for the instance to which the
       the log belongs, to our log list.  Logs can belong to a testgroup
       or a testfailure.
    """
    self._logs.update({proxy: logfile})

  def _add_common_properties(self, dict):
    dict.update({ 'platform': self.platform,
                  'os': self.os,
                  'testgroup': self.testgroup,
                  'starttime': self.starttime,
                  'date': self.date,
                  'machine': self.machine,
                })

    if self.product:
      dict.update({ 'tree': self.product.tree,
                    'revision': self.product.revision,
                    'buildtype': self.product.buildtype,
                    'buildid': self.product.buildid,
                  })

  def add_secondary_product(self, tree=None, revision=None, branch=None,
                            buildtype=None, buildid=None, version=None,
                            buildurl=None, productname=None):
    self.secondary_products.append(AutologProduct(
        tree=tree, branch=branch, revision=revision, buildtype=buildtype,
        version=version, buildurl=buildurl, productname=productname
      ))
    self.dirty = True

  def set_primary_product(self, tree=None, revision=None, branch=None,
                          buildtype=None, buildid=None, version=None,
                          buildurl=None, productname=None):
    if not tree or not revision:
      raise Exception('tree and revision must be specified for primary product')
    self.product = AutologProduct(tree=tree, revision=revision,
                                  branch=branch, buildtype=buildtype,
                                  buildid=buildid, version=version,
                                  buildurl=buildurl, productname=productname)
    self.dirty = True

  def _to_json(self):
    self.total_test_failures = 0
    self.total_perf_records = 0
    for testsuite in self.testsuites:
      for testfailure in testsuite.testfailures:
        self.total_test_failures += len(testfailure.errors)
      self.total_perf_records += len(testsuite.perfdata)

    testgroup = {
      'harness': self.harness,
      'testgroup': self.testgroup,
      'total_test_failures': self.total_test_failures,
      'total_perf_records': self.total_perf_records,
      'machine': self.machine,
      'logurl': self.logurl,
      'platform': self.platform,
      'os': self.os,
      'testrun': self.testrun,
      'starttime': self.starttime,
      'testsuite_count': len(self.testsuites),
      'pending': self.pending,
      'builder': self.builder,
      'date': self.date,
      'frameworkfailures': self.errors,
    }

    if self.id:
      testgroup.update({ 'testgroup_id': self.id })

    if self.product:
      testgroup.update(self.product._to_json())

    if self.secondary_products:
      products = []
      for product in self.secondary_products:
        products.append(product._to_json())
      testgroup.update({ 'secondary_products': products })

    return testgroup

  def submit(self):
    """Submit the testgroup (and related objects, if any) to the Autolog
       database.
    """

    # should be implemented in subclass
    raise NotImplementedError

  def add_test_suite(self, testsuite=None, elapsedtime=None, cmdline=None,
                   passed=0, failed=0, todo=0, id=None):
    if not testsuite:
      testsuite = self.testgroup

    self.testsuites.append(AutologTestSuite(
      testsuite = testsuite,
      elapsedtime = elapsedtime,
      cmdline = cmdline,
      passed = passed,
      failed = failed,
      todo = todo,
      testgroup_id = self.id,
      id = id,
      doc_type = self.testsuite_doc_type
    ))

    self.dirty = True

  def add_test_pass(self, test=None, logurl=None, id=None, duration=None, doc_type=None):
    """add a passing test to the most recent testsuite"""

    assert(len(self.testsuites))

    # get the most recent testsuite
    testsuite = self.testsuites[-1]

    # add the error to the existing related testfailure, or create a new one
    testpass = AutologTestPass(
      test = test,
      logurl = logurl,
      testgroup_id = self.id,
      testsuite_id = testsuite.id,
      id = id,
      duration = duration,
      doc_type = doc_type
    )
    testsuite.testpasses.append(testpass)

    self.dirty = True
    testsuite.dirty = True

  def add_perf_data(self, test=None, id=None, **kwargs):
    """add performance data to the most recent testsuite"""

    # create a dummy testsuite object if none exists
    if not len(self.testsuites):
      self.add_test_suite()

    # get the most recent testsuite
    testsuite = self.testsuites[-1]

    # find an existing performance record for this test, if any
    perfdata = [data for data in testsuite.perfdata if data.test == test]
    if perfdata:
      perfdata = perfdata[0]

    # add the data to the existing performance rcord, if any, or create a new one
    if perfdata:
      perfdata.add_data(**kwargs)
    else:
      perfdata = AutologPerformanceData(
        testgroup_id = self.id,
        testsuite_id = testsuite.id,
        id = id,
        test = test,
        doc_type = self.perfdata_doc_type,
        **kwargs
      )
      testsuite.perfdata.append(perfdata)

    self.dirty = True
    testsuite.dirty = True

  def add_test_failure(self, test=None, logurl=None, id=None, duration=None,
                       logfile=None, **kwargs):
    """add a test failure to the most recent testsuite"""

    assert(len(self.testsuites))

    # get the most recent testsuite
    testsuite = self.testsuites[-1]

    # find an existing testfailure for this test, if any
    testfailure = next((failure for failure in testsuite.testfailures if failure.test == test), None)

    # add the error to the existing related testfailure, or create a new one
    if testfailure:
      testfailure.add_error(**kwargs)
    else:
      testfailure = AutologTestFailure(
        test = test,
        logurl = logurl,
        testgroup_id = self.id,
        testsuite_id = testsuite.id,
        id = id,
        duration = duration,
        doc_type = self.testfailure_doc_type,
        **kwargs
      )
      testsuite.testfailures.append(testfailure)

    self.dirty = True
    testsuite.dirty = True

    if logfile:
      self._add_logfile(testfailure, logfile)


class RESTfulAutologTestGroup(AutologTestGroup):

  def __init__(self, **kwargs):
    AutologTestGroup.__init__(self, **kwargs)

  def submit(self):
    """Submit the testgroup and related objects to the Autolog server
       via HTTP POST.
    """

    # build the JSON to send to the autolog server
    data = {
      'testgroup': self._to_json(),
      'server': self.server,
      'index': [self.read_index, self.write_index],
      'doc_types': [self.doc_type, self.testsuite_doc_type, self.testfailure_doc_type],
      'testsuites': []
    }

    for testsuite in self.testsuites:
      if len(testsuite.testpasses):
        raise("Submitting passing tests not supported via REST API")

      data['testsuites'].append(testsuite._to_json())
      data['testsuites'][-1].update({'testfailures': [],
                                     'perfdata': []})

      for testfailure in testsuite.testfailures:
        data['testsuites'][-1]['testfailures'].append(testfailure._to_json())

      for perfdata in testsuite.perfdata:
        data['testsuites'][-1]['perfdata'].append(perfdata._to_json())

    # make the HTTP POST
    host = "%s/addtestgroup" % self.restserver
    req = urllib2.Request(host, yaml.dump(data), {'content-type': 'text/yaml'})
    response_stream = urllib2.urlopen(req)
    response = yaml.load(response_stream.read())

    # Retrieve the testrun, testgroup_id, and testsuite_id's from the
    # HTTP response JSON, and update the related objects with them.  We
    # rely on the fact that testsuites and testfailures are returned in
    # the same order that they were sent.
    if response.get('testgroup_id'):
      self.id = response.get('testgroup_id')
      self.testrun = response.get('testrun')
      for idx, testsuite in enumerate(self.testsuites):
        testsuite.testgroup_id = self.id
        try:
          testsuite.id = response['testsuites'][idx].get('testsuite_id')
        except:
          pass

        for fidx, testfailure in enumerate(testsuite.testfailures):
          testfailure.testsuite_id = testsuite.id
          testfailure.testgroup_id = self.id
          try:
            testfailure.id = response['testsuites'][idx]['testfailures'][fidx].get('testfailure_id')
          except:
            pass

        for pidx, perfdata in enumerate(testsuite.perfdata):
          perfdata.testsuite_id = testsuite.id
          perfdata.testgroup_id = self.id
          try:
            perfdata.id = response['testsuites'][idx]['perfdata'][pidx].get('perfdata_id')
          except:
            pass

    # if there are any logfiles, gzip them and post them to the server now
    for obj in self._logs:
      # each logfile object is an (Autolog object instance, filename) tuple
      if obj.id:
        # read the contents of the logfile
        f = open(self._logs[obj], 'r+b')
        contents = f.read()
        f.close()

        # gzip the contents into a string buffer
        buffer = StringIO.StringIO()
        gzip_fh = gzip.GzipFile(fileobj=buffer, mode='w+b')
        gzip_fh.write(contents)
        gzip_fh.close()

        # post the gzipped buffer to the autolog server
        host = "%s/savelog?contenttype=text/yaml&id=%s&read_index=%s&write_index=%s&doc_type=%s&server=%s" % \
                                                  (self.restserver,
                                                   obj.id,
                                                   self.read_index,
                                                   self.write_index,
                                                   obj.doc_type,
                                                   self.server)
        req = urllib2.Request(host,
                              buffer.getvalue(),
                              {'content-type': 'application/gzip'})
        response_stream = urllib2.urlopen(req)
        response = yaml.load(response_stream.read())
        if 'url' in response:
          obj.logurl = response['url']
        buffer.close()
