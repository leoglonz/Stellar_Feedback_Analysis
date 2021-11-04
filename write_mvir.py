from analysis import *
import tqdm

keys = ['h148_13','h148_28','h148_37','h148_45','h148_68','h148_80','h148_283',
        'h148_278','h148_329','h229_20','h229_22','h229_23','h229_27','h229_55',
        'h242_24','h242_41','h242_80','h329_33','h329_137']

print('Updating M_vir attributes for the following keys:', keys)

for key in keys:
    sim = str(key[:4])
    haloid = int(key[5:])

    data = read_tracked_particles(sim, haloid)
    timesteps = read_timesteps(sim)
    ts = timesteps[timesteps.z0haloid==haloid]
    ts = ts.rename({'mass':'sat_Mvir'}, axis=1)
    ts = ts[['t','sat_Mvir']]

    data = pd.merge_asof(data, ts.sort_values('t'), left_on='time', right_on='t', direction='nearest', tolerance=1)
    
    filepath = '/home/lonzaric/astro_research/Stellar_Feedback_Code/SNeData/tracked_particles_v2.hdf5'
    print(f'Saving {key} tracked_particles datasets to {filepath}')
    data.to_hdf(filepath, key=key)
