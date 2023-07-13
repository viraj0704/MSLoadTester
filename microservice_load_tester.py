
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
import numpy as np
import seaborn as sns

def generate_descriptor_set(proto_file):
    # Generate the descriptor set file
    file_name = os.path.basename(proto_file)
    descriptor_file =  "GeneratedFiles/" + os.path.splitext(file_name)[0] + ".desc"
    command = f"protoc --include_imports --include_source_info --descriptor_set_out=./{descriptor_file} --proto_path={os.path.dirname(proto_file)}  {proto_file}"
    subprocess.run(command, shell=True)
    return descriptor_file


def getMessage(file_proto, type):
    message = None
    for message_proto in getattr(file_proto,"message_type"):
        if message_proto.name == type.split(".")[-1]:
            message = message_proto
            break
    return message

def getParameters(input_message,messages):
    if input_message:
        if input_message.name not in messages:
            paramters = []
            for field_proto in input_message.field:
                paramters.append(field_proto.name)
            messages[input_message.name] = paramters
    return messages

def parse_proto(proto_file):
    descriptor_file = generate_descriptor_set(proto_file)
    descriptor_set = descriptor_pb2.FileDescriptorSet()
    with open(descriptor_file, "rb") as f:
        descriptor_set.ParseFromString(f.read())

    messages = {}
    services = {}
    messages[''] = []

    for file_proto in descriptor_set.file:
        methods = {}
        for service_proto in file_proto.service:
            for method_proto in service_proto.method:
                input_type = method_proto.input_type
                output_type = method_proto.output_type
                input_message = getMessage(file_proto,input_type)
                messages = getParameters(input_message,messages)
                output_message = getMessage(file_proto,output_type)
                messages = getParameters(output_message,messages)
                methods[method_proto.name] =  [input_message.name if input_message else '']
                methods[method_proto.name].append(output_message.name if output_message else '')
            services[service_proto.name] = methods
    
    return (messages,services)


def generate_proto_files(proto_file):
    # Run the protoc command to generate the Python files
    command = f"python3 -m grpc_tools.protoc  --python_out=. --grpc_python_out=. --proto_path={os.path.dirname(proto_file)} {proto_file}  "
    subprocess.run(command, shell=True)

def add_count(error_counts, error_message):
    if error_message in error_counts:
        error_counts[error_message] += 1
    else:
        error_counts[error_message] = 1
    return error_counts

def save_results_to_file(results, output_file):
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

def read_json_as_array_of_dicts(json_file):
    with open(json_file, 'r') as f:
        return json.load(f)
    
def percentile_i ( response_times, i):
    return response_times[int(len(response_times) * 0.01 * i)]

def plotHistogram (data,title,x_label,y_label):
    num_bins = (int) (np.sqrt(len(data)))
    if(len(data) != 1):
        data = np.clip(data, data[0], percentile_i(data,99))
        iqr = np.percentile(data, 75) - np.percentile(data, 25)
        bin_width = 2 * iqr / (len(data) ** (1/3))
        num_bins = int((data[len(data)-1] - data[0]) / bin_width)
    plt.clf()
    plt.hist(data, bins=num_bins,  edgecolor='black')
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.savefig("LatencyGraphs/" + title,  dpi=300, bbox_inches='tight')

def plot_dictionary(dict,title,x_label,y_label):
    x_val = list(dict.keys())
    y_val = list(dict.values())
    plt.clf()
    plt.plot(x_val,y_val,marker='o', markersize=5, linewidth=2, color='black')
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    plt.savefig("LatencyGraphs/" + title, dpi=300, bbox_inches='tight')
    
def handleGRPCError(error_counts,e,user_id):
    if e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
        print(f'User_ID: {user_id}, Error: Deadline exceeded')
        error_counts['Timeout error'] += 1

    elif e.code() == grpc.StatusCode.INVALID_ARGUMENT:
        print(f'User_ID: {user_id}, Error: {e.details()}')
        error_counts['Invalid Agruments'] += 1
    else:
        print(f'User_ID: {user_id}, Error: {e.details()}')
        error_counts['Internal server error'] += 1
    return error_counts
            

