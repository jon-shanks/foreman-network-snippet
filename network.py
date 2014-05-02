import os, re, glob, socket, StringIO
import yaml
import pycurl

def get_nodeyaml(puppet_node_url):
   output = StringIO.StringIO()
   conn = pycurl.Curl()
   conn.setopt(conn.URL, puppet_node_url)
   conn.setopt(conn.WRITEFUNCTION, output.write)
   conn.setopt(conn.SSL_VERIFYPEER, 0)
   conn.setopt(conn.SSL_VERIFYHOST, 0)
   conn.setopt(conn.HTTPHEADER, ["Accept: yaml"])
   conn.perform()
   return yaml.load(re.sub('.*\!ruby\/.*', '', output.getvalue()))

def valid_address(ip):
   try:
      socket.inet_aton(ip)
      return True
   except:
      return False

def check_declared(**kwargs):
   for k,v in kwargs.iteritems():
      device = k.split('_')[0]
      try:
         kwargs['%s_name' % device]
      except KeyError:
         raise Exception("%s must have %s_name defined" % (device,device))
      if k.startswith('bond'):
         try:
            kwargs['%s_interfaces' % device]
         except KeyError:
            raise Exception("%s has no %s_interfaces defined" % (device,device))
         try:
            kwargs['%s_options' % device]
         except KeyError:
            raise Exception("%s has no bonding options, please define" % device)
      if k.startswith('vlan'):
         try:
            kwargs['%s_device' % device]
         except KeyError:
            raise Exception("%s has no %s_device defined" % (device,device))
      if k.endswith('address'):
         try:
            kwargs['%s_netmask' % device]
         except KeyError:
            raise Exception("%s has no %s_netmask defined" % (device,device))
      if k.endswith('netmask') or k.endswith('gateway'):
         try:
            kwargs['%s_address' % device]
         except KeyError:
            raise Exception("%s has no gateway or netmask defined" % (device,device))

def check_ints(**kwargs):
   check_declared(**kwargs)
   check_int = []
   for k,v in kwargs.iteritems():
      if re.match(r'.+_address$', k):
         if valid_address(v):
            if re.match(r'eth\d+_address', k):
               check_int.append(k.split('_')[0])
         else:
            raise Exception("%s is not a valid IP address" % v)
   for k,v in kwargs.iteritems():
      if k.endswith('interfaces'):
         for i in check_int:
            if i in v:
               raise Exception("%s is in %s, but you have configured %s_address with %s" % (i,k,i,kwargs['%s_address' % i]))

def grab_networkdata(**kwargs):
   interfaces = {}
   int_match = re.compile(r'^(eth|bond|vlan).+', re.I)
   if 'parameters' in kwargs:
      for k,v in kwargs['parameters'].iteritems():
         if int_match.match(k):
            interfaces[k.lower()] = v.lower()
   return interfaces

def get_int_bus():
   """Fetch all interfaces and return the busid to int"""
   ifbus = {}
   for i in glob.glob('/sys/class/net/eth*'):
      ifbus[i] = os.path.basename(os.readlink('%s/device' % i))
   return ifbus

def return_mac_on_bus(busorder):
   """Return the eth to mac dict based sorted on the busid passed"""
   ifmacs = {}
   count = 0
   for k in sorted(busorder, key=busorder.get):
      ifmacs['eth%s' % count] = open('%s/address' % k, 'r').read().rstrip().upper()
      count = count + 1
   return ifmacs

def write_ints(int, name, cfg):
   path = '/etc/sysconfig/network-scripts'
   ifcfg = "%s/ifcfg-%s" % (path, int)
   fh = open(ifcfg, 'w')
   fh.write("#\n# %s\n" % name)
   fh.write("DEVICE=%s\n" % int)
   for k,v in cfg.iteritems():
      fh.write("%s=%s\n" % (k,v))
   fh.close()

def reset_cfg():
   cfg = { 'ONBOOT': 'yes',
           'BOOTPROTO': 'none',
           'USERCTL': 'no',
           'NM_CONTROLLED': 'no' }
   return cfg

def modprobe(device, osver):
   if osver == "6":
      fh = open('/etc/modprobe.d/nyx.conf', 'a')
   else:
      fh = open('/etc/modprobe.conf', 'a')
   fh.write("\nalias %s bonding" % device)
   fh.close()

def create_cfg(netdata, int_order, osver):
   """Create the interface configuration"""
   check_ints(**netdata)
   for device in set([k.split('_')[0] for k in netdata.keys()]):
      cfg = reset_cfg()
      name = netdata['%s_name' % device]
      try:
         cfg['IPADDR'] = netdata['%s_address' % device]
         cfg['NETMASK'] = netdata['%s_netmask' % device]
         cfg['GATEWAY'] = netdata['%s_gateway' % device]
      except:
         pass

      if device.startswith('eth'):
         cfg['HWADDR'] = int_order[device]

      if device.startswith('bond'):
         cfg['BONDING_OPTS'] = "\"%s\"" % netdata['%s_options' % device]
         write_ints(device, name, cfg)
         modprobe(device, osver)
         for int in [v.strip() for v in netdata['%s_interfaces' % device].split(',')]:
            try:
               cfg = reset_cfg()
               intname = "%s is in %s, %s is configured for %s" % (int, device, device, name)
               cfg['HWADDR'] = int_order[int]
               cfg['SLAVE'] = "yes"
               cfg['MASTER'] = device
               write_ints(int, intname, cfg)
            except KeyError:
               raise Exception("%s is defined but system doesn't have a %s" % (int,int))
         continue

      if device.startswith('vlan'):
         device = "%s.%s" % (netdata['%s_device' % device], device)
         cfg['VLAN'] = "yes"
      write_ints(device, name, cfg)

if __name__ == '__main__':
   """The main call for the execution of the python script"""
   puppet_host = '<%= @host.puppetmaster -%>'
   puppet_port = '8140'
   environment = '<%= @host.environment -%>'
   host = '<%= @host.fqdn -%>'
   osver = '<%= @osver -%>'
   puppet_node_url = 'https://%s:%s/%s/node/%s' % (puppet_host, puppet_port, environment, host)
   
   netdata = grab_networkdata(**get_nodeyaml(puppet_node_url))
   
   if not netdata:
      raise Exception("No network data has been defined for the node\n \
          Please at least define eth0_address, eth0_netmask, eth0_gateway at the node level on Foreman")
   else:
      int_ord = return_mac_on_bus(get_int_bus())
      create_cfg(netdata, int_ord, osver)
