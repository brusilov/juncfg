import sys
import argparse
import getpass
from jnpr.junos.factory import loadyaml
from jnpr.junos import Device
from jnpr.junos.utils.config import Config
from jnpr.junos.op.ethport import EthPortTable
from jnpr.junos.op.vlan import VlanTable


devices_list = ('sw23.msk6.ip', 'sw22.msk6.ip', 'sw16.msk4.ip', '192.168.1.14')


def get_vlan_dict(dev, strict=0):
    globals().update(loadyaml('templates/vlans.yaml'))
    vlans = VlanTable(dev)
    vlans.get()
    vlans_keys = vlans.keys()
    vlans_values = vlans.values()
    if strict == 0:
        return {k: v for k, v in zip(vlans_keys, vlans_values)}
    else:
        return {k: v for k, v in zip(vlans_keys, vlans_values) if k == parser.parse_args().vlan[0] }


def get_uplinks_dict(dev):
    ports_dict = {}
    eths = EthPortTable(dev).get()
    for port in eths:
        if port.description != None and port.description.startswith('TRUNK'):
            ports_dict[port.name] = port.description
    return ports_dict


def connect_to_device():
    entered_username = input('Username: ')
    entered_password = getpass.getpass(prompt='Password: ')
    return Device(host=parser.parse_args().dev[0], user=entered_username, password=entered_password, mode='telnet', gather_facts=False).open()


def add_vlan_and_port(dev):
    ports_dict = get_uplinks_dict(dev)
    ports_list = list(ports_dict.keys())
    all_interfaces = ports_list + ['xe-0/0/{0}'.format(parser.parse_args().port[0])]
    config_vars = {
        'uplinks': ports_list,
        'client_port': ['xe-0/0/{0}'.format(parser.parse_args().port[0])],
        'interfaces': all_interfaces,
        'vlan': parser.parse_args().vlan[0],
        'trunk_bool': parser.parse_args().tag
    }

    config_file = "templates/junos-config-add-vlans.conf"
    cu = Config(dev, mode='private')
    cu.load(template_path=config_file, template_vars=config_vars, replace=True)
    cu.pdiff()
    apply_config(dev, cu)


def del_vlan(dev):
    vlan_port_list = []
    vlan_id_dict = get_vlan_dict(dev,strict=1)
    for k, v in vlan_id_dict.items():
        if v[2][1] == 'l2ng-l2rtb-vlan-member-interface':
            break
        for i in v[2][1]:
            vlan_port_list.append(i.rstrip('*'))
    config_vars = {
        'interfaces': vlan_port_list,
        'vlan': parser.parse_args().vlan[0]
    }
    config_file = "templates/junos-config-delete-vlans.conf"
    cu = Config(dev, mode='private')
    cu.load(template_path=config_file, template_vars=config_vars, replace=True, format='set', ignore_warning=True)
    cu.pdiff()
    apply_config(dev, cu)


def set_port_default(dev):
    vlan_numbers_list = []
    vlan_id_dict = get_vlan_dict(dev)
    for k, v in vlan_id_dict.items():
        if v[2][1] == 'l2ng-l2rtb-vlan-member-interface':
            continue
        else:
            vlan_numbers_list.append(k)
    config_vars = {
        'interface': 'xe-0/0/{0}'.format(parser.parse_args().port[0]),
        'units': vlan_numbers_list
    }
    config_file = "templates/junos-config-port-default.conf"
    cu = Config(dev, mode='private')
    cu.load(template_path=config_file, template_vars=config_vars, replace=True, format='set', ignore_warning=True)
    cu.pdiff()
    apply_config(dev, cu)


def apply_config(dev, cu):
    confirm_val = input("Config correct? [y/n] ")
    if confirm_val == 'y':
        cu.commit()
        dev.close()
        print('Commit completed!')
        sys.exit()
    elif confirm_val == 'n':
        cu.rollback(0)
        dev.close()
        print('Aborted.')
        sys.exit()
    else:
        cu.rollback(0)
        dev.close()
        print('Bye.')
        sys.exit()


