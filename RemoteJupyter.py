#!/usr/bin/env python

import sys, os, re, shutil
# import the tkyamlgui library
scriptpath=os.path.dirname(os.path.realpath(__file__))
sys.path.insert(1, scriptpath+'/tkyamlgui')
sys.path.insert(1, scriptpath)

import tkyamlgui as tkyg
import argparse
import subprocess, shlex

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
        sshcmd    = "ssh {user}@{machine} "
        exestring = sshcmd.format(user=user, machine=machine, execmd=execmd)
        print(shlex.split(exestring))

        subprocess.call(exestring, shell=True)

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