def send_requests(user_id, server_address, num_requests,proto_file,service_name,method_name,messages,services,request_name, response_name,input_data,time_per_request):

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
        try:
            request = None
            if request_name != '':
                request_class = getattr(protofile_pb2, request_name)
                request = request_class(**input_data[input_data_index])

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

        except grpc.RpcError as e:
            # Handle gRPC errors
            error_counts = handleGRPCError(error_counts,e,user_id)

        except Exception as e:
            # Handle other exceptions
            print(f'User_ID: {user_id}, Error: {str(e)}')
            error_counts['Internal server error'] += 1

        input_data_index = (input_data_index + 1) % input_data_length
        # time.sleep(1*(random.random()))
    channel.close()
    return (success_count, error_counts,response_times)

def createResult(num_requests,total_success,response_times,error_counts):
    success_rate = (total_success / num_requests) * 100 if (num_requests) > 0 else 0
    response_times = sorted(response_times)
    results = {
        'requests': {
            'total': num_requests,
            'success': total_success,
            'failure': num_requests-total_success,
            'rate': success_rate
        },
        'latency': {
            'average': sum(response_times) / len(response_times),
            'min': response_times[0],
            'max': response_times[-1],
            'percentiles': {
                '10': percentile_i(response_times,10),
                '25': percentile_i(response_times,25),
                '50': percentile_i(response_times,50),
                '75': percentile_i(response_times,75),
                '90': percentile_i(response_times,90),
                '95': percentile_i(response_times,95),
                '99': percentile_i(response_times,99),
            }
        },
        'errors': [
            {'message': error_message, 'count': error_counts[error_message]}
            for error_message in error_counts
        ],
        'throughput': success_rate,
        'status': 'completed'
    }
    return results

def run_load_test(server_address, num_users, num_requests,proto_file,service_name,method_name,initial_users, max_users, ramp_up_users, ramp_up_time,messages,services,request_name, response_name,input_data,output_file):

    generate_proto_files(proto_file)
    if(initial_users != None):
        curr_users = initial_users
    else:
        curr_users = num_users

    if(ramp_up_time == None):
        ramp_up_time = 10000000

    if(max_users == None):
        max_users = curr_users


    actual_curr_users = curr_users
    jump = (max_users - curr_users)/ramp_up_users
    if(jump != (int)(jump)) :
        jump = (int)(jump + 1)
    jump += 1
    num_requests_all = (int) (num_requests/jump) # Number of requests for all the different combinations except last , uniformly divided
    num_requests_last = (int) (num_requests_all +  num_requests - (jump*num_requests_all)) # Number of requests for the last with max_users

    average_latency_overall = {}
    percentile50_latency_overall = {}
    percentile90_latency_overall = {}
    percentile99_latency_overall = {}
    min_latency_overall = {}
    max_latency_overall = {}
    num_requests_overall = num_requests
    total_success_overall = 0
    response_times_overall = []
    flag = 0
    start_time = time.time()
    error_counts_overall = {'Timeout error': 0, 'Internal server error': 0, 'Invalid Agruments' : 0}
    while True:
        if (( time.time() - start_time) < ramp_up_time) and flag == 0:
            if(curr_users >= max_users):
                curr_users = min(curr_users,max_users)
                num_requests_all = num_requests_last
            print(curr_users)
            num_requests = (int) (num_requests_all/curr_users)
            remain_requests = num_requests_all%curr_users

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
                    time_per_request = ramp_up_time
                    if (total_requests != 0):
                        time_per_request = ramp_up_time/total_requests
                    future = executor.submit(send_requests, user_id, server_address, total_requests,proto_file,service_name,method_name,messages,services,request_name, response_name,input_data,time_per_request)
                    futures.append(future)

                # Collect the response times from all the processes
                for future in futures:
                    (result_success_count,result_error_count,result_response_times) = future.result()
                    response_times.extend(result_response_times)
                    success_count += result_success_count
                    for key, value in result_error_count.items():
                        error_counts[key] += value
                        error_counts_overall[key] += value



            total_success = success_count
            total_success_overall += total_success
 
            # Calculate metrics
            if(len(response_times) == 0):
                response_times.append(0)
            avg_response_time = sum(response_times) / len(response_times)
            status_code = 200 if len(response_times) > 0 else 500
            response_times = sorted(response_times)
            response_times_overall.extend(response_times)
            percentile_99 = percentile_i(response_times,99)
            percentile_50 = percentile_i(response_times,50)
            percentile_90 = percentile_i(response_times,90)
            min_response_time = response_times[0]
            max_response_time = response_times[len(response_times)-1]
            average_latency_overall[curr_users] =  avg_response_time
            percentile50_latency_overall[curr_users] =  percentile_50
            percentile90_latency_overall[curr_users] =  percentile_90
            percentile99_latency_overall[curr_users] =  percentile_99
            min_latency_overall[curr_users] = min_response_time
            max_latency_overall[curr_users] = max_response_time
            # results = createResult(num_requests_all,total_success,response_times,error_counts)
            # save_results_to_file(results, output_file.split(".")[0] + ' '+ f'{curr_users}' + ".json")

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
    plot_dictionary(percentile50_latency_overall,"50th Percentile Latency","Number of Users","50th Percentile Latency")
    plot_dictionary(percentile90_latency_overall,"90th Percentile Latency","Number of Users","90th Percentile Latency")
    plot_dictionary(percentile99_latency_overall,"99th Percentile Latency","Number of Users","99th Percentile Latency")
    plot_dictionary(min_latency_overall,"Minimum Latency","Number of Users","Minimum Latency")
    plot_dictionary(max_latency_overall,"Maximum Latency","Number of Users","Maximum Latency")

    results = createResult(num_requests_overall,total_success_overall,response_times_overall,error_counts_overall)
    save_results_to_file(results, output_file)
    plotHistogram(response_times_overall,"Response Time Histogram",'Response Times','Frequency')
    print(f'Load test results saved to {output_file}')

