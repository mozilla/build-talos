/*
 vim:se?t ts=2 sw=2 sts=2 et cindent:
 This Source Code Form is subject to the terms of the Mozilla Public
 License, v. 2.0. If a copy of the MPL was not distributed with this
 file, You can obtain one at http://mozilla.org/MPL/2.0/.
*/

/* Part of this framework has be inspired by the latency-benchmark.js
 * framework
 * This file has the framework for running media tests. Individual
 * test logic are placed in their own Javascript files.
 * See audio_plyback.js for an example.
 */

// Global variable to hold results of all the tests
// Entry in this object will be of the form
//   ==> results{'Test-Name'} : 'Results'
var results = {};
// Our test server
var baseUrl = 'http://localhost:16932';
// Handy area to dump the results of the tests
var testsTable = document.getElementById('tests');
var dontLog = true;

// Taken from :jmaher's latenct-benchmark patch
parseQueryString = function(encodedString, useArrays) {
  // strip a leading '?' from the encoded string
  var qstr = (encodedString[0] == "?") ? encodedString.substring(1) :
                                         encodedString;
  var pairs = qstr.replace(/\+/g, "%20").split(/(\&amp\;|\&\#38\;|\&#x26;|\&)/);
  var o = {};
  var decode;
  if (typeof(decodeURIComponent) != "undefined") {
    decode = decodeURIComponent;
  } else {
    decode = unescape;
  }
  if (useArrays) {
    for (var i = 0; i < pairs.length; i++) {
      var pair = pairs[i].split("=");
      if (pair.length !== 2) {
        continue;
      }
      var name = decode(pair[0]);
      var arr = o[name];
      if (!(arr instanceof Array)) {
        arr = [];
        o[name] = arr;
      }
      arr.push(decode(pair[1]));
    }
  } else {
    for (i = 0; i < pairs.length; i++) {
      pair = pairs[i].split("=");
      if (pair.length !== 2) {
        continue;
      }
      o[decode(pair[0])] = decode(pair[1]);
    }
  }
  return o;
};

var params = parseQueryString(location.search.substring(1), true);

function log(msg) {
  if (!dontLog) {
    var div = document.getElementById("log");
    div.innerHTML =  "<p>" + msg + "</p>";
  }
}

// Updates results to be used for Talos eventually
var updateResults = function(test) {
  // check if test.results has any data, if so, consider
  if(test.results) {
    results[test.name] = test.results
  }
  //update tests table to report on the UI
  var row = document.createElement('tr');
  var nameCell = document.createElement('td');
  nameCell.textContent = test.name;
  var outcomeCell = document.createElement('td');
  outcomeCell.textContent = test.results;
  row.appendChild(nameCell);
  row.appendChild(outcomeCell);
  testsTable.appendChild(row);
};

// Array of Media Tests.
// To add a new test, add an entry in this array and
// provide logic for the test in its own .js file
// See audio_playback.js & pc_audio_quality.js for examples.
var tests = [
  {
      name: 'audio_peer_connection_quality',
      src: 'input16.wav',
      timeout: 10, //record timeout in seconds
      forceTimeout: 15000, //test forced timeout in ms
      test: audioPCQuality
  },
  {
      name: 'audio_playback_quality',
      src: 'input16.wav',
      timeout: 10, //record timeout in seconds
      forceTimeout: 15000, //test forced timeout in ms
      test: audioPlayback
  },
];

var nextTestIndex = 0;

var runNextTest = function() {
  var testIndex = nextTestIndex++;
  if (testIndex >= tests.length ) {
    if (params.results) {
      var obj = encodeURIComponent(JSON.stringify(results));
      var url = params.results + "?" + obj;
      sendTalosResults(url, obj);
    }
    // let's clean up the test framework
    var request = new XMLHttpRequest();
    var url = baseUrl + '/server/config/stop'
    request.open('GET', url, false);
    request.send();
  }
  var test = tests[testIndex];
  // Occasionally <audio> tag doesn't play media properly
  // and this results in test case to hang. Since it
  // never error's out, test.forceTimeout guards against this.
  setTimeout(function() { checkTimeout(test); }, test.forceTimeout);
  test.test();
};

// Test timed out, go through the next test.
var checkTimeout = function(test) {
  if(!test.finished) {
    test.finished = true;
    log("test " + test.name + "timed out");
    runNextTest();
  }
};


results['BEGIN_TIME_STAMP'] = new Date().getTime();
setTimeout(runNextTest, 100);

