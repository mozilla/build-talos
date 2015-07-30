// -*- Mode: js; tab-width: 2; indent-tabs-mode: nil; js2-basic-offset: 2; js2-skip-preprocessor-directives: t; -*-

const { classes: Cc, interfaces: Ci, utils: Cu } = Components;
Cu.import("resource:///modules/NewTabURL.jsm");
Cu.import("resource://gre/modules/Services.jsm");
Cu.import("resource://gre/modules/Promise.jsm");
Cu.import("resource://gre/modules/XPCOMUtils.jsm");

var Profiler = null;

var windowListener = {
  onOpenWindow: function(aWindow) {
    // Ensure we don't get tiles which contact the network
    NewTabURL.override("about:blank")

    // Wait for the window to finish loading
    let window = aWindow.QueryInterface(Ci.nsIInterfaceRequestor).getInterface(Ci.nsIDOMWindowInternal || Ci.nsIDOMWindow);
    let cb = function() {
      window.removeEventListener("load", cb, false);
      loadIntoWindow(window);
    };
    window.addEventListener("load", cb, false);
  },

  onCloseWindow: function(aWindow) {
    NewTabURL.reset()
  },

  onWindowTitleChange: function(aWindow, aTitle) {
  }
};

function promiseOneEvent(target, eventName, capture) {
  let deferred = Promise.defer();
  target.addEventListener(eventName, function handler(event) {
    target.removeEventListener(eventName, handler, capture);
    deferred.resolve();
  }, capture);
  return deferred.promise;
}

function executeSoon(callback) {
  Services.tm.mainThread.dispatch(callback, Ci.nsIThread.DISPATCH_NORMAL);
}

function whenDelayedStartupFinished(win, callback) {
  const topic = "browser-delayed-startup-finished";
  Services.obs.addObserver(function onStartup(subject) {
    if (win == subject) {
      Services.obs.removeObserver(onStartup, topic);
      executeSoon(callback);
    }
  }, topic, false);
}

function waitForTabLoads(browser, numTabs, callback) {
  let listener = {
    count: 0,
    QueryInterface: XPCOMUtils.generateQI(["nsIWebProgressListener",
                                           "nsISupportsWeakReference"]),

    onStateChange: function(aBrowser, aWebProgress, aRequest, aStateFlags, aStatus) {
      let loadedState = Ci.nsIWebProgressListener.STATE_STOP |
        Ci.nsIWebProgressListener.STATE_IS_NETWORK;
      if ((aStateFlags & loadedState) == loadedState &&
          !aWebProgress.isLoadingDocument &&
          aWebProgress.DOMWindow == aWebProgress.DOMWindow.top) {
        this.count++;
        if (this.count == numTabs) {
          browser.removeTabsProgressListener(listener);
          callback();
        }
      }
    },

    onLocationChange: function(aProgress, aRequest, aURI) {
    },
    onProgressChange: function(aWebProgress, aRequest, curSelf, maxSelf, curTot, maxTot) {},
    onStatusChange: function(aWebProgress, aRequest, aStatus, aMessage) {},
    onSecurityChange: function(aWebProgress, aRequest, aState) {}
  }
  browser.addTabsProgressListener(listener);
}

function loadTabs(urls, win, callback) {
  let context = {};
  Services.scriptloader.loadSubScript("chrome://pageloader/content/Profiler.js", context);
  Profiler = context.Profiler;

  // We don't want to catch scrolling the tabstrip in our tests
  win.gBrowser.tabContainer.style.visibility = "hidden";

  let initialTab = win.gBrowser.selectedTab;
  waitForTabLoads(win.gBrowser, urls.length, function() {
    let tabs = win.gBrowser.getTabsToTheEndFrom(initialTab);
    aboutBlankTab = tabs[0];
    callback(tabs);
  });
  // Add about:blank to be the first tab. This will allow us to use about:blank
  // to let paint event stabilize and make all tab switch more even.
  urls.unshift("about:blank");
  win.gBrowser.loadTabs(urls, true);
}

function runTest(tabs, win, callback) {
  let startTab = win.gBrowser.selectedTab;
  let times = [];
  runTestHelper(startTab, tabs, 0, win, times, function() {
    callback(times);
  });
}

function waitForTabSwitchDone(win, callback) {
  if (win.gBrowser.selectedBrowser.isRemoteBrowser) {
    var list = function onSwitch() {
      win.gBrowser.removeEventListener("TabSwitched", list);
      callback();
    };

    win.gBrowser.addEventListener("TabSwitched", list);

  } else {
    // Tab switch is sync so it has already happened.
    callback();
  }
}

