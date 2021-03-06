# -*- coding: utf-8 -*-
"""

@author: Alex Kerr

"""

import itertools
from copy import deepcopy
import csv
import time
import pprint

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

from .molecule import build, chains
from .operation import _calculate_hessian
import ballnspring

amuDict = {1:1.008, 6:12.01, 7:14.01, 8:16.00, 9:19.00,
           15:30.79, 16:32.065, 17:35.45}
           
stapled_index = 30
           
class Calculation:
    
    def __init__(self, base, gamma=10., **minkwargs):
        if len(base.faces) == 2:
            self.base = base
        else:
            raise ValueError("A base molecule with 2 interfaces is needed!")
        self.gamma = gamma
        #minimize the base molecule
        from ._minimize import minimize
        minimize(self.base, **minkwargs)
        #assign minimization attributes
        self.minkwargs = minkwargs
        #other attributes
        self.trialcount = 0
        self.trialList = []
        self.driverList = []
            
    def add(self, molList, indexList):
        """Append a trial molecule to self.trialList with enhancements 
        from molList attached to atoms in indexList"""
        
        from .molecule import _combine
        newTrial = deepcopy(self.base)
        dList = [[],[]]
        for mol, index in zip(molList,indexList):
            #find faces of index
            for count, face in enumerate(self.base.faces):
                if index in face.atoms:
                    face1 = count
            sizetrial = len(newTrial)
            newTrial = _combine(newTrial, mol, index, 0, copy=False)
            #do minus 2 because 1 atom gets lost in combination
            #and another to account to the 'start at zero' indexing
            dList[face1].append(mol.driver + sizetrial - 1)
#            #drive every hydrogen
#            for hindex in np.where(mol.zList==1)[0]:
#                dList[face1].append(hindex + sizetrial - 1)
        newTrial._configure()
        self.driverList.append(dList)
        self.trialList.append(newTrial)
        from ._minimize import minimize
        minimize(newTrial, **self.minkwargs)
        newTrial.name = "%s_trial%s" % (newTrial.name, str(self.trialcount))
        self.trialcount += 1
        return newTrial
        
    def calculate_kappa(self, trial):
        from .plot import bonds
        bonds(self.trialList[trial])
        return calculate_thermal_conductivity(self.trialList[trial], self.driverList[trial], len(self.base), self.gamma)
        
class ParamSpaceExplorer(Calculation):
    
    def __init__(self, base, cnum, clen=[1], cid=["polyeth"], gamma=10., **minkwargs):
        super().__init__(base, gamma=gamma, **minkwargs)
        self.clen = clen
        self.cnum = cnum
        self.cid = cid
        #make zero value array based on dim of parameters
        self.params = [cid, clen, cnum]
        self.values = np.zeros([len(x) for x in self.params])
        
    def explore(self):
        trial = 0
        for idcount, _id in enumerate(self.cid):
            for lencount, _len in enumerate(self.clen):
                chain = build(self.base.ff, _id, count=_len)
                for numcount in range(len(self.cnum)):
                    #find indices of attachment points
                    indices = [index for subindices in self.cnum[0:numcount+1] for index in subindices]
                    self.add([chain]*(numcount+1)*2, indices)
                    kappa = self.calculate_kappa(trial)
                    vals = [kappa.real, chains.index(_id), _len, numcount+1,
                            self.gamma, self.base.ff.name, indices]
                    self.write(self.base.name, vals)
                    self.values[idcount,lencount,numcount] = kappa
                    trial += 1
                    
    @staticmethod               
    def write(filename, vals):
        kappa, cid, clen, cnum, gamma, ff, indices = vals
        with open('{0}'.format(filename), 'a', newline='') as file:
            line_writer = csv.writer(file, delimiter=';')
            line_writer.writerow([kappa, cid, clen, cnum,0,0,0,gamma, ff, indices, time.strftime("%H:%M/%d/%m/%Y")])
            