def generateDirectories():
    if os.path.isdir('./GeneratedFiles'):
        pass
    else:
        os.mkdir('./GeneratedFiles')
    if os.path.isdir('./LatencyGraphs'):
        pass
    else:
        os.mkdir('./LatencyGraphs')

def createOptionsFile(args):
    num_users_display = args.concurrency
    ramp_up_users_display = args.concurrency_step
    ramp_up_time_display = args.concurrency_step_duration
    if(args.concurrency_start != None):
        num_users_display = None
    else:
        ramp_up_users_display = None
        ramp_up_time_display = None
    options_data = {
        "call": args.call,
        "proto": args.proto,
        "addr": args.address,
        "n": args.total,
        "c": num_users_display,
        "concurrency_start" : args.concurrency_start,
        "concurrency_step" : ramp_up_users_display,
        "concurrency_end" : args.concurrency_end,
        "concurrency_step_duration": ramp_up_time_display,
        "output" : args.output,
        "data": args.data,
        "insecure": True,
        "name": f'{callMethod.split(".")[-2]} {callMethod.split(".")[-1]}'
    }
    save_results_to_file(options_data,"GeneratedFiles/options.json")
    
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
    parser.add_argument('-o','--output', type=str, help='Output File',default="output.json")
    
    args = parser.parse_args()
    # Extract arguments
    server_address = args.address
    num_users      = args.concurrency
    num_requests   = args.total
    proto_file     = args.proto
    callMethod     = args.call
    output_file    = args.output
    initial_users  = args.concurrency_start
    ramp_up_users  = args.concurrency_step
    ramp_up_time   = args.concurrency_step_duration
    max_users      = args.concurrency_end
    input_file     = args.data
    service_name   = callMethod.split(".")[-2]
    method_name    = callMethod.split(".")[-1]

    (messages, services) = parse_proto(proto_file)
    request_name = services[service_name][method_name][0]
    response_name = services[service_name][method_name][1]
    input_data = []
    if request_name != '':
        input_data = read_json_as_array_of_dicts(input_file)
        
    generateDirectories()
    createOptionsFile(args)
    run_load_test(server_address, num_users, num_requests, proto_file, service_name, method_name,initial_users, max_users, ramp_up_users, ramp_up_time,  messages, services, request_name, response_name, input_data, output_file)


