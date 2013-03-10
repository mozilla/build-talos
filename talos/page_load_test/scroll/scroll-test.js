function testScroll(target, stepSize)
{
  function myNow() {
    return (window.performance && window.performance.now) ?
            window.performance.now() :
            Date.now();
  };

  var isWindow = target.self === target;

  var getPos =       isWindow ? function() { return target.pageYOffset; }
                              : function() { return target.scrollTop; };

  var gotoTop =      isWindow ? function() { target.scroll(0, 0);  ensureScroll(); }
                              : function() { target.scrollTop = 0; ensureScroll(); };

  var doScrollTick = isWindow ? function() { target.scrollBy(0, stepSize); ensureScroll(); }
                              : function() { target.scrollTop += stepSize; ensureScroll(); };

  function ensureScroll() { // Ensure scroll by reading computed values. screenY is for X11.
    if (!this.dummyEnsureScroll) {
      this.dummyEnsureScroll = 1;
    }
    this.dummyEnsureScroll += window.screenY + getPos();
  }

  function rAFFallback(callback) {
    var interval = 1000 / 60;
    var now = (window.performance && window.performance.now) ?
              window.performance.now() :
              Date.now();
    // setTimeout can return early, make sure to target the next frame.
    if (this.lastTarget && now < this.lastTarget)
      now = this.lastTarget + 0.01; // Floating point errors may result in just too early.
    var delay = interval - now % interval;
    this.lastTarget = now + delay;
    setTimeout(callback, delay);
  }

  var rAF = window.requestAnimationFrame       ||
            window.mozRequestAnimationFrame    ||
            window.webkitRequestAnimationFrame ||
            window.oRequestAnimationFrame      ||
            window.msRequestAnimationFrame     ||
            rAFFallback;

  // For reference, rAF should fire on vsync, but Gecko currently doesn't use vsync.
  // Instead, it uses 1000/layout.frame_rate
  // (with 60 as default value when layout.frame_rate == -1).

  function startTest()
  {
    // We should be at the top of the page now.
    var start = myNow();
    var lastScrollPos = getPos();
    var lastScrollTime = start;
    var durations = [];

    function tick() {
      var now = myNow();
      var duration = now - lastScrollTime;
      lastScrollTime = now;

      durations.push(duration);
      doScrollTick();

      /* stop scrolling if we're at the end */
      if (getPos() == lastScrollPos) {
        // Note: The first (1-5) intervals WILL be longer than the rest.
        // First interval might include initial rendering and be extra slow.
        // Also requestAnimationFrame needs to sync (optimally in 1 frame) after long frames.
        // Suggested: Ignore the first 5 intervals.

        durations.pop(); // Last step was 0.
        durations.pop(); // and the prev one was shorter and with end-of-page logic, ignore both.

        if (window.talosDebug)
          window.talosDebug.displayData = true; // In a browser: also display all data points.
        tpRecordTime(durations.join(","));
        return;
      }

      lastScrollPos = getPos();
      rAF(tick);
    }

    rAF(tick);
  }


  // Not part of the test and does nothing if we're within talos,
  // But provides an alternative tpRecordTime (with some stats display) if running in a browser
  if(document.head) {
    var imported = document.createElement('script');
    imported.src = '../../scripts/talos-debug.js?dummy=' + Date.now(); // For some browsers to re-read
    document.head.appendChild(imported);
  }

  setTimeout(function(){
    gotoTop();
    rAF(startTest);
  }, 260);
}
