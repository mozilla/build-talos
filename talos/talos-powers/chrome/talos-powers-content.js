/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/**
 * Content that wants to quit the whole session should
 * fire the TalosQuitApplication custom event. This will
 * attempt to force-quit the browser.
 */
addEventListener("TalosQuitApplication", () => {
  sendAsyncMessage("Talos:ForceQuit");
});
