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


def generate_random_string():
    string_length = 8
    random_string = uuid.uuid4().hex  # get a random string in a UUID fromat
    random_string = random_string.lower()[0:string_length]  # convert it in a uppercase letter and trim to your size.
    return random_string


def parse_template(template):
    """

    :param template:
    :return:
    """
    cf_client = boto3.client('cloudformation', region_name=Region)
    with open(template) as template_fileobj:
        template_data = template_fileobj.read()
        try:
            response = cf_client.validate_template(TemplateBody=template_data)
            logger.info('Result of Validation is {}'.format(response))
        except ClientError as e:
            logger.info('Got exception {}'.format(e))

    return template_data


def load_template(template_url, params, stack_name):
    """

    :param template_url:
    :param params:
    :param stack_name:
    :return:
    """
    try:
        cf_client = boto3.client('cloudformation', region_name=Region)
        response = cf_client.create_stack(
            StackName=stack_name,
            TemplateURL=template_url,
            Parameters=params,
            DisableRollback=False,
            TimeoutInMinutes=10,
            Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM', 'CAPABILITY_AUTO_EXPAND']
        )
    except Exception as e:
        logger.info('Got exception {}'.format(e))


def get_template(template_file):
    '''
        Read a template file and return the contents
    '''
    try:
        if template_file.startswith("http"):
            response = urlopen(template_file)
            cf_template = response.read()
        elif template_file.startswith("s3"):
            _, path = (template_file.split("//", 1))
            bucket_name, path = path.split("/", 1)

            s3 = boto3.client("s3", region_name=Region)

            response = s3.get_object(Bucket=bucket_name, Key=path)
            val = response['Body'].read()
            cf_template = val.decode('utf-8')
        else:
            f = open(template_file, "r")
            cf_template = f.read()

    except Exception as e:
        print("Error reading file {}: ", template_file)

    return cf_template


def upload_files(s3bucket_name, dir, Region):
    """

    :param s3bucket_name:
    :param dir:
    :param Region:
    :return:
    """
    client = boto3.client('s3', region_name=Region)
    for subdir, dirs, files in os.walk(dir):
        for file in files:
            key = subdir.replace(dir + '/', '')
            full_path = os.path.join(subdir, file)
            filename_path = os.path.join(key, file)
            if 'lambda' in filename_path:
                filename_path = filename_path.replace('lambda/', '')

            with open(full_path, 'rb')as data:
                response = client.put_object(
                    ACL='public-read', Body=data, Bucket=s3bucket_name, Key=filename_path)
            logger.info('Response {}'.format(response))


def validate_cf_template(cf_template, sc):
    """

    :param cf_template:
    :param sc:
    :return:
    """
    global aws_region
    try:
        client = boto3.client('cloudformation', region_name=Region)
        response = client.validate_template(TemplateURL=cf_template)
        if ('Capabilities' in response) and (sc == "no"):
            print(response['Capabilities'], "=>>", response['CapabilitiesReason'])
            return False
        else:
            return True
    except ClientError as e:
        print(e)
        print(sys.exc_info()[1])
        return False
    except Exception as error:
        print(error)
        print(sys.exc_info()[1])
        return False


def monitor_stack(stack_name, Region):
    """

    :param stack_name:
    :return:
    """
    cf_client = boto3.client('cloudformation', region_name=Region)

    while True:
        try:
            stack_data = cf_client.describe_stacks(StackName=stack_name)
            if stack_data['Stacks'][0]['StackStatus'] == 'ROLLBACK_IN_PROGRESS':
                print('Stack is rolling back - check the event logs')
                time.sleep(30)
                continue
            elif stack_data['Stacks'][0]['StackStatus'] == 'DELETE_IN_PROGRESS':
                print('Stack still deleting')
                time.sleep(30)
                continue
            elif stack_data['Stacks'][0]['StackStatus'] == 'CREATE_IN_PROGRESS':
                print('Stack still creating - check again in 30 secs')
                time.sleep(30)
                continue
            elif stack_data['Stacks'][0]['StackStatus'] == 'CREATE_COMPLETE':
                print('Stack has deployed successfully')
                break
            elif stack_data['Stacks'][0]['StackStatus'] == 'DELETE_COMPLETE':
                print('Stack has been deleted')
                break
            elif stack_data['Stacks'][0]['StackStatus'] == 'DELETE_FAILED':
                print('Stack has failed to delete check your console')
                break
            elif stack_data['Stacks'][0]['StackStatus'] == 'ROLLBACK_FAILED':
                print('Stack has failed to rollback check your console')
                break
        except ClientError as error:
            logger.info('Got exception {}'.format(error))
            break
        except Exception as e:
            logger.info('Got exception {}'.format(e))
            break

    return


def main():
    global Region
    """
    Input arguments
    Mandatory -r Region 'eu-west-1' | 'us-east-1' ......

    args = parser.parse_args()

    """
    parser = argparse.ArgumentParser(description='Get Parameters')
    parser.add_argument('-r', '--Region', help='Select Region', default='us-east-1')
    args = parser.parse_args()
    Region = args.Region

    template = 'template.json'
    params_file = 'parameters.json'
    params_list = []
    prefix = generate_random_string()
    s3bucket_name = Region + '-' + prefix + '-tgw-direct'
    template_url = 'https://' + s3bucket_name + '.s3-' + Region + '.amazonaws.com/' + template
    stack_name = 'panw-' + prefix + 'tgw-direct'
    dirs = ['bootstrap']

    config_dict = {
        's3bucket_name' : s3bucket_name,
        'stack_name' : stack_name
    }
    with open('deployment_data.json','w+') as datafile:
        datafile.write(json.dumps(config_dict))

    with open(params_file, 'r') as data:
        params_dict = json.load(data)
        for k, v in params_dict.items():
            temp_dict = {'ParameterKey': k, "ParameterValue": v}
            params_list.append(temp_dict)

    try:
        s3 = boto3.resource('s3', region_name=Region)
        response = s3.create_bucket(Bucket=s3bucket_name, CreateBucketConfiguration={'LocationConstraint': Region})
        print('Created S3 Bucket - {}'.format(response))

    except Exception as e:
        logger.info('Got exception {}'.format(e))


    for dir in dirs:
        upload_files(s3bucket_name, dir, Region)

    if not validate_cf_template(template_url, 'yes'):
        sys.exit("CF Template not valid")
    else:
        load_template(template_url, params_list, stack_name)

    monitor_stack(stack_name, Region)


if __name__ == '__main__':
    main()
