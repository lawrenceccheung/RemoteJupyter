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
import threading
import traceback
from functools import partial

try:
    import SocketServer
except ImportError:
    import socketserver as SocketServer

if sys.version_info[0] < 3:
    import Tkinter as Tk
    import tkFileDialog as filedialog
else:
    import tkinter as Tk
    from tkinter import filedialog as filedialog

# Load ruamel or pyyaml as needed
try:
    import ruamel.yaml as yaml
    #print("# Loaded ruamel.yaml")
    useruamel=True
    loaderkwargs = {'Loader':yaml.RoundTripLoader}
    dumperkwargs = {'Dumper':yaml.RoundTripDumper, 'indent':4, 'default_flow_style':False} # 'block_seq_indent':2, 'line_break':0, 'explicit_start':True, 
except:
    import yaml as yaml
    #print("# Loaded yaml")
    useruamel=False
    loaderkwargs = {}
    dumperkwargs = {'default_flow_style':False }

#import subprocess, shlex
import getpass
import pexpect
import tempfile
import platform

if platform.system()=='Windows':
    from pexpect import popen_spawn

t1        = None
g_verbose = False
tunnel    = None
client    = None
connectdict = {}

# See https://github.com/paramiko/paramiko/blob/main/demos/forward.py
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
            try:
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
            except:
                pass
        peername = self.request.getpeername()
        chan.close()
        self.request.close()
        verbose("Tunnel closed from %r" % (peername,))


