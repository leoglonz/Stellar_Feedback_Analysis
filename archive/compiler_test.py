# This file gives functions for prepping, processing, and manipulation of bulk particle data. More specifically, the functions
# here retrieve gas particles satisfying certain ejection and accretion constraints and constructs respective data frames for 
# each. Said frames include arrtributes such as kinetic and potential energies, location based classifications (i.e., disk vs. 
# halo vs. field), state of supernova heating, and so on.
#
# Collecting these calculations here ensures uniformity in data processing for all instances in the computational analysis of 
# this project.
#
# ____________________________________________________________________________________________
# Ejection/Expulsion code credit to Hollis Akins 2021;
# Github permalink: https://github.com/hollisakins/Justice_League_Code/blob/ 
#                    e049137edcfdc9838ebb3cf0fcaa4ee46e977cec/Analysis/RamPressure/analysis.py
# ____________________________________________________________________________________________
# Last revised: 6 Dec. 2021

import pynbody
import pandas as pd
import numpy as np
import pickle

from base import *
from analysis import *



def read_tracked_particles(sim, haloid, verbose=False):
    '''
    -> Reads in gas particles tracked across a number of simulation satellites and calculates/appends desired particle 
        properties for analysis.
    '''
    #--------------------------------#
    
    if verbose: print(f'Loading tracked particles for {sim}-{haloid}...')
    
    key = f'{sim}_{str(int(haloid))}'

    # import the tracked particles dataset
    path1 = f'{rootPath}Stellar_Feedback_Code/SNeData/tracked_particles.hdf5' # data including virial mass attribute 'Mvir'.
#     path1 = f'{rootPath}Stellar_Feedback_Code/SNeData/tracked_particles.hdf5' # original dataset
    data = pd.read_hdf(path1, key=key)
    
    time = np.unique(data.time)
    dt = time[1:]-time[:-1]
    dt = np.append(dt[0], dt)
    dt = dt[np.unique(data.time, return_inverse=True)[1]]
    data['dt'] = dt
    
    
    if verbose: print('Successfully loaded')
    
    r_gal = np.array([])
    for t in np.unique(data.time):
        d = data[data.time==t]
        r_gas = np.mean(d.sat_r_gas)
        r_half = np.mean(d.sat_r_half)
        rg = np.max([r_gas,r_half])

        if np.isnan(rg):
            rg = r_gal_prev

        if verbose: print(f't = {t:1f} Gyr, satellite R_gal = {rg:.2f} kpc')
        r_gal = np.append(r_gal,[rg]*len(d))

        r_gal_prev = rg

    data['r_gal'] = r_gal
    
    r_gal_prev = 0
    r_gal = np.array([])
    for t in np.unique(data.time):
        d = data[data.time==t]
        r_gas = np.mean(d.host_r_gas)
        r_half = np.mean(d.host_r_half)
        rg = np.max([r_gas,r_half])

        if np.isnan(rg):
            rg = r_gal_prev

        if verbose: print(f't = {t:1f} Gyr, host R_gal = {rg:.2f} kpc')
        r_gal = np.append(r_gal,[rg]*len(d))

        r_gal_prev = rg

    data['host_r_gal'] = r_gal
    
    thermo_disk = (np.array(data.temp) < 1.2e4) & (np.array(data.rho) > 0.1)
    
    in_sat = np.array(data.in_sat)
    other_sat = np.array(data.in_other_sat)
    in_host = np.array(data.in_host) & ~in_sat & ~other_sat
    
    sat_disk = in_sat & thermo_disk
    sat_halo = in_sat & ~thermo_disk
    
    host_disk = in_host & thermo_disk
    host_halo = in_host & ~thermo_disk
    
    IGM = np.array(data.in_IGM)
    
    # basic location classifications.
    data['sat_disk'] = sat_disk
    data['sat_halo'] = sat_halo
    data['host_disk'] = host_disk
    data['host_halo'] = host_halo
    data['other_sat'] = other_sat
    data['IGM'] = IGM

    return data


def read_all_tracked():
    '''
    -> Identifies tracked particles for all satellites used in this study and appends them to a single dataframe. 
    '''
    #--------------------------------#
    
    tracked = pd.DataFrame()
    keys = get_keys()
    for key in keys:
        tracked1 = pd.read_hdf(f'{rootPath}Stellar_Feedback_Code/SNeData/tracked_particles_v3.hdf5', key=key)
        tracked['key'] = key
        tracked = pd.concat([tracked, tracked1])

    print(f'> Returning (tracked) for all available satellites <')
    return tracked



