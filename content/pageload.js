function LagDuringLoad(fe) {
  //benchmark controller
  this._fe = fe;
}

LagDuringLoad.prototype = {
  _timeoutDelay: 100,
  
  scheduleNextEvent: function() {
    let self = this;
    function timeout() {
      let diff = (new Date() - self._beforeTimeout) - self._timeoutDelay;
      self._fe.report.loadlag.push(diff);
      self.scheduleNextEvent();
    }
    if (Browser.selectedTab.isLoading()) {
      this._beforeTimeout = new Date()
      this._timeout = setTimeout(timeout, this._timeoutDelay);
    } else {
      //done with loading
      setTimeout(function() {self._fe.nextTest()}, 5000);
    }
  },
  
  go: function () {
    let browser = Browser.selectedBrowser;
    let self = this;
    
    function dummy() {
    }
  
//    browser.loadURI("http://w3.org", null, null, false);
    browser.loadURI("http://pravda.ru", null, null, false);
    self.scheduleNextEvent();
  }
}
