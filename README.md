foreman-network-snippet
=======================

A snippet for foreman to do the networking, bonding, vlan tagging at build time using puppet + enc setup.

How it works
============

It leverages Puppet, expecting Puppet to be using Foreman as an ENC, in there you define the host data
as parameters and such. When the box builds, it makes a query to its puppet master to get a dump of the
parameters foreman has for the node and then it uses them to setup the networking. 

Examples
========

Currently networking support in Foreman is very basic, it does not handle bonding / vlans / tags etc. 

To get foreman to work with the networking i have had to write a snippet which will get executed in a %post, it fetches the data from foreman and then creates the necessary configuration files in /etc/sysconfig/network-scripts. The formant is:

device_name 
device_address
device_gateway
device_netmask
Device can be any device (eth0, vlan123, bond0 etc.), but the principles mostly are the same throughout, except additional ones depending on the circumstances. A bond would need the interfaces associated with it as well as the bond options, so there will be additional:

# Standard interface no IP config
eth0_name = "Basic interface"

# Standard interface with IP config
eth0_name = "OOB eth0 interface"
eth0_address = "10.123.1.4"
eth0_netmask = "255.255.255.0"
eth0_gateway = "10.123.1.1"

# Bond interface with no IP config
bond0_interfaces = "eth0,eth3"
bond0_name       = "OOB bond"
bond0_options    = "mode=1 miimon=100 downdelay=200 updelay=200 primary=eth0 use_carrier=1"

# Bond interface with IP config
bond0_interfaces = "eth0,eth3"     # the interfaces associated with the bond i.e. eth0,eth3
bond0_address    = "10.123.3.4"    # the bonds IP if required
bond0_netmask    = "255.255.255.0" # the bond netmask if required (could be just a plain bond)
bond0_gateway    = "10.123.3.1"    # the gateway if required (may not be as just a plain bond)
bond0_options    = "mode=1 miimon=100 downdelay=200 updelay=200 primary=eth2 use_carrier=1 primary_reselect=2"                # the bond options
bond0_name       = "OOB BOND"      # the name of the bond (i.e. OOB)

# VLAN interface with no IP config
vlan1234_name  = "Multicast A Send"
vlan1234_device = "bond0"

# Vlan interface with IP configuration
vlan123_name     = "Multicast A send"    # the name of the vlan
vlan123_device   = "bond1"               # The device the vlan is associated with
vlan123_address  = "10.123.3.4"          # The IP of the interface (if required)
vlan123_netmask  = "255.255.255.0"       # the netmask of the interface (if required)
vlan123_gateway  = "10.123.3.1"          # the gateway aof the interface (if required)

The bond0 / vlan's and such can all be defined at different levels i.e. A group called CORE or BASE could contain:

bond0_interfaces = "eth0,eth3"
bond0_name = "OOB interface"
bond0_options = "mode=1 miimon=100"

I would then nest say "application x" inside CORE or BASE, which would inherit that bond setup, i could then add additional elements, OR override it if required. This would by standard, mean that all servers would get eth0,eth3 for bond0 and it would be a dedicated OOB, this would help standardise.

There is a snippet called network_setup, which is then included in the %post of the kickstart template

udev="/etc/udev/rules.d/70-persistent-net.rules"
[ -f $udev ] && rm -f $udev

%post --interpreter /usr/bin/python
<%= snippet "network_setup" %>

