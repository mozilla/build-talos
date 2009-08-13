var BenchFE = {
  currentTest:-1,
  tests: [LagDuringLoad, Zoom, PanDown],
  report: new Report(),
  
  nextTest : function(aEvent) {
    try {
    this.currentTest++;
    if (this.currentTest < this.tests.length) {
      (new this.tests[this.currentTest](this)).go();
    } else {
      Browser.addTab(this.report.save(), true);
      this._currentTest = -1;
      this.report = new Report();
    }
    } catch (x) {
      dump(x + "\n" + x.stack + "\n")
    }
  }
};
//setTimeout(function() {BenchFE.nextTest()}, 1000);
