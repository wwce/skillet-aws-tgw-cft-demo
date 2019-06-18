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
                             region_name=Region,
                             aws_access_key_id=ACCESS_KEY,
                             aws_secret_access_key=SECRET_KEY)

    try:
        stack_data = cf_client.describe_stacks(StackName=stack_name)
        stack_id = stack_data['Stacks'][0]['StackId']
        response = cf_client.delete_stack(StackName=stack_id)
    except ClientError as error:
        print('Error: {}'.format(error.response['Error']['Message']))
    except Exception as e:
        logger.info('Got exception {}'.format(e))


    if 'ResponseMetadata' in response and response['ResponseMetadata']['HTTPStatusCode'] < 300:
        logger.info("Got response: {0}".format(response))

        while True:
            try:
                stack_data = cf_client.describe_stacks(StackName=stack_id)

                if stack_data['Stacks'][0]['StackStatus'] == 'ROLLBACK_IN_PROGRESS':
                    print('Stack is rolling back - check the event logs')
                    time.sleep(30)
                    continue
                elif stack_data['Stacks'][0]['StackStatus'] == 'DELETE_IN_PROGRESS':
                    print('Stack still deleting')
                    time.sleep(30)
                    continue
                elif stack_data['Stacks'][0]['StackStatus'] == 'DELETE_FAILED':
                    print('Stack has failed to delete check your console')
                    return False
                elif stack_data['Stacks'][0]['StackStatus'] == 'ROLLBACK_FAILED':
                    print('Stack has failed to rollback check your console')
                    return False
                elif stack_data['Stacks'][0]['StackStatus'] == 'DELETE_COMPLETE':
                    print('Stack has been deleted')
                    return True
                else:
                    print('Please check the stack deletion status in your AWS console')
                    return False
            except ClientError as error:
                print('Unable to find stack {}'.format(stack_name))
                return False
            except Exception as e:
                logger.info('Got exception {}'.format(e))
                return False
        return True

    else:
        logger.info("There was an Unexpected error. response: {0}".format(response))
        return False


def delete_bucket(s3bucket_name, Region, ACCESS_KEY, SECRET_KEY):
    s3 = boto3.resource('s3',
                        region_name=Region,
                        aws_access_key_id=ACCESS_KEY,
                        aws_secret_access_key=SECRET_KEY)

    bucket = s3.Bucket(s3bucket_name)
    response = bucket.objects.all().delete()
    bucket.delete()
    if 'ResponseMetadata' in response and response[0]['ResponseMetadata']['HTTPStatusCode'] < 300:
        print('Got response to S3 bucket delete all {}'.format(response))
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
    parser.add_argument('-r', '--aws_region', help='Select aws_region', default='us-east-1')
    parser.add_argument('-k', '--aws_access_key', help='AWS Key', required=True)
    parser.add_argument('-s', '--aws_secret_key', help='AWS Secret', required=True)

    args = parser.parse_args()

    ACCESS_KEY = args.aws_access_key
    SECRET_KEY = args.aws_secret_key
    aws_region = args.aws_region

    try:
        with open('deployment_data.json', 'r') as data:
            config_dict = json.load(data)
            stack_name = config_dict['stack_name']
            s3bucket_name = config_dict['s3bucket_name']
    except FileNotFoundError:
        logger.infor('File no longer exists')
    except Exception as e:
        logger.infor('Got exception {}'.format(e))
        sys.exit("Could not find deployment config file 'deployment_data.json'")

    print('Deleting Stack {}'.format(stack_name))



    if delete_stack(stack_name, aws_region, ACCESS_KEY, SECRET_KEY):
        print('Deleted Stack {}'.format(stack_name))
        print('Deleting S3 Bucket {}'.format(s3bucket_name))
        if delete_bucket(s3bucket_name, aws_region, ACCESS_KEY, SECRET_KEY):
            print('Deleted S3 Bucket {}'.format(s3bucket_name))
    else:
        print('There was a problem deteting the stack {}'.format(stack_name))


if __name__ == '__main__':
    main()