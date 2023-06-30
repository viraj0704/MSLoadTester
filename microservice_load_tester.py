
import os
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
import matplotlib.pyplot as plt
from google.protobuf.empty_pb2 import Empty


def generate_descriptor_set(proto_file, descriptor_file):
    # Generate the descriptor set file
    command = f"protoc --include_imports --include_source_info --descriptor_set_out=./{descriptor_file} --proto_path={os.path.dirname(proto_file)}  {proto_file}"
    subprocess.run(command, shell=True)

def parse_proto(proto_file):
    # Generate the descriptor set file
    file_name = os.path.basename(proto_file)
    descriptor_file =  os.path.splitext(file_name)[0] + ".desc"
    # print(descriptor_file)
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
    command = f"python3 -m grpc_tools.protoc  --python_out=. --grpc_python_out=. --proto_path={os.path.dirname(proto_file)} {proto_file}  "
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

def plot_dictionary(dict,title,x_label,y_label):
    x_val = list(dict.keys())
    y_val = list(dict.values())
    plt.clf()
    plt.plot(x_val,y_val)
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    plt.title(title)

    plt.savefig(title)
    
def import_module_from_path(module_path):
    module_name = module_path.replace("/", ".").replace(".py", "")
    module = importlib.import_module(module_name)
    return module


def send_requests(user_id, server_address, num_requests,proto_file,service_name,method_name,messages,services,request_name, response_name,input_data):

    start_time_overall = time.time()
    file_name = os.path.basename(proto_file)
    protofile_pb2_grpc = importlib.import_module(os.path.splitext(file_name)[0] + "_pb2_grpc")
    protofile_pb2 = importlib.import_module(os.path.splitext(file_name)[0] + "_pb2")
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
                # parameters = messages[request_name]
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
            attributes = messages[response_name]
            success_count += 1
            print (f"Latency: {response_time:.4f}",end = ", ")
            # for attr in attributes:
            #     attr_val = getattr(response,attr)
            #     print(f"{attr} : {attr_val}" , end = " ")
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
        time.sleep(0.1)
    channel.close()
    end_time_overall = time.time()
    # print(f'Overall time of user_id : {user_id} is {(end_time_overall-start_time_overall)*1000}')
    return (success_count, error_counts,response_times)


def run_load_test(server_address, num_users, num_requests,proto_file,service_name,method_name,initial_users, max_users, ramp_up_users, ramp_up_time,messages,services,request_name, response_name,input_data,output_file):

    generate_proto_files(proto_file)
    #current users are initial users
    if(initial_users != None):
        curr_users = initial_users
    else:
        curr_users = num_users

    if(ramp_up_time == None):
        ramp_up_time = 10000000


    if(max_users == None):
        max_users = curr_users

    # print (initial_users, max_users, ramp_up_users, ramp_up_time)
    jump = (max_users - curr_users)/ramp_up_users
    if(jump != (int)(jump)) :
        jump = (int)(jump + 1)
    jump += 1
    num_requests_all = (int) (num_requests/jump) # Number of requests for all the different combinations except last , uniformly divided
    num_requests_last = (int) (num_requests_all +  num_requests - (jump*num_requests_all)) # Number of requests for the last with max_users
    # print(jump)
    # print(num_requests_all)
    # print(num_requests_last)

    average_latency_overall = {}
    percentile50_latency_overall = {}
    percentile90_latency_overall = {}
    percentile99_latency_overall = {}
    flag = 0
    start_time = time.time()

    while True:
        if (( time.time() - start_time) < ramp_up_time) and flag == 0:
            if(curr_users >= max_users):
                curr_users = min(curr_users,max_users)
                num_requests_all = num_requests_last
            print(curr_users)

            num_requests = (int) (num_requests_all/curr_users)
            remain_requests = num_requests_all%curr_users
            # print(remain_requests)
            user_ids = ["user" + str(i) for i in range(1, curr_users+1)]

            response_times = []
            success_count = 0
            error_counts = {'Timeout error': 0, 'Internal server error': 0, 'Invalid Agruments' : 0}
            with ProcessPoolExecutor() as executor:
                futures = []
                for user_id in user_ids:
                    user_number = int(user_id[4:])
                    total_requests = num_requests
                    # Compare the user number with remain_requests
                    if user_number <= remain_requests:
                        total_requests += 1
                    future = executor.submit(send_requests, user_id, server_address, total_requests,proto_file,service_name,method_name,messages,services,request_name, response_name,input_data)
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
            total_failures = num_requests_all - total_success

            # Calculate success rate
            success_rate = (total_success / num_requests_all) * 100 if (num_requests_all) > 0 else 0

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
            results = {
                'requests': {
                    'total': num_requests_all,
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
            average_latency_overall[curr_users] =  avg_response_time
            percentile50_latency_overall[curr_users] =  percentile_50
            percentile90_latency_overall[curr_users] =  percentile_90
            percentile99_latency_overall[curr_users] =  percentile_99
                # Save results to file
            save_results_to_file(results, output_file.split(".")[0] + ' '+ f'{curr_users}' + ".json")

            flag = 1
        elif (( time.time() - start_time) < ramp_up_time):
            pass
        else:
            curr_users = curr_users + ramp_up_users
            start_time = time.time()
            flag = 0

        if(curr_users <= max_users):
            continue
        else:
            break
    
    plot_dictionary(average_latency_overall,"Average Latency","Number of Users","Average Latency")
    plot_dictionary(percentile50_latency_overall,"50 Latency","Number of Users","50 Latency")
    plot_dictionary(percentile90_latency_overall,"90 Latency","Number of Users","90 Latency")
    plot_dictionary(percentile99_latency_overall,"99 Latency","Number of Users","99 Latency")


    print(f'Load test results saved to {output_file}')


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='gRPC Load Tester')
    parser.add_argument('-addr','--address', type=str, help='Server address in the format <hostname>:<port>')
    parser.add_argument('-c','--concurrency', type=int, help='Number of concurrent users',default=1)
    parser.add_argument('-c_start','--concurrency_start', type=int, help='Concurrency start value')
    parser.add_argument('-c_step','--concurrency_step', type=int, help='Concurrency step value',default=1)
    parser.add_argument('-c_end','--concurrency_end', type=int, help='Concurrency end value')
    parser.add_argument('-c_step_duration','--concurrency_step_duration', type=int, help='Specifies the concurrency step duration value',default=1)
    parser.add_argument('-n', '--total',type=int, help='Total number of requests',default=1)
    parser.add_argument('-proto', type=str, help='Specifies path to Proto file')
    parser.add_argument('-call', type=str, help='Method to call in syntax: "package.service.method"')
    parser.add_argument('-d','--data', type=str, help='Specifies path to Input data file')
    parser.add_argument('-o', type=str, help='Output File',default="output.json")
    
    args = parser.parse_args()

    server_address = args.address
    num_users = args.concurrency

    # total_requests = args.r
    num_requests = args.total

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
        input_data = read_json_as_array_of_dicts(input_file)
        
    
    initial_users = args.concurrency_start
    ramp_up_users = args.concurrency_step
    ramp_up_time  = args.concurrency_step_duration
    max_users     = args.concurrency_end




    # print(input_data)
    start_time = time.time()
    run_load_test(server_address, num_users, num_requests, proto_file, service_name, method_name,initial_users, max_users, ramp_up_users, ramp_up_time,  messages, services, request_name, response_name, input_data, output_file)
    end_time = time.time()

    print((end_time-start_time)*1000)

