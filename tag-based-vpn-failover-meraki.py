import requests
import json
import time
import logging
import pickle
import os
from pysnmp.hlapi import *
from logging.handlers import TimedRotatingFileHandler

global parameters

api_key = ""
org_id = ""
path = "NetworkDownList.pickle"  # Name of serialzed list file
url = "https://api.meraki.com/api/v0"  # base url
excludedIPs = ["8.8.8.8", "8.8.4.4", "212.58.237.254"]
networkDownList = []
network_list = ["N_something_something", "N"]


def getUplinkStats(api_key, org_id):
    "Utility function to return the uplink loss and latency for WAN1 on every MX in the org"
    try:
        get_url = "{0}/organizations/{1}/uplinksLossAndLatency?uplink=wan1".format(
            url, org_id
        )
        headers = {
            "x-cisco-meraki-api-key": format(str(api_key)),
            "Content-Type": "application/json",
        }
        response = requests.get(get_url, headers=headers)
        response_json = json.loads(response.text)

        if response.status_code == 200:
            sendSNMPTrap(4, "Heartbeat", "Remote system is connected with Meraki") #Sends heartbeat trap to RIM platform
            return response_json

        else:
            logging.error(
                "Error encountered when making API call:" + str(response.status_code)
            )
            exit(0)
    except Exception as e:
        logging.error("Error encountered when making API call: " + str(e))
        exit(0)


def getNetwork(api_key, network):
    "Utility function to return single network information"
    try:
        get_url = "{0}/networks/{1}/".format(url, network)
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


def sendSNMPTrap(severity, notification, description): 
    "Utility function to send SNMP Inform messages"
    try:
        deviceName = parameters["cdm_info"]["device_name"]
        cdmIP = parameters["cdm_info"]["cdm_ip"]
        classType = parameters["cdm_info"]["class"]
        communityKey = parameters["cdm_info"]["community_key"]
        errorIndication, errorStatus, errorIndex, varBinds = next(
            sendNotification(
                SnmpEngine(),
                CommunityData(communityKey, mpModel=1),
                UdpTransportTarget((cdmIP, 162)),
                ContextData(),
                "inform",
                NotificationType(
                    ObjectIdentity(".1.3.6.1.4.1.10714.1.1.1")
                ).addVarBinds(
                    (".1.3.6.1.4.1.10714.1.2.1", OctetString(deviceName)),
                    (".1.3.6.1.4.1.10714.1.2.2", Integer(severity)),
                    (".1.3.6.1.4.1.10714.1.2.3", OctetString(notification)),
                    (".1.3.6.1.4.1.10714.1.2.4", OctetString(description)),
                    (".1.3.6.1.4.1.10714.1.2.5", OctetString(classType)),
                ),
            )
        )
        if errorIndication:
            logging.error(errorIndication)
        elif errorStatus:
            logging.error(
                "%s at %s"
                % (
                    errorStatus.prettyPrint(),
                    errorIndex and varBinds[int(errorIndex) - 1][0] or "?",
                )
            )
        return
    except Exception as e:
        logging.error("Could not send SNMP inform message: " + str(e))
        exit(0)


def importJson(filename):
    "Imports JSON parameter file"
    try:
        with open(filename, "r") as jsonFile:
            jsonObj = json.load(jsonFile)
        return jsonObj
    except Exception as e:
        logging.error(
            "Error encountered when loading JSON configuration file: " + str(e)
        )
        exit(0)


def updateNetworkTags(api_key, network, payload):
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


def readPickle(path, default):
    "Function attempts to open an existing file with list. Otherwise will return an empty list."

    try:
        default = pickle.load(open(path, "rb"))
        return default
    except (OSError, IOError) as e:
        logging.info("No existing Network Down List: " + str(e))
        return default


def writePickle(path, default):
    "Writes list to existing file"

    try:
        pickle.dump(default, open(path, "wb"))
    except (OSError, IOError) as e:
        logging.error("Could not write list to file: " + str(e))


def VPNFailback(network, loss):
    "Swaps tags when the primary VPN is healthy"

    if loss is False and network["networkId"] in networkDownList:
        print("Primary VPN healthy again..swapping back")
        network_info = getNetwork(api_key, network["networkId"])
        tags = network_info["tags"].split()
        for i, tag in enumerate(tags):
            if "_ZS_P_DOWN" in tag:
                tag = tag.replace("_DOWN", "_UP")
                tags[i] = tag
            elif "_ZS_B_UP" in tag:
                tag = tag.replace("_UP", "_DOWN")
                tags[i] = tag

        payload = {"tags": " ".join(tags)}
        updateNetworkTags(api_key, network["networkId"], payload)
        networkDownList.remove(network["networkId"])
        logging.info(
            "FAILBACK - VPN healthy again: {0} IP:{1}.".format(
                network_info["name"], network["ip"]
            )
        )
    return


def VPNFailover(tags, network, network_name, timeseries):
    "Iterates through list of tags, updating the values without overiding"
    for i, tag in enumerate(tags):
        if "_ZS_P_DOWN" in tag:
            return
        elif "_ZS_P_UP" in tag:
            tag = tag.replace("_UP", "_DOWN")
            tags[i] = tag
        elif "_ZS_B_DOWN" in tag:
            tag = tag.replace("_DOWN", "_UP")
            tags[i] = tag

    payload = {"tags": " ".join(tags)}
    updateNetworkTags(api_key, network["networkId"], payload)
    networkDownList.append(network["networkId"])
    logging.info(
        "FAILOVER - {0} IP:{1} Loss: {2} Latency{3}.".format(
            network_name,
            network["ip"],
            timeseries["lossPercent"],
            timeseries["latencyMs"],
        )
    )
    return


def networkHealthCheck(network, loss):
    "Iterates through timeseries list to find cases where losspercent is >=30% or latency is >=100ms"

    for i in network["timeSeries"]:
        if i["lossPercent"] >= 30 or i["latencyMs"] >= 100:
            loss = True
            network_info = getNetwork(api_key, network["networkId"])
            network_name = network_info["name"]
            tags = network_info["tags"].split()
            VPNFailover(tags, network, network_name, i)
            break
    return loss


def sortNetworkMain(org):  # first function to be called
    "Iterates through list of networks in the organization (main function)"

    for network in org:
        if network["ip"] not in excludedIPs and network["networkId"] in network_list:
            loss = False
            loss = networkHealthCheck(network, loss)
            VPNFailback(network, loss)
    return


if __name__ == "__main__":

    # Defines Log File
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    logHandler = TimedRotatingFileHandler(
        "meraki_zscaler_vpn_health.log", when="D", interval=30, backupCount=6
    )
    logHandler.setLevel(logging.INFO)
    logHandler.setFormatter(formatter)
    logger.addHandler(logHandler)
    # Collects parameters from Json file
    parameters = importJson(
        "meraki_parameters.json"
    )  
    api_key = parameters["meraki"]["api_key"]
    org_id = parameters["meraki"]["org_id"]

    # Reads serialized file for latest version of networkDownList
    networkDownList = readPickle(path, networkDownList)
    # Retrieves uplink loss & latencty information for organization + can be used for heartbeat
    org = getUplinkStats(api_key, org_id)
    # Iterates through networks to determine if VPN needs to be swapped
    sortNetworkMain(org)
    # Writes to serialized file with latest version of networkDownList
    writePickle(path, networkDownList)
