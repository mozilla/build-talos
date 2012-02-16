function PanDown(fe) {
  this._fe = fe;
}

PanDown.prototype = {
  go: function() {
    let startTime = new Date();
    let self = this;
    let cwu = Browser.windowUtils;
    let viewport = document.getElementById('content-viewport')
    let pageH = viewport.getBoundingClientRect().height;
    let innerHeight = window.innerHeight;
    let from = innerHeight-1;
    let to = 1;
    let step = 15;
    let x = window.innerWidth/2;
    let r = this._fe.report;
    r.pandistance = pageH;
    function pan () {
      cwu.sendMouseEvent("mousedown", x, from,
                         0, 1, 0, true);
      for (var i = from; i > to;i-=step) {
        cwu.sendMouseEvent("mousemove", x, i,
                           0, 1, 0, true);
      }
      
      let before = new Date();
      cwu.sendMouseEvent("mouseup", x, to, 0, 1, 0, true);
      try {
        cwu.sendMouseEvent("click", x, to, 0, 1, 0, true);
      } catch (ex) {
      }

      let delay = new Date() - before;
      r.panlag.push(delay);
      let timeToDelay = Math.max(0, 200 - delay);
      let pageBottom = viewport.getBoundingClientRect().bottom
      dump([pageH, pageBottom, timeToDelay]+" pageH, pageBottom, timeToPan\n")

      if (parseInt(innerHeight) <= (parseInt(pageBottom) - 10)) {
        setTimeout(pan, timeToDelay, this);
      } else {
        r.pantime = new Date() - startTime;
        setTimeout(function() {self._fe.nextTest()}, 0);
      }
    }
    pan();
  }
}
