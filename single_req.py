# nb_script.py

"""Sample script to generate an OpenNMS requisition from NetBox inventory"""

import os
from typing import List

import pynetbox
from dotenv import load_dotenv
from pyonms import PyONMS
from pyonms.models.requisition import Interface, Requisition, RequisitionNode

load_dotenv()

nb = pynetbox.api(url=os.environ.get("nb_host"), token=os.environ.get("nb_token"))

onms = PyONMS(
    hostname=os.environ.get("onms_host"),
    username=os.environ.get("onms_user"),
    password=os.environ.get("onms_pass"),
    # verify_ssl=False,
)


def parse_ip(ip: str) -> str:
    "Remove subnet from IP address"
    return ip.split("/")[0]


def get_device_ips(device: pynetbox.models.dcim.Devices) -> List[str]:
    "Get a list of all non-primary IP addresses associated with a given device"
    return [
        parse_ip(ip.address)
        for ip in nb.ipam.ip_addresses.filter(device_id=device.id)
        if ip != device.primary_ip4
    ]


def get_device_location(device: pynetbox.models.dcim.Devices) -> dict:
    "Get geolocation and/or address information for a device"
    data = {}
    site = nb.dcim.sites.get(device.site.id)
    if site.latitude and site.longitude:
        data["latitude"] = site.latitude
        data["longitude"] = site.longitude
    if site.physical_address:
        address1, remainder = site.physical_address.split("\r\n")
        city, remainder = remainder.split(", ")
        state, postal = remainder.split(" ")
        data["address1"] = address1
        data["city"] = city
        data["state"] = state
        data["zip"] = postal
    return data


def convert_device(
    device: pynetbox.models.dcim.Devices, requisition: Requisition
) -> RequisitionNode:
    "Build an OpenNMS RequisitionNode from a Netbox Device"
    new_node = requisition.node.get(str(device.id))
    if not new_node:
        new_node = RequisitionNode(foreign_id=str(device.id), node_label=device.name)
    site = nb.dcim.sites.get(device.site.id)

    region = nb.dcim.regions.get(site.region.id)
    if region.name.lower() != "default":
        new_node.location = region.name

    location = get_device_location(device=device)
    for key, value in location.items():
        new_node.set_asset(name=key, value=value)

    new_node.set_asset(name="description", value=device.url)
    if device.location:
        new_node.set_asset(name="room", value=device.location.name)
    new_node.set_asset(name="modelNumber", value=device.device_type.display)

    new_node.set_asset(name="serialNumber", value=device.serial)
    if device.rack:
        new_node.set_asset(name="rack", value=device.rack.name)
        if device.position:
            new_node.set_asset(name="slot", value=device.position)

    if parent := device.custom_fields.get("Parent"):
        if parent_id := parent.get("id"):
            new_node.parent_foreign_id = parent_id

    ip4 = Interface(
        ip_addr=parse_ip(device.primary_ip4.address),
        snmp_primary="P",
    )
    new_node.add_interface(interface=ip4, merge=False)

    for ip in get_device_ips(device=device):
        new_node.add_interface(
            Interface(
                ip_addr=ip,
                snmp_primary="S",
            ),
            merge=False,
        )

    new_node.add_category(category=device.device_role.slug)
    tags = [tag.slug for tag in device.tags]
    for tag in tags:
        if tag not in [cat.name for cat in new_node.category]:
            new_node.add_category(category=tag)
    new_node._to_dict()

    return new_node


if __name__ == "__main__":
    try:
        req = onms.requisitions.get_requisition(name="Netbox")
    except Exception:
        req = Requisition(foreign_source="Netbox")

    devices = nb.dcim.devices.all()

    for device_node in devices:
        if not device_node.primary_ip4:
            continue
        else:
            new_device = convert_device(device=device_node, requisition=req)
            req.add_node(node=new_device, merge=False)

    onms.requisitions.update_requisition(requisition=req)
    # onms.requisitions.import_requisition(name=req.foreign_source, rescan=False)
