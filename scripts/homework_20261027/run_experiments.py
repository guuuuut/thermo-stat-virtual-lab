#!/usr/bin/env python3
"""Single-GPU, restartable teaching data generation. Standard library only."""
from pathlib import Path
import argparse,csv,hashlib,json,os,subprocess,time,traceback
from concurrent.futures import ThreadPoolExecutor,as_completed

BASE=Path.home()/'visual_lab_course_20261027'
ROOT=BASE/'experiments'
DT=.005

def case_list():
    jobs=[]
    for p in [.1,.2,.3,.4,.5]:
        for r in range(1,4):
            jobs.append(dict(id=f'pressure_p{round(p*100):03}_r{r}',family='pressure',temperature=2.,density=p/2,cells=8,pressure=p,seed=713000+1009*r,replicate=r,production_steps=100000))
    for t in [1.5,2.,3.]:
        for r in range(1,4):
            jobs.append(dict(id=f'temperature_t{round(t*10):02}_r{r}',family='temperature',temperature=t,density=.1,cells=8,seed=815000+1009*r,replicate=r,production_steps=100000,speeds=True,dense=(t==2.)))
    for cells in [4,6,8,12]:
        n=4*cells**3
        for r in range(1,6):
            jobs.append(dict(id=f'size_n{n:04}_r{r}',family='size',temperature=1.5,density=.8,cells=cells,seed=916000+1009*r,replicate=r,production_steps=200000))
    for r in range(1,4):
        jobs.append(dict(id=f'boundary_reflect_r{r}',family='boundary',temperature=2.,density=.1,cells=8,seed=815000+1009*r,replicate=r,production_steps=100000,reflect=True))
    return jobs

def input_text(c):
    t=c['temperature'];rho=c['density'];cells=c['cells'];seed=c['seed'];prod=c['production_steps'];sample=c.get('sample_interval',100)
    lines=[
        '# LJ teaching experiment. All values are in reduced LJ units.',
        'clear','units lj','dimension 3','boundary p p p','atom_style atomic',
        f'lattice fcc {rho:.12g}',f'region box block 0 {cells} 0 {cells} 0 {cells} units lattice',
        'create_box 1 box','create_atoms 1 box','mass 1 1.0',
        'pair_style lj/cut 2.5','pair_coeff 1 1 1.0 1.0 2.5','pair_modify shift yes',
        'neighbor 0.3 bin','neigh_modify delay 0 every 1 check yes',f'timestep {DT}',
        f'velocity all create {t} {seed} mom yes rot no dist gaussian',
        'thermo 1000','thermo_style custom step atoms temp press density vol pe ke etotal',
        'thermo_modify norm no flush yes',
    ]
    if 'pressure' in c:
        p=c['pressure'];lines.append(f'fix preparation all npt temp {t} {t} 0.5 iso {p} {p} 5.0 drag 1.0')
    else:lines.append(f'fix preparation all nvt temp {t} {t} 1.0')
    lines += [f'run {c.get("preparation_steps",30000)}','unfix preparation']
    if c.get('reflect'):
        lines += ['set group all image 0 0 0','change_box all boundary f f f','fix walls all wall/reflect xlo EDGE xhi EDGE ylo EDGE yhi EDGE zlo EDGE zhi EDGE units box']
    lines += [f'fix settling all nvt temp {t} {t} 1.0',f'run {c.get("settling_steps",10000)}','unfix settling',
        'reset_timestep 0',f'fix production all nvt temp {t} {t} 1.0','compute displacement all msd com yes',
        'variable out_step equal step','variable out_time equal time','variable out_temp equal temp','variable out_press equal press',
        'variable out_rho equal density','variable out_vol equal vol','variable out_msd equal c_displacement[4]',
        'variable out_pe equal pe/atoms','variable out_ke equal ke/atoms','variable out_e equal etotal/atoms',
        f'fix thermo_output all print {sample} "${{out_step}},${{out_time}},${{out_temp}},${{out_press}},${{out_rho}},${{out_vol}},${{out_pe}},${{out_ke}},${{out_e}}" file thermo.csv screen no title "step,time,temp,pressure,density,volume,pe_per_atom,ke_per_atom,etotal_per_atom"',
        f'fix msd_output all print {sample} "${{out_step}},${{out_time}},${{out_msd}}" file msd.csv screen no title "step,time,msd"',
    ]
    if c.get('speeds'):
        lines += ['dump speed_samples all custom 2000 speed_samples.lammpstrj id vx vy vz','dump_modify speed_samples sort id format float %.10g']
    if c.get('dense'):
        lines += ['group tracers id <= 512','dump dense tracers custom 4 dense_velocity.lammpstrj id vx vy vz','dump_modify dense sort id format float %.10g','compute vc all vacf',
            'variable out_vacf equal c_vc[4]',
            'fix vacf_output all print 4 "${out_time},${out_vacf}" file vacf_single_origin.csv screen no title "time,vacf"',
            'run 20000','undump dense','unfix vacf_output',f'run {prod-20000}']
    else:lines.append(f'run {prod}')
    lines += ['write_data final.data','write_restart final.restart']
    return '\n'.join(lines)+'\n'

