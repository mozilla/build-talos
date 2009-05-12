function PanDown(fe) {
  this._fe = fe;
}

PanDown.prototype = {
  go: function() {
    let startTime = new Date();
    let self = this;
    let cwu = Browser.windowUtils;
    let cb = Browser._canvasBrowser;
    //    cb.zoomLevel = 2;
    let pageH = cb._contentAreaDimensions[1];        
    let from = window.innerHeight-1;
    let to = 1;
    let step = 15;
    let x = window.innerWidth/2;
    let r = this._fe.report;
    r.pandistance = cb._pageToScreen(pageH);
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
        dump("ex:"+ex+"\n");
      }
      let delay = new Date() - before;
      r.panlag.push(delay);
      let timeToDelay = Math.max(0, 200 - delay);
      let viewBottom = cb._visibleBounds.bottom;
      dump([pageH, viewBottom, timeToDelay]+" pageH, viewBottom, timeToPan\n");
      if (pageH > viewBottom) {
        setTimeout(pan, timeToDelay, this);
      } else {
        r.pantime = new Date() - startTime;;
        setTimeout(function() {self._fe.nextTest()}, 0);
      }
    }
    pan();
  }
}
