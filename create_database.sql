CREATE DATABASE sql_config;
USE sql_config;
CREATE TABLE EC2_TERMINATE_CONFIGURATION(
	time_of_insert TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    configuration_id INT PRIMARY KEY AUTO_INCREMENT,
    logger_bucket_name VARCHAR(255),
    list_of_tags TEXT,
    slack_web_hook TEXT
);