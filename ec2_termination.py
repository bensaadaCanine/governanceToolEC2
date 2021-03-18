import boto3
import requests
import pymysql
import sys
import logging
import datetime
from dateutil.relativedelta import relativedelta
import os

# Define RDS DB info (SAFE mod only)
DATABASE_NAME = "sql_config"
TABLE_NAME = "EC2_TERMINATE_CONFIGURATION"


def configuration():
    x = datetime.datetime.now()
    # Catalog of monthly logs
    # logging_Month_Year.log
    logger = f'logging_{x.strftime("%B")}_{x.strftime("%Y")}.log'
    
    # Find the last month's string
    last_month = x - relativedelta(months=1)
    last_month_logger = f'logging_{last_month.strftime("%B")}_{x.strftime("%Y")}.log'
    # Deleting older log files on the machine (locally)
    if os.path.exists(last_month_logger):
        os.remove(last_month_logger)
        
    # Define the logger
    logging.basicConfig(level=logging.INFO, format='%(asctime)s :: %(levelname)s :: %(message)s',
                        handlers=[logging.FileHandler(logger),
                                  logging.StreamHandler()])

    # Checking the state of the program via Sys.Argv (SAFE/UNSAFE)
    if sys.argv[1] == "unsafe":
        logging.warning("Working In UNSAFE Mod.")
        # return [bucket,list_of_tags,slack_web_hook,logger]. all None except logger
        return [None, None, None, logger]
    else:
        bucket, list_of_tags, slack_web_hook = get_config_from_rds()

        # Can't split None - so checking for the existence of list_of_tags first
        if list_of_tags:
            list_of_tags = list_of_tags.split(",")

        return [bucket, list_of_tags, slack_web_hook, logger]


def ec2_termination_main():
    # Connecting to EC2 services with a user that have READ and DELETE abilities and get the current instances
    instances = []
    logging.info("Getting All Instances...")

    # Attach all regions to their instances
    regions = boto3.client('ec2').describe_regions()['Regions']
    for region in regions:
        instances.append(
            [region['RegionName'], boto3.resource('ec2', region_name=region['RegionName']).instances.filter(
                Filters=[{'Name': 'instance-state-name', 'Values': ['running', 'stopped']}])])
        # [[region,instancesCollection]]

    if list_of_tags:
        # Extracting instances Id's to a list according to the tag list
        logging.info(
            "Extracting Instances According To list_of_tags row")
        unprotected_instances = filtering_unprotected_instances(
            list_of_tags, instances)
    else:
        # Extracting the unprotected (not(tagKey/tagValue named "protected")) instances Id's to a list
        logging.info("Extracting UNPROTECTED Instances...")
        unprotected_instances = filtering_unprotected_instances(
            ["protected"], instances)

    if len(unprotected_instances) > 0:
        # Creating AMI's for the following unprotected instances and terminate them
        create_ami_and_terminate(unprotected_instances)
        update_log_file()
    else:
        logging.info("No Instances To Terminate :)")
        update_log_file()


def get_config_from_rds():

    # Checking the RDS credentials from Sys.Argv
    config = sys.argv[1].split(",")

    # Aborting in case of missing parameters
    if len(config) < 3:
        logging.critical("Please Insert RDS info! (Host,Username,Password)")
        sys.exit(0)

    else:
        try:
            # Trying to connect to the DB
            logging.info("Fetching Configuration from RDS...")
            db = pymysql.connect(
                host=config[0], user=config[1], password=config[2], database=DATABASE_NAME)

            # Get the last inserted row of the table defined globaly
            cursor = db.cursor()
            sql = f"SELECT logger_bucket_name,list_of_tags,slack_web_hook FROM ${TABLE_NAME} ORDER BY " \
                  "time_of_insert DESC LIMIT 1; "
            cursor.execute(sql)
            data = cursor.fetchone()
            return data

        except:
            # Aborting program if there is an exception while trying to get data
            logging.critical(
                "FAILED ATTEMPT TO CONNECT RDS! PLEASE CHECK CREDENTIALS! ABORTING...")
            sys.exit(0)