class ModeInspector(Calculation):
    """A class designed to inspect quantities related to the thermal conductivity
    calculation.  Inherits from Calculation, but is intended to have only a single 
    trial molecule."""
    
    def __init__(self, base, molList, indices, gamma, **minkwargs):
        super().__init__(base, gamma=gamma, **minkwargs)
        super().add(molList, indices)
        self.mol = self.trialList[0]
        self.k = _calculate_hessian(self.mol, stapled_index, numgrad=False)
        self.N = len(self.k)
        self.dim = self.N//len(self.mol.mass)
        self.evec = ballnspring.calculate_thermal_evec(self.k, self.g, self.m)
        
    @property
    def g(self):
        return ballnspring.calculate_gamma_mat(self.dim, len(self.mol), self.gamma, self.driverList[0])
        
    @property
    def m(self):
        return np.diag(np.repeat(self.mol.mass,self.dim))
        
    def coeff(self):
        val, vec = self.evec
        return ballnspring.calculate_coeff(val, vec, np.diag(self.m), np.diag(self.g)), val, vec
        
    def tcond(self):
        
        coeff, val, vec = self.coeff()
        
        crossings = find_interface_crossings(self.mol, len(self.base))
        
        kappaList = []
        kappa = 0.
        for crossing in crossings:
            i,j = crossing
            kappa += ballnspring.calculate_power_list(i,j, self.dim, val, vec, coeff, self.k, self.driverList[0], kappaList)
            
        self.kappa = kappa
        self.kappaList = kappaList
            
        return kappa, kappaList, val, vec
        
    def plot_mode(self, evec_index):
        
        from .plot import normal_modes
        normal_modes(self.mol, self.evec[1][:self.N, evec_index])
        
    def plot_ppation_base(self, indices):
        
        val = self.evec[0][indices]
        vec = self.evec[1][:self.N,indices]
        
        num = np.sum((vec**2), axis=0)**2
        den = len(vec)*np.sum(vec**4, axis=0)
        
        fig = plt.figure()        
        
        plt.plot(val, num/den, 'bo')
        
        fig.suptitle("Val vs p-ratio of selected modes")
        
        plt.show()
        
    def plot_ppation(self):
        
        kappa, kappaList, val, vec = self.tcond()
        
        pprint.pprint(kappaList)
        
        vec = vec[:self.N,:]
        
        num = np.sum((vec**2), axis=0)**2
        den = len(vec)*np.sum(vec**4, axis=0)
        
        fig = plt.figure()        
        
        plt.plot(val, num/den, 'bo')
        
        #plot points corresponding to the highest values
        max_indices = []
        for entry in kappaList:
            #get the sigma, tau indices
            max_indices.extend([entry['sigma'], entry['tau']])
            
        max_indices = np.array(max_indices)
        
        plt.plot(val[max_indices], num[max_indices]/den[max_indices], 'rx', markersize=10)
        
        fig.suptitle("Val vs p-ratio")
        
        plt.axis([-.1,.1, 0., 1.])        
        plt.show()
        
    def plot_val(self):
        """Plot the real vs imag parts of the eigenvalues."""
        
        val,_ = self.evec()
        
        fig = plt.figure()
        
        plt.plot(np.real(val), np.imag(val), 'bo')
        
        fig.suptitle("Re[val] vs Im[val]")
        
        plt.show()
        
    def plot_contributions(self):
        
        kappa, kappaList,_,_ = self.tcond()
        
        size = len(kappaList)
        val = np.zeros((size, 3))
        
        for index, entry in enumerate(kappaList):
            val[index] = entry['kappa'], entry['val_num'], 1./entry['val_den']
         
        fig = plt.figure() 
        ax = fig.add_subplot(111, projection='3d')        
        
        ax.scatter(val[:,0], val[:,1], val[:,2], c='b')
        dx = 1.015
        for index in np.arange(val.shape[0]):
            ax.text(val[index,0]*dx, val[index,1]*dx, val[index,2]*dx, index, color="red")
        
        ax.set_xlabel('kappa')
        ax.set_ylabel('numerator')
        ax.set_zlabel('denominator')
        
        fig.suptitle("Distribution of max kappa contributions")
        
        plt.show()
        
    def plot_contrib_mode(self, kappa_index):
        
        dict_ = self.kappaList[kappa_index]
        sigma, tau = dict_['sigma'], dict_['tau']
        print(sigma, tau)
        
        self.plot_mode(sigma)
        self.plot_mode(tau)
        
