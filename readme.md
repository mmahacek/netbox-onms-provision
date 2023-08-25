# netbox-onms-provision

# Overview

This is a proof of concept of using [pynetbox](https://github.com/netbox-community/pynetbox) and [pyonms](https://github.com/mmahacek/PyONMS) to build a requisition and send it to an OpenNMS instance.

NOTE: This is just a sample of pulling devices and building a requisition.
You will most likely want to update the logic to fit how you want to provision your devices.

# Setup

## Install requirements

1. Setup a Python virtual environment `python3 -m venv venv`
1. Activate the virtual environment `source venv/bin/activate`
1. Import the necessary libraries `pip3 install -r requirements.txt`

## Define secrets

Define system environment variables, or create a `.env` file that defines the following:

- onms_host
- onms_user
- onms_pass
- nb_host
- nb_token
