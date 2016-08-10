# -*- coding: utf-8 -*-
"""
Created on Tue Mar 22 17:52:49 2016

@author: Alex Kerr

Define a set of operations for use on Molecule objects that we don't want being methods.
"""

import os
import errno
from copy import deepcopy
import pickle

import numpy as np

#change in position for the finite difference equations
ds = 1e-6
dx = ds
dy = ds
dz = ds

vdx = np.array([dx,0.0,0.0])
vdy = np.array([0.0,dy,0.0])
vdz = np.array([0.0,0.0,dz])
           
save_dir = "./kappa_save/"

def _path_exists(path):
    """Make a path if it doesn't exist"""
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise
            
def _file_exists(path):
    """Return True if file path exists, False otherwise"""
    return os.path.isfile(path)

def save(molecule):
    """Save a pickled molecule into /kerrNM/systems/"""
    path = save_dir + molecule.name
    _path_exists(path)
    pickle.dump(molecule, open( path + "/mol.p", "wb" ) )
    
def load(name):
    """Load a pickled molecule given a name"""
    return pickle.load(open(save_dir+name+"/mol.p", "rb"))
    
def _calculate_hessian(molecule, numgrad=False):
    """Return the Hessian matrix for the given molecule after calculation."""
    
    N = len(molecule)
    
    H = np.zeros([3*N,3*N])
    
    if numgrad:
        calculate_grad = molecule.define_gradient_routine_numerical()
    else:
        calculate_grad = molecule.define_gradient_routine_analytical()
    
    for i in range(N):
        
        ipos = molecule.posList[i]
        
        ipos += vdx
        plusXTestGrad,_,_ = calculate_grad()
        ipos += -2.0*vdx
        minusXTestGrad,_,_ = calculate_grad()
        ipos += vdx + vdy
        plusYTestGrad,_,_ = calculate_grad()
        ipos += -2.0*vdy
        minusYTestGrad,_,_ = calculate_grad()
        ipos += vdy + vdz
        plusZTestGrad,_,_ = calculate_grad()
        ipos += -2.0*vdz
        minusZTestGrad,_,_ = calculate_grad()
        ipos += vdz
        
        xiRow = (plusXTestGrad - minusXTestGrad)/2.0/dx
        yiRow = (plusYTestGrad - minusYTestGrad)/2.0/dy
        ziRow = (plusZTestGrad - minusZTestGrad)/2.0/dz
        
        H[3*i    ] = np.hstack(xiRow)
        H[3*i + 1] = np.hstack(yiRow)
        H[3*i + 2] = np.hstack(ziRow)
        
    return H
    
def hessian(molecule):
    """Return the Hessian for a molecule; if it doesn't exist calculate it otherwise load it
    from the numpy format."""
    path = save_dir + molecule.name
    #check if path exists
    _path_exists(path)
    #if Hessian file exists then load it; otherwise calculate it and save it
    if _file_exists(path + "/hessian.npy"):
        print("Loading Hessian matrix from file...")
        return np.load(path + "/hessian.npy")
    else:
        print("Calculating the Hessian matrix for " + molecule.name + "...")
        H = _calculate_hessian(molecule)
        print("Done!")
        np.save(path + "/hessian.npy", H)
        return H
    
def evecs(hessian):
    """Return the eigenvalues and eigenvectors associated with a given Hessian matrix."""
    w,vr = np.linalg.eig(hessian)
    return w,vr
    
