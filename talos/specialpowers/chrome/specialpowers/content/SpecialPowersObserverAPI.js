/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/**
 * Special Powers Exception - used to throw exceptions nicely
 **/
function SpecialPowersException(aMsg) {
  this.message = aMsg;
  this.name = "SpecialPowersException";
}

SpecialPowersException.prototype.toString = function() {
  return this.name + ': "' + this.message + '"';
};

function SpecialPowersObserverAPI() {
}

SpecialPowersObserverAPI.prototype = {

  _observe: function(aSubject, aTopic, aData) {
  },

  _getURI: function (url) {
    return Components.classes["@mozilla.org/network/io-service;1"]
                     .getService(Components.interfaces.nsIIOService)
                     .newURI(url, null, null);
  },

  /**
   * messageManager callback function
   * This will get requests from our API in the window and process them in chrome for it
   **/
  _receiveMessageAPI: function(aMessage) {
    switch(aMessage.name) {
      case "SPPrefService":
        var prefs = Components.classes["@mozilla.org/preferences-service;1"].
                    getService(Components.interfaces.nsIPrefBranch);
        var prefType = aMessage.json.prefType.toUpperCase();
        var prefName = aMessage.json.prefName;
        var prefValue = "prefValue" in aMessage.json ? aMessage.json.prefValue : null;

        if (aMessage.json.op == "get") {
          if (!prefName || !prefType)
            throw new SpecialPowersException("Invalid parameters for get in SPPrefService");
        } else if (aMessage.json.op == "set") {
          if (!prefName || !prefType  || prefValue === null)
            throw new SpecialPowersException("Invalid parameters for set in SPPrefService");
        } else if (aMessage.json.op == "clear") {
          if (!prefName)
            throw new SpecialPowersException("Invalid parameters for clear in SPPrefService");
        } else {
          throw new SpecialPowersException("Invalid operation for SPPrefService");
        }

        try {
          // Now we make the call
          switch(prefType) {
            case "BOOL":
              if (aMessage.json.op == "get")
                return(prefs.getBoolPref(prefName));
              else 
                return(prefs.setBoolPref(prefName, prefValue));
            case "INT":
              if (aMessage.json.op == "get") 
                return(prefs.getIntPref(prefName));
              else
                return(prefs.setIntPref(prefName, prefValue));
            case "CHAR":
              if (aMessage.json.op == "get")
                return(prefs.getCharPref(prefName));
              else
                return(prefs.setCharPref(prefName, prefValue));
            case "COMPLEX":
              if (aMessage.json.op == "get")
                return(prefs.getComplexValue(prefName, prefValue[0]));
              else
                return(prefs.setComplexValue(prefName, prefValue[0], prefValue[1]));
            case "":
              if (aMessage.json.op == "clear") {
                prefs.clearUserPref(prefName);
                return;
              }
          }
        } catch (ex) {
          return {}
        }
        break;

      default:
        throw new SpecialPowersException("Unrecognized Special Powers API");
    }
  }
};

