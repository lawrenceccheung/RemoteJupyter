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

def ssh(host, cmd, user, password, timeout=30, inputopts='',bg_run=False):
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
    child = pexpect.spawn(ssh_cmd, timeout=timeout)  #spawnu for Python 3
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
                                    leftframeh=350,
                                    *args, **kwargs)
    def launchserver(self):
        uselab    = self.inputvars['usejupyterlab'].getval()
        servercmd = self.inputvars['launchservercmd'].getval()
        NBLAB     = 'lab' if uselab else 'notebook' 
        REMOTEPORT= self.inputvars['remoteportnum'].getval()
        user      = self.inputvars['username'].getval()
        machine   = self.inputvars['servername'].getval()
        execmd    = servercmd.format(NBLAB=NBLAB, REMOTEPORT=REMOTEPORT)

        pwd = getpass.getpass()
        out=ssh(machine,'w',user,pwd)
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

