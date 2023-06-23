
import time
import random
import grpc
from concurrent.futures import ProcessPoolExecutor
import subprocess
import importlib
import google.protobuf.descriptor_pb2 as descriptor_pb2
import argparse
import json
import sys
import csv
from google.protobuf.empty_pb2 import Empty

def generate_descriptor_set(proto_file, descriptor_file):
    # Generate the descriptor set file
    command = f"protoc --include_imports --include_source_info --descriptor_set_out={descriptor_file} {proto_file}  2>/dev/null"
    subprocess.run(command, shell=True)

def parse_proto(proto_file):
    # Generate the descriptor set file
    descriptor_file = proto_file.split(".")[0] + ".desc"
    generate_descriptor_set(proto_file, descriptor_file)

    # Parse the descriptor set file
    descriptor_set = descriptor_pb2.FileDescriptorSet()
    with open(descriptor_file, "rb") as f:
        descriptor_set.ParseFromString(f.read())

    messages = {}
    services = {}
    messages[''] = []

    # Extract the services and their methods
    for file_proto in descriptor_set.file:
        methods = {}

        for service_proto in file_proto.service:
            for method_proto in service_proto.method:
                input_type = method_proto.input_type
                output_type = method_proto.output_type

                input_message = None
                for message_proto in file_proto.message_type:
                    if message_proto.name == input_type.split(".")[-1]:
                        input_message = message_proto
                        break
                
                if input_message:
                    if input_message.name not in messages:
                        paramters = []
                        for field_proto in input_message.field:
                            paramters.append(field_proto.name)
                        messages[input_message.name] = paramters
                

                output_message = None
                for message_proto in file_proto.message_type:
                    if message_proto.name == output_type.split(".")[-1]:
                        output_message = message_proto
                        break
                
                if output_message:
                    if output_message.name not in messages:
                        paramters = []
                        for field_proto in output_message.field:
                            paramters.append(field_proto.name)
                        messages[output_message.name] = paramters

                methods[method_proto.name] =  [input_message.name if input_message else '', output_message.name if output_message else '']


            services[service_proto.name] = methods
    
    return (messages,services)


def generate_proto_files(proto_file):
    # Run the protoc command to generate the Python files
    command = f"python3 -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. {proto_file}  2>/dev/null"
    subprocess.run(command, shell=True)


def generate_information(proto_file):
    return parse_proto(proto_file)

def add_count(error_counts, error_message):
    if error_message in error_counts:
        error_counts[error_message] += 1
    else:
        error_counts[error_message] = 1

def save_results_to_file(results, output_file):
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)


def read_csv_as_array_of_dicts(csv_file):
    result = []

    with open(csv_file, 'r') as csvfile:
        reader = csv.reader(csvfile)
        headers = next(reader)  # Read the first row as headers
        for row in reader:
            row_dict = {}
            for i, value in enumerate(row):
                try:
                    # Try converting the value to an integer
                    value = int(value)
                except ValueError:
                    pass  # Keep the value as a string if it cannot be converted to an integer
                row_dict[headers[i]] = value
            result.append(row_dict)

    return result


def read_json_as_array_of_dicts(json_file):
    with open(json_file, 'r') as f:
        return json.load(f)

def send_requests(user_id, server_address, num_requests,proto_file,service_name,method_name,messages,services,request_name, response_name,input_data):

    protofile_pb2_grpc = importlib.import_module(proto_file.split(".")[0] + "_pb2_grpc")
    protofile_pb2 = importlib.import_module(proto_file.split(".")[0] + "_pb2")
    # Create a channel for this user
    channel = grpc.insecure_channel(server_address)
    service_stub_class = getattr(protofile_pb2_grpc, service_name + 'Stub')

    stub = service_stub_class(channel)

    response_times = []
    input_data_length = max(len(input_data),1)
    input_data_index = 0
    success_count = 0 
    error_counts = {'Timeout error': 0, 'Internal server error': 0 , 'Invalid Agruments':0}
    for req in range(num_requests):
        # request = grpc_client.createRequest( method_name, user_id)
        # request_name = "MyRequest"
        try:
            request = None
            if request_name != '':
            # request_name = services[service_name][method_name][0]
                parameters = messages[request_name]
                request = None
                request_class = None

                request_class = getattr(protofile_pb2, request_name)
                request = request_class(**input_data[input_data_index])

                # for data in input_data:
                #     for para in parameters:

                #This will give the parameters in this request

            else:
                request = Empty()

            method_stub = getattr(stub, method_name)
                
            start_time = time.time()
            response = method_stub(request)
            end_time = time.time()
            response_time = (end_time - start_time)*1000
            # if random.random() < 0.05:
            #     raise Exception("Random exception occurred")
            response_times.append(response_time)
            # response_name = services[service_name][method_name][1]
            attributes = messages[response_name]
            success_count += 1
            # add_count(success_count,user_id)
            print (f"Latency: {response_time:.4f}",end = ", ")
            for attr in attributes:
                attr_val = getattr(response,attr)
                print(f"{attr} : {attr_val}" , end = " ")
            print(f" #user_id {user_id} , request number : {req}")
            
        except grpc.RpcError as e:
            # Handle gRPC errors
            if e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                print(f'User_ID: {user_id}, Error: Deadline exceeded')
                error_counts['Timeout error'] += 1
            
            elif e.code() == grpc.StatusCode.INVALID_ARGUMENT:
                print(f'User_ID: {user_id}, Error: {e.details()}')
                error_counts['Invalid Agruments'] += 1
            else:
                print(f'User_ID: {user_id}, Error: {e.details()}')
                error_counts['Internal server error'] += 1
        
        except Exception as e:
            # Handle other exceptions
            print(f'User_ID: {user_id}, Error: {str(e)}')
            error_counts['Internal server error'] += 1
        # print() 
        input_data_index = (input_data_index + 1) % input_data_length
        # Process the response
        # print(f"User_ID: {user_id}, Latency: {response_time:.4f}, Message: {response.answer}, ReuestNumber:  {req}")


    return (success_count, error_counts,response_times)


