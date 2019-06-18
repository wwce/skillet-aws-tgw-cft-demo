import argparse
import json
import logging
import os
import sys
import time
import uuid
from urllib.request import urlopen

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)
Region = ''

def delete_stack(stack_name, Region, ACCESS_KEY, SECRET_KEY):
    """

    :param stack_name:
    :param Region:
    :return:
    """
    cf_client = boto3.client('cloudformation', 
                        region_name = Region,
                        aws_access_key_id=ACCESS_KEY,
                        aws_secret_access_key=SECRET_KEY)

    response = cf_client.delete_stack(StackName=stack_name)
    if 'ResponseMetadata' in response and response['ResponseMetadata']['HTTPStatusCode'] < 300:
        logger.info("Got response: {0}".format(response))
        return True
    else:
        logger.info("There was an Unexpected error. response: {0}".format(response))
        return False

def delete_bucket(s3bucket_name, Region, ACCESS_KEY, SECRET_KEY):
    s3 = boto3.resource('s3', 
                        region_name = Region,
                        aws_access_key_id=ACCESS_KEY,
                        aws_secret_access_key=SECRET_KEY)

    bucket = s3.Bucket(s3bucket_name)
    response = bucket.objects.all().delete()
    bucket.delete()
    if 'ResponseMetadata' in response and response[0]['ResponseMetadata']['HTTPStatusCode'] < 300:
        print ('Got response to S3 bucket delete all {}'.format(response))
        return True
    else:
        return False

def main():
    """

    :return:
    """

    global Region
    """
    Input arguments
    Mandatory -r Region 'eu-west-1' | 'us-east-1' ......
    """
    parser = argparse.ArgumentParser(description='Get Parameters')
    parser.add_argument('-k', '--aws_access_key', help='AWS Key', required=True)
    parser.add_argument('-s', '--aws_secret_key', help='AWS Secret', required=True)
    parser.add_argument('-r', '--aws_region', help='Select aws_region', default='us-east-1')
    args = parser.parse_args()
    
    ACCESS_KEY = args.aws_access_key
    SECRET_KEY = args.aws_secret_key
    aws_region = args.aws_region

    try:
        with open('deployment_data.json', 'r') as data:
            config_dict = json.load(data)
            stack_name = config_dict['stack_name']
            s3bucket_name = config_dict['s3bucket_name']
    except Exception as e:
        logger.infor('Got exception {}'.format(e))
        sys.exit("Could not find deployment config file 'deployment_data.json'")

    if delete_stack(stack_name, aws_region, ACCESS_KEY, SECRET_KEY):
        print ('Deleted Stack {}'.format(stack_name))
    else:
       logger.info('Failed to delete stack') 

    if delete_bucket(s3bucket_name, aws_region, ACCESS_KEY, SECRET_KEY):
        print ('Deleted S3 Bucket {}'.format(s3bucket_name))
    else:
       logger.info('Failed to delete bucket') 



if __name__ == '__main__':
    main()