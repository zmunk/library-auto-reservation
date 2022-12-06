
`sudo yum update -y`  
`sudo yum install -y awslogs git gcc openssl-devel bzip2-devel libffi-devel docker`

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
`cd library`  
`vim config.py`
```
DEV = False
credentials = [
    ("account1", "username1", "****"),
]
```

`vim library_accessKeys.csv`
```
Access key ID,Secret access key
****,****
```

`sudo usermod -aG docker ${USER}`  
`newgrp docker`  
`sudo systemctl start docker`  
`sudo systemctl enable docker.service`  
`docker build . -t reservation && docker run reservation`  

`chmod +x run.sh`  
`crontab -e`
```
# run at 8 am every day
0 8 * * * /home/ec2-user/library/run.sh
```

Note: attach IAM role to instance  
https://docs.amazonaws.cn/en_us/AmazonCloudWatch/latest/logs/QuickStartEC2Instance.html
