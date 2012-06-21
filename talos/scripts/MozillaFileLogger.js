/**
 * MozFileLogger, a log listener that can write to a local file.
 */

// Detect if we are on older branches that don't have specialpowers enabled talos available
var ua_plat = window.navigator.userAgent.split('(')[1].split(')')[0];
var parts = ua_plat.split(';');
var useSpecialPowers = true;
if (parts.length >= 2) {
  var rev = parseInt(parts[2].split(':')[1]);
  if (parts[0].replace(/^\s+|\s+$/g, '') == 'Android' && parts[1].replace(/^\s+|\s+$/g, '') == 'Mobile' && parseInt(rev) < 16)
  {
    useSpecialPowers = false;
  }
} //else we are on windows xp or windows 7

var ipcMode = false; // running in e10s build and need to use IPC?
if (!useSpecialPowers) {
  try {
    netscape.security.PrivilegeManager.enablePrivilege("UniversalXPConnect");
    var ipcsanity = Components.classes["@mozilla.org/preferences-service;1"]
                      .getService(Components.interfaces.nsIPrefBranch);
    ipcsanity.setIntPref("mochitest.ipcmode", 0);
  } catch (e) {
    ipcMode = true;
  }
}

function contentDispatchEvent(type, data, sync) {
  if (typeof(data) === "undefined") {
    data = {};
  }

  var element = document.createEvent("datacontainerevent");
  element.initEvent("contentEvent", true, false);
  element.setData("sync", sync);
  element.setData("type", type);
  element.setData("data", JSON.stringify(data));
  document.dispatchEvent(element);
}

function contentSyncEvent(type, data) {
  contentDispatchEvent(type, data, 1);
}

function contentAsyncEvent(type, data) {
  contentDispatchEvent(type, data, 0);
}

//double logging to account for normal mode and ipc mode (mobile_profile only)
//Ideally we would remove the dump() and just do ipc logging
function dumpLog(msg) {
  dump(msg);
  if (ipcMode == true) {
    contentAsyncEvent('Logger', msg);
  } else if (useSpecialPowers) {
    SpecialPowers.log(msg);
  } else {
    MozFileLogger.log(msg);
  }
}


if (!useSpecialPowers) {
  try {
    netscape.security.PrivilegeManager.enablePrivilege("UniversalXPConnect");

    if (Cc === undefined) {
      var Cc = Components.classes;
      var Ci = Components.interfaces;
    }
  } catch (ex) {} //running in ipcMode-chrome
}

try {
  const FOSTREAM_CID = "@mozilla.org/network/file-output-stream;1";
  const LF_CID = "@mozilla.org/file/local;1";
  
  // File status flags. It is a bitwise OR of the following bit flags.
  // Only one of the first three flags below may be used.
  const PR_READ_ONLY    = 0x01; // Open for reading only.
  const PR_WRITE_ONLY   = 0x02; // Open for writing only.
  const PR_READ_WRITE   = 0x04; // Open for reading and writing.
  
  // If the file does not exist, the file is created.
  // If the file exists, this flag has no effect.
  const PR_CREATE_FILE  = 0x08;
  
  // The file pointer is set to the end of the file prior to each write.
  const PR_APPEND       = 0x10;
  
  // If the file exists, its length is truncated to 0.
  const PR_TRUNCATE     = 0x20;
  
  // If set, each write will wait for both the file data
  // and file status to be physically updated.
  const PR_SYNC         = 0x40;
  
  // If the file does not exist, the file is created. If the file already
  // exists, no action and NULL is returned.
  const PR_EXCL         = 0x80;
} catch (ex) {
 // probably not running in the test harness
}

/** Init the file logger with the absolute path to the file.
    It will create and append if the file already exists **/
var MozFileLogger = {};


MozFileLogger.init = function(path) {
  if (ipcMode) {
    contentAsyncEvent("LoggerInit", {"filename": path});
    return;
  }

  try {
    netscape.security.PrivilegeManager.enablePrivilege("UniversalXPConnect");
  } catch (ex) {} //running in ipcMode-chrome

  MozFileLogger._file = Cc[LF_CID].createInstance(Ci.nsILocalFile);
  MozFileLogger._file.initWithPath(path);
  MozFileLogger._foStream = Cc[FOSTREAM_CID].createInstance(Ci.nsIFileOutputStream);
  MozFileLogger._foStream.init(this._file, PR_WRITE_ONLY | PR_CREATE_FILE | PR_APPEND,
                                   0664, 0);
}

MozFileLogger.getLogCallback = function() {
  if (ipcMode) {
    return function(msg) {
      contentAsyncEvent("Logger", {"num": msg.num, "level": msg.level, "info": msg.info.join(' ')});
    }
  }

  return function (msg) {
    try {
      netscape.security.PrivilegeManager.enablePrivilege("UniversalXPConnect");
    } catch(ex) {} //running in ipcMode-chrome

    var data = msg.num + " " + msg.level + " " + msg.info.join(' ') + "\n";
    if (MozFileLogger._foStream)
      MozFileLogger._foStream.write(data, data.length);

    if (data.indexOf("SimpleTest FINISH") >= 0) {
      MozFileLogger.close();
    }
  }
}

// This is only used from chrome space by the reftest harness
MozFileLogger.log = function(msg) {
  netscape.security.PrivilegeManager.enablePrivilege("UniversalXPConnect");

  try {
    if (MozFileLogger._foStream)
      MozFileLogger._foStream.write(msg, msg.length);
  } catch(ex) {}
}

MozFileLogger.close = function() {
  if (ipcMode) {
    contentAsyncEvent("LoggerClose");
    return;
  }

  try {
    netscape.security.PrivilegeManager.enablePrivilege("UniversalXPConnect");
  } catch(ex) {} //running in ipcMode-chrome

  if(MozFileLogger._foStream)
    MozFileLogger._foStream.close();
  
  MozFileLogger._foStream = null;
  MozFileLogger._file = null;
}

if (ipcMode == false) {
  if (!useSpecialPowers) {
    try {
      var prefs = Components.classes['@mozilla.org/preferences-service;1']
        .getService(Components.interfaces.nsIPrefBranch2);
      var filename = prefs.getCharPref('talos.logfile');
      MozFileLogger.init(filename);
    } catch (ex) {} //pref does not exist, return empty string
  } else {
    try {
      var filename = SpecialPowers.getCharPref('talos.logfile');
      SpecialPowers.setLogFile(filename);
    } catch (ex) {} //pref does not exist, return empty string
  }
}

