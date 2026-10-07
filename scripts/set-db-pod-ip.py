#!/usr/bin/env python3
"""Renseigne l'IP du Pod db dans le manifeste API (sans appliquer de ressource)."""
import argparse
import ipaddress
from pathlib import Path
import re
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--context', required=True, help='Contexte Kubernetes explicite')
args = parser.parse_args()
address = subprocess.check_output(
    ['kubectl', '--context', args.context, '-n', 'taskflow', 'get', 'pod', 'db',
     '-o', 'jsonpath={.status.podIP}'], text=True,
).strip()
ipaddress.ip_address(address)
path = Path(__file__).resolve().parents[1] / 'k8s/pods/api.yaml'
content, count = re.subn(r'value: "[^"\n]+" # DB_POD_IP',
                         f'value: "{address}" # DB_POD_IP', path.read_text())
if count != 1:
    raise SystemExit('Marqueur DB_POD_IP absent ou ambigu : aucun fichier modifié')
path.write_text(content)
print(f'DB_HOST={address} dans {path}')