def run_case(c,cpu=False):
    folder=ROOT/c['id'];folder.mkdir(parents=True,exist_ok=True)
    if (folder/'complete.json').exists():
        previous=json.loads((folder/'complete.json').read_text())
        if previous['case']!=c or (folder/'input.lmp').read_text()!=input_text(c):
            raise RuntimeError('Existing case differs from requested input; use a new case id: '+c['id'])
        return previous
    (folder/'input.lmp').write_text(input_text(c),encoding='ascii');(folder/'metadata.json').write_text(json.dumps(c,indent=2))
    cmd=[str(BASE/'install/bin/lmp' if cpu else BASE/'bin/lmp-gpu'),'-in','input.lmp','-log','log.lammps','-screen','screen.txt']
    env=os.environ.copy();env['CUDA_VISIBLE_DEVICES']='0';env['OMP_NUM_THREADS']='4' if not cpu else '1'
    start=time.time()
    with (folder/'launcher.log').open('w') as f:p=subprocess.run(cmd,cwd=folder,env=env,stdout=f,stderr=subprocess.STDOUT)
    text=(folder/'screen.txt').read_text(errors='replace') if (folder/'screen.txt').exists() else (folder/'launcher.log').read_text()
    if p.returncode or 'ERROR' in text:raise RuntimeError(f'{c["id"]} exit={p.returncode}: {text[-2000:]}')
    if not cpu and ('Device Time Info' not in text or 'Using acceleration for lj/cut' not in text or 'Device 0: NVIDIA GeForce RTX 5090' not in text):
        raise RuntimeError('GPU execution not confirmed: '+c['id'])
    result=dict(case=c,elapsed_seconds=time.time()-start,command=cmd,warnings=[ln for ln in text.splitlines() if 'WARNING' in ln],gpu_confirmed=not cpu,
        outputs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.name in ['thermo.csv','msd.csv']})
    (folder/'complete.json').write_text(json.dumps(result,indent=2));return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--smoke',action='store_true');ap.add_argument('--family');ap.add_argument('--workers',type=int,default=3);args=ap.parse_args()
    ROOT.mkdir(exist_ok=True)
    if args.smoke:
        c=dict(id='smoke_gpu',family='smoke',temperature=2.,density=.1,cells=5,seed=27102026,replicate=1,production_steps=200,preparation_steps=20,settling_steps=20,sample_interval=10)
        print(json.dumps(run_case(c)),flush=True);cpu=dict(c,id='smoke_cpu');print(json.dumps(run_case(cpu,cpu=True)),flush=True)
        return
    jobs=case_list();(ROOT/'manifest.json').write_text(json.dumps(dict(date='2026-10-27',dt=DT,gpu=0,lammps_version='stable_30Sep2026',precision='double',gpu_neighbors=False,omp_threads=4,cases=jobs),indent=2))
    selected=[c for c in jobs if not args.family or c['family']==args.family]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(run_case,c):c for c in selected}
        for i,future in enumerate(as_completed(futures),1):
            c=futures[future];result=future.result()
            (ROOT/'progress.json').write_text(json.dumps(dict(completed=i,total=len(selected),last_completed=c['id'],updated=time.time(),workers=args.workers,gpu=0)))
            print(f'{i}/{len(selected)} {c["id"]}: {result["elapsed_seconds"]:.2f}s',flush=True)
    if all((ROOT/c['id']/'complete.json').exists() for c in jobs):
        (ROOT/'all.complete').write_text(str(time.time()))
if __name__=='__main__':
    try:main()
    except Exception:
        traceback.print_exc();raise
