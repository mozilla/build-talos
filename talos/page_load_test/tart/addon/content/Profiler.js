// Finer grained profiler control
//
// Use this object to pause and resume the profiler so that it only profiles the
// relevant parts of our tests.
var Profiler;
(function(){
  var _profiler;
  var test_name = document.location.pathname;

  try {
    netscape.security.PrivilegeManager.enablePrivilege('UniversalXPConnect');
    _profiler = Components.classes["@mozilla.org/tools/profiler;1"].getService(Components.interfaces.nsIProfiler);
  } catch (ex) { dumpLog(ex + "\n"); }

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