def internal2interactions(internals):
    """
    Return an Nx2 array of indices which interact given a list of list
    of indices that comprise internal coordinates.
    """
    interactions = []
    for internal in internals:
        for index in internal[1:]:
            if index > internal[0]:
                interactions.append([internal[0], index])
    return interactions
        
def find_interface_crossings(mol, baseSize):
    """Return the interactions that cross the molecular interfaces."""
    
    crossings = []
    atoms0 = mol.faces[0].attached
    atoms1 = mol.faces[1].attached
    
    if mol.ff.dihs:
        interactions = mol.dihList
    elif mol.ff.angles:
        interactions = mol.angleList
    elif mol.ff.lengths:
        interactions = mol.bondList
    
    try:
        for it in interactions:
            for atom in atoms0:
                if atom in it:
                    #find elements that are part of the base molecule
                    #if there are any, then add them to interactions
                    elements = [x for x in it if x < baseSize]
                    for element in elements:
                        crossings.append([atom, element])
            for atom in atoms1:
                if atom in it:
                    elements = [x for x in it if x < baseSize]
                    for element in elements:
                        crossings.append([element, atom])
    except UnboundLocalError:
        pass
    
    # add nonbonded interactions
    # NOTE: this method only works if the interfacial atoms are indexed
    #   smaller than the side chains
    if mol.ff.lj or mol.ff.es:
        for atom in atoms0:
            x = np.intersect1d(np.where(mol.nbnList[:,1]==atom)[0], np.where(mol.nbnList[:,0] < baseSize)[0])
            for nbn in mol.nbnList[x]:
                crossings.append([atom, nbn[0]])
        for atom in atoms1:
            x = np.intersect1d(np.where(mol.nbnList[:,1]==atom)[0], np.where(mol.nbnList[:,0] < baseSize)[0])
            for nbn in mol.nbnList[x]:
                crossings.append([nbn[0], atom])
    
                    
    # remove duplicate interactions
    crossings.sort()
    return list(k for k,_ in itertools.groupby(crossings))

def find_interface_crossings_old(mol, baseSize):
    """Return the interactions that cross the molecular interfaces."""
    
    crossings = []
    atoms0 = mol.faces[0].attached
    atoms1 = mol.faces[1].attached
    
    if mol.ff.dihs:
        interactions = mol.dihList
    elif mol.ff.angles:
        interactions = mol.angleList
    elif mol.ff.lengths:
        interactions = mol.bondList

    for it in interactions:
        for atom in atoms0:
            if atom in it:
                #find elements that are part of the base molecule
                #if there are any, then add them to interactions
                elements = [x for x in it if x < baseSize]
                for element in elements:
                    crossings.append([atom, element])
        for atom in atoms1:
            if atom in it:
                elements = [x for x in it if x < baseSize]
                for element in elements:
                    crossings.append([element, atom])
                    
    #add nonbonded interactions
    ''' to 
        be 
        completed '''
                    
    #remove duplicate interactions
    crossings.sort()
    return list(k for k,_ in itertools.groupby(crossings))

def calculate_thermal_conductivity(mol, driverList, baseSize, gamma):
    
    crossings = find_interface_crossings(mol, baseSize)
    
    kmat = _calculate_hessian(mol, stapled_index, numgrad=False)
    
    return ballnspring.kappa(mol.mass, kmat, driverList, crossings, gamma)
        