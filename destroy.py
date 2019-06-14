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

def delete_stack(stack_name, Region):
    """

    :param stack_name:
    :param Region:
    :return:
    """
    cf_client = boto3.client('cloudformation', region_name=Region)
    response = cf_client.delete_stack(StackName=stack_name)
    if 'ResponseMetadata' in response and response['ResponseMetadata']['HTTPStatusCode'] < 300:
        logger.info("Got response: {0}".format(response))
        return True
    else:
        logger.info("There was an Unexpected error. response: {0}".format(response))
        return False

def delete_bucket(s3bucket_name, Region):
    s3 = boto3.resource('s3', region_name = Region)
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
    parser.add_argument('-r', '--Region', help='Select Region', default='us-east-1')
    args = parser.parse_args()
    Region = args.Region

    try:
        with open('deployment_data.json', 'r') as data:
            config_dict = json.load(data)
            stack_name = config_dict['stack_name']
            s3bucket_name = config_dict['s3bucket_name']
    except Exception as e:
        logger.infor('Got exception {}'.format(e))
        sys.exit("Could not find deployment config file 'deployment_data.json'")

    # if delete_stack(stack_name, Region):
        print ('Deleted Stack {}'.format(stack_name))

    if delete_bucket(s3bucket_name, Region):
        print ('Deleted S3 Bucket {}'.format(s3bucket_name))












if __name__ == '__main__':
    main()