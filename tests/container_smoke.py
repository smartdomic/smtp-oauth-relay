"""Offline image smoke test; run with --network none and writable /tmp tmpfs."""

import os
import smtplib
import ssl
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

assert os.getuid() == 10001
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(hours=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), True)
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = root / "cert.pem", root / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    key_path.chmod(0o600)
    env = dict(
        os.environ,
        TLS_SOURCE="file",
        REQUIRE_TLS="true",
        TLS_CERT_FILEPATH=str(cert_path),
        TLS_KEY_FILEPATH=str(key_path),
    )
    process = subprocess.Popen([sys.executable, "-B", "main.py"], env=env)
    try:
        deadline = time.monotonic() + 10
        while True:
            try:
                client = smtplib.SMTP("localhost", 8025, timeout=3)
                break
            except OSError:
                if process.poll() is not None or time.monotonic() >= deadline:
                    raise
                time.sleep(0.1)
        with client:
            client.ehlo()
            assert "starttls" in client.esmtp_features
            assert "auth" not in client.esmtp_features
            assert client.mail("sender@example.invalid")[0] == 530
            client.starttls(context=ssl.create_default_context(cafile=str(cert_path)))
            client.ehlo()
            assert "auth" in client.esmtp_features
            assert client.mail("sender@example.invalid")[0] == 530
        print(
            "PASS: non-root, verified STARTTLS, TLS required, AUTH required; no mail sent"
        )
    finally:
        process.terminate()
        process.wait(timeout=5)