def filtering_unprotected_instances(list_of_values, instances_per_region):
    unprotected_instances = []

    # instances_per_region = [[region, instancesCollection]]
    for instances in instances_per_region:
        for i in instances[1]:  # instances[1] = instancesCollection
            if i.tags is None:
                # Create a list of dics which points on instance_id and it's region
                unprotected_instances.append(
                    {"instance_id": i.instance_id, "region": instances[0]})
            else:
                for tag in i.tags:
                    if tag["Key"].lower() in list_of_values or tag["Value"].lower() in list_of_values:
                        # If it happen to get unto a key or value that matches the list - it stops the search
                        break
                    # In case of not finding any of the written tags:
                    unprotected_instances.append(
                        {"instance_id": i.instance_id, "region": instances[0]})

    return unprotected_instances

# Get a list via S3 bucket
# def get_dynamic_list():
#     s3 = boto3.resource('s3')
#
#     try:
#         obj = s3.Object(bucket, "list_of_tags.txt")
#         body = obj.get()['Body'].read().decode("utf-8")
#         list_of_tags = body.split(" ")
#         return list_of_tags
#     except:
#         slack_message_bot(
#             f'WARNING::list_of_tags.txt wasn\'t found in the bucket. Please check '
#             f'<https://s3.console.aws.amazon.com/s3/buckets/{bucket}|S3 Bucket>.\nFiltering UNPROTECTED Instances')
#         logging.warning(
#                 "list_of_tags.txt wasn\'t found in the bucket. Filtering UNPROTECTED Instances")
#         return None


def update_log_file():
    logging.info("Log File Is Being Updated...")

    # Checking if the var bucket is set. bucket = OPTIONAL
    if bucket:

        s3 = boto3.client('s3')

        try:
            # Upload log file to S3 bucket/folder. If it's the first time - it creates the folder.
            s3.upload_file(log, bucket, f'logFiles/{log}')

        except:
            slack_message_bot(
                f'ERROR:: Something went wrong with log file uploading. Please check '
                f'<https://s3.console.aws.amazon.com/s3/buckets/{bucket}|S3 Bucket> permissions/existence.')
            logging.error(
                'Something went wrong with log file uploading. Please check bucket permissions/existence.')
    else:
        logging.error("No Bucket Name Inserted")
        slack_message_bot(f'ERROR:: No Bucket Name Inserted')


def create_ami_and_terminate(list_of_instances):
    for instance in list_of_instances:
        # Creating boto3 calls according to the current region
        ec2 = boto3.client('ec2', region_name=instance['region'])
        ec2_res = boto3.resource('ec2', region_name=instance['region'])

        # Create AMI for the current instance
        logging.info(
            f"Creating AMI For {instance['instance_id']} in '{instance['region']}' Region...")
        image = ec2.create_image(InstanceId=instance['instance_id'],
                                 NoReboot=True, Name=instance['instance_id'])
        waiter = ec2.get_waiter('image_available')

        try:
            # Wait for the AMI to be available
            logging.info(
                f'Waiting for {instance["instance_id"]} AMI to be Availabe...')
            waiter.wait(ImageIds=[image["ImageId"]])
            logging.info(f'Image {instance["instance_id"]} is Available.')

            # Stop and terminate the current instance
            logging.warning(
                f'Terminating The Following Instance: {instance["instance_id"]} from \'{instance["region"]}\' '
                f'Region...')
            slack_message_bot(
                f'WARNING:: Terminating The Following Instance: {instance["instance_id"]} from \'{instance["region"]}\'...')
            ec2_res.instances.filter(
                InstanceIds=[instance["instance_id"]]).stop()
            ec2_res.instances.filter(
                InstanceIds=[instance["instance_id"]]).terminate()

            logging.info("MISSION ACCOMPLISHED :)")

        except:
            logging.error(
                f"Something went wrong with creating AMI for instance {instance['instance_id']}.")
            slack_message_bot(
                f'ERROR:: Something went wrong with creating AMI for instance {instance["instance_id"]}.')

            # Aborting program
            logging.critical(
                "Aborting Program. Please Check The Logs For Further Information")
            slack_message_bot(
                f'CRITICAL:: Aborting Program. Please Check The Logs For Further Information')

            sys.exit(0)


def slack_message_bot(text):
    # Using the Slack REST API to update the team ASAP on logs starting from WARNING level
    if slack_web_hook:
        try:
            headers = {
                'Content-type': 'application/json',
            }
            data = '{"text":"' + text + '"}'
            requests.post(
                slack_web_hook, headers=headers, data=data)
        except:
            logging.error(
                "Something went wrong with Slack messages sending. Please check endpoint.")
            return


bucket, list_of_tags, slack_web_hook, log = configuration()
ec2_termination_main()
