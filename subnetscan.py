#!/usr/bin/env python3

"""
  Script Name:  Scan_for_roles.py
  Purpose:  This script lists IAM roles that are configure for SAML authentication
  Requirements:  Python3 with the import modules available and iam access.
  Author:  Manjot Pelia
"""

import boto3, botocore, sys, json, argparse, uuid, shutil, os
from time import sleep
from datetime import datetime
import socket
import smtplib
from os.path import basename

#IAM_User_To_Search = "aws_sys_prd_snow01"
now = datetime.now()
formatnow = now.strftime("%Y-%m-%d-%H-%M")
csv_header = "AWS_Account_number,AWS_Account_Name,Region,VPCId,SubnetID,CiDrblock,AZ, AZId"
csv_file = "AWS-Subnets-" + formatnow + ".csv"
with open(csv_file, 'w') as csv:
    csv.write(csv_header + "\n")
    
# Get account listing
print("\nObtaining active account list from AWS Organizations...")
sts_client = boto3.client('sts')
session_name = "ListAccounts-" + str(uuid.uuid4()).split('-')[0]
assumed_role = sts_client.assume_role(RoleArn="arn:aws:iam::101437356159:role/MIT_OrganizationsReadOnly",RoleSessionName=session_name)
sleep(1)
credentials = assumed_role['Credentials']
org_client = boto3.client('organizations', aws_access_key_id=credentials['AccessKeyId'],
                          aws_secret_access_key=credentials['SecretAccessKey'], aws_session_token=credentials['SessionToken'])
sleep(1)
account_list = []
accounts = org_client.list_accounts()
output_acc_array = []
subnet = {}

for account in accounts['Accounts']:
    output_acc = {}
    output_acc['Id'] = account['Id']
    output_acc['Name'] = account['Name']
    output_acc['Status'] = account['Status']
    output_acc_array.append(output_acc)        
next_token = False
if "NextToken" in accounts.keys():
    next_token = True
    token_id = accounts['NextToken']
    while next_token == True:
        sleep(1)
        next_accounts = org_client.list_accounts(NextToken=token_id)
        for account in next_accounts['Accounts']:  
            output_acc = {}
            output_acc['Id'] = account['Id']
            output_acc['Name'] = account['Name']
            output_acc['Status'] = account['Status']
            output_acc_array.append(output_acc)
        if "NextToken" in next_accounts.keys():
            next_token = True
            token_id = next_accounts['NextToken']
        else:
            next_token = False
            
print(output_acc_array)
print("\nGetting a current region list...\n")
ec2_client = boto3.client('ec2', region_name='us-east-1')
regions = ec2_client.describe_regions()['Regions']
print(regions)

for account in output_acc_array:
    print("****-------------- Begin Account: " + account['Name'] + " --------------****\n")
    subnet[account['Name']] = {}
    role_to_assume = "arn:aws:iam::" + account['Id'] + ":role/mitss/MIT_ReadOnly"
    sts_client = boto3.client('sts')
    try:
        assumed_role = sts_client.assume_role(RoleArn=role_to_assume, RoleSessionName=session_name)
        sleep(.1)
    except botocore.exceptions.ClientError as e:
        print(
            "\nThere was an error assuming the role. Be sure the role exists and the CloudBees role has rights to assume.")
        print("\nAttempting to assume role: " + role_to_assume)
        print("\nError:" + str(e))
        print("\n****-------------- End Account: " + account['Name'] + " ----------------****\n")
        subnet[account['Name']]['Access'] = "DENIED"
        continue

    credentials = assumed_role['Credentials']
    line1 = account['Name'] + ',' + account['Id']
    print("Successfully assumed role. Performing scans in all regions.\n")
    for region in regions:
        print("--------- Begin region " + region['RegionName'] + " ---------\n")
        ec2_client = boto3.client("ec2", region_name=region['RegionName'], aws_access_key_id=credentials['AccessKeyId'],
                                  aws_secret_access_key=credentials['SecretAccessKey'],
                                  aws_session_token=credentials['SessionToken'])
        subnet_call = ec2_client.describe_subnets()
        subnet_details = subnet_call['Subnets']
        line2 = line1 + ',' + region['RegionName']
        for subnet in subnet_details:
         	with open(csv_file, 'a') as csv:
                 line3 = (line2 + ',' + subnet['VpcId'] + ',' + subnet['SubnetId'] + ',' + subnet['CidrBlock'] + ',' + subnet['AvailabilityZone'] + ',' + subnet['AvailabilityZoneId'])
                 print(line3)
                 csv.write(line3 + "\n")
            
workspace = os.environ['WORKSPACE']
file_url = 'https://jenkins.cloud.moodys.net'
for folder in workspace.split('/')[4:]:
    file_url += '/job/' + folder
file_url += '/ws/' + csv_file
file_url = file_url.replace(' ', '%20')
print("\n\nAWS Subnets: " + file_url)
