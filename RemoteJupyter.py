#!/usr/bin/env python

import sys, os, re, shutil
# import the tkyamlgui library
scriptpath=os.path.dirname(os.path.realpath(__file__))
sys.path.insert(1, scriptpath+'/tkyamlgui')
sys.path.insert(1, scriptpath)

import tkyamlgui as tkyg
import argparse
import paramiko
import socket
import select

try:
    import SocketServer
except ImportError:
    import socketserver as SocketServer
    
#import subprocess, shlex
import getpass
import pexpect
import tempfile
import platform

if platform.system()=='Windows':
    from pexpect import popen_spawn

g_verbose = False


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
    if g_verbose:
        print(s)    
    
def ssh(host, cmd, username, password, verbose=False):
    client = paramiko.client.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=username, password=password)
    _stdin, _stdout,_stderr = client.exec_command(cmd)
    print(_stdout.read().decode())
    if verbose: print(_stderr.read().decode())
    client.close()
    return 

    
def ssh2(host, cmd, user, password, timeout=30, inputopts='',
        bg_run=False, verbose=False):
    """SSH'es to a host using the supplied credentials and executes a
    command.  Throws an exception if the command doesn't return 0.
    bgrun: run command in the background
    """
    # From 

    fname = tempfile.mktemp()
    fout = open(fname, 'w')
    
    options = inputopts+' -q -oStrictHostKeyChecking=no -oUserKnownHostsFile=/dev/null -oPubkeyAuthentication=no'
    if bg_run:
        options += ' -f'
    ssh_cmd = 'ssh %s@%s %s "%s"' % (user, host, options, cmd)
    if verbose: print(ssh_cmd)
    if platform.system() == 'Windows':
        child = popen_spawn.PopenSpawn(ssh_cmd, timeout=timeout)
    else:
        if sys.version_info[0] < 3:
            child = pexpect.spawn(ssh_cmd, timeout=timeout)  
        else:
            child = pexpect.spawnu(ssh_cmd, timeout=timeout)  #spawnu for Python 3 
    child.expect(['[pP]assword: '])
    child.sendline(password)

    child.logfile = fout
    child.expect(pexpect.EOF)
    child.close()
    fout.close()
    
    fin = open(fname, 'r')
    stdout = fin.read()
    fin.close()
    
    if 0 != child.exitstatus:
        raise Exception(stdout)
    
    return stdout

class MyApp(tkyg.App, object):
    def __init__(self, *args, **kwargs):
        super(MyApp, self).__init__(dorightframe=False,
                                    geometry="530x400",
                                    leftframeh=360,
                                    *args, **kwargs)

    def editExpertButton(self):
        self.inputvars['password'].setval('')
        self.inputvars['editexpertsettings'].setval(True)
        return
    
    def launchserver(self):
        uselab    = self.inputvars['usejupyterlab'].getval()
        servercmd = self.inputvars['launchservercmd'].getval()
        NBLAB     = 'lab' if uselab else 'notebook' 
        REMOTEPORT= self.inputvars['remoteportnum'].getval()
        user      = self.inputvars['username'].getval()
        machine   = self.inputvars['servername'].getval()
        execmd    = servercmd.format(NBLAB=NBLAB, REMOTEPORT=REMOTEPORT)
        pwd       = self.inputvars['password'].getval()
        if pwd == '':
            pwd = getpass.getpass()
        else:
            self.inputvars['editexpertsettings'].setval(False)
        out=ssh(machine, execmd, user, pwd)
        #print(out)
        return

    def listserver(self):
        user      = self.inputvars['username'].getval()
        machine   = self.inputvars['servername'].getval()
        servercmd = self.inputvars['listsessionscmd'].getval()
        pwd       = self.inputvars['password'].getval()
        if pwd == '':
            pwd = getpass.getpass()
        else:
            self.inputvars['editexpertsettings'].setval(False)
        out=ssh(machine, servercmd, user, pwd)
        #print(out)        
        return

    def stopserver(self):
        user      = self.inputvars['username'].getval()
        machine   = self.inputvars['servername'].getval()
        servercmd = self.inputvars['stopsessionscmd'].getval()
        REMOTEPORT= self.inputvars['remoteportnum'].getval()
        uselab    = self.inputvars['usejupyterlab'].getval()
        NBLAB     = 'lab' if uselab else 'notebook' 

        pwd       = self.inputvars['password'].getval()
        if pwd == '':
            pwd = getpass.getpass()
        else:
            self.inputvars['editexpertsettings'].setval(False)
        execmd = servercmd.format(NBLAB=NBLAB, REMOTEPORT=REMOTEPORT)
        out=ssh(machine, execmd, user, pwd)
        #print(out)        
        return

    def startconnect(self):
        uselab    = self.inputvars['usejupyterlab'].getval()
        NBLAB     = 'lab' if uselab else 'notebook' 
        REMOTEPORT= self.inputvars['remoteportnum'].getval()
        LOCALPORT = self.inputvars['localportnum'].getval()
        user      = self.inputvars['username'].getval()
        machine   = self.inputvars['servername'].getval()
        serveropt = self.inputvars['sshforwardopt'].getval()
        opts      = serveropt.format(LOCALPORT=LOCALPORT,
                                     REMOTEPORT=REMOTEPORT)
        pwd       = self.inputvars['password'].getval()
        if pwd == '':
            pwd = getpass.getpass()
        else:
            self.inputvars['editexpertsettings'].setval(False)
        execmd=''
        print("STARTING CONNECTION")

        
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.WarningPolicy())

        #verbose("Connecting to ssh host %s:%d ..." % (server[0], server[1]))
        try:
            client.connect(
                machine,
                22,
                username=user,
                #key_filename=options.keyfile,
                #look_for_keys=options.look_for_keys,
                password=pwd,
            )
        except Exception as e:
            print("*** Failed to connect to %s:%d: %r" % (machine, 22, e))
            sys.exit(1)
        
        try:
            forward_tunnel(
                LOCALPORT, 'localhost', REMOTEPORT, client.get_transport()
            )
        except KeyboardInterrupt:
            print("C-c: Port forwarding stopped.")
            sys.exit(0)

        #out=ssh(machine, execmd, user, pwd, inputopts=opts)
        #print(out)
        return
    
if __name__ == "__main__":
    title          = 'Remote Jupyter'
    localconfigdir = os.path.join(scriptpath,'local')
    configfile     = 'config.yaml'

    # Check the command line arguments
    parser         = argparse.ArgumentParser(description=title)
    parser.add_argument('--localconfigdir',   
                        default=localconfigdir,  
                        help="Local configuration directory [default: %s]"%localconfigdir)

    args           = parser.parse_args()
    localconfigdir = args.localconfigdir
    
    # Instantiate the app
    mainapp=MyApp(configyaml=os.path.join(scriptpath,configfile), 
                  localconfigdir=localconfigdir, 
                  scriptpath=scriptpath,
                  title=title)
    mainapp.notebook.enable_traversal()
    mainapp.mainloop()

