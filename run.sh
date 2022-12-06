#!/bin/bash
# IMPORTANT: don't forget to run 'chmod +x run.sh'
logfile="/var/log/app.log"
echo "$(date) ============ begin" >>"$logfile"
docker run reservation &>>"$logfile"
status=$?
echo "$(date) exit status: $status"  >>"$logfile"
exit $status
