function Zoom(fe) {
  this._fe = fe;
  this._initialZoomLevel = Browser._browserView.getZoomLevel();
}

Zoom.prototype = {
  go: function() {
    let toX = window.innerWidth-1;
    let toY = window.innerHeight-1;
    this._x = 1;
    this._y = 200;
    this._stepsLeft = 20;
    this._stepX = (toX - this._x)/this._stepsLeft;
    this._stepY = (toY - this._y)/this._stepsLeft;

    this.nextStep();
  },

  click: function(x,y) {
    let cwu = Browser.windowUtils;
    cwu.sendMouseEvent("mousedown", x, y,
                       0, 1, 0, true);
    cwu.sendMouseEvent("mousemove", x, y,
                       0, 1, 0, true);
    cwu.sendMouseEvent("mouseup", x, y,
                       0, 1, 0, true);
  },
  
  nextStep: function () {
    let r = this._fe.report;
    let startTime = new Date();    
    let oldZoom = Browser._browserView.getZoomLevel();
    let self = this;
    this.click(this._x, this._y);
    this.click(this._x, this._y);
    
    //only report successful zoom changes
    if (oldZoom != Browser._browserView.getZoomLevel())
      r.zoominlag.push(new Date() - startTime);
    this._stepsLeft--;
    if (this._stepsLeft > 0) {
      this._x += this._stepX;
      this._y += this._stepY;
      setTimeout(function() {self.nextStep()}, 1000);
    } else {
      Browser._browserView.setZoomLevel(this._zoomLevel);
      Browser.scrollContentToTop();
      setTimeout(function() {self._fe.nextTest()}, 1000);
    }
  }
}
