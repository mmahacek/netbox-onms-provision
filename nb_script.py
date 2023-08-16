# nb_script.py

import os
from typing import List

import pynetbox
from dotenv import load_dotenv
from pyonms import PyONMS
from pyonms.models.requisition import (
    AssetField,
    Category,
    Interface,
    PrimaryType,
    Requisition,
    RequisitionNode,
)

load_dotenv()


def get_device_ips(device: pynetbox.models.dcim.Devices) -> List[str]:
    return [
        ip.address.split("/")[0]
        for ip in nb.ipam.ip_addresses.filter(device_id=device.id)
        if ip != device.primary_ip4
    ]


def get_device_location(device: pynetbox.models.dcim.Devices) -> List[AssetField]:
    data = []
    site = nb.dcim.sites.get(device.site.id)
    if site.latitude and site.longitude:
        data.append(AssetField(name="latitude", value=site.latitude))
        data.append(AssetField(name="longitude", value=site.longitude))
    elif site.physical_address:
        address1, remainder = site.physical_address.split("\r\n")
        city, remainder = remainder.split(", ")
        state, postal = remainder.split(" ")
        data.append(AssetField(name="address1", value=address1))
        data.append(AssetField(name="city", value=city))
        data.append(AssetField(name="state", value=state))
        data.append(AssetField(name="zip", value=postal))
    return data


def convert_device(device: pynetbox.models.dcim.Devices) -> RequisitionNode:
    new_node = RequisitionNode(foreign_id=str(device.id), node_label=device.name)
    site = nb.dcim.sites.get(device.site.id)

    region = nb.dcim.regions.get(site.region.id)
    if region.name.lower() != "default":
        new_node.location = region.name

    location = get_device_location(device=device)
    for field in location:
        new_node.asset.append(field)

    new_node.set_asset(name="description", value=device.url)
    if device.location:
        new_node.set_asset(name="room", value=device.location.name)
    new_node.asset.append(
        AssetField(name="modelNumber", value=device.device_type.display)
    )
    new_node.set_asset(name="serialNumber", value=device.serial)
    if device.rack:
        new_node.set_asset(name="rack", value=device.rack.name)
        if device.position:
            new_node.set_asset(name="slot", value=device.position)

    if parent := device.custom_fields.get("Parent"):
        if parent_id := parent.get("id"):
            new_node.parent_foreign_id = parent_id

    # interfaces = list(nb.dcim.interfaces.filter(device_id=device.id))

    ip4 = Interface(
        ip_addr=device.primary_ip4.address.split("/")[0],
        snmp_primary=PrimaryType.PRIMARY,
    )
    new_node.add_interface(
        interface=ip4,
        merge=False,
    )

    ips = get_device_ips(device=device)
    for ip in ips:
        new_node.add_interface(
            Interface(
                ip_addr=ip,
                snmp_primary=PrimaryType.SECONDARY,
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


nb = pynetbox.api(url=os.environ.get("nb_host"), token=os.environ.get("nb_token"))

onms = PyONMS(
    hostname=os.environ.get("onms_host"),
    username=os.environ.get("onms_user"),
    password=os.environ.get("onms_pass"),
)

try:
    req = onms.requisitions.get_requisition(name="Netbox")
except Exception:
    req = Requisition(foreign_source="Netbox")

devices = nb.dcim.devices.all()

for device in devices:
    if not device.primary_ip4:
        continue
    else:
        new_node = convert_device(device=device)
        req.add_node(node=new_node, merge=False)

# print("---")
# print(req._to_dict())
onms.requisitions.update_requisition(requisition=req)
pass
