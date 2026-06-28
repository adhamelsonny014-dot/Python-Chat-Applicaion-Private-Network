from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from flask_socketio import SocketIO, emit
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import HKDF
from Crypto.Hash import SHA256
from Crypto.Random import get_random_bytes
import socket as py_socket
import platform
from termcolor import colored
from colorama import init
from datetime import datetime
import logging
from threading import Thread
import time
import os

# Initialize
init()
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
app.secret_key = os.urandom(24)
socketio = SocketIO(app, async_mode='threading')

# Global storage for active connections
active_connections = {}

# Constants
PRIME = 0xFFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F83655D23DCA3AD961C62F356208552BB9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3BE39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF6955817183995497CEA956AE515D2261898FA051015728E5A8AACAA68FFFFFFFFFFFFFFFF
GENERATOR = 2

def generate_dh_key():
    private_key = int.from_bytes(get_random_bytes(32), byteorder='big') % PRIME
    public_key = pow(GENERATOR, private_key, PRIME)
    return private_key, public_key

def derive_shared_key(private_key, peer_public_key):
    shared_secret = pow(peer_public_key, private_key, PRIME)
    return HKDF(shared_secret.to_bytes(256, byteorder='big'), 32, b'', SHA256)

def encrypt_message(key, message):
    iv = get_random_bytes(16)
    cipher = AES.new(key, AES.MODE_GCM, iv)
    ciphertext, tag = cipher.encrypt_and_digest(message.encode())
    return iv + ciphertext + tag

def decrypt_message(key, encrypted):
    iv = encrypted[:16]
    ciphertext = encrypted[16:-16]
    tag = encrypted[-16:]
    cipher = AES.new(key, AES.MODE_GCM, iv)
    return cipher.decrypt_and_verify(ciphertext, tag).decode()

def listen_for_raw_messages(sock, socketio_sid):
    buffer = b''
    while True:
        try:
            # Read message length (4 bytes)
            while len(buffer) < 4:
                data = sock.recv(4 - len(buffer))
                if not data:
                    raise ConnectionError("Connection closed")
                buffer += data
            
            msg_len = int.from_bytes(buffer[:4], byteorder='big')
            buffer = buffer[4:]
            
            # Read the message content
            while len(buffer) < msg_len:
                data = sock.recv(min(4096, msg_len - len(buffer)))
                if not data:
                    raise ConnectionError("Connection closed")
                buffer += data
            
            encrypted_msg = buffer[:msg_len]
            buffer = buffer[msg_len:]
            
            conn_info = active_connections.get(socketio_sid)
            if not conn_info or not conn_info.get('shared_key'):
                logging.error("No shared key available")
                break
                
            decrypted = decrypt_message(conn_info['shared_key'], encrypted_msg)
            
            socketio.emit('message', {
                'text': decrypted,
                'sender': {'name': 'Server', 'avatar': 'https://i.pravatar.cc/150?img=8'},
                'timestamp': datetime.now().isoformat()
            }, room=socketio_sid)
            
        except ConnectionError as e:
            logging.error(f"Connection error: {e}")
            break
        except Exception as e:
            logging.error(f"Message processing error: {e}")
            break
    
    # Clean up
    cleanup_connection(socketio_sid)

def cleanup_connection(socketio_sid):
    if socketio_sid in active_connections:
        sock = active_connections[socketio_sid].get('sock')
        if sock:
            try:
                sock.close()
            except:
                pass
        del active_connections[socketio_sid]
    
    socketio.emit('status-update', {
        'text': 'Disconnected',
        'class': 'offline'
    }, room=socketio_sid)
    
    socketio.emit('user-disconnected', {
        'name': 'Server'
    }, room=socketio_sid)