def calc_ejected_expelled(sim, haloid, save=True, verbose=True):
    '''
    -> Identifies gas particles meeting 'ejection' and 'expulsion' criteria, as well as those that have been cooled and
        reaccreted by their respective satellites.
    '''
    #--------------------------------#
    
    import tqdm
    data = read_tracked_particles(sim, haloid, verbose=verbose)

    if verbose: print(f'Now compiling ejected/expelled particles for {sim}-{haloid}...')
    ejected = pd.DataFrame()
    cooled = pd.DataFrame()
    expelled = pd.DataFrame()
    accreted = pd.DataFrame()
    
    pids = np.unique(data.pid)
    for pid in tqdm.tqdm(pids):
        dat = data[data.pid==pid]

        sat_disk = np.array(dat.sat_disk, dtype=bool)
        sat_halo = np.array(dat.sat_halo, dtype=bool)
        in_sat = np.array(dat.in_sat, dtype=bool)
        outside_sat = ~in_sat

        host_halo = np.array(dat.host_halo, dtype=bool)
        host_disk = np.array(dat.host_disk, dtype=bool)
        IGM = np.array(dat.IGM, dtype=bool)
        other_sat = np.array(dat.other_sat, dtype=bool)
        
        time = np.array(dat.time,dtype=float)



        for i,t2 in enumerate(time[1:]):
                i += 2
                if sat_disk[i-1] and sat_halo[i]:
                    out = dat[time==t2].copy()
                    ejected = pd.concat([ejected, out])
                    
                if sat_halo[i-1] and sat_disk[i]:
                    out = dat[time==t2].copy()
                    cooled = pd.concat([cooled, out])
                    
                if in_sat[i-1] and outside_sat[i]:
                    out = dat[time==t2].copy()
                    if sat_halo[i-1]:
                        out['state1'] = 'sat_halo'
                    elif sat_disk[i-1]:
                        out['state1'] = 'sat_disk'
                        
                    expelled = pd.concat([expelled, out])
                    
                if outside_sat[i-1] and in_sat[i]:
                    out = dat[time==t2].copy()
                    if sat_halo[i]:
                        out['state2'] = 'sat_halo'
                    elif sat_disk[i]:
                        out['state2'] = 'sat_disk'
                        
                    accreted = pd.concat([accreted, out])
                  

    # apply the calc_angles function along the rows of ejected and expelled
    print('Calculating ejection angles')
    ejected = ejected.apply(calc_angles, axis=1)
    print('Calculating expulsion angles')
    expelled = expelled.apply(calc_angles, axis=1)
    
#     # apply the calc_angles function along the rows of ejected and expelled
#     print('Calculating ejection angles (for tidal force)')
#     ejected = ejected.apply(calc_angles_tidal, axis=1)
#     print('Calculating expulsion angles (for tidal force)')
#     expelled = expelled.apply(calc_angles_tidal, axis=1)
    
    if save:
        key = f'{sim}_{str(int(haloid))}'
        filepath = f'{rootPath}Stellar_Feedback_Code/SNeData/ejected_particles.hdf5'
        print(f'Saving {key} ejected particle dataset to {filepath}')
        ejected.to_hdf(filepath, key=key)
        
        filepath = f'{rootPath}Stellar_Feedback_Code/SNeData/cooled_particles.hdf5'
        print(f'Saving {key} cooled particle dataset to {filepath}')
        cooled.to_hdf(filepath, key=key)

        filepath = f'{rootPath}Stellar_Feedback_Code/SNeData/expelled_particles.hdf5'
        print(f'Saving {key} expelled particle dataset to {filepath}')
        expelled.to_hdf(filepath, key=key)
                
        filepath = f'{rootPath}Stellar_Feedback_Code/SNeData/accreted_particles.hdf5'
        print(f'Saving {key} accreted particle dataset to {filepath}')
        accreted.to_hdf(filepath, key=key)
        
        
    print(f'> Returning (ejected, cooled, expelled, accreted) datasets <')

    return ejected, cooled, expelled, accreted



