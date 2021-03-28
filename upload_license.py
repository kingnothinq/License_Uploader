import ifaddr
import re
import telnetlib
import time
import sys

from csv import reader
from icmplib import ping
from pathlib import Path
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import ThreadedFTPServer
from threading import Thread


def find_ip_devices(csv_path):
    """Open CSV file and find all IP-addresses in it."""

    ips_remote = []
    with open(csv_path, mode='r') as file:
        csv_reader = list(reader(file, delimiter=','))
        csv_reader = list(filter(lambda x: len(x) != 0, csv_reader))
    for line in csv_reader:
        if pattern_ip.search(str(line)):
            ips_remote.append(''.join(line))
    return ips_remote


def find_ip_local():
    """Find all the configured IP-addresses on this machine."""

    nics = ifaddr.get_adapters()
    ips_local = []
    for nic in nics:
        for ip in nic.ips:
            pattern_ip = re.compile(r'([0-9]{1,3}[\.]){3}[0-9]{1,3}')
            pattern_ip_dhcp = re.compile(r'169\.254\.[0-9]{1,3}\.[0-9]{1,3}')
            pattern_ip_lhost = re.compile(r'127\.([0-9]{1,3}[\.]){2}[0-9]{1,3}')
            if pattern_ip.search(str(ip.ip)) \
                    and not (pattern_ip_dhcp.search(str(ip.ip)) or pattern_ip_lhost.search(str(ip.ip))):
                ips_local.append(ip.ip)
    return ips_local


def find_licenses(lic_path):
    """Find all licenses in the selected folder.
     License requirements:
     - filename extension is *.dat
     - filename contains a serial number
     """

    lic_dict = {}
    lic_files = list(lic_path.glob('*.dat'))
    for lic_file in lic_files:
        lic_sn = re.search(r'(\d+)', str(lic_file))
        if lic_sn is not None:
            lic_sn = lic_sn.group(1)
            lic_dict[lic_sn] = lic_file
    return lic_dict


def start_ftp(ftp_folder):
    """Start FTP server."""

    authorizer = DummyAuthorizer()
    authorizer.add_anonymous(str(ftp_folder), perm='elradfmw')

    handler = FTPHandler
    handler.authorizer = authorizer

    server = ThreadedFTPServer(('0.0.0.0', 21), handler)
    server.max_cons = 100
    server.max_cons_per_ip = 2

    server.serve_forever()


def tn_connect(ip_remote, ftp_ip, ftp_local):
    """Connect via telnet"""

    if ftp_local:
        for ip_local in ips_local:
            host = ping(ip_remote, count=2, interval=0.1, source=ip_local)
            if host.is_alive:
                ftp_path = ip_local
                break
    else:
        ftp_path = f'{ftp_ip}/FTP'

    with telnetlib.Telnet(ip_remote, 23) as tn:
        tn.read_until(b'Login:')
        tn.write(b'admin\n\r')
        tn.read_until(b'Password:')
        tn.write(b'admin\n\r')
        tn.write(b'sys ver\n\r')
        time.sleep(3)
        result = tn.read_very_eager().decode('utf-8')
        pattern = re.compile(r'SN:(\d+)')
        if pattern.search(result):
            sn = pattern.search(result).group(1)
            if sn in licenses:
                ftp_file = licenses[sn].name
                ftp_command = f'license --install=ftp://anonymous:anonymous@{ftp_path}/{ftp_file}\n\r'
                tn.write(ftp_command.encode('utf-8'))
                time.sleep(3)
                tn.write(b'co sa; rest y\n\r')
                #result = tn.read_very_eager().decode('utf-8')
                #print(result)
            else:
                print(f'ERROR: The license not found.')


if __name__ == '__main__':
    pattern_ip = re.compile(r'([0-9]{1,3}[\.]){3}[0-9]{1,3}')
    pattern_ip_dhcp = re.compile(r'169\.254\.[0-9]{1,3}\.[0-9]{1,3}')
    pattern_ip_lhost = re.compile(r'127\.([0-9]{1,3}[\.]){2}[0-9]{1,3}')

    print(f'Please select a CSV file with IP-addresses.')
    csv_file = input(f'<Press ENTER to set default ("Script Folder\\Input\\ips.csv")>\r\n')
    if len(csv_file) == 0:
        csv_file = Path.cwd() / 'Input' / 'ips.csv'
        if csv_file.exists() is False:
            print(f'ERROR: "Script Folder\\Input\\ips.csv" does not exist.')
    else:
        while Path(csv_file).is_file() is False:
            csv_file = input(f'<This is not a file or it does not exist.>\r\n')
    ips_remote = find_ip_devices(csv_file)

    print(f'Please select a folder with licenses.')
    lic_folder = input(f'<Press ENTER to set default ("Script Folder\\Licenses")>\r\n')
    if len(lic_folder) == 0:
        lic_folder = Path.cwd() / 'Licenses'
        if lic_folder.exists() is False:
            print(f'ERROR: "Script Folder\\Licenses" does not exist.')
    else:
        while Path(lic_folder).is_dir() is False:
            lic_folder = input(f'<This is not a folder or it does not exist.>\r\n')
    licenses = find_licenses(lic_folder)

    print(f'Please enter the IP-address of the FTP server.')
    ip_ftp = input(f'<Press ENTER to launch a local FTP server.>\r\n')
    if len(ip_ftp) == 0:
        thread = Thread(target=start_ftp, args=(lic_folder, ))
        thread.start()
        thread_stop = False
        ips_local = find_ip_local()
        ftp_local = True
    else:
        while pattern_ip.search(ip_ftp) is None:
            ip_ftp = input(f'<This is the wrong IP-address.>\r\n')
        ftp_local = False

    for ip in ips_remote:
        tn_connect(ip, ip_ftp, ftp_local)

    print('Licenses have been uploaded.')
    sys.exit()