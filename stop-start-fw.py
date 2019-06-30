import argparse
import json
import logging
import time

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

aws_region = ''
ACCESS_KEY = ''
SECRET_KEY = ''



#
# Initial constants
#
DEPLOYMENTDATA = './deployment_data.json'
PARAMSFILE = './parameters.json'
TEMPLATEFILE = 'template.json'


def stop_firewall(fw_instance_id):

    result = ec2_client.stop_instances(InstanceIds=[fw_instance_id])
    return


def start_firewall(fw_instance_id):

    result = ec2_client.start_instances(InstanceIds=[fw_instance_id])
    return


def update_env_variable(function, key, value):

    try:
        function_data = lambda_client.get_function_configuration(FunctionName=function)
        env_variables = function_data['Environment']['Variables']
    except Exception as e:
        print('Error getting lambda function details {}'.format(function))

    env_variables.update({key: value})

    try:
        response = lambda_client.update_function_configuration(
            FunctionName=function,
            Environment={
                'Variables': env_variables}
        )
    except Exception as e:
        print('Error {}'.format(e))
    return


def main():
    global ACCESS_KEY
    global SECRET_KEY
    global aws_region
    global ec2_client
    global lambda_client

    parser = argparse.ArgumentParser(description='Get Parameters')
    parser.add_argument('-p', '--preempt', help='Preempt', default='yes')
    parser.add_argument('-f', '--firewall', help='Firewall to start/stop')
    parser.add_argument('-a', '--action', help='Firewall to start/stop', default='start')
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

    except Exception as e:
        print('Could not open file {} to find stack info'.format(DEPLOYMENTDATA))

    if stack:
        cf_client = boto3.client('cloudformation', region_name=aws_region,
                             aws_access_key_id=ACCESS_KEY,
                             aws_secret_access_key=SECRET_KEY)
        ec2_client = boto3.client('ec2', region_name=aws_region,
                             aws_access_key_id=ACCESS_KEY,
                             aws_secret_access_key=SECRET_KEY)
        lambda_client = boto3.client('lambda', region_name=aws_region,
                              aws_access_key_id=ACCESS_KEY,
                              aws_secret_access_key=SECRET_KEY)
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
        fw1_instance_data = ec2_client.describe_instances(
            InstanceIds=[fw1_instance_id]
        )

        fw2_instance_data = ec2_client.describe_instances(
            InstanceIds=[fw2_instance_id]
        )

    except Exception as e:
        print('Error {}'.format(e))
    print_header = '\n#########################################\n'

    # Setup lambda environment variables for next run
    print(print_header)
    print('{:^38s}'.format('Setting Environment Variables'))
    update_env_variable(lambda_function, 'splitroutes', split_routes)
    update_env_variable(lambda_function, 'preempt', preempt)

    # Perform Firewall Action
    print(print_header)
    print('{:^38}\n'.format('Modifying firewall ' + firewall_to_change))
    print('{:^38}\n'.format('Action ' + fw_action))
    print(print_header)

    if firewall_to_change == 'Firewall2':
        firewall_id = fw2_instance_id
    else:
        firewall_id = fw1_instance_id
    fw_data = ec2_client.describe_instances(
        InstanceIds=[firewall_id]
    )
    fwstate = fw_data['Reservations'][0]['Instances'][0]['State']['Name']
    if fw_action == 'stop' and fwstate == 'running':
        stop_firewall(firewall_id)
        time.sleep(30)
    elif fwstate == 'stopped' and fw_action == 'start':
        start_firewall(firewall_id)
        time.sleep(300)
    else:

        print(print_header)
        print('{:^38}\n'.format(firewall_to_change + ' is in a ' + fwstate + ' state. Nothing to do'))

    # Get new route table


if __name__ == '__main__':
    main()
