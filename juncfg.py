import sys
import argparse
import getpass
from jnpr.junos.utils.config import Config
from jnpr.junos.op.vlan import VlanTable
from jnpr.junos.factory import loadyaml

devices_list = ('sw1.example.local', 'sw2.example.local', 'sw3.example.local', '192.168.1.14')


def get_vlan_dict(dev, strict=0):
    globals().update(loadyaml('templates/vlans.yaml'))
    vlans = VlanTable(dev)
    vlans.get()
    vlans_keys = vlans.keys()
    vlans_values = vlans.values()
    if strict == 0:
        return {k: v for k, v in zip(vlans_keys, vlans_values)}
    else:
        return {k: v for k, v in zip(vlans_keys, vlans_values) if k == parser.parse_args().vlan[0]}


def create_irb_and_policer(dev):
    import netaddr
    from lxml import etree
    policer_present = 0
    policer_config = dev.rpc.get_config(filter_xml=etree.XML(
        '<configuration><firewall><policer></policer></firewall></configuration>'),
        options={'source':'running'}, normalize=True)
    for node in policer_config.xpath(".//name"):
        if node.text == 'car-' + parser.parse_args().policer[0]:
            policer_present = 1

    ip = netaddr.IPNetwork(parser.parse_args().address[0])

    config_vars = {
        'vlan_id': parser.parse_args().vlan[0],
        'ip_address': '{}/{}'.format(ip.ip.__str__() if ip.ip.__str__() != ip.network.__str__() else ip[1].__str__(),
                                     ip.prefixlen.__str__()),
        'policer_precence': policer_present,
        'policer_name': parser.parse_args().policer[0],
        'description': parser.parse_args().descr[0]
    }
    config_file = "templates/junos-config-irb.conf"
    cu = Config(dev, mode='private')
    cu.load(template_path=config_file, template_vars=config_vars, replace=True, format='set', ignore_warning=True)
    cu.pdiff()
    apply_config(dev, cu)


def connect_to_device():
    from jnpr.junos import Device
    entered_username = input('Username: ')
    entered_password = getpass.getpass(prompt='Password: ')
    return Device(host=parser.parse_args().host[0], user=entered_username, password=entered_password, mode='telnet',
                  gather_facts=False).open()


def add_vlan_and_port(dev):
    from jnpr.junos.op.ethport import EthPortTable
    ports_dict = {}
    eths = EthPortTable(dev).get()
    for port in eths:
        ports_dict[port.name] = port.description

    uplinks = [k for k,v in ports_dict.items() if v != None and v.startswith('TRUNK')]
    config_vars = {
        'uplinks': uplinks,
        'client_port': [parser.parse_args().port[0]],
        'interfaces': uplinks + [parser.parse_args().port[0]],
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
            continue
        else:
            vlan_port_list.append(v[2][1].rstrip('*'))

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
            if isinstance(v[2][1], list):
                for i in v[2][1]:
                    if i.rstrip('*').find(parser.parse_args().port[0]):
                        vlan_numbers_list.append(k)

    config_vars = {
        'interface': parser.parse_args().port[0],
        'units': set(vlan_numbers_list)
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
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--host', '-h', nargs=1, choices=devices_list, help='This will be option One', required=True)
    parser.add_argument('--port', '-p', nargs=1, help='This will be option One', type=str, required=True)
    parser.add_argument('--vlan', '-v', nargs=1, help='This will be option One', required=True)
    parser.add_argument('--tag', '-t', action='store_const', const=1, default=0, help='This will be option One')
    parser.parse_args()
    dev = connect_to_device()
    add_vlan_and_port(dev)
elif len(sys.argv) == 6 and '--del' in sys.argv[-1]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--host', '-h', nargs=1, choices=devices_list, help='This will be option One', required=True)
    parser.add_argument('--vlan', '-v', nargs=1, help='This will be option One', required=True)
    parser.add_argument('--del', dest='bool_vlan', action='store_const', const=1, default=0,
                        help='This will be option One', required=True)
    parser.parse_args()
    dev = connect_to_device()
    del_vlan(dev)
elif len(sys.argv) == 6 and '--default' in sys.argv[-1]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--host', '-h', nargs=1, choices=devices_list, help='This will be option One', required=True)
    parser.add_argument('--port', '-p', nargs=1, help='This will be option One', type=str, required=True)
    parser.add_argument('--default', dest='bool_vlan', action='store_const', const=1, default=0,
                        help='This will be option One', required=True)
    parser.parse_args()
    dev = connect_to_device()
    set_port_default(dev)
elif len(sys.argv) == 11 and '-a' in sys.argv[5]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--host', '-h', nargs=1, choices=devices_list, help='This will be option One', required=True)
    parser.add_argument('--vlan', '-v', nargs=1, help='This will be option One', required=True)
    parser.add_argument('--address', '-a', nargs=1, help='This will be option One', required=True)
    parser.add_argument('--policer', '-p', nargs=1, help='This will be option One', required=True)
    parser.add_argument('--descr', nargs=1, help='This will be option One', required=True)
    parser.parse_args()
    dev = connect_to_device()
    create_irb_and_policer(dev)
else:
    help_var = '''
    Usage:
    configure port in access mode:
    {0} -h <host to connect> -p <port name on device> -v <vlan number to add>
    configure port in trunk mode:
    {0} -h <host to connect> -p <port name on device> -v <vlan number to add> -t
    delete vlan from device:
    {0} -h <host to connect> -v <vlan number to del> --del
    set port to default config:
    {0} -h <host to connect> -p <port name on device> --default
    create irb interface with ip address and policer (if not exist)
    {0} -h <host to connect> -v <vlan number to add> -a <address on irb int> -p <policer> --descr "<description>"
    '''.format(sys.argv[0])
    print(help_var)
    sys.exit()