def socket_client_thread(ip, port, name, socketio_sid):
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        sock = None
        try:
            sock = py_socket.socket(py_socket.AF_INET, py_socket.SOCK_STREAM)
            if platform.system() == 'Windows':
                sock.setsockopt(py_socket.SOL_SOCKET, py_socket.SO_REUSEADDR, 1)
            
            sock.settimeout(15)
            
            logging.info(colored(f"[*] Connecting to {ip}:{port} (attempt {attempt + 1})", "yellow"))
            sock.connect((ip, port))
            logging.info(colored(f"[+] Connected to {ip}:{port}", "green"))
            
            # DH Key Exchange
            # Receive server params
            server_data = b''
            while True:
                chunk = sock.recv(1024)
                if not chunk:
                    raise ValueError("Connection closed during key exchange")
                server_data += chunk
                if b'\n' in chunk:
                    break
            
            server_params = server_data.decode().strip().split(',')
            if len(server_params) != 3:
                raise ValueError("Invalid DH parameters format")
            
            server_public_key = int(server_params[0])
            prime = int(server_params[1])
            generator = int(server_params[2])
            
            private_key, public_key = generate_dh_key()
            sock.sendall(f"{public_key}\n".encode())
            
            shared_key = derive_shared_key(private_key, server_public_key)
            
            # Store connection
            active_connections[socketio_sid] = {
                'sock': sock,
                'shared_key': shared_key
            }
            
            logging.info(colored("[+] Key exchange completed", "green"))
            socketio.emit('status-update', {
                'text': 'Connected',
                'class': 'online'
            }, room=socketio_sid)
            
            socketio.emit('user-connected', {
                'name': 'Server'
            }, room=socketio_sid)
            
            # Start message listener
            Thread(target=listen_for_raw_messages,
                  args=(sock, socketio_sid),
                  daemon=True).start()
            
            # Reset timeout for normal operation
            sock.settimeout(None)
            return
            
        except py_socket.timeout:
            logging.error(colored(f"[!] Connection timeout (attempt {attempt + 1})", "red"))
            if sock:
                sock.close()
            if attempt == max_retries - 1:
                socketio.emit('status-update', {
                    'text': 'Connection failed',
                    'class': 'offline'
                }, room=socketio_sid)
            time.sleep(retry_delay)
            
        except Exception as e:
            logging.error(colored(f"[!] Connection error: {str(e)}", "red"))
            if sock:
                try:
                    sock.close()
                except:
                    pass
            if attempt == max_retries - 1:
                socketio.emit('status-update', {
                    'text': 'Connection failed',
                    'class': 'offline'
                }, room=socketio_sid)
            time.sleep(retry_delay)
    
    # If we get here, all retries failed
    socketio.emit('status-update', {
        'text': 'Connection failed',
        'class': 'offline'
    }, room=socketio_sid)

@app.route('/')
def index():
    if 'client_data' not in session:
        return redirect(url_for('client_setup'))
    return render_template('index.html')

@app.route('/client-setup', methods=['GET', 'POST'])
def client_setup():
    if request.method == 'POST':
        session['client_data'] = {
            'name': request.form['name'],
            'ip': request.form['ip'],
            'port': int(request.form['port'])
        }
        return redirect(url_for('index'))
    return render_template('client-setup.html')

@app.route('/get-user-data')
def get_user_data():
    if 'client_data' in session:
        return jsonify({
            'user': {
                'name': session['client_data']['name'],
                'avatar': 'https://i.pravatar.cc/150?img=5'
            },
            'otherUser': {
                'name': 'Anonymous',
                'avatar': 'https://i.pravatar.cc/150?img=8',
                'online': False
            },
            'isServer': False
        })
    return jsonify({'error': 'No session data'}), 400

@socketio.on('connect')
def handle_connect():
    if 'client_data' in session:
        Thread(target=socket_client_thread,
              args=(session['client_data']['ip'],
                    session['client_data']['port'],
                    session['client_data']['name'],
                    request.sid),
              daemon=True).start()

@socketio.on('message')
def handle_message(msg):
    if request.sid not in active_connections:
        emit('error', {'message': 'Not connected'})
        return
    
    try:
        conn_info = active_connections[request.sid]
        shared_key = conn_info['shared_key']
        sock = conn_info['sock']
        
        message = f"{session['client_data']['name']}: {msg['text']}"
        encrypted = encrypt_message(shared_key, message)
        
        # Send message length first
        sock.sendall(len(encrypted).to_bytes(4, byteorder='big'))
        # Then send the message
        sock.sendall(encrypted)
        
    except ConnectionError as e:
        logging.error(f"Connection error while sending: {e}")
        cleanup_connection(request.sid)
        emit('error', {'message': 'Connection lost while sending'})
    except Exception as e:
        logging.error(f"Message sending error: {e}")
        emit('error', {'message': str(e)})

@socketio.on('disconnect')
def handle_disconnect():
    cleanup_connection(request.sid)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)