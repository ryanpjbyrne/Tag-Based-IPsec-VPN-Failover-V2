#!/bin/bash

#update packages

apt-get update -y
apt-get upgrade -y
apt install git 

#Pull code from scm.dimensiondata.com 
git --version
cd home 
#clone directly from repository
git clone https://gitlab-deploy-token-meraki:UhCraKb2L2qpyxX-y_yV@scm.dimensiondata.com/UK-Professional_Services/tag-based-vpn-failover-meraki.git

#Insert new crontab command (commented out)
#crontab -l > mycron 
#insert new cron jobs 
#echo "* * * * * echo hello >> mycron 
#crontab mycron 
#rm mycon 

#Reads requirements.txt file and downloads packages
pip3 install -r requirements.txt 