import requests, json, time
api_key = ''
org_id = ''
#Specify monitored IPs to exclude from the script, typicaly all non Zscaler IPs you monitor
ipToExclude  = ['8.8.8.8','8.8.4.4','208.67.220.220','208.67.222.222']
url = 'https://api.meraki.com/api/v0/organizations/'+org_id+'/uplinksLossAndLatency?uplink=wan1'
header = {"X-Cisco-Meraki-API-Key": api_key, "Content-Type": "application/json"}
previousNetwork = ""
while True:
    response = requests.get(url,headers=header)
    for network in response.json():
        tagsAfter = [] #Array with final tags
        tagsString = "" #String with final tags
        if network['ip'] not in ipToExclude and network['networkId'] != previousNetwork:
            skipNetwork = False
            network_info = requests.get("https://api.meraki.com/api/v0/networks/"+network['networkId'], headers=header)
            print("-------------------------------------")
            print("Network Name : "+network_info.json()['name'])
            print("Network Id : "+network['networkId'])
            print("Device Serial : "+network['serial'])
            print("Monitored IP : "+network['ip'])
            loss=False
            tagsBefore = network_info.json()['tags'].split(' ')
            swapped = False
            #We get all tags of Network, and specificaly Primary and Backup ZENs. If there is a ZEN_Forced tag, we stop
            for tag in tagsBefore:
                if "ZEN_Forced" in tag:
                    skipNetwork = True
                if "ZEN_Primary" in tag:
                    primary = tag
                    print("Primary ZEN : " + primary)
                elif "ZEN_Backup" in tag:
                    backup = tag
                    print("Backup ZEN : " + backup)
                elif tag == "ZEN_Swapped":
                    swapped = True
                else:
                    tagsAfter.append(tag)
            if skipNetwork:
                print("ZEN Forced, skip network")
                break
            #We then check connectivity Health, and if conditions are not met, we Swap Backup and Primary, and add a ZEN_Swapped tag
            for iteration in network['timeSeries']:
                if iteration['lossPercent'] >= 30 or iteration['latencyMs'] >= 100:
                    loss=True
                    if swapped == True:
                        print("VPN already swapped")
                        break
                    else:
                        print("Need to change VPN, recent loss - "+str(iteration['lossPercent'])+"% - "+str(iteration['latencyMs'])+"ms")
                        tagsAfter.append(primary.split("_Up")[0]+"_Down")
                        tagsAfter.append(backup.split("_Down")[0]+"_Up")
                        tagsAfter.append("ZEN_Swapped")
                        for tag in tagsAfter:
                            tagsString+= tag + " "
                        print("New List of Tags : "+tagsString)
                        payload = {'tags': tagsString.strip()}
                        new_network_info = requests.put("https://api.meraki.com/api/v0/networks/"+network['networkId'], data=json.dumps(payload), headers=header)
                        break
            #If connectivity Health is back to normal on Primary we swap back
            if loss==False and swapped == True:
                print("Primary VPN healthy again..Swapping back")
                tagsAfter.append(primary.split("_Down")[0]+"_Up")
                tagsAfter.append(backup.split("_Up")[0]+"_Down")
                for tag in tagsAfter:
                    tagsString+= tag + " "
                print("New List of Tags : "+tagsString)
                payload = {'tags': tagsString.strip()}
                new_network_info = requests.put("https://api.meraki.com/api/v0/networks/"+network['networkId'], data=json.dumps(payload), headers=header)
        previousNetwork = network['networkId']
    print("Sleeping for 30s...")
    print("#####################################")
    print("#####################################")
    time.sleep(30)