if len(sys.argv) in [7,8]:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dev', '-d', nargs=1, choices=devices_list, help='This will be option One', required=True)
    parser.add_argument('--port', '-p', nargs=1, help='This will be option One', type=int, required=True)
    parser.add_argument('--vlan', '-v', nargs=1, help='This will be option One', required=True)
    parser.add_argument('--tag', '-t', action='store_const', const=1, default=0, help='This will be option One')
    parser.parse_args()
    dev = connect_to_device()
    add_vlan_and_port(dev)
elif len(sys.argv) == 6 and sys.argv[-1] == '--del':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dev', '-d', nargs=1, choices=devices_list, help='This will be option One', required=True)
    parser.add_argument('--vlan', '-v', nargs=1, help='This will be option One', required=True)
    parser.add_argument('--del', dest='bool_vlan', action='store_const', const=1, default=0, help='This will be option One', required=True)
    parser.parse_args()
    dev = connect_to_device()
    del_vlan(dev)
elif len(sys.argv) == 6 and sys.argv[-1] == '--default':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dev', '-d', nargs=1, choices=devices_list, help='This will be option One', required=True)
    parser.add_argument('--port', '-p', nargs=1, help='This will be option One', type=int, required=True)
    parser.add_argument('--default', dest='bool_vlan', action='store_const', const=1, default=0, help='This will be option One', required=True)
    parser.parse_args()
    dev = connect_to_device()
    set_port_default(dev)
else:
    help_var = '''
    Usage:
    {0} -d <device to connect> -p <port number on device> -v <vlan number to add> [-t]
    {0} -d <device to connect> -v <vlan number to del> --del
    {0} -d <device to connect> -p <port number on device> --default
    '''.format(sys.argv[0])
    print(help_var)
    sys.exit()

'''
dev = Device(host=device, user=username, password=passwd, mode='telnet', gather_facts=False)
json_config = dev.rpc.get_config(options={'format': 'json'})

def get_vlan_list(json_config):
    vlan_list = []
    for obj1 in json_config['configuration']:
        for obj2 in obj1['vlans']:
            for obj3 in obj2['vlan']:
                for obj4 in obj3['vlan-id']:
                    vlan_list.append(int(obj4['data']))
    return vlan_list

def get_interfaces_uplinks(json_config):
    interface_descr_dict = {}
    interface_uplink_list = []
    for obj1 in json_config['configuration']:
        for obj2 in obj1['interfaces']:
            for obj3 in obj2['interface']:
                if 'description' not in obj3:
                    continue
                else:
                    for obj4 in obj3['description']:
                        #print(obj3['name']['data'], obj4['data'])
                        interface_descr_dict[obj3['name']['data']] = obj4['data']
    for k, v in interface_descr_dict.items():
        if v.startswith('TRUNK'):
            interface_uplink_list.append(k)
    return interface_uplink_list
======================================
interfaces {
{% for int in interfaces %}
    {{ int.physical_interface }} {
        description {{ int.description }};
        unit 0 {
{% if int.ip_address is defined %}
            family inet {
                address {{ int.ip_address }};
        }
{% else %}
            family inet;
{% endif %}
        }
    } {% endfor %}
}

config_vars = {
          'interfaces' : [
             { 'physical_interface' : 'ge-0/0/2', 'description' : 'to_VMX02', 'ip_address' : '10.10.10.1/24' } ,
             { 'physical_interface' : 'ge-0/0/0', 'description' : 'to_VMX03', 'ip_address' : '10.10.30.1/24' }
           ]
}
outputText = template.render( config_vars )
http://networktocode.com/labs/tutorials/automating-juniper-vmx-bgp-configuration-with-pyez/
==========================================
r = dev.rpc.get_interface_information(terse=True)

# also you can get rid of \n from your code using normalize-space
interface = r.xpath('physical-interface[normalize-space(name)="ge-1/1/0"]/logical-interface[normalize-space(name)="ge-1/1/0.2"]')
address = interface[0].xpath("address-family[normalize-space(address-family-name)='inet']/interface-address/ifa-local")
print address[0].text
'''