// waitForPaints is from mochitest
var waitForAllPaintsFlushed = null;
(function() {
 var accumulatedRect = null;
 var onpaint = function() {};
 var debug = false;
 var registeredWin = null;
 const FlushModes = {
   FLUSH: 0,
   NOFLUSH: 1
 };

  function paintListener(event) {
    if (event.target != registeredWin) {
      return;
    }
    var eventRect =
      [ event.boundingClientRect.left,
        event.boundingClientRect.top,
        event.boundingClientRect.right,
        event.boundingClientRect.bottom ];
    if (debug) {
      dump("got MozAfterPaint: " + eventRect.join(",") + "\n");
    }
    accumulatedRect = accumulatedRect
                    ? [ Math.min(accumulatedRect[0], eventRect[0]),
                        Math.min(accumulatedRect[1], eventRect[1]),
                        Math.max(accumulatedRect[2], eventRect[2]),
                        Math.max(accumulatedRect[3], eventRect[3]) ]
                    : eventRect;
    onpaint();
  }

  function waitForPaints(win, callback, subdoc, flushMode) {
    if (!registeredWin) { // delay the register until we have a window
      registeredWin = win;
      win.addEventListener("MozAfterPaint", paintListener, false);
    }

    // Wait until paint suppression has ended
    var utils = win.QueryInterface(Ci.nsIInterfaceRequestor)
                   .getInterface(Ci.nsIDOMWindowUtils);
    if (utils.paintingSuppressed) {
      if (debug) {
        dump("waiting for paint suppression to end...\n");
      }
      onpaint = function() {};
      win.setTimeout(function() {
        waitForPaints(win, callback, subdoc, flushMode);
      }, 0);
      return;
    }

    // The call to getBoundingClientRect will flush pending layout
    // notifications. Sometimes, however, this is undesirable since it can mask
    // bugs where the code under test should be performing the flush.
    if (flushMode === FlushModes.FLUSH) {
      win.document.documentElement.getBoundingClientRect();
      if (subdoc) {
        subdoc.documentElement.getBoundingClientRect();
      }
    }

    if (utils.isMozAfterPaintPending) {
      if (debug) {
        dump("waiting for paint...\n");
      }
      onpaint =
        function() { waitForPaints(win, callback, subdoc, FlushModes.NOFLUSH); };
      if (utils.isTestControllingRefreshes) {
        utils.advanceTimeAndRefresh(0);
      }
      return;
    }

    if (debug) {
      dump("done...\n");
    }
    var result = accumulatedRect || [ 0, 0, 0, 0 ];
    accumulatedRect = null;
    onpaint = function() {};
    callback.apply(null, result);
  }

  waitForAllPaintsFlushed = function(win, callback, subdoc) {
    waitForPaints(win, callback, subdoc, FlushModes.FLUSH);
  };

  waitForAllPaints = function(win, callback) {
    waitForPaints(win, callback, null, FlushModes.NOFLUSH);
  };
})();

function runTestHelper(startTab, tabs, index, win, times, callback) {
  let tab = tabs[index];

  if (typeof(Profiler) !== "undefined") {
    Profiler.resume(tab.linkedBrowser.currentURI.spec);
  }
  let start = win.performance.now();
  win.gBrowser.selectedTab = tab;

  waitForTabSwitchDone(win, function() {
    // This will fire when we're about to paint the tab switch
    win.requestAnimationFrame(function() {
      // This will fire on the next vsync tick after the tab has switched.
      // If we have a sync transaction on the compositor, that time will
      // be included here. It will not accuratly capture the composite time
      // or the time of async transaction.
      win.requestAnimationFrame(function() {
        times.push(win.performance.now() - start);
        if (typeof(Profiler) !== "undefined") {
          Profiler.pause(tab.linkedBrowser.currentURI.spec);
        }

        // Select about:blank which will let the browser reach a steady no
        // painting state
        win.gBrowser.selectedTab = aboutBlankTab;

        waitForTabSwitchDone(win, function() {
          win.requestAnimationFrame(function() {
            win.requestAnimationFrame(function() {
              // Let's wait for all the paints to be flushed. This makes
              // the next test load less noisy.
              waitForAllPaintsFlushed(win, function() {
                if (index == tabs.length - 1) {
                  callback();
                } else {
                  runTestHelper(startTab, tabs, index + 1, win, times, function() {
                    callback();
                  });
                }
              });
            });
          });
        });
      });
    });
  });
}

