# Script to dynamically update the IP address of a DNS record on Cloudflare

import requests

# disable urllib warning about SSL cert
from urllib3 import disable_warnings, exceptions
import configparser
from os import path

disable_warnings(exceptions.InsecureRequestWarning)

BASEURL = "https://api.cloudflare.com/client/v4/"

config = configparser.ConfigParser()
config.read(path.join(path.dirname(__file__), "DDNS.config"))
config = config["DEFAULT"]

# first, get our current IP address
currentIP = requests.get("https://ysap.sh/ip").content.decode("utf-8")
if config["verbose"]:
    print("Current IP: " + currentIP)

# next, verify the Cloudflare login with the /tokens/verify endpoint
# we will reuse these headers later
headers = {
    "X-Auth-Email": config["email"],
    "Authorization": "Bearer " + config["key"],
    "Content-Type": "application/json",
}

authResult = requests.get(BASEURL + "user/tokens/verify", headers=headers).json()
if authResult["success"] != True:
    print(
        "Error authenticating to Cloudflare: " + authResult["errors"][0].get("message"),
        authResult.get("errors"),
    )
    exit(1)
elif config["verbose"]:
    print("Authentication successful")

# now, get the zone ID for the domain we want to update
zoneResult = requests.get(
    BASEURL + "zones?name=" + config["domains"], headers=headers
).json()
if zoneResult["success"] != True:
    print(
        "Error getting zone ID: " + zoneResult["errors"][0].get("message"),
        zoneResult["errors"][0].get("error_chain"),
    )
    exit(1)
elif config["verbose"]:
    print("Zone ID: " + zoneResult["result"][0]["id"])

# next, get the DNS record IDs for the domains
dnsResult = requests.get(
    BASEURL
    + "zones/"
    + zoneResult["result"][0]["id"]
    + "/dns_records?type=A&name="
    + config["domains"],
    headers=headers,
).json()
if dnsResult["success"] != True:
    print(
        "Error getting DNS record ID: " + dnsResult["errors"][0]["message"],
        dnsResult["errors"][0]["error_chain"],
    )
    exit(1)
dnsRecordIDs = []
for recordID in dnsResult["result"]:
    dnsRecordIDs.append(recordID)
    if config["verbose"]:
        print(
            "DNS Record ID for "
            + recordID["name"]
            + ":\n\tID:m"
            + recordID["id"]
            + "\n\tIP: "
            + recordID["content"]
        )

# finally, update the DNS record with the current IP address if it has changed
for recordID in dnsRecordIDs:
    if (
        config["ignore_TLD"] not in [False, "false", "False", "no", "No"]
        and dnsRecordIDs.index(recordID) == 0
    ):
        print("Ignoring TLD " + recordID["name"] + " due to ignore_TLD setting...")
        continue

    if recordID["content"] != currentIP:
        print(
            "Updating "
            + recordID["name"]
            + " with IP "
            + currentIP
            + ". Old IP was "
            + recordID["content"]
        )
        body = {
            "type": recordID["type"],
            "name": recordID["name"],
            "content": currentIP,
            "ttl": 3600,
            "proxied": False,
            "comment": "Maintained automatically by DDNS.py",
        }
        updateResult = requests.patch(
            BASEURL + "zones/" + recordID["zone_id"] + "/dns_records/" + recordID["id"],
            headers=headers,
            json=body,
        ).json()
        if updateResult["success"] != True:
            print("Error updating DNS record: " + updateResult)
            exit(1)
        print("DNS record updated successfully")
    else:
        print("DNS record " + recordID["name"] + " already up to date")

print("Script complete")
