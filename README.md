Tag-Based IPsec VPN Failover
============= 

## Overview
Tagged Based VPN Failover is utilized for third party Data Center Failover and OTT SD WAN Integration. This is accomplished by utilizing the API at each branch or Data Center. Each MX appliance will utilize IPsec VPN with cloud VPN nodes. IPsec along with the API is utilized to facilitate the dynamic tag allocation.

Spoke sites will form a VPN tunnel to the primary DC

dual active VPN tunnels to both DC’s is not possible with IPSEC given that interesting traffic is often needed to bring up an ipsec tunnel and that interesting traffic will be routed to the first tunnel/peer configured and never the second

Each spoke will be configured with a tracked IP of its primary DC under the traffic shaping page

If the tracked IP experiences loss in the last 5 minutes, the API script (below) will re-tag the network in order to swap to the secondary ipsec VPN tunnel

Once the tracked IP has not had any loss in the last 5 minutes, the tags will be swapped back to swap back to the primary DC (to avoid flapping)



### Configuration of network tags

Navigate to Organization > Overview on the Meraki Dashboard.  Select the network you wish to tag and add one tag for each IPSEC peer.  Tags should be in the format:

<identifier>_<primary/backup>_<state(up/down)>

 

As an example, if my primary VPN endpoint is London and backup is Paris my tags would be:

**london_primary_up** (default state for primary is up)

**paris_backup_down** (default state for the backup is down)


### Developer Notes

This script is based of an vendor script : https://documentation.meraki.com/MX/Site-to-site_VPN/Tag-Based_IPsec_VPN_Failover

Following changes: 

*  Refactored - Removal of infinite loop, functions etc
*  Fix of tagging functionality 
*  Cron compatible
*  SNMP monitoring 

 


