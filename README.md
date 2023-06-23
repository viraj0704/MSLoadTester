## gRPC Load Tester
The gRPC Load Tester is a command-line tool designed to perform load testing on gRPC servers. It allows you to simulate multiple concurrent users and send a specified number of requests to the server. This tool supports the use of a Proto file for defining the gRPC service and method to call.

### Getting Started
To get started with the gRPC Load Tester, follow these steps:

1. Download the **'microservice_load_tester.py'** file from this repository.
2. Place the Proto file and input data file in the same directory as the **'microservice_load_tester.py'** file.
### Usage
Run the following command in your terminal to execute the load tester:
```shell
python load_tester.py [-h] [-addr ADDRESS] [-c CONCURRENCY] [-n TOTAL] [-proto PROTO] [-call CALL] [-d DATA] [-o OUTPUT]
```

### Arguments

- `-h`, `--help`: Show the help message and exit.
- `-addr ADDRESS`, `--address ADDRESS`: Server address in the format `<hostname>:<port>`.
- `-c CONCURRENCY`, `--concurrency CONCURRENCY`: Number of concurrent users. (Default: 1)
- `-n TOTAL`, `--total TOTAL`: Total number of requests. (Default: 1)
- `-proto PROTO`: Specifies the Proto file (should be in the same directory as the script).
- `-call CALL`: Method to call in the syntax: `package.service.method`.
- `-d DATA`, `--data DATA`:  Specifies the input data file (should be in the same directory as the script).
- `-o OUTPUT`: Output file name. (Default: "output.json")

Please ensure that you have placed the necessary Proto file and input data file in the same directory as the microservice_load_tester.py script. Adjust the command-line arguments as per your gRPC server configuration and load testing requirements.