def calc_discharged(sim, haloid, save=True, verbose=True):
    '''
    -> Identifies discharged particles (collecting their properties predischarge into 'predischarge', and postdischarge into  
        'discharged'. 
    -> Further identifies all gas particles that have been accreted onto their respective satellite's disk; these are 
        collected in 'dsrg_accreted'. (This is a basic calculation. See 'calc_reaccreted' specifically for reaccreted particles.)
    '''
    #--------------------------------#
    
    import tqdm
    data = read_tracked_particles(sim, haloid, verbose=verbose)

    if verbose: print(f'Now compiling discharged particles for {sim}-{haloid}...')
    predischarged = pd.DataFrame() # discharged gas particles but with their properties before discharge.
    discharged = pd.DataFrame() # gas particles that are removed from their satellite's disk.
    dsrg_accreted = pd.DataFrame() # all accreted gas, irrespective of whether or not it originated from the disk.
    
        
    pids = np.unique(data.pid)
    for pid in tqdm.tqdm(pids):
        dat = data[data.pid==pid]

        sat_disk = np.array(dat.sat_disk, dtype=bool)
        in_sat = np.array(dat.in_sat, dtype=bool)
        outside_disk = ~sat_disk
        
        time = np.array(dat.time, dtype=float)

        for i,t2 in enumerate(time[1:]):
                i += 1
                if (sat_disk[i-1] and outside_disk[i]):
                    in_ = dat[time==time[i-1]].copy()
                    out = dat[time==t2].copy()
                    predischarged = pd.concat([predischarged, in_])
                    discharged = pd.concat([discharged, out])
                    
                   
                # specifically picking out gas accreted after one time step. (We use the 'dsrg' identifier to avoid confusion 
                # with the gas dataset from 'calc_ejected_expelled'.)
                if (outside_disk[i-1] and sat_disk[i]):
                    acc = dat[time==t2].copy()
                    dsrg_accreted = pd.concat([dsrg_accreted, acc])
                 

    # apply the calc_angles function along the rows of discharged particles.
    print('(1) Calculating angles pre-discharge.')
    predischarged = predischarged.apply(calc_angles, axis=1)
    print('(2) Calculating angles post-discharge.')
    discharged = discharged.apply(calc_angles, axis=1)
    
    
    # preallocating column that will give a boolean 'True' if SNe heating is active, and 'False' otherwise.    
    hot = {'heating': ""} 
    discharged = discharged.join(pd.DataFrame(columns=heating))

    print('Appending `heating` boolean to discharged.')
    coolontime = np.asarray(discharged.coolontime)
    time = np.asarray(predischarged.time) # use predischarged here b/c we want to check particle SNe-heating prior to discharge.
    discharged['hot'] = coolontime > time
    
    
    if save:
        key = f'{sim}_{str(int(haloid))}'
        filepath = f'{rootPath}Stellar_Feedback_Code/SNeData/predischarged_particles.hdf5'
        print(f'Saving {key} predischarged particle dataset to {filepath}')
        predischarged.to_hdf(filepath, key=key)
 
        filepath = f'{rootPath}Stellar_Feedback_Code/SNeData/discharged_particles.hdf5'
        print(f'Saving {key} discharged particle dataset to {filepath}')
        discharged.to_hdf(filepath, key=key)
        
        filepath = f'{rootPath}Stellar_Feedback_Code/SNeData/dsrg_accreted_particles.hdf5'
        print(f'Saving {key} accreted particle dataset to {filepath}')
        dsrg_accreted.to_hdf(filepath, key=key)
        
        
    print(f'> Returning (predischarged, discharged, accreted) datasets <')

    return predischarged, discharged, dsrg_accreted



