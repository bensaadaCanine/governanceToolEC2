# governanceToolEC2
Terminates EC2 Instances according to an outer list of tags (and more...)

# READ FIRST:
 In order for this code to run smoothly - you need to have an AWS account configured on this machine with access to
 EC2 (READ,CREATING AMI,STOP,TERMINATE) and S3 (WRITE). This code runs in two versions - UNSAFE and SAFE (depends on
 sys.argv[1] => 'unsafe'/RDS info ('Host,Username,Password'). If you will choose to run in UNSAFE mod - this program
 will terminate all the instances without the tagKey/tgValue 'protected'. In SAFE mod - it will attempt to get info
 from RDS 'sql_config' DB. in the 'sql_config' DB you need to have a table named: EC2_TERMINATE_CONFIGURATION with
 4 fields: time_of_insert(timestamp),configuration_id(int),logger_bucket_name(text),list_of_tags(text),
 slack_web_hook(text). The tags should be separated by "," ONLY. This is a Cross Origin Version so it might take some
 time to find all the instances.
 
 -Update 17 March 2020 :<br>
   You can set the RDS DB name and table in global vars.<br>
   Added sql query file for setting the basic database and table.
