import requests
import json
import time
import logging
import pickle
import os
global parameters

api_key = ""
org_id = ""
path="NetworkDownList.pickle" #Name of serialzed list file
url = "https://api.meraki.com/api/v0"  # base url
excludedIPs = ['8.8.8.8','8.8.4.4','212.58.237.254']
networkDownList = []


def getUplinkLoss(api_key, org_id):
    "Utility function to return the uplink loss and latency for every MX in the org"
    try:
        get_url = "{0}/organizations/{1}/uplinksLossAndLatency?uplink=wan1".format(url, org_id)
        headers = {
            "x-cisco-meraki-api-key": format(str(api_key)),
            "Content-Type": "application/json",
        }
        response = requests.get(get_url, headers=headers)
        response = json.loads(response.text)
        return response
    except Exception as e: 
        logging.error("Error encountered when making API call: " + str(e))
        exit(0)



def getNetwork(api_key, network):
    "Utility function to return single network information"
    try:
        get_url = "{0}/networks/{1}/".format(url,network)
        headers = {
            "x-cisco-meraki-api-key": format(str(api_key)),
            "Content-Type": "application/json",
        }
        response = requests.get(get_url, headers=headers)
        response = json.loads(response.text)
        return response
    except Exception as e:
        logging.error("Error encountered when making API call: " + str(e))
        exit(0)

def send_snmp(severity,notification,description):
    "Utility function to send SNMP Inform messages"
    try:
        deviceName = parameters['cdm_info']['device_name']
        cdmIP = parameters['cdm_info']['cdm_ip']
        classType=parameters['cdm_info']['class']
        communityKey=parameters['cdm_info']['community_key']
        errorIndication, errorStatus, errorIndex, varBinds = next(
            sendNotification(
                SnmpEngine(),
                CommunityData(communityKey, mpModel=1),
                UdpTransportTarget((cdmIP, 162)),
                ContextData(),
                'inform',
                NotificationType(
                    ObjectIdentity('.1.3.6.1.4.1.10714.1.1.1')
                ).addVarBinds(
                    ('.1.3.6.1.4.1.10714.1.2.1', OctetString(deviceName)),
                    ('.1.3.6.1.4.1.10714.1.2.2', Integer(severity)),
                    ('.1.3.6.1.4.1.10714.1.2.3', OctetString(notification)),
                    ('.1.3.6.1.4.1.10714.1.2.4', OctetString(description)),
                    ('.1.3.6.1.4.1.10714.1.2.5', OctetString(classType)),
                )
            )
        )
        if errorIndication:
            logging.error(errorIndication)
        elif errorStatus:
           logging.error('%s at %s' % (errorStatus.prettyPrint(),
                                errorIndex and varBinds[int(errorIndex) - 1][0] or '?'))
    except Exception as e:
        logging.error('Could not send SNMP inform message: ' + str(e))
        exit(0)


def importJson(filename):
    "Imports json parameter file"
    try:
        with open(filename, 'r') as jsonFile:
            jsonObj = json.load(jsonFile)
        return jsonObj
    except Exception as e:
        logging.error("Error encountered when loading JSON configuration file: "+ str(e))
        exit(0)



def readPickle(path,default): 
    "Function attempts to open an existing file with list. Otherwise will return an empty list."

    try:
        default= pickle.load(open(path,"rb"))
        return default
    except (OSError,IOError) as e :
        logging.info('No existing Network Down List: ' + str(e))
        return default

def writePickle(path,default):
    "Writes list to existing file"

    try:
        pickle.dump(default,open(path,"wb")) 
    except(OSError,IOError) as e :
        logging.error("Could not write list to file: " + str(e))


def updateNetwork(api_key, network, payload):
    "Utility function to update network configuration"

    try:
        get_url = "{0}/networks/{1}".format(url, network)
        headers = {
            "x-cisco-meraki-api-key": format(str(api_key)),
            "Content-Type": "application/json",
        }
        response = requests.put(get_url, headers=headers, data=json.dumps(payload))
        return response
    except Exception as e: 
        logging.error("Error encountered when making API call: " + str(e))
        exit(0)




def swapVPN(network, loss):
    "Swaps tags when the primary VPN is healthy"

    if loss is False and network["networkId"] in networkDownList:
        print("Primary VPN healthy again..swapping back")
        network_info = getNetwork(api_key, network["networkId"])
	network_name = network_info["name"]
        tags = network_info["tags"].split()
        for i,tag in enumerate(tags):
            if "_primary_down" in tag:
                tag = tag.replace("_down", "_up")
                tags[i]=tag
            elif "_backup_up" in tag:
                tag = tag.replace("_up", "_down")
                tags[i]=tag

        payload = {"tags": " ".join(tags)}
        updateNetwork(api_key, network['networkId'], payload)
        networkDownList.remove(network["networkId"])
        logging.info("FAILBACK - VPN healthy again: {0} IP:{1}.".format(network_info["name"],network["ip"]))
    return


def sortTags(tags, network,network_name,timeseries):
    "Iterates through list of tags, updating the values without overiding"
    for i,tag in enumerate(tags):
        if "_primary_down" in tag:
            #print("VPN already swapped")
            return
        elif "_primary_up" in tag:
            tag = tag.replace("_up", "_down")
            tags[i]=tag
            #print("Changing VPN Recent Loss")
        elif "_backup_down" in tag:
            tag = tag.replace("_down", "_up")
            tags[i]=tag

    payload = {"tags": " ".join(tags)}
    updateNetwork(api_key, network["networkId"], payload)
    networkDownList.append(network["networkId"])
    logging.info("FAILOVER - {0} IP:{1} Loss: {2} Latency{3}.".format(network_name,network["ip"],timeseries["lossPercent"],timeseries["latencyMs"]))
    return


def networkTags(network,loss):
    "Iterates through timeseries list to find cases where losspercent is >=30% or latency is >=100ms"

    for i in network["timeSeries"]:
        if i["lossPercent"] >= 30 or i['latencyMs'] >= 100:
            loss = True
            network_info = getNetwork(api_key, network["networkId"])
            network_name=network_info["name"]
            tags = network_info["tags"].split()
            sortTags(tags,network,network_name,i)
            break
    return loss


def sortNetworkMain(org):  # first function to be called
    "Iterates through list of networks in the organization (main function)"
    
    for network in org:
        if network["ip"] not in excludedIPs : 
            loss = False
            loss = networkTags(network,loss)
            swapVPN(network, loss)
    return


if __name__ == "__main__":

    # Defines Log File
    logging.basicConfig(filename='meraki_vpn_health.log',
                        format='%(asctime)s %(levelname)s: %(message)s',
                        level=logging.INFO)

    parameters=importJson('meraki_parameters.json') #Collects parameters from Json file
    api_key= parameters['meraki']['api_key']
    org_id= parameters['meraki']['org_id']

    #Reads serialized file for latest version of networkDownList
    networkDownList=readPickle(path,networkDownList) 
    #Retrieves uplink loss & latencty information for organization
    org = getUplinkLoss(api_key, org_id)
    #Iterates through networks to determine if VPN needs to be swapped
    sortNetworkMain(org)
    #Writes to serialized file with latest version of networkDownList
    networkDownList=writePickle(path,networkDownList)


   
