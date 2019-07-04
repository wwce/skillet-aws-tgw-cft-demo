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
aws_region = ''

ACCESS_KEY = ''
SECRET_KEY = ''

#
# Initial constants
#
DEPLOYMENTDATA = 'deployment_data.json'
PARAMSFILE = './parameters.json'
TEMPLATEFILE = 'template.json'


def generate_random_string():
    """

    Generates a random string that is used to generate a uniques name for the S3 bucket and template stack
    :return: 8 character string
    """
    string_length = 8
    random_string = uuid.uuid4().hex  # get a random string in a UUID fromat
    random_string = random_string.lower()[0:string_length]  # convert it in a uppercase letter and trim to your size.
    return random_string


def parse_template(template):
    """

    Takes a Cloud Formation Template in json format and validates the template prior to deployment
    :param template:
    :return: A valid CFT
    """
    cf_client = boto3.client('cloudformation',
                             region_name=aws_region,
                             aws_access_key_id=ACCESS_KEY,
                             aws_secret_access_key=SECRET_KEY)

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

    Creates a stack from a template.  We need to load the template from S3 as the boto3 client has a limit on the size
    of the template that can be uploaded from the local machine.

    :param template_url: (format s3:xxxxxx
    :param params: Json dictionary of template parameters
    :param stack_name: Unique stack name
    :return:
    """
    cf_client = boto3.client('cloudformation',
                             region_name=aws_region,
                             aws_access_key_id=ACCESS_KEY,
                             aws_secret_access_key=SECRET_KEY)
    try:

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
    """

    Read a template file in json format and return the contents
    :param: string template_file:
    :return: valid template file
    """

    s3_client = boto3.client("s3",
                             region_name=aws_region,
                             aws_access_key_id=ACCESS_KEY,
                             aws_secret_access_key=SECRET_KEY)
    try:
        if template_file.startswith("http"):
            response = urlopen(template_file)
            cf_template = response.read()
        elif template_file.startswith("s3"):
            path = (template_file.split("//", 1))
            bucket_name, path = path.split("/", 1)

            response = s3_client.get_object(Bucket=bucket_name, Key=path)
            val = response['Body'].read()
            cf_template = val.decode('utf-8')
        else:
            f = open(template_file, "r")
            cf_template = f.read()

    except Exception as e:
        print("Error reading file {}: ", template_file)

    return cf_template


def upload_files(s3bucket_name, working_dir, aws_region):
    """

    Uploads template file, parameters file and bootstrap files to an S3 bucket
    local file structure is replicated for config, content, license, software
    by placing a 0 bytes file in each folder.  S3 does not implement a true folder structure so a zero bytes file is
    required to create the folder structure.
    file in the 'lambda folder are placed into the root of the bucket
    :param s3bucket_name:
    :param working_dir:
    :param aws_region:
    :return:
    """
    s3_client = boto3.client("s3",
                             region_name=aws_region,
                             aws_access_key_id=ACCESS_KEY,
                             aws_secret_access_key=SECRET_KEY)

    for subdir, dirs, files in os.walk(working_dir):
        for file in files:
            key = subdir.replace(working_dir + '/', '')
            full_path = os.path.join(subdir, file)
            filename_path = os.path.join(key, file)
            if 'lambda' in filename_path:
                filename_path = filename_path.replace('lambda/', '')

            with open(full_path, 'rb')as data:
                response = s3_client.put_object(
                    ACL='public-read', Body=data, Bucket=s3bucket_name, Key=filename_path)
            logger.info('Response {}'.format(response))


def validate_cf_template(cf_template, sc):
    """

    Takes a Cloud Formation Template in json format and validates the template prior to deployment
    :param cf_template:
    :param sc:
    :return: True / False
    """
    cf_client = boto3.client('cloudformation',
                             region_name=aws_region,
                             aws_access_key_id=ACCESS_KEY,
                             aws_secret_access_key=SECRET_KEY)

    try:

        response = cf_client.validate_template(TemplateURL=cf_template)
        if ('Capabilities' in response) and (sc == "no"):
            print(response['Capabilities'], "=>>", response['CapabilitiesReason'])
            return False
        else:
            return True
    except ClientError as e:
        print(e)
        return False
    except Exception as error:
        print(error)
        return False


def monitor_stack(stack_name, aws_region):
    """

    Monitors the status of the deployment by running describe_stacks every 30 secs to report progress to the user
    :param stack_name:
    :return:
    """
    cf_client = boto3.client('cloudformation',
                             region_name=aws_region,
                             aws_access_key_id=ACCESS_KEY,
                             aws_secret_access_key=SECRET_KEY)

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
    """

    Input arguments
    Mandatory --aws_region --aws_access_key --aws_secret_key --aws_key_pair

    Stores the name of the stack and S3 bucket in file defined by DEPLOYMENTDATA
    Bucket is defind by aws_region + '-' + 'Random string' + '-tgw-direct'
    Default parameters are stored in PARAMSFILE are read and used to generate a parameters dictionary

    :return:
    """
    global ACCESS_KEY
    global SECRET_KEY
    global aws_region

    fwints = {}
    out = {}
    config_dict = {}

    parser = argparse.ArgumentParser(description='Get Parameters')
    parser.add_argument('-r', '--aws_region', help='Select aws_region', default='us-east-1')
    parser.add_argument('-k', '--aws_access_key', help='AWS Key', required=True)
    parser.add_argument('-s', '--aws_secret_key', help='AWS Secret', required=True)
    parser.add_argument('-c', '--aws_key_pair', help='AWS EC2 Key Pair', required=True)

    args = parser.parse_args()
    ACCESS_KEY = args.aws_access_key
    SECRET_KEY = args.aws_secret_key
    aws_region = args.aws_region
    KeyName = args.aws_key_pair

    cf_client = boto3.client('cloudformation',
                             region_name=aws_region,
                             aws_access_key_id=ACCESS_KEY,
                             aws_secret_access_key=SECRET_KEY)

    s3_client = boto3.client("s3",
                             region_name=aws_region,
                             aws_access_key_id=ACCESS_KEY,
                             aws_secret_access_key=SECRET_KEY)

    params_list = []
    prefix = generate_random_string()
    s3bucket_name = aws_region + '-' + prefix + '-tgw-direct'
    #
    # In us-east-1 url does not have s3-{aws_region}.amazonaws.com but simply s3.amazonaws.com
    #
    if aws_region == 'us-east-1':
        template_url = 'https://' + s3bucket_name + '.s3.amazonaws.com/' + TEMPLATEFILE
    else:
        template_url = 'https://' + s3bucket_name + '.s3-' + aws_region + '.amazonaws.com/' + TEMPLATEFILE
    stack_name = 'panw-' + prefix + 'tgw-direct'
    dirs = ['bootstrap']



    # Create zones from region in this case Zone a and Zone b
    # Required string is
    # 'eu-west-1a,eu-west-1b'
    # The string is passed as a parameter and is results in "Type": "List<AWS::EC2::AvailabilityZone::Name>"

    vpc_azs_str = aws_region + 'a,' + aws_region + 'b'

    #The format of the dictionary file is a list with structure
    #    [
    #        {'ParameterKey': k, "ParameterValue": v},
    #        {'ParameterKey': k, "ParameterValue": v}
    #    ]
    try:
        with open(PARAMSFILE, 'r') as data:
            #
            # Add the required parameters to the parameters file
            #
            params_list = []
            params_list.append({'ParameterKey': 'KeyName', 'ParameterValue': KeyName})
            params_list.append({'ParameterKey': 'VpcAzs', 'ParameterValue': vpc_azs_str})
            params_list.append({'ParameterKey': 'BootstrapBucket', 'ParameterValue': s3bucket_name})
            params_list.append({'ParameterKey': 'LambdaFunctionsBucketName', 'ParameterValue': s3bucket_name})

            params_dict = json.load(data)
            for k, v in params_dict.items():
                temp_dict = {'ParameterKey': k, "ParameterValue": v}
                params_list.append(temp_dict)
    except Exception as e:
        print('Got exception {}'.format(e))

    try:
        if  aws_region == 'us-east-1':
            s3_client.create_bucket(
                Bucket=s3bucket_name
            )
        else:
            s3_client.create_bucket(Bucket=s3bucket_name,
                                    CreateBucketConfiguration={'LocationConstraint': aws_region})

        print('Created S3 Bucket {}'.format(s3bucket_name))
    except Exception as e:
        print('Got exception trying to create S3 bucket {}'.format(e))

    for dir in dirs:
        upload_files(s3bucket_name, dir, aws_region)

    if not validate_cf_template(template_url, 'yes'):
        sys.exit("CF Template not valid")
    else:
        print('Deploying template')
        load_template(template_url, params_list, stack_name)

    monitor_stack(stack_name, aws_region)

    r = cf_client.describe_stacks(StackName=stack_name)

    stack, = r['Stacks']
    outputs = stack['Outputs']

    for o in outputs:
        key = o['OutputKey']
        out[key] = o['OutputValue']
        config_dict.update({o['OutputKey']: o['OutputValue']})
        if o['OutputKey'] == 'FW1TrustNetworkInterface' or o['OutputKey'] == 'FW2TrustNetworkInterface':
            intkey = o['OutputValue']
            fwints[intkey] =o['Description']
            config_dict.update({o['OutputValue']:o['Description']})

    config_dict.update({'route_table_id' : out['fromTGWRouteTableId']})


    config_dict.update({
        's3bucket_name': s3bucket_name,
        'stack_name': stack_name,
        'aws_region' : aws_region
    })

    with open(DEPLOYMENTDATA, 'w+') as datafile:
        datafile.write(json.dumps(config_dict))




if __name__ == '__main__':
    main()
