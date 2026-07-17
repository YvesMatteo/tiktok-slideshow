#!/bin/zsh
# Import this run's slides into the macOS Photos app.
# iCloud Photos will sync them to your iPhone automatically if enabled.
echo "Importing 6 slides into Photos..."
osascript <<'APPLESCRIPT'
tell application "Photos"
  activate
  import {POSIX file "/tmp/cv_shots_slideys_2176/tiktok-slideshow/runs_screenshots/2026-07-17_135339/slide_00.jpg", POSIX file "/tmp/cv_shots_slideys_2176/tiktok-slideshow/runs_screenshots/2026-07-17_135339/slide_01.jpg", POSIX file "/tmp/cv_shots_slideys_2176/tiktok-slideshow/runs_screenshots/2026-07-17_135339/slide_02.jpg", POSIX file "/tmp/cv_shots_slideys_2176/tiktok-slideshow/runs_screenshots/2026-07-17_135339/slide_03.jpg", POSIX file "/tmp/cv_shots_slideys_2176/tiktok-slideshow/runs_screenshots/2026-07-17_135339/slide_04.jpg", POSIX file "/tmp/cv_shots_slideys_2176/tiktok-slideshow/runs_screenshots/2026-07-17_135339/slide_05.jpg"}
end tell
APPLESCRIPT
echo ""
echo "Done. Photos has opened. iCloud will sync to your iPhone shortly."
echo "(closing in 3 seconds)"
sleep 3
