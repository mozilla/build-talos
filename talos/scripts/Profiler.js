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
var Profiler;

(function(){
  var _profiler;
  var test_name = document.location.pathname;

  try {
    // Outside of talos, this throws a security exception which no-op this file.
    // (It's not required nor allowed for addons since Firefox 17)
    // It's used inside talos from non-privileged pages (like during tscroll),
    // and it works because talos disables all/most security measures.
    netscape.security.PrivilegeManager.enablePrivilege('UniversalXPConnect');
  } catch (e) {}

  try {
    _profiler = Components.classes["@mozilla.org/tools/profiler;1"].getService(Components.interfaces.nsIProfiler);
  } catch (ex) { (typeof(dumpLog) == "undefined" ? dump : dumpLog)(ex + "\n"); }

  Profiler = {
    resume: function Profiler__resume (name, explicit) {
      if (_profiler) {
        if (_profiler.ResumeSampling) {
          _profiler.ResumeSampling();
        }
        _profiler.AddMarker(explicit ? name : 'Start of test "' + (name || test_name) + '"');
      }
    },
    pause: function Profiler__pause (name, explicit) {
      if (_profiler) {
        if (_profiler.PauseSampling) {
          _profiler.PauseSampling();
        }
        _profiler.AddMarker(explicit ? name : 'End of test "' + (name || test_name) + '"');
      }
    },
    mark: function Profiler__mark (marker, explicit) {
      if (_profiler) {
        _profiler.AddMarker(explicit ? marker : 'Profiler: "' + (marker || test_name) + '"');
      }
    }
  };
})();