def calc_heated(sim, haloid, save=True, verbose=True):
    '''
    -> Identifies discharged gas particles that experienced supernova heating at time of discharge, recorded in 'heated'. The 
        properties of these particles prior to discharge are recorded in 'preheated'. 
    '''
    #--------------------------------#
    
    import tqdm
    data = read_tracked_particles(sim, haloid, verbose=verbose)
    
    if verbose: print(f'Now compiling heated particles for {sim}-{haloid}...')
    
    preheated = pd.DataFrame() # pre-discharge properties for heated gas.
    heated = pd.DataFrame() # discharged gas particles that experienced SNe heating just prior to removal from disk.

    
    pids = np.unique(data.pid)
    for pid in tqdm.tqdm(pids):
        dat = data[data.pid==pid]

        sat_disk = np.array(dat.sat_disk, dtype=bool)
        in_sat = np.array(dat.in_sat, dtype=bool)
        outside_disk = ~sat_disk
        
        time = np.array(dat.time, dtype=float)
        coolontime = np.array(dat.coolontime, dtype=float)


        for i,t2 in enumerate(time[1:]):
                i += 1
                if sat_disk[i-1] and outside_disk[i] and (coolontime[i] > time[i-1]):
                    in_ = dat[time==time[i-1]].copy()
                    out = dat[time==t2].copy()
                    preheated = pd.concat([preheated, in_])
                    heated = pd.concat([heated, out])
                 

    # apply the calc_angles function along the rows of discharged particles.
    print('Calculating heated angles')
    preheated = preheated.apply(calc_angles, axis=1)
    heated = heated.apply(calc_angles, axis=1)
   
    
    if save:
        key = f'{sim}_{str(int(haloid))}'
        filepath = f'{rootPath}Stellar_Feedback_Code/SNeData/preheated_particles.hdf5'
        print(f'Saving {key} preheated particle dataset to {filepath}')
        preheated.to_hdf(filepath, key=key)
        
        filepath = f'{rootPath}Stellar_Feedback_Code/SNeData/heated_particles.hdf5'
        print(f'Saving {key} heated particle dataset to {filepath}')
        heated.to_hdf(filepath, key=key)
        
        
    print(f'> Returning (preheated, heated) datasets <')

    return preheated, heated



def calc_reaccreted(sim, haloid, save=True, verbose=True):
    '''
    -> Screening the 'accreted' df compiled by 'calc_discharge()' specifically for gas particles that are reaccreted 
        (that is, gas discharged from its satellite's disk, but which is accreted back onto the disk at a later timestep.)
    '''
    #--------------------------------#

    import tqdm
    key = f'{sim}_{str(int(haloid))}'

    path = f'{rootPath}Stellar_Feedback_Code/SNeData/discharged_particles.hdf5'
    discharged = pd.read_hdf(path, key=key)
    
    path = f'{rootPath}Stellar_Feedback_Code/SNeData/dsrg_accreted_particles.hdf5'
    accreted = pd.read_hdf(path, key=key)


    if verbose: print(f'Now computing reaccreted particles for {sim}-{haloid}...')
    reaccreted = pd.DataFrame() # gas accreted following a discharge event.
  
    # defining attribute giving the length of time between discharge and accretion event for each gas particle:
    recycleTime = {'recycleTime': ""} 
    accreted = accreted.join(pd.DataFrame(columns=recycleTime)) 
    discharged = discharged.join(pd.DataFrame(columns=recycleTime))
    # ensuring that our new accreted dataframe inherits sne heating identified 'hot'.
    hot = {'hot':  ""}
    accreted = accreted.join(pd.DataFrame(columns=hot))
    discharged = discharged.join(pd.DataFrame(columns=hot))    
        
        
    pids = np.unique(discharged.pid) # quicker to use 'discharged' because fewer unique particles.
    for pid in tqdm.tqdm(pids):
        dis = discharged[discharged.pid==pid]
        acc = accreted[accreted.pid==pid]

        dTime = np.asarray(dis.time)
        aTime = np.asarray(acc.time)


        # removing initial accretion event if it does not correspond to a discharge; else no alterations.
        # check to ensure that our discharge event actually has an accretion:
        if (len(dTime) == 0):
            print('Problem: No instance of discharge per particle for '+str(pid))
            continue
        if (len(aTime) == 0): # if no instances of accretion, move on to next particle
            if (len(dis) != 1):
                print('Problem: multiple discharges but no accretion events for '+str(pid))
                continue
            aCache = dis[0]
            aCache['recycleTime'] = np.array([-1])
            reaccreted = pd.concat([reaccreted, aCache])
            continue
        if (aTime[0] < dTime[0]): # In there is an initial accretion
            aCache = acc[1:]
        else:
            aCache = acc

        dCache = dis #[0:len(aCache)]
    
        aCache['recycleTime'] = np.array(aCache['time']) - (np.array(dCache['time'])[0:len(aCache)])
#         print(dCache['time'],aCache['time'], aCache['recycleTime'])
        aCache['hot'] = dCache['hot']
        if len(dCache) != len(aCache):
            dCache.iloc[-1]['recycleTime'] = -1
            aCache = aCache.append(dCache.iloc[-1])
            
    
        reaccreted = pd.concat([reaccreted, aCache])
        

    if save:
        key = f'{sim}_{str(int(haloid))}'
        filepath = f'{rootPath}Stellar_Feedback_Code/SNeData/reaccreted.hdf5'
        print(f'Saving {key} reaccreted particle dataset to {filepath}')
        reaccreted.to_hdf(filepath, key=key)
        
        
        
    print(f'> Returning (reaccreted) dataset <')

    return reaccreted



