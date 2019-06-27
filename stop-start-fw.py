
import re
import boto3
import logging
import json
import argparse


logger = logging.getLogger()
logger.setLevel(logging.INFO)

aws_region = ''
ACCESS_KEY = ''
SECRET_KEY = ''
ec2_client = boto3.client('ec2')
cf_client = boto3.client('cloudformation')

#
# Initial constants
#
DEPLOYMENTDATA = 'deployment_data.json'
PARAMSFILE = './parameters.json'
TEMPLATEFILE = 'template.json'

def stop_firewall(fw_instance_id):
    result  = ec2_client.stop_instances(InstanceIds=[fw_instance_id])
    return

def start_firewall(fw_instance_id):
    result  = ec2_client.start_instances(InstanceIds=[fw_instance_id])
    return

def update_env_variable(function, key, value):

    try:
        function_data = cf_client.get_function_configuration(FunctionName=function)
        env_variables = function_data['Environment']['Variables']
    except Exception as e:
        print ('Error getting lambda function details {}'.format(function))

    env_variables.update({key : value})

    response = cf_client.update_function_configuration(
        FunctionName='string',
         Environment={
        'Variables': env_variables}
    )
    return

def main():

    global ACCESS_KEY
    global SECRET_KEY
    global aws_region
    global ec2_client

    parser = argparse.ArgumentParser(description='Get Parameters')
    parser.add_argument('-p', '--preempt', help='Preempt', default='yes')
    parser.add_argument('-f', '--firewall', help='Firewall to start/stop')
    parser.add_argument('-f', '--action', help='Firewall to start/stop',default='start')
    parser.add_argument('-r', '--split_routes', help='Split routes', default='yes')
    parser.add_argument('-k', '--aws_access_key', help='AWS Key', required=True)
    parser.add_argument('-s', '--aws_secret_key', help='AWS Secret', required=True)

    args = parser.parse_args()
    ACCESS_KEY = args.aws_access_key
    SECRET_KEY = args.aws_secret_key
    split_routes = args.split_routes
    preempt = args.preempt
    firewall_to_change = args.firewall
    fw_action = args.action





    # Read stack data from file 
    # deploy stores data in config_dict
    #
    # config_dict = {
    #     's3bucket_name': s3bucket_name,
    #     'stack_name': stack_name
    # }
    
    try:
        with open(DEPLOYMENTDATA, 'r') as data:
            stack_data = json.load(data)
            stack = stack_data['stack_name']
            aws_region = stack_data['aws_region']
            lambda_function = stack_data['lambda_function_name']
    except Exception as e:
        print('Could not open file {} to find stack info'.format(DEPLOYMENTDATA))

    if stack:
        cf_client = boto3.client('cloudformation', region_name = aws_region)
        ec2_client = boto3.client('ec2', region_name = aws_region)
        r = cf_client.describe_stacks(StackName=stack)
        stack, = r['Stacks']
        outputs = stack['Outputs']
        fwinstances = {}
        out = {}
        for o in outputs:
            key = o['OutputKey']
            out[key] = o['OutputValue']

    fw1_instance_id = out['Fw1InstanceId']
    fw2_instance_id = out['Fw2InstanceId']
    lambda_function = out['LambdaFunctionName']



    try:
        fw1_instance_data =  ec2_client.describe_instances(InstanceIds=[fw1_instance_id])
        fw2_instance_data = ec2_client.describe_instances(InstanceIds=[fw2_instance_id])
    except Exception as e:
        print('Error {}'.format(e))

    # Setup lambda environment variables for next run
    update_env_variable(lambda_function, 'splitroutes', split_routes)
    update_env_variable(lambda_function, 'preempt', preempt)


if __name__ == '__main__':
    main()