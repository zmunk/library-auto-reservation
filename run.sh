#!/bin/bash
# IMPORTANT: don't forget to run 'chmod +x run.sh'
logfile="/var/log/app.log"
echo "$(date) ============ begin" >>"$logfile"
python app.py &>>"$logfile"
status=$?
echo "$(date) exit status: $status"  >>"$logfile"
exit $status
