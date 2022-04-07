#!/usr/bin/env python

import sys, os, re, shutil
# import the tkyamlgui library
scriptpath=os.path.dirname(os.path.realpath(__file__))
sys.path.insert(1, scriptpath+'/tkyamlgui')
sys.path.insert(1, scriptpath)

import tkyamlgui as tkyg
import argparse
import subprocess, shlex
import getpass
import pexpect
import tempfile

def ssh(host, cmd, user, password, timeout=30, inputopts='',
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
        print(out)
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
        print(out)        
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
        print(out)        
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
        out=ssh(machine, execmd, user, pwd, inputopts=opts)
        print(out)
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

