import requests, json, time
api_key = ''
org_id = ''
url = 'https://api.meraki.com/api/v0/organizations/'+org_id+'/uplinksLossAndLatency'
header = {"X-Cisco-Meraki-API-Key": api_key, "Content-Type": "application/json"}
networkDownList = []
while True:
    response = requests.get(url,headers=header)
    for network in response.json():
        if network['ip'] != '8.8.8.8' and network['uplink']!="wan1":
            print(network['networkId'])
            print(network['ip'])
            loss=False
            for iteration in network['timeSeries']:
                if iteration['lossPercent'] >= 30:
                    loss=True
                    network_info = requests.get("https://api.meraki.com/api/v0/networks/"+network['networkId'], headers=header)
                    print(network_info.json()['name'])
                    tags = network_info.json()['tags'].split() # no '  ' - [' ',a,b,' '] [a,b]
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
                    new_network_info = requests.put("https://api.meraki.com/api/v0/networks/"+network['networkId'], data=json.dumps(payload), headers=header)
                    networkDownList.append(network)
                    print(networkDownList)
                    break
            if loss is False and network["networkId"] in networkDownList:
                print("Primary VPN healthy again..swapping back")
                network_info = requests.get("https://api.meraki.com/api/v0/networks/"+network['networkId'], headers=header)
                tags = network_info["tags"].split()
                for tag in tags:
                    if "_primary_down" in tag:
                        tag = tags.replace("_down", "_up")
                    elif "_backup_up" in tag:
                        tag = tags.replace("_up", "_down")

                payload = {"tags": " ".join(tags)}
                new_network_info = requests.put("https://api.meraki.com/api/v0/networks/"+network['networkId'], data=json.dumps(payload), headers=header)
                networkDownList.remove(network["networkId"])
                print(networkDownList)
    print("Sleeping for 5s...")
    time.sleep(5)