def _combine(oldMolecule1,oldMolecule2,index1,index2, nextIndex1, face1, face2, copy=True):
    """Return a single molecule which is the combination of 2 inputed molcules where indices
    1 and 2 are the same atom effectively."""
    
    #check validity of parameters
    if oldMolecule1.zList[index1] != oldMolecule2.zList[index2]:
        raise ValueError('Two combined atoms must have the same atomic number')
    if index1 in oldMolecule1.faces[face1].closed or index2 in oldMolecule2.faces[face2].closed:
        raise ValueError('Atoms to be combined must not be closed')
    
    ###################
    #start combine process
    
    #create copies of molecules
    if copy:
        molecule1 = deepcopy(oldMolecule1)
    else:
        molecule1 = oldMolecule1
    molecule2 = deepcopy(oldMolecule2)
    
    size1 = len(molecule1)
    
    #anticipate new index1
    if nextIndex1 == index2:
        nextIndex1 = index1
    elif nextIndex1 > index2:
        nextIndex1 = nextIndex1 + size1 - 1
    else:
        nextIndex1 = nextIndex1 + size1
        
    ###########
    #change the positions of the atoms of the added molecule
    
    #rotate molecule2
    norm1, norm2 = molecule1.faces[face1].norm, molecule2.faces[face2].norm
    #check to see if they
    axis = np.cross(norm1, norm2)
    mag = np.linalg.norm(axis)
    if mag < 1e-10:
        #check for parallel/anti-parallel
        dot = np.dot(norm1,norm2)
        if dot < 0.:
            #don't rotate
            pass
        if dot > 0.:
            #flip the molecule
            molecule2.invert()
            pass
    else:
        angle = np.degrees(np.arcsin(mag))
        molecule2.rotate(axis,angle)
    
    #shift molecule 2 into position
    pos1, pos2 = molecule1.posList, molecule2.posList
    z1, z2 = molecule1.zList, molecule2.zList
    facetrack1, facetrack2 = molecule1.facetrack, molecule2.facetrack
    displaceVec = pos1[index1] - pos2[index2]
    molecule2.translate(displaceVec)
    
    ###########
    #change the attributes of the molecules
    
    #adjust neighbor lists
    #add neighbors to atom1
    for neighbor in molecule2.nList[index2]:
        if neighbor > index2:
            molecule1.nList[index1].append(neighbor + size1 - 1)
        elif neighbor < index2:
            molecule1.nList[index1].append(neighbor + size1)
        else:
            raise ValueError("An atom can't neighbor itself")
    for index,nList in enumerate(molecule2.nList):
        if index != index2:
            newNList = []
            for neighbor in nList:
                if neighbor == index2:
                    newNList.append(index1)
                elif neighbor > index2:
                    newNList.append(neighbor + size1 - 1)
                else:
                    newNList.append(neighbor + size1)
            molecule2.nList[index] = newNList
     
    #########      
    #delete single atom interfaces
            
    #a number to account for deleted interfaces, for facetracking
    delAccount = 0
    #establish the face in which to 'close' the chained atom
    #default will be face1 unless its deleted below
    closeFace = molecule1.faces[face1]
    
    if len(molecule2.faces[face2].atoms) == 1 and len(molecule1.faces[face1].atoms) == 1:
        molecule1.faces[face1].norm = np.array([0.,0.,1.])
        del molecule2.faces[face2]
        delAccount += 1
    elif len(molecule2.faces[face2].atoms) == 1:
        del molecule2.faces[face2]
        delAccount += 1
    elif len(molecule1.faces[face1].atoms) == 1:
        #change closeFace because face1 will be deleted
        closeFace = molecule2.faces[face2]
        del molecule1.faces[face1]
        delAccount += 1
    
    closeFace.closed.append(index1)
    
    #adjust facetracking
    #where factrack ISN'T -1, add the number of interfaces in mol1
    facesize1 = len(molecule1.faces) 
    whereNotNegOne = np.where(facetrack2!=-1)
    facetrack2[whereNotNegOne] = facetrack2[whereNotNegOne] + (facesize1-delAccount)*np.full(len(whereNotNegOne),
                                                                                1, dtype=np.int8)
    #where facetrack is -1, change it to interface num
    whereNegOne = np.where(facetrack2==-1)
    facetrack2[whereNegOne] = np.full(len(whereNegOne), face1, dtype=np.int8)
      
    #add interfaces to base molecule
    for count, face in enumerate(molecule2.faces):
        #change the indices of the interfacial atoms and 'closed' atoms
        newAtoms = []
        newClosed = []
        for oldatom in face.atoms:
            if oldatom == index2:
                newIndex = index1
            elif oldatom > index2:
                newIndex = oldatom + size1 - 1
            else:
                newIndex = oldatom + size1
            newAtoms.append(newIndex)
            if oldatom in face.closed:
                newClosed.append(newIndex)                
        face.atoms = newAtoms
        face.closed = newClosed
        #add interface paths
        #start with path of base interface
        newPath = molecule1.faces[face1].path[:]
        #add the path of the added interface with indices incremented by size of molecule1
        newPath.extend([x+facesize1 for x in range(len(face.path))])
        face.path = newPath
        #add to molecule1.faces
        molecule1.faces.append(face)
        
        
        
    ##############
    #complete new molecule
        
    #delete the attributes regarding atom of index2
    #because that atom doesn't exist anymore        
    pos2 = np.delete(pos2, index2, 0)
    z2 = np.delete(z2, index2, 0)
    facetrack2 = np.delete(facetrack2, index2, 0)
    del molecule2.nList[index2]
    
    #add atoms/attributes to molecule1
    pos1 = np.concatenate((pos1,pos2), axis=0)
    z1 = np.append(z1,z2)
    facetrack1 = np.append(facetrack1, facetrack2)
    molecule1.nList.extend(molecule2.nList)
    
    #assign attributes
    molecule1.posList = pos1
    molecule1.zList = z1
    molecule1.facetrack = facetrack1
    
    return molecule1, nextIndex1
    
def chain(molList, indexList, name=""):
    """Return a single molecule as a chain of the inputted molecules."""
    
    if len(molList) != len(indexList)+1:
        raise ValueError('There should be one more molecule than connections')
    
    molChain = molList[0]
    i,j = indexList[0]
    
    for molNum, mol in enumerate(molList[1:]):
        
        if molNum+1 < len(indexList):
            nextI = indexList[molNum+1][0]
        else:
            nextI = 0
        j = indexList[molNum][1]
        for count,face in enumerate(molChain.faces):
            if i in face.atoms:
                iface = count
        for count, face in enumerate(mol.faces):
            if j in face.atoms:
                jface = count
        molChain, i = _combine(molChain, mol, i, j, nextI, iface, jface)
        
    if not name:
        name = molList[0].name
    molChain.name = name
#    molChain._configure()
        
    return molChain
        