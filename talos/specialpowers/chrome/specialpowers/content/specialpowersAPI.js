/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */
/* This code is loaded in every child process that is started by mochitest in
 * order to be used as a replacement for UniversalXPConnect
 */

var Ci = Components.interfaces;
var Cc = Components.classes;

function SpecialPowersAPI() { 
  this._mfl = null;
}

function bindDOMWindowUtils(aWindow) {
  if (!aWindow)
    return

  var util = aWindow.QueryInterface(Components.interfaces.nsIInterfaceRequestor)
                   .getInterface(Components.interfaces.nsIDOMWindowUtils);
  // This bit of magic brought to you by the letters
  // B Z, and E, S and the number 5.
  //
  // Take all of the properties on the nsIDOMWindowUtils-implementing
  // object, and rebind them onto a new object with a stub that uses
  // apply to call them from this privileged scope. This way we don't
  // have to explicitly stub out new methods that appear on
  // nsIDOMWindowUtils.
  //
  // Note that this will be a chrome object that is (possibly) exposed to
  // content. Make sure to define __exposedProps__ for each property to make
  // sure that it gets through the security membrane.
  var proto = Object.getPrototypeOf(util);
  var target = { __exposedProps__: {} };
  function rebind(desc, prop) {
    if (prop in desc && typeof(desc[prop]) == "function") {
      var oldval = desc[prop];
      try {
        desc[prop] = function() {
          return oldval.apply(util, arguments);
        };
      } catch (ex) {
        dump("WARNING: Special Powers failed to rebind function: " + desc + "::" + prop + "\n");
      }
    }
  }
  for (var i in proto) {
    var desc = Object.getOwnPropertyDescriptor(proto, i);
    rebind(desc, "get");
    rebind(desc, "set");
    rebind(desc, "value");
    Object.defineProperty(target, i, desc);
    target.__exposedProps__[i] = 'rw';
  }
  return target;
}

SpecialPowersAPI.prototype = {
  // Mimic the get*Pref API
  getBoolPref: function(aPrefName) {
    return (this._getPref(aPrefName, 'BOOL'));
  },
  getIntPref: function(aPrefName) {
    return (this._getPref(aPrefName, 'INT'));
  },
  getCharPref: function(aPrefName) {
    return (this._getPref(aPrefName, 'CHAR'));
  },
  getComplexValue: function(aPrefName, aIid) {
    return (this._getPref(aPrefName, 'COMPLEX', aIid));
  },

  // Mimic the set*Pref API
  setBoolPref: function(aPrefName, aValue) {
    return (this._setPref(aPrefName, 'BOOL', aValue));
  },
  setIntPref: function(aPrefName, aValue) {
    return (this._setPref(aPrefName, 'INT', aValue));
  },
  setCharPref: function(aPrefName, aValue) {
    return (this._setPref(aPrefName, 'CHAR', aValue));
  },
  setComplexValue: function(aPrefName, aIid, aValue) {
    return (this._setPref(aPrefName, 'COMPLEX', aValue, aIid));
  },

  // Mimic the clearUserPref API
  clearUserPref: function(aPrefName) {
    var msg = {'op':'clear', 'prefName': aPrefName, 'prefType': ""};
    this._sendSyncMessage('SPPrefService', msg);
  },

  // Private pref functions to communicate to chrome
  _getPref: function(aPrefName, aPrefType, aIid) {
    var msg = {};
    if (aIid) {
      // Overloading prefValue to handle complex prefs
      msg = {'op':'get', 'prefName': aPrefName, 'prefType':aPrefType, 'prefValue':[aIid]};
    } else {
      msg = {'op':'get', 'prefName': aPrefName,'prefType': aPrefType};
    }
    var val = this._sendSyncMessage('SPPrefService', msg);

    if (val == null || val[0] == null)
      throw "Error getting pref";
    return val[0];
  },
  _setPref: function(aPrefName, aPrefType, aValue, aIid) {
    var msg = {};
    if (aIid) {
      msg = {'op':'set','prefName':aPrefName, 'prefType': aPrefType, 'prefValue': [aIid,aValue]};
    } else {
      msg = {'op':'set', 'prefName': aPrefName, 'prefType': aPrefType, 'prefValue': aValue};
    }
    return(this._sendSyncMessage('SPPrefService', msg)[0]);
  },

  getConsoleMessages: function() {
    var consoleService = Cc['@mozilla.org/consoleservice;1'].getService(Ci.nsIConsoleService);
    var messages = {}
    consoleService.getMessageArray(messages, {});
    var retVal = {}
    retVal.value = []
    for (var i = 0; i < messages.value.length; i++) {
      ival = messages.value[i];
      if (ival === undefined || ival == null)
        continue;

      retVal.value[i] = {}
      rval = retVal.value[i];
      for (var obj in ival) {
        rval[obj] = ival[obj];
      }
    }
    return retVal;
  },

  get ID() {
    var appInfo = Cc["@mozilla.org/xre/app-info;1"].getService(Ci.nsIXULAppInfo);
    try {
      var id = appInfo.ID;
      return id;
    } catch(err) {};
    return null;
  },

  get Version() {
    var appInfo = Cc["@mozilla.org/xre/app-info;1"].getService(Ci.nsIXULAppInfo);
    return appInfo.version;
  },

  get BuildID() {
    var appInfo = Cc["@mozilla.org/xre/app-info;1"].getService(Ci.nsIXULAppInfo);
    return appInfo.appBuildID;
  },

  isAccessible: function() {
    return Cc["@mozilla.org/accessibleRetrieval;1"].getService(Ci.nsIAccessibleRetrieval);
  },

  getAccessible: function(aAccOrElmOrID, aInterfaces)
  {
    if (!aAccOrElmOrID) {
      return null;
    }

    var elm = null;

    if (aAccOrElmOrID instanceof Ci.nsIAccessible) {
      aAccOrElmOrID.QueryInterface(Ci.nsIAccessNode);
      elm = aAccOrElmOrID.DOMNode;
    } else if (aAccOrElmOrID instanceof Ci.nsIDOMNode) {
      elm = aAccOrElmOrID;
    } else {
      elm = this.window.get().document.getElementById(aAccOrElmOrID);
    }

    var acc = (aAccOrElmOrID instanceof Ci.nsIAccessible) ? aAccOrElmOrID : null;
    if (!acc) {
      try {
        acc = gAccRetrieval.getAccessibleFor(elm);
      } catch (e) {
      }
    }

    if (!aInterfaces) {
      return acc;
    }

    if (aInterfaces instanceof Array) {
      for (var index = 0; index < aInterfaces.length; index++) {
        try {
          acc.QueryInterface(aInterfaces[index]);
        } catch (e) {
        }
      }
      return acc;
    }
  
    try {
      acc.QueryInterface(aInterfaces);
    } catch (e) {
    }
  
    return acc;
  },

  setLogFile: function(path) {
    this._mfl = new MozillaFileLogger(path);
  },

  log: function(data) {
    if (this._mfl) {
      this._mfl.log(data);
    }
  },

  closeLogFile: function() {
    if (this._mfl) {
      this._mfl.close();
    }
  }
};
