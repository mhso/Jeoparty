import json
import select
from argparse import ArgumentParser

import socketserver as SocketServer
from jeoparty.api.config import Config

import sys

import paramiko

SSH_PORT = 22
LOCAL_PORT = 5432
PG_PORT = 5432

class ForwardServer(SocketServer.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


class Handler(SocketServer.BaseRequestHandler):
    def handle(self):
        try:
            chan = self.ssh_transport.open_channel(
                "direct-tcpip",
                (self.chain_host, self.chain_port),
                self.request.getpeername(),
            )
        except Exception as e:
            verbose(
                "Incoming request to %s:%d failed: %s"
                % (self.chain_host, self.chain_port, repr(e))
            )
            return
        if chan is None:
            verbose(
                "Incoming request to %s:%d was rejected by the SSH server."
                % (self.chain_host, self.chain_port)
            )
            return

        verbose(
            "Connected!  Tunnel open %r -> %r -> %r"
            % (
                self.request.getpeername(),
                chan.getpeername(),
                (self.chain_host, self.chain_port),
            )
        )
        while True:
            r, w, x = select.select([self.request, chan], [], [])
            if self.request in r:
                data = self.request.recv(1024)
                if len(data) == 0:
                    break
                chan.send(data)
            if chan in r:
                data = chan.recv(1024)
                if len(data) == 0:
                    break
                self.request.send(data)

        peername = self.request.getpeername()
        chan.close()
        self.request.close()
        verbose("Tunnel closed from %r" % (peername,))


def forward_tunnel(local_port, remote_host, remote_port, transport):
    # this is a little convoluted, but lets me configure things for the Handler
    # object.  (SocketServer doesn't give Handlers any way to access the outer
    # server normally.)
    class SubHander(Handler):
        chain_host = remote_host
        chain_port = remote_port
        ssh_transport = transport

    ForwardServer(("", local_port), SubHander).serve_forever()


def verbose(s):
    print(s, file=sys.stderr)

def get_host_port(spec, default_port):
    "parse 'hostname:22' into a host and port, with the port optional"
    args = (spec.split(":", 1) + [default_port])[:2]
    args[1] = int(args[1])
    return args[0], args[1]


def main():
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.WarningPolicy())

    with open(f"{Config.STATIC_FOLDER}/secret.json") as fp:
        secrets = json.load(fp)

    jump_host = secrets["ssh_jump_host"]
    remote_host = secrets["ssh_remote_host"]

    verbose("Connecting to ssh host %s:%d ..." % (jump_host, SSH_PORT))
    try:
        client.connect(
            jump_host,
            SSH_PORT,
            username="mikkel",
            look_for_keys=True,
            password=secrets["ssh_password"],
            timeout=10,
        )
    except Exception as e:
        print("*** Failed to connect to %s:%d: %r" % (jump_host, SSH_PORT, e))
        sys.exit(1)

    verbose(
        "Now forwarding port %d to %s:%d ..."
        % (LOCAL_PORT, remote_host, PG_PORT)
    )

    print("ready")

    try:
        forward_tunnel(
            LOCAL_PORT, remote_host, PG_PORT, client.get_transport()
        )
    except KeyboardInterrupt:
        print("C-c: Port forwarding stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
