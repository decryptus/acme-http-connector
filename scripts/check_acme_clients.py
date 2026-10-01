#!/usr/bin/env python3
# Copyright 2026 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise installed clients against a disposable Pebble CA and receiving API.

Nothing listens outside loopback. Reserved .test names resolve through Pebble's
own test DNS service. Private keys and client state stay in a temporary directory.
"""
import argparse
from collections import Counter
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import os
from pathlib import Path
import shutil
import shlex
import signal
import socket
import subprocess
import tempfile
import threading
import time

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
import requests
import yaml


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def free_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def tls_fixture(directory):
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Disposable ACME test CA')])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost'),
                x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), critical=False)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .sign(key, hashes.SHA256()))
    cert_path, key_path = directory / 'tls.pem', directory / 'tls.key'
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    key_path.chmod(0o600)
    return cert_path, key_path


class Receiver:
    def __init__(self):
        self.challenges = {}
        self.deployments = []
        self.events = Counter()
        self.reject_validation = False

    def handler(self):
        state = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def reply(self, status, data=b''):
                self.send_response(status)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_PUT(self):
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                state.challenges[self.path] = payload
                state.events['publish'] += 1
                self.reply(200)

            def do_GET(self):
                state.events['validation_read'] += 1
                value = state.challenges.get(self.path)
                if state.reject_validation or value is None:
                    self.reply(404)
                else:
                    self.reply(200, value.encode())

            def do_DELETE(self):
                state.challenges.pop(self.path, None)
                state.events['cleanup'] += 1
                self.reply(200)

            def do_POST(self):
                require(self.path == '/certificates', 'Unexpected deployment path')
                state.deployments.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                state.events['deploy'] += 1
                self.reply(200)

        return Handler


def stop_process(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def start_process(stack, command, env, log_path):
    log = stack.enter_context(log_path.open('w+'))
    process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
    stack.callback(stop_process, process)
    return process


def wait_ready(url, verify, processes):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        require(all(process.poll() is None for process in processes), 'Fixture exited before readiness')
        try:
            if requests.get(url, verify=verify, timeout=1).ok:
                return
        except requests.RequestException:
            pass
        time.sleep(0.1)
    raise RuntimeError('ACME fixture readiness timed out')


def run(command, env, label, expected_success=True):
    with subprocess.Popen(command, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, start_new_session=True) as process:
        try:
            output, _ = process.communicate(timeout=120)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise RuntimeError(label + ': timed out') from None
    success = process.returncode == 0
    if success != expected_success:
        # All fixtures are disposable; clients never print PEM private keys.
        raise RuntimeError(label + '\n' + output[-6000:])


def check_deployment(payload, domains):
    cert = x509.load_pem_x509_certificate(payload['cert'].encode())
    key = serialization.load_pem_private_key(payload['key'].encode(), password=None)
    chain = x509.load_pem_x509_certificates(payload['chain'].encode())
    require(chain, 'Missing certificate chain')
    cert.verify_directly_issued_by(chain[0])
    public = lambda value: value.public_bytes(serialization.Encoding.DER,
                                              serialization.PublicFormat.SubjectPublicKeyInfo)
    require(public(cert.public_key()) == public(key.public_key()), 'Certificate/key mismatch')
    names = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    require(set(names.get_values_for_type(x509.DNSName)) == set(domains), 'Wrong certificate SANs')
    require(payload['domain'] in domains, 'Wrong deployment domain')
    return cert.serial_number


def exercise(args, directory, stack):
    receiver = Receiver()
    server = ThreadingHTTPServer(('127.0.0.1', 0), receiver.handler())
    stack.callback(server.server_close)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    stack.callback(worker.join, 5)
    stack.callback(server.shutdown)
    api = 'http://127.0.0.1:%d' % server.server_port
    config_path = directory / 'connector.yml'
    config_path.write_text(yaml.safe_dump({
        'perform': {'uri': api}, 'cleanup': {'uri': api},
        'deploy': {'uri': api, 'path': '/certificates'}}))
    tls_cert, tls_key = tls_fixture(directory)
    acme_port, management_port, dns_port, dns_management = [free_port() for _ in range(4)]
    pebble_config = directory / 'pebble.json'
    pebble_config.write_text(json.dumps({'pebble': {
        'listenAddress': '127.0.0.1:%d' % acme_port,
        'managementListenAddress': '127.0.0.1:%d' % management_port,
        'certificate': str(tls_cert), 'privateKey': str(tls_key),
        'httpPort': server.server_port, 'tlsPort': free_port(),
        'retryAfter': {'authz': 1, 'order': 1}}}))
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('PEBBLE_', 'CBT_HTTPREQ_', 'ACME_HTTP_CONNECTOR_'))}
    env.update(PEBBLE_VA_NOSLEEP='1', PEBBLE_AUTHZREUSE='0', PEBBLE_WFE_NONCEREJECT='0',
               REQUESTS_CA_BUNDLE=str(tls_cert), CURL_CA_BUNDLE=str(tls_cert),
               ACME_HTTP_CONNECTOR_CONFIG=str(config_path), NO_PROXY='localhost,127.0.0.1')
    dns = start_process(stack, [str(args.challtestsrv), '-dnsserver', '127.0.0.1:%d' % dns_port,
        '-defaultIPv6', '', '-http01', '', '-https01', '', '-tlsalpn01', '', '-doh', '',
        '-management', '127.0.0.1:%d' % dns_management], env, directory / 'dns.log')
    ca = start_process(stack, [str(args.pebble), '-config', str(pebble_config),
        '-dnsserver', '127.0.0.1:%d' % dns_port], env, directory / 'pebble.log')
    directory_url = 'https://localhost:%d/dir' % acme_port
    wait_ready(directory_url, str(tls_cert), [dns, ca])
    domains = ['one.example.test', 'two.example.test']
    certbot_base = [shutil.which('certbot'), '--non-interactive', '--agree-tos',
        '--register-unsafely-without-email', '--server', directory_url,
        '--config-dir', str(directory / 'certbot/config'), '--work-dir', str(directory / 'certbot/work'),
        '--logs-dir', str(directory / 'certbot/logs')]
    certbot_issue = certbot_base + ['run', '--authenticator', 'certbot-httpreq:auth',
        '--installer', 'certbot-httpreq:installer', '--certbot-httpreq:auth-config', str(config_path),
        '--certbot-httpreq:installer-config', str(config_path), '--cert-name', 'connector-test',
        '-d', ','.join(domains)]
    dehydrated_dir = directory / 'dehydrated'
    dehydrated_dir.mkdir()
    (dehydrated_dir / 'challenges').mkdir()
    (dehydrated_dir / 'domains.txt').write_text(' '.join(domains) + '\n')
    dehydrated_config = dehydrated_dir / 'config'
    # Shell configuration is read by Dehydrated. Temporary paths and discovered
    # executable paths are quoted with shlex, never evaluated as our own shell command.
    settings = {'CA': directory_url, 'BASEDIR': str(dehydrated_dir),
        'WELLKNOWN': str(dehydrated_dir / 'challenges'),
        'DOMAINS_TXT': str(dehydrated_dir / 'domains.txt'), 'CHALLENGETYPE': 'http-01',
        'HOOK': shutil.which('acme-http-dehydrated'), 'HOOK_CHAIN': 'yes', 'KEY_ALGO': 'prime256v1'}
    dehydrated_config.write_text('\n'.join(key + '=' + shlex.quote(value) for key, value in settings.items()) + '\n')
    dehydrated_base = ['bash', str(args.dehydrated), '--config', str(dehydrated_config)]
    run(dehydrated_base + ['--register', '--accept-terms'], env, 'Dehydrated registration')
    results = []
    for client, issue, renew in (
            ('Certbot', certbot_issue, certbot_base + ['renew', '--no-random-sleep-on-renew', '--force-renewal', '--cert-name', 'connector-test']),
            ('Dehydrated', dehydrated_base + ['--cron'], dehydrated_base + ['--cron', '--force'])):
        serials = []
        for operation, command in [('issue', issue), ('renew', renew)]:
            before = receiver.events.copy()
            offset = len(receiver.deployments)
            run(command, env, client + ' ' + operation)
            delta = receiver.events - before
            require(delta['publish'] >= len(domains), client + ': missing fresh challenges')
            require(delta['validation_read'] >= len(domains), client + ': missing HTTP-01 reads')
            require(delta['cleanup'] == delta['publish'] and not receiver.challenges,
                    client + ': challenges not cleaned')
            deployments = receiver.deployments[offset:]
            require(deployments, client + ': no certificate deployed')
            current_serials = {check_deployment(payload, domains) for payload in deployments}
            require(len(current_serials) == 1, client + ': inconsistent deployed certificates')
            serials.append(current_serials.pop())
            print(client + ' ' + operation + ': OK ' + json.dumps(dict(delta)), flush=True)
            results.append({'client': client, 'operation': operation, 'events': dict(delta)})
        require(serials[0] != serials[1], client + ': renewal reused old certificate')
        # No fresh validation is bypassed: bad HTTP-01 must prevent deployment.
        receiver.reject_validation = True
        before = receiver.events.copy()
        run(renew, env, client + ' invalid challenge', expected_success=False)
        delta = receiver.events - before
        require(delta['publish'] > 0 and delta['validation_read'] > 0,
                client + ': rejection did not exercise HTTP-01')
        require(delta['deploy'] == 0, client + ': deployed despite invalid challenge')
        require(not receiver.challenges, client + ': failed challenge not cleaned')
        receiver.reject_validation = False
        print(client + ' invalid challenge: rejected, no deployment, cleaned', flush=True)
        results.append({'client': client, 'operation': 'invalid-challenge', 'events': dict(delta)})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pebble', type=Path, required=True)
    parser.add_argument('--challtestsrv', type=Path, required=True)
    parser.add_argument('--dehydrated', type=Path, required=True)
    args = parser.parse_args()
    for name in ('pebble', 'challtestsrv', 'dehydrated'):
        setattr(args, name, getattr(args, name).resolve(strict=True))
    for executable in ('certbot', 'acme-http-dehydrated', 'bash', 'curl', 'openssl'):
        require(shutil.which(executable), 'Missing executable: ' + executable)
    with tempfile.TemporaryDirectory(prefix='acme-clients-') as temporary, ExitStack() as stack:
        exercise(args, Path(temporary), stack)
    print('PASS: both clients issued, renewed, deployed and rejected invalid HTTP-01 challenges.')


if __name__ == '__main__':
    main()
