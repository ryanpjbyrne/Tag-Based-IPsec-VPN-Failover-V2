import requests
import json
import time

"""
Future improvements:
1) Consider using latency as a additional failing condition:  i.e 'or i['latencyMs'] >= 100'
2) Error Handling - Cases where the API does not respond or is response is empty will fail the script - use of try/expect will fix this. 
3) Logging - Useful if not running scripts manually 
4) previousNetwork list 
"""


api_key = "0eb3bc01975ac5648cfb69d76f1c68fca2e1096b"
org_id = "775803"
url = "https://api.meraki.com/api/v0"  # base url
networkDownList = []


def getUplinkLoss(api_key, org_id):
    "Utility function to return the uplink loss and latency for every MX in the org"

    get_url = "{0}/organizations/{1}/uplinksLossAndLatency".format(url, org_id)
    headers = {
        "x-cisco-meraki-api-key": format(str(api_key)),
        "Content-Type": "application/json",
    }
    response = requests.get(get_url, headers=headers)
    # print(response.status_code)
    response = json.loads(response.text)
    # print(response)
    return response


def getAllNetworks(api_key, org_id):
    "Utility function to return organization network information"

    get_url = "{0}/organizations/{1}/networks".format(url, org_id)
    headers = {
        "x-cisco-meraki-api-key": format(str(api_key)),
        "Content-Type": "application/json",
    }
    response = requests.get(get_url, headers=headers)
    # print(response.status_code)
    response = json.loads(response.text)
    # print(response)
    return response


def getNetwork(api_key, network):
    "Utility function to return single network information"

    get_url = "networks/{0}/".format(network)
    headers = {
        "x-cisco-meraki-api-key": format(str(api_key)),
        "Content-Type": "application/json",
    }
    response = requests.get(get_url, headers=headers)
    response = json.loads(response.text)
    return response


def updateNetwork(api_key, network, payload):
    "Utility function to update network configuration"

    get_url = "{0}/networks/{1}".format(url, network)
    headers = {
        "x-cisco-meraki-api-key": format(str(api_key)),
        "Content-Type": "application/json",
    }
    response = requests.put(get_url, headers=headers, data=json.dumps(payload))
    # print(response.text)
    # print(response.status_code)
    return response


def swapVPN(network, loss):
    "Swaps tags when the primary VPN is healthy"

    if loss is False and network["networkId"] in networkDownList:
        print("Primary VPN healthy again..swapping back")
        network_info = getNetwork(api_key, network["networkId"])
        tags = network_info["tags"].split()
        for tag in tags:
            if "_primary_down" in tag:
                tag = tags.replace("_down", "_up")
            elif "_backup_up" in tag:
                tag = tags.replace("_up", "_down")

        payload = {"tags": " ".join(tags)}
        # print(payload)
        updateNetwork(api_key, network, payload)
        networkDownList.remove(network["networkId"])
        print(networkDownList)
    return


def sort_tags(tags, network):
    "Iterates through list of tags, updating the values without overiding"
    for tag in tags:
        if "_primary_down" in tag:
            print("VPN already swapped")
            break
        elif "_primary_up" in tag:
            tag = tags.replace("_up", "_down")
            print("Changing VPN Recent Loss")
        elif "_backup_down" in tag:
            tag = tags.replace("_down", "_up")

    payload = {"tags": " ".join(tags)}
    print(payload)
    updateNetwork(api_key, network, payload)
    networkDownList.append(network)
    print(networkDownList)
    return


def network_tags(network):
    "Iterates through timeseries list to find cases where losspercent is >30"

    for i in network["timeseries"]:
        if i["lossPercent"] >= 30:  # consider using latency: or i['latencyMs'] >= 100
            loss = True
            network_info = getNetwork(api_key, network["networkId"])
            print(network_info["name"])
            tags = network_info["tags"].split()
            network = network_info["networkId"]
            sort_tags(tags, network)
            break
    return loss


def sortNetworkMain(org):  # first function to be called
    "Iterates through list of networks in the organization (main function)"
    
    for network in org:
        if network["ip"] != "8.8.8.8" and network["uplink"] != "wan1":
            loss = False
            print(network["networkId"])
            print(network["ip"])
            loss = network_tags(network)
            swapVPN(network, loss)
    return


if __name__ == "__main__":
    while True:
        org = getUplinkLoss(api_key, org_id)
        sortNetworkMain(org)
        print("Sleeping for 5s...")
        time.sleep(30)