def read_all_ejected_expelled():
    '''
    -> Reads ejected, cooled, expelled, and accreted into workable dataframes for analysis in notebooks.
    '''
    #--------------------------------#
    
    ejected = pd.DataFrame()
    cooled = pd.DataFrame()
    expelled = pd.DataFrame()
    accreted = pd.DataFrame()
    keys = get_keys()
    for key in keys:
        if key in ['h148_3','h148_28','h242_12']: continue;
            
        ejected1 = pd.read_hdf(f'{rootPath}Stellar_Feedback_Code/SNeData/ejected_particles.hdf5', key=key)
        ejected1['key'] = key
        ejected = pd.concat([ejected, ejected1])
        cooled1 = pd.read_hdf(f'{rootPath}Stellar_Feedback_Code/SNeData/cooled_particles.hdf5', key=key)
        cooled1['key'] = key
        cooled = pd.concat([cooled, cooled1])
        expelled1 = pd.read_hdf(f'{rootPath}Stellar_Feedback_Code/SNeData/expelled_particles.hdf5', key=key)
        expelled1['key'] = key
        expelled = pd.concat([expelled, expelled1])
        accreted1 = pd.read_hdf(f'{rootPath}Stellar_Feedback_Code/SNeData/accreted_particles.hdf5', key=key)
        accreted1['key'] = key
        accreted = pd.concat([accreted, accreted1])

    print(f'> Returning (ejected, cooled, expelled, accreted) for all available satellites <')
    return ejected, cooled, expelled, accreted



def read_all_discharged():
    '''
    -> Reads predischarged, discharged, reaccreted, preheated, and heated into workable dataframes for analysis in notebooks.
    '''
    #--------------------------------#
    
    predischarged = pd.DataFrame()
    discharged = pd.DataFrame()
    reaccreted = pd.DataFrame()
    preheated= pd.DataFrame()
    heated= pd.DataFrame()
    
    keys = get_keys()

    for i,key in enumerate(keys):
        i += 1
        sim = key[:4]
        haloid = int(key[5:])
        predischarged1 = pd.read_hdf(f'{rootPath}Stellar_Feedback_Code/SNeData/predischarged_particles.hdf5', key=key)
        predischarged1['key'] = key
        predischarged = pd.concat([predischarged, predischarged1])
        
        discharged1 = pd.read_hdf(f'{rootPath}Stellar_Feedback_Code/SNeData/discharged_particles.hdf5', key=key)
        discharged1['key'] = key
        discharged = pd.concat([discharged, discharged1])
        
        reaccreted1 = pd.read_hdf(f'{rootPath}Stellar_Feedback_Code/SNeData/reaccreted.hdf5', key=key)
        reaccreted1['key'] = key
        reaccreted = pd.concat([reaccreted, reaccreted1])
  
        preheated1 = pd.read_hdf(f'{rootPath}Stellar_Feedback_Code/SNeData/preheated_particles.hdf5', key=key)
        preheated1['key'] = key
        preheated = pd.concat([preheated, preheated1])
        
        heated1 = pd.read_hdf(f'{rootPath}Stellar_Feedback_Code/SNeData/heated_particles.hdf5', key=key)
        heated1['key'] = key
        heated = pd.concat([heated, heated1])
       
    print(f'> Returning (predischarged, discharged, reaccreted, preheated, heated) <')
    return predischarged, discharged, reaccreted, preheated, heated



def read_accreted():
    '''
    -> Reads reaccreted particles off into workable dataframes for analysis in notebooks.
    '''
    #--------------------------------#
    
    reaccreted = pd.DataFrame()

    keys = get_keys()

    for i,key in enumerate(keys):
        i += 1
        sim = key[:4]
        haloid = int(key[5:])
        reaccreted1 = pd.read_hdf(f'{rootPath}Stellar_Feedback_Code/SNeData/reaccreted.hdf5', key=key)
        reaccreted1['key'] = key
        reaccreted = pd.concat([reaccreted, reaccreted1])


    print(f'> Returning (reaccreted) for all available satellites <')
    return reaccreted
