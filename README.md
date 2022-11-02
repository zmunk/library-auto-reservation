
`sudo yum update -y`  
`sudo yum install -y awslogs git`  

sudo yum -y groupinstall "Development Tools"
sudo yum -y install gcc openssl-devel bzip2-devel libffi-devel
wget https://www.python.org/ftp/python/3.9.7/Python-3.9.7.tgz
tar zxvf Python-3.9.7.tgz
cd Python-3.9.7/
./configure 
make
sudo make altinstall
cd ..


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
`export AWS_DEFAULT_REGION=us-east-1`

`python3.9 -m venv env`  
`source env/bin/activate`  
`pip install -r requirements.txt`  

`crontab -e`
```
# run at 8 am every day
0 8 * * * /home/ec2-user/library/run.sh
```

https://docs.amazonaws.cn/en_us/AmazonCloudWatch/latest/logs/QuickStartEC2Instance.html
