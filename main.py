import sys, time, requests
from concurrent.futures import ThreadPoolExecutor

# NOTE: please use python 3.11 or higher

root_ip = "https://api.waqi.info"

# ---------------------------
# utils:

def is_float(string:str) -> bool:
    try:
        float(string)
        return True
    except ValueError:
        return False

# make several http requests in parallel
def get_responses_batch(url_list:list[str], workers=16) -> list[requests.Response]:
    with ThreadPoolExecutor(max_workers=workers) as executor:
        request_url = lambda url: requests.get(url)
        return list(executor.map(request_url, url_list))

# ---------------------------
# sampling:

def get_station_requests(coords:str, api_token:str, iaqi:str="pm25") -> list[str]:
    map_query_request = "{}/map/bounds?token={}&latlng={}".format(root_ip, api_token, coords)

    response = requests.get(map_query_request)
    response_dict = response.json()

    if response_dict["status"] == "error":
        raise Exception("API error: " + response_dict["data"])
    else:
        if len(response_dict["data"]) == 0:
            return 0.0

        # create set of requests
        station_urls = [f"{root_ip}/feed/@{city_dict['uid']}/?token={api_token}" for city_dict in response_dict["data"]]
        station_uids = [ int(city_dict["uid"]) for city_dict in response_dict["data"] ]

        response_list = get_responses_batch(station_urls)

        filtered_station_urls = []
        filtered_station_uids = []
        for response, url, uid in zip(response_list, station_urls, station_uids):
            # I've noticed that some stations don't report pm25, so we want to ignore those stations
            if iaqi in response.json()["data"]["iaqi"]:
                filtered_station_urls += [url]
                filtered_station_uids += [uid]
            else:
                print(f"Ignoring station {uid}")

        return filtered_station_urls, filtered_station_uids

def get_samples(station_urls:list[str], iaqi:str="pm25") -> list[float]:
    response_list = get_responses_batch(station_urls)
    
    measurement_list = []
    for response in response_list:
        response_dict = response.json()
        if response_dict["status"] == "error":
            raise Exception(response_dict["message"])
        else:
            measurement_list += [response_dict["data"]["iaqi"][iaqi]["v"]]

    return measurement_list

# ---------------------------
# handling arguments 

def get_input():
    if len(sys.argv) < 3:
        print("Error: too few arguments. Please provide the arguments: api_token lat1,lng1,lat2,lng2 sampling_period sampling_rate")
        sys.exit(1)
    elif len(sys.argv) > 5:
        print("Error: too many arguments. Please provide the arguments: api_token lat1,lng1,lat2,lng2 sampling_period sampling_rate")
        sys.exit(1)
    else:
        api_token = sys.argv[1]
        coords = sys.argv[2]
        if len(sys.argv) == 3:
            sampling_period = 5.0
            sampling_rate = 1.0
        elif len(sys.argv) == 4:
            coords = sys.argv[2]
            sampling_period = sys.argv[3]
            sampling_rate = 1.0
        elif len(sys.argv) == 5:
            coords = sys.argv[2]
            sampling_period = sys.argv[3]
            sampling_rate = sys.argv[4]

    return api_token, coords, sampling_period, sampling_rate

def validate_input(coords, sampling_period, sampling_rate):
    if not "," in coords:
        print("Error: lat1,lng1,lat2,lng2 parameter invalid, please provide a list of 4 comma separated coordinates " +
              "without spaces in between.")
        sys.exit(1)

    if is_float(sampling_period):
        sampling_period = float(sampling_period)
    else:
        print("Error: sampling_period must be valid decimal number.")
        sys.exit(1)

    if is_float(sampling_rate):
        sampling_rate = float(sampling_rate)
    else:
        print("Error: sampling_rate must be valid decimal number.")
        sys.exit(1)

    if sampling_rate / 60.0 > 1000.0:
        # NOTE: this is in the worst case, since two api requests need to be made
        print("Error: sampling rate is too high for the api to keep up, please choose a smaller sampling rate.")
        sys.exit(1)
    
    return coords, sampling_period, sampling_rate

# ---------------------------
# body:

if __name__ == "__main__":
    # 
    api_token, coords, sampling_period, sampling_rate = get_input()
    coords, sampling_period, sampling_rate = validate_input(coords, sampling_period, sampling_rate)

    station_urls, station_uids = get_station_requests(coords, api_token)
    print("There are {} valid stations in the requested area.".format(len(station_urls)))

    # get number of stations in the area, and determine the max sampling rate based on api limits
    estimate_requests_per_sec = (sampling_rate / 60) * len(station_urls)
    if estimate_requests_per_sec > 1000.0:
        print(f"Error: sampling_rate={sampling_rate} is too high for the api limits to keep up for this query, " + 
               "please choose a smaller sampling rate.")
        sys.exit(2)
    elif estimate_requests_per_sec > 500.0:
        print(f"Warning: sampling_rate={sampling_rate} is nearly too high for the api to keep up for this query. " + 
               "Consider lowering sample rate")

    sample_total = 0.0
    num_samples = 0
    time_elapsed = 0.0

    while time_elapsed < (sampling_period * 60.0):
        last_time = time.time()
        sample_list = get_samples(station_urls)
        elapsed_during_request = time.time() - last_time

        print("\tCollected samples: (took {:.3f}s)".format(elapsed_during_request))
        for sample, uid in zip(sample_list, station_uids):
            print("\t\tPM2.5 @ station {}\t= {:.2f}".format(uid, sample))

        sample_total += sum(sample_list) / len(sample_list)
        num_samples += 1
        
        sleep_time = (60.0 / sampling_rate) - elapsed_during_request
        if sleep_time < 0:
            print(f"Error: api requests taking too long ({elapsed_during_request}s), please decrease sampling rate")
            sys.exit(2)

        # ensure sampling rate is accurate by taking request time into account
        time.sleep(sleep_time)
        time_elapsed += 60.0 / sampling_rate

    sample_time_avg = sample_total / num_samples
    print("The average PM2.5 quality over {} samples is:\n{:.5f}".format(num_samples, sample_time_avg))