def forward_tunnel(local_port, remote_host, remote_port, transport, lock, key):
    # this is a little convoluted, but lets me configure things for the Handler
    # object.  (SocketServer doesn't give Handlers any way to access the outer
    # server normally.)
    global tunnel, connectdict
    class SubHander(Handler):
        chain_host = remote_host
        chain_port = remote_port
        ssh_transport = transport
    lock.acquire()
    #key = remote_host+':'+repr(remote_port)
    #print("Connectdict: ",connectdict)
    connectdict[key]['tunnel'] = ForwardServer(("", local_port), SubHander)
    connectdict[key]['tunnel'].serve_forever()
    #tunnel = ForwardServer(("", local_port), SubHander)
    #tunnel.serve_forever()

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
                                    geometry="530x430",
                                    leftframeh=390,
                                    *args, **kwargs)
        self.report_callback_exception = self.showerror

    def showerror(self, *args):
        err = traceback.format_exception(*args)

    def menubar(self, root):
        """ 
        Adds a menu bar to root
        See https://www.tutorialspoint.com/python/tk_menu.htm
        """
        menubar  = Tk.Menu(root)

        # File menu
        filemenu = Tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Save settings", 
                             command=self.savesettings)
        filemenu.add_command(label="Save settings as...", 
                             command=self.savesettingsGUI)
        filemenu.add_command(label="Load settings", 
                             command=self.loadsettings)
        filemenu.add_command(label="Load settings from...", 
                             command=self.loadsettingsGUI)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=root.quit)
        menubar.add_cascade(label="File", menu=filemenu)
        # Help menu
        help_text ="""
 Remote Jupyter app 
        by
 Lawrence Cheung 
"""
        helpmenu = Tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="About...", 
                             command=partial(tkyg.messagewindow, root,
                                             help_text))
        menubar.add_cascade(label="Help", menu=helpmenu)
        
        root.config(menu=menubar)
        return

    def editExpertButton(self):
        self.inputvars['password'].setval('')
        self.inputvars['editexpertsettings'].setval(True)
        return
    
    def launchserver(self):
        uselab    = self.inputvars['usejupyterlab'].getval()
        if uselab:
            NBLAB = 'lab'
            servercmd = self.inputvars['launchlabcmd'].getval()
        else:
            NBLAB = 'notebook'
            servercmd = self.inputvars['launchservercmd'].getval()
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
        global t1, tunnel, client, connectdict
        uselab    = self.inputvars['usejupyterlab'].getval()
        NBLAB     = 'lab' if uselab else 'notebook' 
        REMOTEPORT= self.inputvars['remoteportnum'].getval()
        LOCALPORT = self.inputvars['localportnum'].getval()
        user      = self.inputvars['username'].getval()
        machine   = self.inputvars['servername'].getval()
        pwd       = self.inputvars['password'].getval()
        if pwd == '':
            pwd = getpass.getpass()
        else:
            self.inputvars['editexpertsettings'].setval(False)
        execmd=''

        sshport = 22
        key = machine+':'+repr(REMOTEPORT)
        print("STARTING CONNECTION "+key)
        connectdict[key] = {}
        connectdict[key]['client'] = paramiko.SSHClient()
        #clientX = connectdict[key]['client']
        #client = paramiko.SSHClient()
        #clientX.load_system_host_keys()
        #clientX.set_missing_host_key_policy(paramiko.WarningPolicy())
        connectdict[key]['client'].load_system_host_keys()
        connectdict[key]['client'].set_missing_host_key_policy(paramiko.WarningPolicy())
        #verbose("Connecting to ssh host %s:%d ..." % (server[0], server[1]))
        try:
            #client.connect(
            connectdict[key]['client'].connect(
                machine,
                sshport,
                username=user,
                #key_filename=options.keyfile,
                #look_for_keys=options.look_for_keys,
                password=pwd,
            )
        except Exception as e:
            print("*** Failed to connect to %s:%d: %r" % (machine, 22, e))
            sys.exit(1)

        lock = threading.Lock()
        #t1 = threading.Thread(target=forward_tunnel,
        connectdict[key]['thread'] = threading.Thread(target=forward_tunnel,
                              daemon=True,
                              args=(LOCALPORT,
                                    'localhost',
                                    REMOTEPORT,
                                    connectdict[key]['client'].get_transport(),
                                    lock,
                                    key))
        #t1.start()
        connectdict[key]['thread'].start()
        #out=ssh(machine, execmd, user, pwd, inputopts=opts)
        #print(out)
        return

    def stopconnect(self):
        global connectdict
        for key, connect in connectdict.items():
            print("STOPPING CONNECTION "+key)
            connect['tunnel'].shutdown()
            connect['client'].close()
            connect['thread'].join()
        # global t1, tunnel, client, connectdict
        # #if t1 is not None:
        # print("STOPPING CONNECTION")
        # tunnel.shutdown()
        # client.close()
        # t1.join()
        return

    def savesettings(self, filename='default.yaml'):
        tag = 'savename'
        savedict = dict(self.getDictFromInputs(tag, onlyactive=False))
        outfile = sys.stdout if filename == sys.stdout else open(filename, 'w')
        yaml.dump(savedict, outfile, **dumperkwargs)
        outfile.close()
        return

    def savesettingsGUI(self):
        filename  = filedialog.asksaveasfilename(initialdir = "./",
                                                 title = "Save settings file",
                                                 filetypes=[("yaml files",
                                                             "*.yaml"),
                                                            ("all files","*.*")
                                                 ])
        if len(filename)>0: self.savesettings(filename=filename)
        return

    def loadsettings(self, filename='default.yaml'):
        yamldict = {}
        tag = 'savename'
        # Load the yaml input file
        with open(filename, 'r') as fp:
            if useruamel: Loader=yaml.load
            else:         Loader=yaml.safe_load
            yamldict = dict(Loader(fp, **loaderkwargs))
        self.setinputfromdict(tag, yamldict)
        return

    def loadsettingsGUI(self):
        kwargs = {'filetypes':[("YAML files","*.yaml"), ("all files","*.*")]}
        filename  = filedialog.askopenfilename(initialdir = "./",
                                               title = "Select save file",
                                               **kwargs)
        if len(filename)>0: self.loadsettings(filename=filename)
        return
    
if __name__ == "__main__":
    title          = 'Remote Jupyter'
    localconfigdir = os.path.join(scriptpath,'local')
    configfile     = 'config.yaml'

    # Check the command line arguments
    parser         = argparse.ArgumentParser(description=title)
    parser.add_argument('settingsfile', nargs='?', default='default.yaml')
    parser.add_argument('--localconfigdir',   
                        default=localconfigdir,  
                        help="Local configuration directory [default: %s]"%localconfigdir)

    args           = parser.parse_args()
    localconfigdir = args.localconfigdir
    settingsfile   = args.settingsfile
    
    # Instantiate the app
    mainapp=MyApp(configyaml=os.path.join(scriptpath,configfile), 
                  localconfigdir=localconfigdir, 
                  scriptpath=scriptpath,
                  title=title)
    mainapp.notebook.enable_traversal()
    if os.path.exists(settingsfile):
        #print("Loading settings from "+settingsfile)
        mainapp.loadsettings(filename=settingsfile)
    mainapp.mainloop()

