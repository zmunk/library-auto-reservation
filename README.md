
`sudo yum update -y`  
`sudo yum install -y awslogs git python-pip`  
```
# /etc/awslogs/awslogs.conf
[/var/log/app.log]
datetime_format = %b %d %H:%M:%S
file = /var/log/app.log
buffer_duration = 5000
log_stream_name = {instance_id}
initial_position = start_of_file
log_group_name = /var/log/app.log
```
`sudo systemctl start awslogsd`  
`sudo systemctl enable awslogsd.service`  

`LOGFILE=/var/log/app.log`  
`sudo touch $LOGFILE`  
`sudo chmod o+w $LOGFILE`  
`git clone https://github.com/zmunk/library-auto-reservation.git library`  

`vim library/config.py`
```
credentials = [
    ("account1", "username1", "****"),
]
```

`vim library/library_accessKeys.csv`
```
Access key ID,Secret access key
****,****
```

`pip3 install -r requirements.txt`  

`crontab -e`
```
# run at 8 am every day
0 8 * * * /home/ec2-user/library/run.sh
```

https://docs.amazonaws.cn/en_us/AmazonCloudWatch/latest/logs/QuickStartEC2Instance.html
