/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

// - NOTE: This file is duplicated verbatim at:
//         - talos/scripts/Profiler.js
//         - talos/pageloader/chrome/Profiler.js
//         - talos/page_load_test/tart/addon/content/Profiler.js
//
//  - Please keep these copies in sync.
//  - Please make sure your changes apply cleanly to all use cases.

// Finer grained profiler control
//
// Use this object to pause and resume the profiler so that it only profiles the
// relevant parts of our tests.
var Profiler = { // Initialize as placeholder, replace with actual if available.
  resume: function() {},
  pause:  function() {},
  mark:   function() {}
};

(function(){
  var _profiler;
  var test_name = document.location.pathname;

  try {
    netscape.security.PrivilegeManager.enablePrivilege('UniversalXPConnect');
    _profiler = Components.classes["@mozilla.org/tools/profiler;1"].getService(Components.interfaces.nsIProfiler);
  } catch (ex) { (typeof(dumpLog) == "undefined" ? dump : dumpLog)(ex + "\n"); }

  Profiler = {
    resume: function Profiler__resume (name) {
      if (_profiler) {
        if (_profiler.ResumeSampling) {
          _profiler.ResumeSampling();
        }
        _profiler.AddMarker('Start of test "' + (name || test_name) + '"');
      }
    },
    pause: function Profiler__pause (name) {
      if (_profiler) {
        if (_profiler.PauseSampling) {
          _profiler.PauseSampling();
        }
        _profiler.AddMarker('End of test "' + (name || test_name) + '"');
      }
    },
    mark: function Profiler__mark (marker) {
      if (_profiler) {
        _profiler.AddMarker('Profiler: "' + (marker || test_name) + '"');
      }
    }
  };
})();
