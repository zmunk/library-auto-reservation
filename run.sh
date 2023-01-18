#!/bin/bash
# IMPORTANT: don't forget to run 'chmod +x run.sh'
logfile="/var/log/app.log"
echo "$(date) ============ begin" >>"$logfile"
cd /etc/myapp
export AWS_DEFAULT_REGION=us-east-1
source env/bin/activate
python app.py --reserve-all &>> "$logfile"
status=$?
echo "$(date) exit status: $status"  >>"$logfile"
exit $status
