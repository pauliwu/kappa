# -*- coding: utf-8 -*-
"""
Created on Sat Feb 27 20:02:19 2016

@author: Alex Kerr

Demonstrating the Green's function calculation for a 1D system of atoms.
"""

import numpy as np
import scipy.linalg as linalg
import scipy.integrate as integrate
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import matplotlib.animation as animation

ti = 0.
tf = 50.
mult = 3


def main():
    
    k0 = 1.
    m0 = 1.
    gamma0 = 0.1
    N = 3
    
    #get neighbor lists
    nLists = find_neighbors(N)
    
    #get Kmatrix (N x N)
    KMatrix = calculate_K_matrix(N,k0,nLists)
    
    #get gamma matrix (N x N)
    gammaMatrix = calculate_gamma_matrix(N,gamma0)
    
    #mass matrix now (N x N)
    MMatrix = calculate_M_matrix(N,m0)
    
    #find eigenvalues and eigenvectors
    #2N eigenvalues: N lambdha and N lambdha*
    #2N eigenvectors of length 2N
    val,vec = calculate_evec(MMatrix,gammaMatrix,KMatrix)

    coeff = calculate_greens_function(val, vec, MMatrix, gammaMatrix)
    
    print(coeff)
    print(vec)
    
#    q,t = calculate_position(coeff, val, vec)
    
#    print(np.shape(q))

#    plot(q,t)
#    animate(N,q,t)
    
def calculate_position(coeff, val, vec):
    
    N = len(val)//2
    num = mult*int(tf-ti)
    tList = np.linspace(ti, tf, num=num)
    
    def integrand(t1,t):
        
        expMat = np.exp(np.dot(np.diag((t-t1)*val),np.ones((2*N,N))), dtype=complex)
        
        gFunc = np.dot(vec[:N,:],np.multiply(expMat,coeff))
        
        #now the force
        force = np.zeros(N)
    
        #cosine driven force
        w = 1.5
        force[0] = np.cos(w*t1)
#        force[1] = np.cos(w*t1)
        
        #impulse force
#        w = 1.
#        force[0] = np.exp(-w*t1)
#        force[N-1] = -force[0]
        
        x = np.dot(gFunc,force)
        return np.real(x)
    
    q = np.zeros((num,N))

    for count, t in enumerate(tList):
        
        innerNum = mult*int(t-tList[0])
        t1List = np.linspace(0,t,num=innerNum)
        yList = np.zeros((innerNum,N))
        for t1count,t1 in enumerate(t1List):
            yList[t1count] = integrand(t1,t)
            
        for atom in range(N):
            q[count,atom] = integrate.trapz(yList[:,atom],t1List)
        
    return q,tList

    
def calculate_greens_function(val, vec, massMat, gMat):
    """Return the 2N x N Green's function coefficient matrix."""
    
    N = len(vec)//2
    
    #need to determine coefficients in eigenfunction/vector expansion
    # need linear solver to solve equations from notes
    # AX = B where X is the matrix of expansion coefficients
    
    A = np.zeros((2*N, 2*N), dtype=complex)
    A[:N,:] = vec[:N,:]

    #adding mass and damping terms to A
    lamda = np.tile(val, (N,1))

    A[N:,:] = np.multiply(A[:N,:], np.dot(massMat,lamda) + np.dot(gMat,np.ones((N,2*N))))
    
    #now prep B
    B = np.concatenate((np.zeros((N,N)), np.identity(N)), axis=0)

    return np.linalg.solve(A,B)
    
def calculate_evec(M,G,K):
    
    N = len(M)
    
    a = np.zeros([N,N])
    a = np.concatenate((a,np.identity(N)),axis=1)
    b = np.concatenate((K,G),axis=1)
    c = np.concatenate((a,b),axis=0)
    
    x = np.identity(N)
    x = np.concatenate((x,np.zeros([N,N])),axis=1)
    y = np.concatenate((np.zeros([N,N]),-M),axis=1)
    z = np.concatenate((x,y),axis=0)
    
    w,vr = linalg.eig(c,b=z,right=True)
    
    return w,vr
    
def calculate_M_matrix(N,m):
    """Return the scaled identity matrix (Cartesian coords.)"""
    return m*np.identity(3*N)
    
def calculate_gamma_matrix(N,g0):
    """Return the damping matrix, assuming only the ends are damped."""
    
    gMatrix = np.zeros([3*N,3*N])
    gMatrix[0,0] = g0
    gMatrix[1,1] = g0
    gMatrix[2,2] = g0
    gMatrix[3*N-1,3*N-1] = g0
    gMatrix[3*N-2,3*N-2] = g0
    gMatrix[3*N-3,3*N-3] = g0
    
    return gMatrix
    
def calculate_K_matrix(N,k0,nLists):
    """Return the Hessian of a linear chain of atoms assuming only nearest neighbor interactions."""
    
    KMatrix = np.zeros([3*N,3*N])
    
    for i,nList in enumerate(nLists):
        KMatrix[3*i  ,3*i  ] = k0*len(nList)
        KMatrix[3*i+1,3*i+1] = k0*len(nList)
        KMatrix[3*i+2,3*i+2] = k0*len(nList)
        for neighbor in nList:
            KMatrix[3*i  ,3*neighbor] = -k0
            KMatrix[3*i+1,3*neighbor+1] = -k0
            KMatrix[3*i+2,3*neighbor+2] = -k0
    
    return KMatrix
    
def find_neighbors(N):
    """Return a list of neighbor lists indexed like corresponding atoms, calculated for a single line"""
    
    nLists = []
    for i in range(N):
        if i == 0:
            nLists.append([1])
        elif i == N-1:
            nLists.append([N-2])
        else:
            nLists.append([i-1,i+1])
            
    #return as numpy array
    return np.array(nLists)
    
def plot(y,x):
    
    for i in range(np.shape(y)[1]):
        plt.plot(x,y[:,i] + 2*i*np.ones(len(x)))
    plt.ylabel('displacement')
    plt.xlabel('time')
    plt.show()
    
def animate(N,q,t):
    """From 'simple_3danim.py' from matplotlib main site examples."""
    
    #choose equilibrium positions
    for i in range(N):
        q[:,3*i] += 5*i*np.ones(len(t))
    
    def update_lines(num, dataLines, lines):
        for line, data in zip(lines, dataLines):
            # NOTE: there is no .set_data() for 3 dim data...
            line.set_data(data[0:2, :num])
            line.set_3d_properties(data[2, :num])
            
        
    fig = plt.figure()
    ax = Axes3D(fig)
    
    #reshape data
    data = np.zeros((N,3,len(t)))
    for i in range(len(t)):
        for j in range(N):
            data[j,0:3,i] = q[i,3*j:3*j+3]
    
    # Creating fifty line objects.
    # NOTE: Can't pass empty arrays into 3d version of plot()
#    lines = [ax.plot(dat[0, 0:1], dat[1, 0:1], dat[2, 0:1], 'o')[0] for dat in data]
    lines = [ax.plot(dat[0, 0:1], dat[1, 0:1], dat[2, 0:1], 'o')[0] for dat in data]
    
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    
    line_ani = animation.FuncAnimation(fig, update_lines, mult*int(tf-ti), fargs=(data, lines),
                                   interval=100, blit=False)
                                   
    plt.show(fig)
    
    
main()
