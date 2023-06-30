## gRPC Load Tester
The gRPC Load Tester is a command-line tool designed to perform load testing on gRPC servers. It allows you to simulate multiple concurrent users and send a specified number of requests to the server. This tool supports the use of a Proto file for defining the gRPC service and method to call.

### Getting Started
To get started with the gRPC Load Tester, follow these steps:

1. Download the **'microservice_load_tester.py'** file from this repository.
2. Ensure that you have the necessary Proto file and input data file for your gRPC service.
### Usage
Run the following command in your terminal to execute the load tester:
```shell
[-h] [-addr ADDRESS] [-c CONCURRENCY] [-c_start CONCURRENCY_START] [-c_step CONCURRENCY_STEP] [-c_end CONCURRENCY_END] [-c_step_duration CONCURRENCY_STEP_DURATION] [-n TOTAL] [-proto PROTO] [-call CALL] [-d DATA] [-o OUTPUT]
```

### Arguments

- `-h`, `--help`: Show the help message and exit.
- `-addr ADDRESS`, `--address ADDRESS`: Server address in the format `<hostname>:<port>`.
- `-c CONCURRENCY`, `--concurrency CONCURRENCY`: Number of concurrent users. (Default: 1)
- `-c_start CONCURRENCY_START`: Concurrency start value.
- `-c_step CONCURRENCY_STEP`: Concurrency step value. (Default: 1)
- `-c_end CONCURRENCY_END`: Concurrency end value.
- `-c_step_duration CONCURRENCY_STEP_DURATION`: Specifies the concurrency step duration value. (Default: 1)
- `-n TOTAL`, `--total TOTAL`: Total number of requests. (Default: 1)
- `-proto PROTO`: Specifies path to Proto file.
- `-call CALL`: Method to call in syntax: "package.service.method".
- `-d DATA`, `--data DATA`: Specifies path to input data file.
- `-o OUTPUT`: Output file name. (Default: "output.json")

## Dynamic Change in Concurrent Users

The gRPC Load Tester provides a powerful feature that allows you to dynamically change the number of concurrent users over time during your load testing. This feature is particularly useful for scenarios where you want to gradually increase the load on your gRPC server.

To utilize this feature, you need to specify the following additional arguments:

- `-c_start CONCURRENCY_START`: This argument sets the starting number of concurrent users.
- `-c_step CONCURRENCY_STEP`: This argument determines the number of concurrent users to increment after each specified duration.
- `-c_end CONCURRENCY_END`: This argument sets the final number of concurrent users.
- `-c_step_duration CONCURRENCY_STEP_DURATION`: This argument specifies the duration (in seconds) after which the number of concurrent users will be incremented by the value specified in `-c_step`.

For example, let's say you set `-c_start` to 10, `-c_step` to 5, `-c_end` to 30, and `-c_step_duration` to 10. In this case, the load tester will start with 10 concurrent users, and every 10 seconds, it will increase the number of concurrent users by 5 until it reaches 30.

Please ensure that you provide the correct path for the Proto file and input data file by using the -proto and -d options respectively. Adjust the command-line arguments as per your gRPC server configuration and load testing requirements.
