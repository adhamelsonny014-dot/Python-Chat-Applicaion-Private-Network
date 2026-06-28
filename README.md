# SecureChat — End-to-End Encrypted Two-Party Chat

A peer-to-peer chat application with end-to-end encryption using **Diffie-Hellman key exchange** and **AES-256-GCM**. Built with Python (Flask + Flask-SocketIO) and a browser-based UI, it requires no third-party messaging server — the two parties connect directly over TCP.

---

## Features

- **Diffie-Hellman Key Exchange** — 2048-bit MODP group; keys never leave the endpoints
- **AES-256-GCM Encryption** — authenticated encryption with unique random nonces per message
- **HKDF Key Derivation** — shared secret is derived via HKDF-SHA256 before use
- **Browser UI** — dark-themed chat interface served locally; no desktop client needed
- **Client/Server architecture** — one party runs `server.py`, the other runs `client.py`
- **Auto-retry** — client retries the connection up to 3 times on failure
- **Comprehensive test suite** — unit, integration, security, load, performance, and regression tests

---

## Project Structure

```
project enhanced/
├── server.py                  # Server-side Flask app (listens for connections)
├── client.py                  # Client-side Flask app (connects to server)
├── requirements.txt           # Python dependencies
├── Tutorial.txt               # Quick-start guide
├── client_server_architecture_overview.svg
├── static/
│   ├── script.js              # Frontend WebSocket logic
│   └── style.css              # UI styling
├── templates/
│   ├── index.html             # Main chat page
│   ├── server-setup.html      # Server configuration form
│   └── client-setup.html      # Client configuration form
└── tests/
    ├── crypto_helpers.py           # Shared crypto primitives for tests
    ├── test_unit_crypto.py         # Unit tests — DH, encrypt/decrypt
    ├── test_unit_routes.py         # Unit tests — Flask routes
    ├── test_integration_handshake.py  # Integration — full DH handshake
    ├── test_security.py            # Security — replay, tampering, key isolation
    ├── test_load.py                # Load — concurrent sessions
    ├── test_performance.py         # Performance — throughput benchmarks
    └── test_regression.py          # Regression — edge cases
```

---

## How It Works

```
Server                              Client
  |                                   |
  |── DH Public Key + PRIME + G ─────>|
  |<─────────────────── DH Public Key─|
  |                                   |
  |  Both sides compute shared secret via pow(peer_pub, priv, PRIME)
  |  HKDF-SHA256 derives a 32-byte AES key from shared secret
  |                                   |
  |<──── AES-GCM encrypted message ──>|
  |      (IV + ciphertext + GCM tag)  |
```

Each message is prefixed with a 4-byte length header for reliable framing over TCP.

---

## Prerequisites

- Python 3.8+
- Two terminal windows (or two machines on the same network)

---

## Installation

```bash
pip install -r requirements.txt
```

**Dependencies:** `flask`, `flask-socketio`, `pycryptodome`, `termcolor`, `colorama`

---

## Usage

### Step 1 — Start the Server

```bash
python server.py
```

Open the server UI at: `http://localhost:5000`

Enter your name, the IP address of the machine, and a port (e.g. `9000`), then click **Connect**.

### Step 2 — Start the Client

```bash
python client.py
```

Open the client UI at: `http://localhost:5001`

Enter your name, the **server's IP address**, and the **same port**, then click **Connect**.

> The server must be started and waiting before the client connects.


---

## Security Notes

- The 2048-bit MODP prime used is the RFC 3526 Group 14 prime — suitable for academic and demonstration use.
- AES-GCM nonces are randomly generated per message, making ciphertext non-deterministic.
- The GCM authentication tag ensures any tampering with the ciphertext or nonce is detected and rejected.
- The application does not implement sequence numbers, so replay detection is the responsibility of the application layer.
- For production use, consider TLS for the initial key exchange and certificate-based authentication.

---

## Architecture Diagram

See `client_server_architecture_overview.svg` in the project root for a visual overview of the client-server flow.

---

## License

This project was developed as an academic assignment for CS322 (Network Fundameltals) Course.
