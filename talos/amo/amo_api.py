
from amo import AMOOAuth
import mozinfo
import os

def avg_excluding_max(values):
  """return float rounded to two decimal places, converted to string
     calculates the average value in the list excluding the max value"""
  i = len(values)
  total = sum(float(v) for v in values)
  maxval = max(float(v) for v in values)
  if total > maxval:
    avg = round((total - maxval)/(i-1), 2)
  else:
    avg = round(total, 2)
  return avg


# This is hacky and specific to the machines that we have for talos (which I tested on)
# Please find a better library to get this information.  The key is we need specific strings
# returned to match values in the AMO database
def getOSDetails():
  import platform

  amo_os_values = {}
  amo_os_values['linux'] = "Linux"
  amo_os_values['win'] = "WINNT"
  amo_os_values['mac'] = "Darwin"

  osname = amo_os_values[mozinfo.info['os']]
  osversion = mozinfo.info['version']
  
  #define os, osversion, platform to match https://bugzilla.mozilla.org/show_bug.cgi?id=693209
  if osname == "Linux":
    relver = platform.release()
    osversion = relver.split('-')[0]

  #return 5.1 instead of 5.1.2600
  elif osname == "WINNT":
    v = osversion.split('.')
    osversion = '.'.join(v[0:-1])

  return osname, osversion, mozinfo.info['processor']

# sample data structure:
# amo.perf({'os':'WINNT', 'version':'1.23', 'platform': 'x86_64',
#           'product': 'fx', 'product_version': '4.2.6',
#           'average': 1.3, 'test': 'ts', 'addon_id': 22})
def upload_amo_results(addonid, appversion, product, testname, vals):  
  os, osversion, platform = getOSDetails()

  data = {'addon_id': addonid,
          'product': product,
          'platform': platform,
          'os': os,
          'average': avg_excluding_max(vals),
          'product_version': appversion,
          'version': osversion,
          'test': testname}

  # TODO: allow for domain to be dynamically configured.  Potentially in the addons.config file
  # NOTE: credentials are stored in ~/.amo-oauth
  amo = AMOOAuth(domain="addons-dev.allizom.org", port=443, protocol='https',
                 prefix='/z')
  retVal = amo.create_perf(data)
  if retVal == "OK":
    print "Uploaded results to AMO successfully: %s" % data
  else:
    print "ERROR: Uploading results to AMO failed: %s : %s" % (retVal, data)
  return retVal