function test(window) {
  let win = window.OpenBrowserWindow();
  let testURLs;

  try {
    let prefFile = Services.prefs.getCharPref("addon.test.tabswitch.urlfile");
    if (prefFile) {
      testURLs = handleFile(win, prefFile);
    }
  } catch (ex) { /* error condition handled below */ }
  if (!testURLs || testURLs.length == 0) {
    dump("no tabs to test, 'addon.test.tabswitch.urlfile' pref isn't set to page set path\n");
    return;
  }
  whenDelayedStartupFinished(win, function() {
    loadTabs(testURLs, win, function(tabs) {
      runTest(tabs, win, function(times) {
        let output = '<!DOCTYPE html>'+
                     '<html lang="en">'+
                     '<head><title>Tab Switch Results</title></head>'+
                     '<body><h1>Tab switch times</h1>' +
                     '<table>';
        let time = 0;
        for(let i in times) {
          time += times[i];
          output += '<tr><td>' + testURLs[i] + '</td><td>' +times[i] + 'ms</td></tr>';
        }
        output += '</table></body></html>';
        dump("total tab switch time:" + time + "\n");

        let resultsTab = win.gBrowser.loadOneTab('data:text/html;charset=utf-8,' +
                                                 encodeURIComponent(output));
        let pref = Services.prefs.getBoolPref("browser.tabs.warnOnCloseOtherTabs");
        if (pref)
          Services.prefs.setBoolPref("browser.tabs.warnOnCloseOtherTabs", false);
        win.gBrowser.removeAllTabsBut(resultsTab);
        if (pref)
          Services.prefs.setBoolPref("browser.tabs.warnOnCloseOtherTabs", pref);
        Services.obs.notifyObservers(win, 'tabswitch-test-results', JSON.stringify({'times': times, 'urls': testURLs}));
      });
    });
  });
}

function unloadFromWindow(window) {
  if (!window)
    return;
  let toolsMenu = window.document.getElementById("menu_ToolsPopup");
  if (!toolsMenu)
    return;
  toolsMenu.removeChild(window.document.getElementById("start_test_item"));
}

function loadIntoWindow(window) {
  if (!window)
    return;
  let item = window.document.createElement("menuitem");
  item.setAttribute("label", "Start test");
  item.id = "start_test_item";
  window.tab_switch_test = test;
  item.setAttribute("oncommand", "tab_switch_test(window)");
  let toolsMenu = window.document.getElementById("menu_ToolsPopup");
  if (!toolsMenu)
    return;
  toolsMenu.appendChild(item);
}

function install(aData, aReason) {}
function uninstall(aData, aReason) {}

function shutdown(aData, aReason) {
  // When the application is shutting down we normally don't have to clean
  // up any UI changes made
  if (aReason == APP_SHUTDOWN) {
    return;
  }

  Services.wm.removeListener(windowListener);

  // Unload from any existing windows
  let list = Services.wm.getEnumerator("navigator:browser");
  while (list.hasMoreElements()) {
    let window = list.getNext().QueryInterface(Ci.nsIDOMWindow);
    unloadFromWindow(window);
  }
  Services.obs.removeObserver(observer, "tabswitch-urlfile");
  Services.obs.removeObserver(observer, "tabswitch-do-test");
}

function handleFile(win, file) {

  let localFile = Cc["@mozilla.org/file/local;1"]
    .createInstance(Ci.nsILocalFile);
  localFile.initWithPath(file);
  let localURI = Services.io.newFileURI(localFile);
  let req = new win.XMLHttpRequest();
  req.open('get', localURI.spec, false);
  req.send(null);


  let testURLs = [];
  let parent = localURI.spec.split(localFile.leafName)[0];
  let lines = req.responseText.split('<a href=\"');
  testURLs = [];
  lines.forEach(function(a) {
    if (a.split('\"')[0] != "") {
      testURLs.push(parent + "tp5n/" + a.split('\"')[0]);
    }
  });

  return testURLs;
}

let observer = {
  observe: function(aSubject, aTopic, aData) {
    if (aTopic == "tabswitch-do-test") {
      test(aSubject);
    } else if (aTopic == "tabswitch-urlfile") {
      handleFile(aSubject, aData);
    }
  }
};

function startup(aData, aReason) {
  // Load into any existing windows
  let list = Services.wm.getEnumerator("navigator:browser");
  let window;
  while (list.hasMoreElements()) {
    window = list.getNext().QueryInterface(Ci.nsIDOMWindow);
    loadIntoWindow(window);
  }

  // Load into any new windows
  Services.wm.addListener(windowListener);

  Services.obs.addObserver(observer, "tabswitch-urlfile", false);
  Services.obs.addObserver(observer, "tabswitch-do-test", false);
}