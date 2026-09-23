# Pressure-series LJ trajectory data

This archive contains five isothermal pressure cases at target reduced
pressures P* = 0.10, 0.20, 0.30, 0.40, and 0.50, with T* = 2.0 and 500
particles. The simulation box uses periodic boundaries in all three axes.

## Folders

- preview/: five trajectories used by the 3D animation. The NVT production
  segment spans 0–100 reduced time units. With timestep 0.005 and a dump
  every 250 steps, each trajectory has 81 frames at 1.25-time-unit intervals.
- analysis/: five longer NVT trajectories used for diffusion analysis. The
  production segment spans 0–500 reduced time units. With a dump every
  2,500 steps, each trajectory has 41 frames at 12.5-time-unit intervals.
  Each case includes its corresponding msd.csv and thermo.csv.
- analysis/summary.json and analysis/diffusion_vs_pressure.csv: derived
  diffusion coefficients and pressure-series results.

The preview and analysis outputs are separate simulation runs. Do not join
them end-to-end as though they were one continuous trajectory.

## LAMMPS trajectory fields

Each trajectory.lammpstrj frame contains id type x y z xu yu zu vx vy vz.
The x/y/z coordinates are wrapped or near the periodic box; xu/yu/zu are
unwrapped coordinates for displacement analysis; vx/vy/vz are velocities.
Types 1 and 2 are physically identical tracer labels assigned according to
the left and right half of the box at the start of NVT production.
In the older 500-time-unit analysis exports, one periodic-boundary particle
in each of the P*=0.10 and P*=0.40 first frames appears across the displayed
half-box boundary from its tracer label. The 100-time-unit preview exports
have no such first-frame mismatch. This affects visualization labels only;
the two types have identical interactions and mass.

Time is t* = timestep × 0.005 after resetting the production step counter
to zero. The animation's illustrative argon mapping uses approximately
2.156349 ps per reduced time unit. The source LAMMPS input is
lammps/in.lj_diffusion_pressure in the project repository.
