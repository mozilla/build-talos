/*
 vim:se?t ts=2 sw=2 sts=2 et cindent:
 This Source Code Form is subject to the terms of the Mozilla Public
 License, v. 2.0. If a copy of the MPL was not distributed with this
 file, You can obtain one at http://mozilla.org/MPL/2.0/.
*/

// audioPlayback Test plays an input file from a given
// <audio> and records the same to compute PESQ scores
var audioPlayback = function() {
  var test = this;
  var cleanupTimeout = 5000;
  var audio = document.createElement('audio');

  // start audio recorder
  initiateAudioRecording(test);
  if (test.failed) {
    test.finished = true;
    runNextTest();
    return;
  }

  audio.addEventListener('ended', function(evt) {
    // stop the recorder
    cleanupAudioRecording(test);
    if (!test.failed) {
      getPESQScores(test);
      var res = JSON.parse(test.http_response);
      if(res["PESQ-SCORE"]) {
        // fix the test nane
        var pesqScores = res["PESQ-SCORE"].split(",");
        var testName = test.name;
        test.name = testName+"_pesq_mos";
        test.results = pesqScores[0];
        updateResults(test);
        test.name = testName+"_pesq_lqo";
        test.results = pesqScores[1];
        updateResults(test);
        // restore the name of the test
        test.name = testName;
      }
    }
    test.finished = true;
    runNextTest();
  });

  audio.addEventListener('error', function(evt) {
    // cleanup any started processes and run the next
    // test
    cleanupAudioRecording(test);
    test.finished = true;
    runNextTest();
  });

  audio.volume = 0.9;
  audio.src = test.src;
  audio.play();
};
