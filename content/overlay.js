var BenchFE = {
  currentTest:-1,
  tests:[LagDuringLoad, PanDown],
  report:new Report(),
  
  nextTest : function(aEvent) {
    this.currentTest++;
    if (this.currentTest < this.tests.length) {
      (new this.tests[this.currentTest](this)).go();
    } else {
      Browser.addTab(this.report.save(), true);
      this._currentTest = -1;
      this.report = new Report();
    }
  }
};
