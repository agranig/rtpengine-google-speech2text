#!/bin/sh

export GOOGLE_APPLICATION_CREDENTIALS=google-service-account.json
rm -f /tmp/out*.wav
/etc/init.d/ngcp-rtpengine-recording-daemon stop 1>/dev/null 2>/dev/null
./rtp.py | grep '>>>'