def run_load_test(server_address, user_ids, num_requests,proto_file,service_name,method_name,messages,services,request_name, response_name,input_data,output_file):

    generate_proto_files(proto_file)
    # Create channels for each user_id

    response_times = []
        # Initialize success count dictionary
    success_count = 0
    error_counts = {'Timeout error': 0, 'Internal server error': 0, 'Invalid Agruments' : 0}
    with ProcessPoolExecutor() as executor:
        futures = []
        for user_id in user_ids:
            future = executor.submit(send_requests, user_id, server_address, num_requests,proto_file,service_name,method_name,messages,services,request_name, response_name,input_data)
            futures.append(future)

        # Collect the response times from all the processes
        for future in futures:
            (result_success_count,result_error_count,result_response_times) = future.result()
            response_times.extend(result_response_times)
            success_count += result_success_count
            for key, value in result_error_count.items():
                error_counts[key] += value



    total_success = success_count

    # Calculate number of failures
    total_failures = (num_users * num_requests) - total_success

    # Calculate success rate
    success_rate = (total_success / (num_users * num_requests)) * 100 if (num_users * num_requests) > 0 else 0




    # request_sizes = [len(data) for data in input_data.values()]
    # response_sizes = [len(response) for response in responses.values()]
    # min_request_size = min(request_sizes) if request_sizes else 0
    # max_request_size = max(request_sizes) if request_sizes else 0
    # average_request_size = sum(request_sizes) / len(request_sizes) if request_sizes else 0
    # min_response_size = min(response_sizes) if response_sizes else 0
    # max_response_size = max(response_sizes) if response_sizes else 0
    # average_response_size = sum(response_sizes) / len(response_sizes) if response_sizes else 0

    # Calculate metrics
    avg_response_time = sum(response_times) / len(response_times)
    status_code = 200 if len(response_times) > 0 else 500
    percentile_index_99 = int(len(response_times) * 0.99)
    percentile_index_50 = int(len(response_times) * 0.50)
    percentile_index_90 = int(len(response_times) * 0.90)
    response_times = sorted(response_times)
    percentile_99 = response_times[percentile_index_99]
    percentile_50 = response_times[percentile_index_50]
    percentile_90 = response_times[percentile_index_90]
    min_response_time = response_times[0]
    max_response_time = response_times[len(response_times)-1]
    
    # Print metrics
    results = {
        'requests': {
            'total': num_users * num_requests,
            'success': total_success,
            'failure': total_failures,
            'rate': success_rate
        },
        'latency': {
            'average': avg_response_time,
            'min': min_response_time,
            'max': max_response_time,
            'percentiles': {
                '50': percentile_50,
                '90': percentile_90,
                '99': percentile_99
            }
        },
        'errors': [
            {'message': error_message, 'count': error_counts[error_message]}
            for error_message in error_counts
        ],
        'throughput': success_rate,
        'status': 'completed'
    }

    # Save results to file
    save_results_to_file(results, output_file)

    print(f'Load test results saved to {output_file}')


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='gRPC Load Tester')
    parser.add_argument('-addr','--address', type=str, help='Server address in the format <hostname>:<port>')
    parser.add_argument('-c','--concurrency', type=int, help='Number of concurrent users',default=1)
    parser.add_argument('-n', '--total',type=int, help='Total number of requests',default=1)
    parser.add_argument('-proto', type=str, help='Proto file')
    parser.add_argument('-call', type=str, help='Method to call in syntax: "package.service.method"')
    parser.add_argument('-d','--data', type=str, help='Input data file')
    parser.add_argument('-o', type=str, help='Output File',default="output.json")
    args = parser.parse_args()

    server_address = args.address
    num_users = args.concurrency
    user_ids = ["user" + str(i) for i in range(1, num_users+1)]
    # total_requests = args.r
    num_requests = args.total
    num_requests = (int) (num_requests/num_users)
    proto_file = args.proto
    callMethod = args.call
    output_file = args.o
    service_name = callMethod.split(".")[-2]
    method_name = callMethod.split(".")[-1]
    (messages, services) = generate_information(proto_file)
    # print(messages)
    # print(services)
    request_name = services[service_name][method_name][0]
    response_name = services[service_name][method_name][1]
    input_file = args.data
    input_data = []
    if request_name != '':
        if(input_file.split(".")[-1] == "json"):
            input_data = read_json_as_array_of_dicts(input_file)
        elif(input_file.split(".")[-1] == "csv"):
            input_data = read_csv_as_array_of_dicts(input_file)
    

    # print(input_data)

    run_load_test(server_address, user_ids, num_requests, proto_file, service_name, method_name, messages, services, request_name, response_name, input_data, output_file)

