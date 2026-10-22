# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Compare four-axis palm and five-axis shoulder/hip-twist candidates [m, rad, s].

Input is build.json from lizard2_palm_spatial_candidate.py. Uses saved Blender motion as an
independent oracle, then the existing URDF tree/FK readers for bounded IK and mesh collision.
Historical fixed-point/level-palm +/-3 degree pitch is a regression diagnostic ONLY, not a gait
requirement. Roll and yaw use the same amplitude as exploratory samples. No dynamics/adoption.
--lock_twist is the fail-before control: the real added axes remain in the asset but are held zero.
--inject_error twist_axis must fail the source/Blender checks, not produce a successful report.
--static_slices samples lf/rr independently: twist lo/0/hi x elbow/knee 9 x wrist/ankle 5.
Other movable joints stay zero, root rotation stays identity, and neutral palm mesh minima
set one shared root height. Limits are URDF placeholders, not approved ROM. No trajectory,
dynamics, safety clearance or safe-domain verdict. --self_check needs no candidate;
--local_path explores lf/rr separately with all five axes, using 1% of the shorter actual
bone segment per task step. Eight points per phase, 1e-5 m numerical task tolerance,
0.05 rad joint steps, three deterministic attempts of at most 200 actual residual calls.
Endpoints and joint-linear midpoints are checked; contact solves both within the same call budget.
Failure stops that leg. Midpoint contact does not establish contact along a whole segment. No time mapping.
--self_check --break_test <case> intentionally fails the corresponding regression assertion.
All sampling modes register input/code ownership before collection and retain run.json on
failure. --work_id, --owner and --retention_reason override ownership defaults. Existing
reports keep their geometry schema. Python optimization is refused before input reads.
"""

import argparse
import getpass
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

if sys.flags.optimize != 0:
    raise RuntimeError('palm_spatial_probe does not support Python optimization (-O/-OO or PYTHONOPTIMIZE); '
                       'identity validation requires assertions')

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "rl_exp/tools/verify"))
import check_leg_reachability as reach  # noqa: E402
import palm_motion_boundaries as motion  # noqa: E402
sys.path.insert(0, str(REPO / "rl_exp/tools/runrecord"))
from binding import sha256_file as digest  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from artifact_paths import ArtifactPaths, artifact_path  # noqa: E402
from artifact_run import ArtifactRun  # noqa: E402

csc = motion.gait.csc
names = reach.joint_names


class Leg:
    """Read the actual ordered tree and express a sole point and upward normal [m]."""

    def __init__(self, path, leg, naming):
        self.leg = leg
        self.urdf = csc.load_urdf(path)
        self.names = reach.chain_joint_names(path, leg, naming)
        self.chain = reach.load_chain(path, leg, naming)
        self.end = names.end_link(leg, naming)
        self.root = csc.fk(self.urdf['joints'], self.urdf['joints'][self.names[0]]['parent'], {})
        self.lo = np.array([s['limits'][0] for s in self.chain])
        self.hi = np.array([s['limits'][1] for s in self.chain])
        pose = self.pose(np.zeros(len(self.names)))
        self.vertices = csc.read_obj(self.urdf['links'][self.end]['collision'])
        world = self.vertices @ pose[:3, :3].T + pose[:3, 3]
        self.sole_local = (world[world[:, 2] < world[:, 2].min() + 1e-3].mean(0) - pose[:3, 3]) @ pose[:3, :3]
        self.neutral, _ = self.sole(np.zeros(len(self.names)))

    def pose(self, q):
        return csc.fk(self.urdf['joints'], self.end, dict(zip(self.names, q)))

    def sole(self, q):
        pose = self.pose(q)
        return pose[:3, :3] @ self.sole_local + pose[:3, 3], pose[:3, 2]

    def solve(self, point, up, guess, lock_twist=False):
        free = [i for i, name in enumerate(self.names) if not (lock_twist and '_twist_joint' in name)]

        def expand(x):
            q = np.zeros(len(self.names))
            q[free] = x
            return q

        def residual(x):
            p, n = self.sole(expand(x))
            # Consistent old/new scaling; full normal rejects an upside-down solution.
            return np.r_[(p - point) / 1e-4, (n - up) / np.radians(2)]

        # At a cycle's neutral crossing, roundoff-sized starts can collapse TRF's initial
        # trust radius. Exact zero gives the solver its normal initial radius.
        start = guess[free].copy()
        if np.linalg.norm(start) < 1e-8:
            start[:] = 0
        result = least_squares(residual, start, bounds=(self.lo[free], self.hi[free]),
                               xtol=1e-12, ftol=1e-12, gtol=1e-12, max_nfev=300)
        return expand(result.x)


def check_blender(build, urdf, inject):
    """Compare saved Blender pivots/mesh samples against the independent URDF FK [m]."""
    if inject:
        urdf['joints']['lf_shoulder_twist_joint']['axis'] = np.array([0., 0., 1.])
    candidate = artifact_path(Path(build['candidate_urdf']))
    root = ET.parse(candidate).getroot()
    visual = {}
    for link in root.findall('link'):
        mesh = link.find('visual/geometry/mesh')
        if mesh is not None:
            visual[link.get('name')] = cKDTree(csc.read_obj(candidate.parent / mesh.get('filename')))
    pivot_error, mesh_error = 0., 0.
    for snapshot in build['snapshots']:
        q = snapshot['q_rad']
        # Exporter uses world-neutral axes and subtracts the base bone head from positions.
        base_origin = np.array(snapshot['pivots']['base_link'])
        for name, point in snapshot['pivots'].items():
            frame = csc.fk(urdf['joints'], name, q)
            pivot_error = max(pivot_error, float(np.linalg.norm(frame[:3, 3] - (point - base_origin))))
        for row in snapshot['meshes'].values():
            frame = csc.fk(urdf['joints'], row['link'], q)
            local = (np.array(row['points']) - base_origin - frame[:3, 3]) @ frame[:3, :3]
            mesh_error = max(mesh_error, float(visual[row['link']].query(local)[0].max()))
    # Source mesh/URDF positions are rounded to six decimals; Blender uses float32.
    assert pivot_error < 1e-5 and mesh_error < 1e-5, (pivot_error, mesh_error)
    return {'max_pivot_error_m': pivot_error, 'max_visual_sample_error_m': mesh_error,
            'cases': len(build['snapshots']), 'budget_m': 1e-5,
            'budget_basis': 'six-decimal exported positions plus float32 multi-link transforms'}


def measure(leg, q, rotate):
    point, normal = leg.sole(q)
    return {'q_rad': q.tolist(), 'position_error_m': float(np.linalg.norm(rotate @ point - leg.neutral)),
            'tilt_deg': float(np.degrees(np.arccos(np.clip((rotate @ normal)[2], -1, 1)))),
            'limit_margin_deg': float(np.degrees(np.minimum(q - leg.lo, leg.hi - q).min()))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build_report', type=Path)
    parser.add_argument('--output_dir', type=Path)
    parser.add_argument('--work_id', default='diagnostic-artifact-lifecycle')
    parser.add_argument('--owner', default=getpass.getuser())
    parser.add_argument('--retention_reason', default='Bound spatial geometry diagnostic and failure evidence.')
    parser.add_argument('--local_path', action='store_true')
    parser.add_argument('--static_slices', action='store_true')
    parser.add_argument('--refine_slices', action='store_true')
    parser.add_argument('--source_report', type=Path)
    parser.add_argument('--angle_resolution', type=float)
    parser.add_argument('--self_check', action='store_true')
    parser.add_argument('--break_test', choices=('misaligned', 'missing_twist', 'ground', 'solid', 'zero_trigger',
                                               'refine_state', 'refine_shrink', 'local_budget',
                                               'local_ground', 'local_step', 'local_closure', 'local_stop',
                                               'local_contact', 'local_task'))
    parser.add_argument('--lock_twist', action='store_true')
    parser.add_argument('--inject_error', choices=('twist_axis',))
    args = parser.parse_args()
    if args.local_path and (args.static_slices or args.refine_slices or args.self_check
                            or args.lock_twist or args.inject_error
                            or args.source_report is not None or args.angle_resolution is not None):
        parser.error('--local_path cannot use other mode controls')
    if args.refine_slices:
        if args.static_slices or args.lock_twist or args.inject_error or args.self_check:
            parser.error('--refine_slices cannot use static/history/self_check controls')
        if args.source_report is None or args.angle_resolution is None:
            parser.error('--refine_slices requires --source_report and explicit --angle_resolution')
        if not np.isfinite(args.angle_resolution) or args.angle_resolution <= 0:
            parser.error('--angle_resolution must be finite and positive [rad]')
    elif args.source_report is not None or args.angle_resolution is not None:
        parser.error('--source_report and --angle_resolution require --refine_slices')
    if args.self_check:
        if args.static_slices or args.lock_twist or args.inject_error:
            parser.error('--self_check cannot be combined with sampling controls')
        _static_self_check(args.break_test)
        return
    if args.break_test:
        parser.error('--break_test requires --self_check')
    if args.build_report is None or args.output_dir is None:
        parser.error('--build_report and --output_dir are required unless --self_check')
    if args.static_slices and (args.lock_twist or args.inject_error):
        parser.error('--static_slices cannot use historical regression controls')
    _run_probe(args)


def _probe_metadata(args, paths):
    inputs = []

    def bind(path, expected=None):
        row = paths.describe(Path(path), expected)
        if row not in inputs:
            inputs.append(row)
        return paths.resolve(Path(path), expected)

    build = json.loads(bind(args.build_report).read_text(encoding='utf-8'))
    candidate = Path(build['candidate_urdf'])
    actual = bind(candidate, build['candidate_sha256'])
    bind(candidate.with_suffix('.blend'), build['candidate_blend_sha256'])
    files = build.get('candidate_files_sha256', {})
    modern = args.local_path or args.static_slices or args.refine_slices
    if modern and not files:
        raise ValueError('self-contained candidate hashes required')
    for relative, sha in files.items():
        child = candidate.parent / relative
        if not child.resolve().is_relative_to(candidate.parent.resolve()):
            raise ValueError('candidate binding escapes its directory')
        bind(child, sha)
    if modern and (files.get(candidate.name) != build['candidate_sha256']
                   or files.get(candidate.with_suffix('.blend').name) != build['candidate_blend_sha256']):
        raise ValueError('inconsistent candidate binding')
    urdfs = [actual]
    if not modern:
        for name, sha in build['input_sha256'].items():
            bind(name, sha)
        urdfs.append(bind(build['source_urdf']))
    for urdf in urdfs:
        for mesh in ET.parse(urdf).getroot().iter('mesh'):
            target = (urdf.parent / mesh.get('filename')).resolve()
            if modern and not any(Path(row['location']) == target or
                                  paths.root / row['location'] == target for row in inputs):
                raise ValueError(f'unbound candidate mesh: {target}')
            bind(target)
    if args.refine_slices:
        bind(args.source_report)
    bind(REPO / 'rl_exp/versions/lizard2/assets.json')
    runtime = Path(__file__).resolve().parents[3]
    sources = {Path(module.__file__).resolve() for module in tuple(sys.modules.values())
               if getattr(module, '__file__', None) and Path(module.__file__).is_absolute()
               and str(module.__file__).endswith('.py') and Path(module.__file__).resolve().is_relative_to(runtime)}
    sources.add(Path(__file__).resolve())
    command = [sys.executable, '-B', str(Path(__file__).resolve()), '--build_report', str(args.build_report),
               '--output_dir', str(args.output_dir)]
    for key in ('local_path', 'static_slices', 'refine_slices', 'lock_twist'):
        if getattr(args, key):
            command.append('--' + key)
    for key in ('source_report', 'angle_resolution', 'inject_error', 'work_id', 'owner', 'retention_reason'):
        value = getattr(args, key)
        if value is not None:
            command.extend(['--' + key, str(value)])
    return {'topic': 'palm-spatial-probe', 'work_id': args.work_id, 'owner': args.owner,
            'retention_reason': args.retention_reason, 'command': command, 'inputs': inputs,
            'code': [paths.describe(p) for p in sorted(sources)]}


def _run_probe(args):
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(17, 'fresh isolated output required', str(output))
    paths = ArtifactPaths(storage_root=REPO)
    metadata = _probe_metadata(args, paths)
    required = ['report.json']
    if args.static_slices:
        required.append('static_slices.png')
    elif not (args.local_path or args.refine_slices or args.lock_twist):
        required.append('comparison.png')
    with ArtifactRun(output, paths, metadata, required):
        if args.local_path:
            _local_path(args.build_report, output)
        elif args.refine_slices:
            _refine_slices(args.build_report, args.source_report, output, args.angle_resolution)
        elif args.static_slices:
            _static_slices(args.build_report, output)
        else:
            _historical_probe(args)


def _historical_probe(args):
    output = args.output_dir.resolve()
    build_path = artifact_path(args.build_report)
    build = json.loads(build_path.read_text(encoding='utf-8'))
    candidate = artifact_path(Path(build['candidate_urdf']))
    assert digest(candidate) == build['candidate_sha256']
    assert digest(candidate.with_suffix('.blend')) == build['candidate_blend_sha256']
    for relative, sha in build.get('candidate_files_sha256', {}).items():
        assert digest(candidate.parent / relative) == sha, relative
    for path, sha in build['input_sha256'].items():
        assert digest(artifact_path(Path(path))) == sha, path
    source = artifact_path(Path(build['source_urdf']))
    for path in (source, candidate):
        motion.validate_geometry(path)
    new = {leg: Leg(candidate, leg, names.PALM_SPATIAL_NAMING) for leg in names.LEGS}
    old = {leg: Leg(source, leg, names.PALM_NAMING) for leg in names.LEGS}
    urdf = csc.load_urdf(candidate)
    blender = check_blender(build, urdf, bool(args.inject_error))
    capability = {}
    for leg, model in new.items():
        q = np.zeros(5)
        assert np.linalg.norm(model.neutral - old[leg].neutral) < 1e-10
        # Two independent implementations of transform composition agree away from zero.
        mixed = np.array([.05, -.04, .08, .06, -.03])
        stdlib = model.root @ np.array(reach.chain_frames(model.chain, mixed)[-1])
        assert np.max(np.abs(stdlib - model.pose(mixed))) < 1e-10
        bend = build['definitions'][leg]['bend']
        original_bend = csc.fk(urdf['joints'], bend, {})[:3, 3]
        q[2] = np.radians(10)
        moved_bend = csc.fk(urdf['joints'], bend, dict(zip(model.names, q)))[:3, 3]
        assert np.linalg.norm(moved_bend - original_bend) < 1e-7, 'Twist is not along upper limb'
        displacement = np.linalg.norm(model.sole(q)[0] - model.neutral)
        assert displacement > 1e-3, 'Added joint has no downstream effect'
        ranks = {}
        for label, item in (('old', old[leg]), ('new', model)):
            def task(q):
                p, n = item.sole(q)
                return np.r_[p, n[:2]]
            zero = np.zeros(len(item.names))
            jac = np.column_stack([(task(zero + np.eye(len(zero))[i] * 1e-6)
                                    - task(zero - np.eye(len(zero))[i] * 1e-6)) / 2e-6
                                   for i in range(len(zero))])
            ranks[label] = {'rank': int(np.linalg.matrix_rank(jac, tol=1e-7)),
                            'singular_values_mixed_units': np.linalg.svd(jac, compute_uv=False).tolist()}
        assert ranks['new']['rank'] == 5
        capability[leg] = {'twist_knee_elbow_position_error_m': float(np.linalg.norm(moved_bend - original_bend)),
                           'twist_10deg_sole_displacement_m': float(displacement), 'task_jacobian': ranks}
    # Mirror has a negative sign on the polar long-axis direction, unlike an axial-vector convention.
    mirror_error = 0.
    for left, right in (('lf', 'rf'), ('rl', 'rr')):
        a, b = new[left], new[right]
        signs = motion.gait.mirror_signs(type('Axes', (), {'axes': [np.array(s['axis']) for s in a.chain]})(),
                                        type('Axes', (), {'axes': [np.array(s['axis']) for s in b.chain]})())
        assert np.isfinite(signs).all() and signs[2] == -1
        q = np.array([.05, -.04, .08, .06, -.03])
        pa, na = a.sole(q)
        pb, nb = b.sole(q * signs)
        mirror_error = max(mirror_error, float(np.linalg.norm(pb - pa * [1, -1, 1])),
                           float(np.linalg.norm(nb - na * [1, -1, 1])))
    assert mirror_error < 2e-4, mirror_error  # existing neutral geometry has micrometre asymmetry
    masses = [sum(row['mass'] for row in reach.link_inertials(path).values()) for path in (source, candidate)]
    assert abs(masses[0] - masses[1]) < 1e-10
    rows = []
    for mode, axis in (('pitch', [0, 1, 0]), ('roll', [1, 0, 0]), ('yaw', [0, 0, 1])):
        guesses = {(version, leg): np.zeros(len(models[leg].names))
                   for version, models in (('old', old), ('new', new)) for leg in names.LEGS}
        # Closed cycle includes both extrema and return to neutral.
        for frame, angle in enumerate(3 * np.sin(np.linspace(0, 2 * np.pi, 17))):
            rotate = motion.gait.rotation(np.array(axis, float), np.radians(angle))
            row = {'mode': mode, 'frame': frame, 'body_angle_deg': float(angle), 'root_rotation': rotate.tolist()}
            for version, models in (('old', old), ('new', new)):
                row[version] = {}
                for leg, model in models.items():
                    q = model.solve(rotate.T @ model.neutral, rotate.T @ np.array([0., 0., 1.]),
                                    guesses[version, leg], args.lock_twist and version == 'new')
                    guesses[version, leg] = q
                    row[version][leg] = measure(model, q, rotate)
            rows.append(row)
    maximum = {version: {key: max(row[version][leg][key] for row in rows for leg in names.LEGS)
                         for key in ('position_error_m', 'tilt_deg')}
               for version in ('old', 'new')}
    regression = maximum['new']['position_error_m'] <= 1e-4 and maximum['new']['tilt_deg'] <= 2
    assert maximum['old']['tilt_deg'] > 2, 'The historical failure was not reproduced'
    # Check actual geometry at neutral and both pitch/roll extrema; sparse samples only.
    collision = motion.Collision(urdf, .005)
    remap = {d['abduct']: d['twist'] for d in build['definitions'].values()}
    approved = {frozenset(remap.get(n, n) for n in pair) for pair in motion.gait.APPROVED}
    collision.pairs = [(a, b) for a, b in collision.pairs if frozenset((a, b)) not in approved]
    collisions = []
    if not args.lock_twist:
        for row in [rows[0]] + [r for r in rows if r['mode'] != 'yaw' and abs(r['body_angle_deg']) > 2.999]:
            q = {n: angle for leg, model in new.items() for n, angle in zip(model.names, row['new'][leg]['q_rad'])}
            pairs = collision.check(q)
            collisions.append({'mode': row['mode'], 'body_angle_deg': row['body_angle_deg'],
                               'minimum_gap_m': min(p['gap_lower_m'] for p in pairs),
                               'failures': [p for p in pairs if p['fail']]})
    summary = {'maxima': maximum, 'regression_pass': regression, 'lock_twist': args.lock_twist,
               'capability': capability, 'blender': blender, 'mirror_residual_m_or_unitless': mirror_error,
               'old_new_mass_kg': masses, 'collision_samples': collisions,
               'source_build_report': str(args.build_report.resolve()), 'build_report_sha256': digest(build_path),
               'probe_sha256': digest(__file__), 'rows': rows,
               'limits': 'Kinematics only. 51 samples per leg; collision only five full-body poses. Not a continuous safe domain, gait, dynamics or hardware ROM proof.'}
    (output / 'report.json').write_text(json.dumps(summary, indent=1), encoding='utf-8')
    if not args.lock_twist:
        plot(output, old, new, rows)
    print(json.dumps({'maxima': maximum, 'blender': blender, 'regression_pass': regression,
                      'collision_failures': sum(len(r['failures']) for r in collisions)}, indent=1), flush=True)
    if not regression:
        raise SystemExit('REGRESSION_REJECTED: fixed-point/normal diagnostic still fails')


def _static_axes(model):
    assert len(model.names) == len(model.chain) == len(model.lo) == len(model.hi), 'misaligned chain'
    assert tuple(s['name'] for s in model.chain) == tuple(model.names), 'misaligned chain names'
    assert np.isfinite(model.lo).all() and np.isfinite(model.hi).all()
    assert np.all((model.lo < 0) & (model.hi > 0)), 'neutral zero must be inside limits'
    roles = ('shoulder_twist', 'elbow', 'wrist') if model.leg in ('lf', 'rf') else ('hip_twist', 'knee', 'ankle')
    indices = [model.names.index(f'{model.leg}_{role}_joint') for role in roles]
    grids = []
    for index, count in zip(indices, (3, 9, 5)):
        lo, hi = model.lo[index], model.hi[index]
        grid = np.array([lo, 0., hi]) if count == 3 else np.linspace(lo, hi, count)
        # Preserve both endpoints and count for asymmetric placeholder limits; include exact zero.
        if not np.any(grid == 0):
            grid[np.argmin(np.abs(grid[1:-1])) + 1] = 0.
        assert len(np.unique(grid)) == count and np.all(np.diff(grid) > 0)
        grids.append(grid)
    return indices, grids


def _static_ground(vertices, pose, root):
    world = vertices @ pose[:3, :3].T + pose[:3, 3]
    world = world @ root[:3, :3].T + root[:3, 3]
    assert len(world) and np.isfinite(world).all(), 'invalid collision vertices'
    index = int(np.argmin(world[:, 2]))
    return {'vertex_index': index, 'position_m': world[index].tolist(), 'height_m': float(world[index, 2])}


def _static_pair_readings(rows):
    solid = [r for r in rows if r.get('intersects', False) or r.get('contained', False)]
    positive = [r for r in rows if r['gap_lower_m'] > 0 and r not in solid]
    return solid, positive


def _static_prepare(build_report):
    build_path = artifact_path(build_report)
    build = json.loads(build_path.read_text(encoding='utf-8'))
    assert build['naming'] == 'palm_spatial'
    candidate = artifact_path(Path(build['candidate_urdf'])).resolve()
    files = build['candidate_files_sha256']
    assert files, 'self-contained candidate hashes required'
    bound = {}
    for relative, sha in files.items():
        path = (candidate.parent / relative).resolve()
        assert candidate.parent in path.parents and sha and digest(path) == sha, relative
        bound[path] = sha
    assert bound.get(candidate) == build['candidate_sha256']
    assert bound.get(candidate.with_suffix('.blend')) == build['candidate_blend_sha256']
    # Only consumed candidate artifacts need rereading; source hashes remain provenance in build.json.
    root_xml = ET.parse(candidate).getroot()
    for mesh in root_xml.iter('mesh'):
        assert (candidate.parent / mesh.get('filename')).resolve() in bound, 'unbound mesh'
    motion.validate_geometry(candidate)
    models = {leg: Leg(candidate, leg, names.PALM_SPATIAL_NAMING) for leg in names.LEGS}
    urdf = csc.load_urdf(candidate)
    movable = {j.get('name') for j in root_xml.findall('joint') if j.get('type') != 'fixed'}
    assert movable == {n for n, s in urdf['joints'].items() if s['axis'] is not None}
    for name in movable:
        spec = urdf['joints'][name]
        assert np.isfinite(spec['limits']).all() and spec['limits'][0] <= 0 <= spec['limits'][1], name
        assert np.isfinite(spec['axis']).all() and np.linalg.norm(spec['axis']) > 0, name
    zero = {n: 0. for n in sorted(movable)}
    for model in models.values():
        _static_axes(model)
        mixed = np.linspace(.01, .05, len(model.names))
        independent = model.root @ np.array(reach.chain_frames(model.chain, mixed)[-1])
        assert np.max(np.abs(independent - model.pose(mixed))) < 1e-10, 'chain/FK mismatch'
    blender = check_blender(build, urdf, False)
    # Numerical trigger ONLY: clearance=0 skips all overlapping AABBs in Collision.check.
    collision = motion.Collision(urdf, 1e-9)
    remap = {d['abduct']: d['twist'] for d in build['definitions'].values()}
    assert set(build['definitions']) == set(names.LEGS)
    for leg, model in models.items():
        d = build['definitions'][leg]
        assert d['abduct'] + '_joint' in model.names and d['twist'] + '_joint' in model.names
        assert urdf['joints'][d['twist'] + '_joint']['child'] == d['twist']
    approved = {frozenset(remap.get(n, n) for n in p) for p in motion.gait.APPROVED}
    # Reconstruct exact permitted set: do not inherit stale approved geometry exclusions.
    import itertools
    excluded, pairs = [], []
    for a, b in itertools.combinations(sorted(collision.local), 2):
        direct = csc.jointed_pair(urdf['joints'], a, b)
        if direct or frozenset((a, b)) in approved:
            excluded.append({'pair': [a, b], 'reason': 'direct_connected' if direct else 'approved_abduct_to_twist'})
        else:
            pairs.append((a, b))
    collision.pairs = pairs
    assert pairs, 'no checked collision pairs'
    root = np.eye(4)
    neutral = {leg: _static_ground(m.vertices, m.pose(np.zeros(len(m.names))), root)
               for leg, m in models.items()}
    root[2, 3] = -min(r['height_m'] for r in neutral.values())
    code_paths = [Path(__file__), Path(motion.__file__), Path(motion.gait.__file__),
                  Path(csc.__file__), Path(reach.__file__), Path(names.__file__),
                  REPO / 'rl_exp/tools/runrecord/binding.py']
    identity = {'build_report': str(build_report.resolve()), 'build_report_sha256': digest(build_path),
                'candidate_files_sha256': files, 'source_input_sha256_provenance_only': build['input_sha256'],
                'code_sha256': {str(p.resolve()): digest(p) for p in code_paths}}
    assert all(identity['code_sha256'].values())
    return build, models, urdf, zero, collision, excluded, root, neutral, blender, identity


def _static_slices(build_report, output_dir):
    output = output_dir.resolve()
    build, models, urdf, zero, collision, excluded, root, neutral, blender, identity = _static_prepare(build_report)
    rows, axes = [], {}
    for leg in ('lf', 'rr'):
        model = models[leg]
        indices, grids = _static_axes(model)
        axes[leg] = {model.names[i]: grid.tolist() for i, grid in zip(indices, grids)}
        for ti, twist in enumerate(grids[0]):
            for bi, bend in enumerate(grids[1]):
                for wi, wrist in enumerate(grids[2]):
                    q = zero.copy()
                    q.update({model.names[i]: float(v) for i, v in zip(indices, (twist, bend, wrist))})
                    chain_q = np.array([q[n] for n in model.names])
                    pose = model.pose(chain_q)
                    reference, normal = model.sole(chain_q)
                    lowest = _static_ground(model.vertices, pose, root)
                    all_lowest = {link: _static_ground(verts, csc.fk(urdf['joints'], link, q), root)
                                  for link, (verts, _) in collision.local.items()}
                    pair_rows = collision.check(q)  # root is a common rigid transform: pair distances unchanged
                    solid, positive = _static_pair_readings(pair_rows)
                    world_normal = root[:3, :3] @ normal
                    rows.append({'leg': leg, 'grid_index': [ti, bi, wi], 'q_rad': q,
                                 'twist_context': {'joint': model.names[indices[0]], 'angle_rad': float(twist)},
                                 'bend_joint': model.names[indices[1]], 'bend_angle_rad': float(bend),
                                 'distal_joint': model.names[indices[2]], 'distal_angle_rad': float(wrist),
                                 'end_reference_point_m': (root[:3, :3] @ reference + root[:3, 3]).tolist(),
                                 'end_reference_displacement_m': (root[:3, :3] @ (reference - model.neutral)).tolist(),
                                 'palm_normal': world_normal.tolist(), 'directed_normal_z': float(world_normal[2]),
                                 'back_side_up': bool(world_normal[2] < 0), 'palm_lowest_vertex': lowest,
                                 'minimum_all_collision_height_m': min(r['height_m'] for r in all_lowest.values()),
                                 'bone_geometry': {'thigh_shank_angle_deg': reach.thigh_shank_angle(model.chain, chain_q)},
                                 'solid_pairs': solid, 'positive_gap_pairs': positive,
                                 'zero_gap_non_solid_pairs': [r for r in pair_rows if r['gap_lower_m'] == 0 and r not in solid]})
    assert len(rows) == 270
    summary = {'mode': 'sampled_static_slices', 'sample_count': len(rows), 'identity': identity,
               'axes_rad': axes, 'root_transform': root.tolist(), 'neutral_palm_minima_before_root': neutral,
               'fixed_context': 'All other movable joints zero, including other legs, trunk and tail; identity root rotation.',
               'excluded_pairs': excluded, 'checked_pairs': [list(p) for p in collision.pairs],
               'numerical_geometry_trigger_m': collision.clearance, 'safety_clearance_m': None,
               'blender': blender, 'rows': rows,
               'limits': 'Sampled lf/rr slices only; URDF placeholder limits, not ROM. No trajectory, dynamics, PD, speed, continuous safety or safe-domain PASS. Positive gaps may be AABB lower bounds. Numerical trigger is not safety margin; directed normal and ground heights are readings, not tilt rejection.',
               'candidate_limits': build['limits']}
    # Serialize before writing: invalid/nonfinite results must not leave a success report.
    payload = json.dumps(summary, indent=1, allow_nan=False)
    _static_plot(output, rows, axes)
    (output / 'report.json').write_text(payload, encoding='utf-8')
    print(json.dumps({'mode': summary['mode'], 'sample_count': len(rows),
                      'solid_pose_count': sum(bool(r['solid_pairs']) for r in rows),
                      'output_dir': str(output)}, indent=1), flush=True)


def _refine_bracket(low, high, resolution, check):
    """Shrink an opposite-state endpoint bracket [rad], without assuming monotonicity."""
    assert np.isfinite(resolution) and resolution > 0, 'invalid angle resolution'
    assert low['angle_rad'] < high['angle_rad'], 'unordered bracket'
    assert low['target_collision'] != high['target_collision'], 'same-state endpoints'
    while high['angle_rad'] - low['angle_rad'] > resolution:
        width = high['angle_rad'] - low['angle_rad']
        angle = low['angle_rad'] + width / 2
        assert low['angle_rad'] < angle < high['angle_rad'], 'resolution below float spacing'
        middle = check(angle)
        assert middle['angle_rad'] == angle and type(middle['target_collision']) is bool
        if middle['target_collision'] == low['target_collision']:
            low = middle
        else:
            high = middle
        assert high['angle_rad'] - low['angle_rad'] < width, 'bracket did not shrink'
        assert low['target_collision'] != high['target_collision'], 'lost opposite states'
    return low, high


def _refine_slices(build_report, source_report, output_dir, resolution):
    output = output_dir.resolve()
    assert np.isfinite(resolution) and resolution > 0, 'invalid angle resolution'
    source_path = artifact_path(source_report)
    source = json.loads(source_path.read_text(encoding='utf-8'))
    assert source['mode'] == 'sampled_static_slices' and source['sample_count'] == 270
    build, models, urdf, zero, collision, excluded, root, neutral, blender, identity = _static_prepare(build_report)
    old_identity = source['identity']
    assert set(old_identity) == set(identity), 'source identity schema mismatch'
    paths = ArtifactPaths(storage_root=REPO)
    for key in identity.keys() - {'code_sha256'}:
        if key == 'build_report':
            assert paths.same_identity(Path(old_identity[key]), Path(identity[key])), 'source build identity mismatch'
        else:
            assert old_identity[key] == identity[key], f'source identity mismatch: {key}'
    old_code, current_code = old_identity['code_sha256'], identity['code_sha256']
    assert len(old_code) == len(current_code), 'source dependency set mismatch'
    matched = set()
    for path, sha in old_code.items():
        assert isinstance(sha, str) and len(sha) == 64 and all(c in '0123456789abcdef' for c in sha)
        matches = [current for current in current_code if paths.same_identity(Path(path), Path(current))]
        assert len(matches) == 1 and matches[0] not in matched, 'source dependency identity mismatch'
        current = matches[0]
        matched.add(current)
        if not paths.same_identity(Path(current), Path(__file__).resolve()):
            assert sha == current_code[current], f'source dependency changed: {path}'
    assert source['root_transform'] == root.tolist(), 'source root mismatch'
    assert source['neutral_palm_minima_before_root'] == neutral, 'source neutral mismatch'
    assert source['excluded_pairs'] == excluded, 'source exclusions mismatch'
    checked = [list(p) for p in collision.pairs]
    assert source['checked_pairs'] == checked, 'source checked pair set mismatch'
    assert source['numerical_geometry_trigger_m'] == collision.clearance
    assert source['safety_clearance_m'] is None
    axes, indexed = {}, {}
    for leg in ('lf', 'rr'):
        model = models[leg]
        indices, grids = _static_axes(model)
        axes[leg] = {model.names[i]: grid.tolist() for i, grid in zip(indices, grids)}
    assert source['axes_rad'] == axes, 'source axes mismatch'
    assert len(zero) == 30 and len(source['rows']) == 270, 'source joint/row count mismatch'
    for row in source['rows']:
        leg, index, q = row['leg'], row['grid_index'], row['q_rad']
        assert leg in axes and len(index) == 3 and all(type(i) is int for i in index)
        assert all(0 <= i < count for i, count in zip(index, (3, 9, 5)))
        key = (leg, *index)
        assert key not in indexed, 'duplicate source grid row'
        expected = zero.copy()
        expected.update({n: grid[i] for (n, grid), i in zip(axes[leg].items(), index)})
        assert set(q) == set(zero) and all(type(v) in (int, float) and np.isfinite(v) for v in q.values())
        assert q == expected, 'source full q disagrees with named grid/fixed zero'
        twist, bend, distal = axes[leg]
        assert row['twist_context'] == {'joint': twist, 'angle_rad': q[twist]}
        assert row['bend_joint'] == bend and row['bend_angle_rad'] == q[bend]
        assert row['distal_joint'] == distal and row['distal_angle_rad'] == q[distal]
        assert all(urdf['joints'][n]['limits'][0] <= v <= urdf['joints'][n]['limits'][1] for n, v in q.items())
        # All three partitions must account for every checked pair, once each.
        partitions = [row[k] for k in ('solid_pairs', 'positive_gap_pairs', 'zero_gap_non_solid_pairs')]
        readings = [p for group in partitions for p in group]
        assert len(readings) == len(checked) and sorted(p['pair'] for p in readings) == sorted(checked)
        assert all(type(p['gap_lower_m']) in (int, float) and np.isfinite(p['gap_lower_m'])
                   and p['gap_lower_m'] >= 0 for p in readings)
        solid, positive = _static_pair_readings(readings)
        assert solid == partitions[0] and positive == partitions[1], 'source pair classification mismatch'
        indexed[key] = row
    assert len(indexed) == 270, 'incomplete source grids'
    target = ['base_link', 'rr_ankle']
    assert target in checked, 'target pair excluded'
    def target_state(row):
        return any(p['pair'] == target for p in row['solid_pairs'])
    seeds = []
    for key, row in indexed.items():
        if key[0] != 'rr':
            continue
        for axis in range(3):
            neighbor = list(key)
            neighbor[axis + 1] += 1
            other = indexed.get(tuple(neighbor))
            if other is not None and target_state(row) != target_state(other):
                seeds.append((row, other, list(axes['rr'])[axis]))
    assert seeds, 'no opposite-state adjacent rr target edges'
    model = models['rr']
    def reading(q, joint, angle):
        q = q.copy()
        q[joint] = angle
        pair_rows = collision.check(q)  # Never reduce collision.pairs to the target.
        assert [p['pair'] for p in pair_rows] == checked, 'incomplete current pair check'
        solid, _ = _static_pair_readings(pair_rows)
        target_reading = next(p for p in pair_rows if p['pair'] == target)
        chain_q = np.array([q[n] for n in model.names])
        _, normal = model.sole(chain_q)
        return {'angle_rad': angle, 'q_rad': q, 'solid_pairs': solid,
                'target_collision': any(p['pair'] == target for p in solid),
                'target_pair_reading': target_reading,
                'palm_lowest_vertex': _static_ground(model.vertices, model.pose(chain_q), root),
                'normal_z': float((root[:3, :3] @ normal)[2])}
    brackets, verified = [], {}
    for low_row, high_row, joint in seeds:
        ends = []
        for row in (low_row, high_row):
            key = tuple(row['grid_index'])
            if key not in verified:
                value = reading(row['q_rad'], joint, row['q_rad'][joint])
                assert value['target_collision'] == target_state(row), 'source target state changed'
                assert value['solid_pairs'] == row['solid_pairs'], 'source full solid pairs/count changed'
                verified[key] = value
            value = verified[key].copy()
            value['angle_rad'] = row['q_rad'][joint]
            ends.append(value)
        assert ends[0]['target_collision'] != ends[1]['target_collision']
        low, high = _refine_bracket(*ends, resolution,
                                   lambda angle: reading(low_row['q_rad'], joint, angle))
        brackets.append({'joint': joint, 'source_grid_indices': [low_row['grid_index'], high_row['grid_index']],
                         'source_angles_rad': [r['q_rad'][joint] for r in (low_row, high_row)],
                         'low': low, 'high': high, 'angle_width_rad': high['angle_rad'] - low['angle_rad']})
    summary = {'mode': 'refined_static_slices', 'identity': identity, 'source_identity': old_identity,
               'source_report': str(source_report.resolve()), 'source_report_sha256': digest(source_path),
               'source_sample_count': len(indexed),
               'source_rr_solid_pose_count': sum(bool(r['solid_pairs']) for k, r in indexed.items() if k[0] == 'rr'),
               'source_rr_target_pose_count': sum(target_state(r) for k, r in indexed.items() if k[0] == 'rr'),
               'axes_rad': axes, 'root_transform': root.tolist(), 'excluded_pairs': excluded,
               'checked_pairs': checked, 'angle_resolution_rad': resolution, 'target_pair': target,
               'bracket_count': len(brackets), 'brackets': brackets, 'blender': blender,
               'numerical_geometry_trigger_m': collision.clearance, 'safety_clearance_m': None,
               'limits': 'Only opposite-state adjacent source rr edges for base_link/rr_ankle; other coordinates fixed. '
                         'Same-state edges not scanned; narrow collision bands unknown. Endpoint angle width only, '
                         'not contact accuracy, a continuous-domain or monotonic-domain claim. Nonmonotonic edges may '
                         'contain multiple transitions; bisection retains one opposite-state bracket. Resolution larger '
                         'than source edge leaves original rechecked bracket. No sampled absence implies safety; '
                         'no safety margin, asset/ROM/PD change or actual motion. Positive gap may be AABB lower bound.'}
    payload = json.dumps(summary, indent=1, allow_nan=False)
    (output / 'report.json').write_text(payload, encoding='utf-8')
    print(json.dumps({'mode': summary['mode'], 'bracket_count': len(brackets), 'output_dir': str(output)}), flush=True)


def _static_plot(output, rows, axes):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, panels = plt.subplots(3, 2, figsize=(13, 11), constrained_layout=True)
    values = [r['palm_lowest_vertex']['height_m'] for r in rows]
    for col, leg in enumerate(('lf', 'rr')):
        twist, bend, distal = axes[leg].values()
        for ti in range(3):
            data = np.empty((5, 9))
            ax = panels[ti, col]
            for row in rows:
                t, b, w = row['grid_index']
                if row['leg'] == leg and t == ti:
                    data[w, b] = row['palm_lowest_vertex']['height_m']
                    if row['solid_pairs']:
                        ax.plot(b, w, 'kx', markersize=8)
            image = ax.imshow(data, origin='lower', aspect='auto', vmin=min(values), vmax=max(values), cmap='coolwarm')
            ax.set_xticks(range(9), [f'{np.degrees(v):.1f}' for v in bend], rotation=45)
            ax.set_yticks(range(5), [f'{np.degrees(v):.1f}' for v in distal])
            ax.set(title=f'{leg}: twist {np.degrees(twist[ti]):.1f} deg',
                   xlabel='Elbow / knee [deg]', ylabel='Wrist / ankle [deg]')
    fig.colorbar(image, ax=panels.ravel().tolist(), label='Minimum palm collision vertex z [m]; X = solid intersection/containment')
    fig.suptitle('Sampled static slices only — no safe-domain verdict')
    fig.savefig(output / 'static_slices.png', dpi=150)
    plt.close(fig)


def _local_residual(model, q, previous, root, target, config, contact=False):
    pose = model.pose(q)
    point, _ = model.sole(q)
    point = root[:3, :3] @ point + root[:3, 3]
    height = _static_ground(model.vertices, pose, root)['height_m']
    task = (np.array([point[0], point[1], height]) - target) / config['position_tolerance_m']
    if contact:
        middle_height = _static_ground(model.vertices, model.pose((previous + q) / 2), root)['height_m']
        task = np.r_[task, middle_height / config['position_tolerance_m']]
    return np.r_[task, (q - previous) * 1e-4]


def _local_solve(residual, previous, lo, hi, config):
    """Bound calls; task entries precede one regularizer entry per joint."""
    lower = np.maximum(lo, previous - config['joint_step_rad'])
    upper = np.minimum(hi, previous + config['joint_step_rad'])
    seeds = (previous, np.zeros(len(previous)), previous + np.linspace(-.01, .01, len(previous)))
    attempts, candidate = [], previous.copy()
    for seed in seeds:
        count, best_error, best = 0, float('inf'), previous.copy()
        exhausted = False

        def counted(q):
            nonlocal count, best_error, best
            if count >= config['evaluations_per_attempt']:
                raise StopIteration('residual evaluation budget')
            count += 1
            value = residual(q)
            error = float(np.linalg.norm(value[:-len(previous)]))
            if error < best_error:
                best_error, best = error, q.copy()
            if error <= 1:
                raise StopIteration('task tolerance reached')
            return value

        start = np.clip(seed, lower + 1e-12, upper - 1e-12)
        if 0 < np.linalg.norm(start) < 1e-8 and np.all(lower < 0) and np.all(upper > 0):
            start[:] = 0
        try:
            result = least_squares(counted, start, bounds=(lower, upper),
                                   max_nfev=config['evaluations_per_attempt'],
                                   xtol=1e-10, ftol=1e-10, gtol=1e-10)
            candidate = result.x
        except StopIteration as stop:
            exhausted, candidate = str(stop) != 'task tolerance reached', best
        attempts.append({'evaluations': count, 'budget_exhausted': exhausted,
                         'best_scaled_position_error': best_error, 'q_rad': candidate.tolist()})
        if not exhausted and best_error <= 1:
            return candidate, attempts, False
    return candidate, attempts, True


def _local_failures(state, previous, target, config, contact=False, landing=False):
    failures = []
    tolerance = config['position_tolerance_m']
    if target is not None and np.max(np.abs(np.array(state['task_m']) - target)) > tolerance:
        failures.append('task residual')
    if state['all_ground_min_m'] < -tolerance:
        failures.append('ground penetration')
    if contact and abs(state['task_m'][2]) > tolerance:
        failures.append('contact residual')
    if state['normal_z'] <= 0:
        failures.append('back-side palm')
    if state['reverse_bend']:
        failures.append('reverse bend')
    if state['solid_pairs']:
        failures.append('solid intersection')
    if previous is not None:
        delta = np.max(np.abs(np.array(state['chain_q_rad']) - previous['chain_q_rad']))
        if delta > config['joint_step_rad'] + 1e-12:
            failures.append('joint step')
        if landing and state['task_m'][2] > previous['task_m'][2] + tolerance:
            failures.append('landing height increased')
    return failures


def _local_closed(final, initial, config):
    """Check full joint branch and reference-point closure, not sole position alone."""
    return (bool(np.max(np.abs(np.array(final['chain_q_rad']) - initial['chain_q_rad'])) <= 1e-12)
            and bool(np.max(np.abs(np.array(final['reference_point_m']) - initial['reference_point_m']))
                     <= config['position_tolerance_m']))


def _local_path(build_report, output_dir):
    output = output_dir.resolve()
    build, models, urdf, zero, collision, excluded, root, neutral, blender, identity = _static_prepare(build_report)
    config = {'segment_step_fraction': .01, 'points_per_phase': 8,
              'position_tolerance_m': 1e-5, 'joint_step_rad': .05,
              'evaluations_per_attempt': 200, 'attempts_per_point': 3,
              'midpoint_check': True, 'path_parameter_only': True,
              'contact_task': 'endpoint XY/minimum z plus joint-linear midpoint minimum z',
              'solver_task_norm': 'L2 of all tolerance-scaled task entries; joint regularizer excluded'}
    results = {}
    for leg in ('lf', 'rr'):
        model = models[leg]
        knee_name = f"{leg}_{'elbow' if leg == 'lf' else 'knee'}_joint"
        knee = model.names.index(knee_name)
        frames = [model.root @ np.array(f) for f in reach.chain_frames(model.chain, np.zeros(len(model.names)))]
        pivot = frames[knee + 1][:3, 3]
        upper_length = next(float(np.linalg.norm(pivot - f[:3, 3])) for f in reversed(frames[:knee + 1])
                            if np.linalg.norm(pivot - f[:3, 3]) > 1e-12)
        lower_length = next(float(np.linalg.norm(f[:3, 3] - pivot)) for f in frames[knee + 2:]
                            if np.linalg.norm(f[:3, 3] - pivot) > 1e-12)
        step = min(upper_length, lower_length) * config['segment_step_fraction']
        straight = reach.straight_hfe(model.chain)

        def state(q):
            named = {**zero, **dict(zip(model.names, map(float, q)))}
            pose = model.pose(q)
            independent = model.root @ np.array(reach.chain_frames(model.chain, q)[-1])
            assert np.max(np.abs(pose - independent)) < 1e-10, 'local path FK mismatch'
            point, normal = model.sole(q)
            point = root[:3, :3] @ point + root[:3, 3]
            lowest = _static_ground(model.vertices, pose, root)
            ground = {link: _static_ground(v, csc.fk(urdf['joints'], link, named), root)
                      for link, (v, _) in collision.local.items()}
            pairs = collision.check(named)
            solid, positive = _static_pair_readings(pairs)
            return {'q_rad': named, 'chain_q_rad': q.tolist(),
                    'task_m': [float(point[0]), float(point[1]), lowest['height_m']],
                    'reference_point_m': point.tolist(), 'palm_lowest_vertex': lowest,
                    'all_ground_min_m': min(g['height_m'] for g in ground.values()),
                    'normal_z': float((root[:3, :3] @ normal)[2]),
                    'palm_normal': (root[:3, :3] @ normal).tolist(),
                    'thigh_shank_angle_deg': reach.thigh_shank_angle(model.chain, q),
                    'reverse_bend': bool(q[knee] * np.sign(straight) >= abs(straight)),
                    'solid_pairs': solid, 'positive_gap_pairs': positive}

        previous = state(np.zeros(len(model.names)))
        initial = previous.copy()
        rows = [{'phase': 'neutral', 's': 0., 'state': initial}]
        initial_failures = _local_failures(initial, None, None, config, contact=True)
        failure = {'phase': 'neutral', 'failures': initial_failures} if initial_failures else None
        if initial_failures:
            rows[0]['failures'] = initial_failures
        neutral_xy = np.array(initial['task_m'][:2])
        phase_start_q = None
        for phase in ('backward_contact', 'lift', 'forward_air', 'return_neutral'):
            if failure is not None:
                break
            phase_start = np.array(previous['task_m'])
            phase_start_q = np.array(previous['chain_q_rad'])
            for index in range(1, config['points_per_phase'] + 1):
                before = np.array(previous['chain_q_rad'])
                if phase == 'return_neutral':
                    q = phase_start_q * (1 - index / config['points_per_phase'])
                    attempts, solve_failed, target = [], False, None
                else:
                    target = phase_start.copy()
                    if phase == 'backward_contact':
                        target[0] -= index * step
                        target[2] = 0.
                    elif phase == 'lift':
                        target[2] += index * step
                    else:
                        target[0] += index * (neutral_xy[0] - phase_start[0]) / config['points_per_phase']
                    def residual(q):
                        return _local_residual(model, q, before, root, target, config,
                                               contact=phase == 'backward_contact')
                    q, attempts, solve_failed = _local_solve(residual, before, model.lo, model.hi, config)
                endpoint = state(q)
                midpoint = state((before + q) / 2)
                contact = phase == 'backward_contact'
                failed = _local_failures(endpoint, previous, target, config, contact, phase == 'return_neutral')
                middle_failed = _local_failures(midpoint, previous, None, config, contact, phase == 'return_neutral')
                if phase == 'return_neutral':
                    failed.extend(_local_failures(endpoint, midpoint, None, config, landing=True))
                if solve_failed:
                    failed.append('solver budget or residual')
                if phase in ('lift', 'forward_air') and endpoint['task_m'][2] <= config['position_tolerance_m']:
                    failed.append('no resolved lift')
                if phase == 'forward_air' and endpoint['task_m'][0] <= previous['task_m'][0] + config['position_tolerance_m']:
                    failed.append('no resolved forward displacement')
                if phase == 'backward_contact' and endpoint['task_m'][0] >= previous['task_m'][0] - config['position_tolerance_m']:
                    failed.append('no resolved backward displacement')
                if middle_failed:
                    failed.append('midpoint geometry')
                row = {'phase': phase, 'point': index, 's': (len(rows)) / 32,
                       'target_m': None if target is None else target.tolist(),
                       'state': endpoint, 'midpoint': midpoint, 'midpoint_failures': middle_failed,
                       'attempts': attempts, 'failures': failed}
                rows.append(row)
                if failed:
                    failure = row
                    break
                previous = endpoint
            if failure is not None:
                break
        closed = failure is None and _local_closed(previous, initial, config)
        results[leg] = {'bone_lengths_m': [upper_length, lower_length], 'exploration_step_m': step,
                        'completed_local_loop': closed, 'rows': rows, 'failure_phase': None if failure is None else failure['phase'],
                        'accepted_points': sum(not r.get('failures') for r in rows[1:]),
                        'evaluations': sum(a['evaluations'] for r in rows for a in r.get('attempts', []))}
    report = {'mode': 'budgeted_local_path', 'identity': identity, 'config': config,
              'root_transform': root.tolist(), 'neutral_ground': neutral, 'blender': blender,
              'checked_pairs': [list(p) for p in collision.pairs], 'excluded_pairs': excluded,
              'forward_axis': '+X of URDF root; body fixed, not world no-slip stance', 'legs': results,
              'limits': 'Local deterministic continuation only, not maximal capability, approved stride/height, safe domain, time, speed, PD or dynamics. Failure stops that leg, without widening tolerances. Midpoints are samples, not continuous proof. Lowest vertex identity is not contact material slip. Numerical ground tolerance is not mechanical permission.'}
    payload = json.dumps(report, indent=1, allow_nan=False)
    (output / 'report.json').write_text(payload, encoding='utf-8')
    print(json.dumps({leg: {k: result[k] for k in ('completed_local_loop', 'accepted_points', 'failure_phase', 'evaluations')}
                      for leg, result in results.items()}, indent=1), flush=True)


def _local_self_check(break_test=None):
    from unittest.mock import patch
    import inspect
    changed = {'local_contact': (_local_residual, 'if contact:', 'if False:'),
               'local_task': (_local_solve, 'value[:-len(previous)]', 'value[:3]'),
               'local_stop': (_local_solve, 'if error <= 1:', 'if False:'),
               'local_budget': (_local_solve, "count >= config['evaluations_per_attempt']", 'False'),
               'local_ground': (_local_failures, "state['all_ground_min_m'] < -tolerance", 'False'),
               'local_step': (_local_failures, "delta > config['joint_step_rad'] + 1e-12", 'False'),
               'local_closure': (_local_closed,
                                 "np.max(np.abs(np.array(final['chain_q_rad']) - initial['chain_q_rad'])) <= 1e-12",
                                 'True')}
    if break_test in changed:
        function, old, new = changed[break_test]
        code = inspect.getsource(function)
        assert old in code
        scope = dict(globals())
        exec(code.replace(old, new), scope)
        with patch.dict(globals(), {function.__name__: scope[function.__name__]}):
            return _local_self_check()
    config = {'joint_step_rad': .05, 'evaluations_per_attempt': 12, 'position_tolerance_m': 1e-5}
    _, contact_attempts, contact_failed = _local_solve(lambda q: np.r_[np.zeros(3), 10., q * 1e-4],
                                                     np.zeros(5), np.full(5, -.6), np.full(5, .6), config)
    assert contact_failed and contact_attempts[0]['best_scaled_position_error'] >= 10, 'midpoint task ignored'
    from types import SimpleNamespace
    def curved_pose(q):
        pose = np.eye(4)
        pose[2, 3] = q[2] + q[0] ** 2 + q[0] * q[3]
        return pose
    model = SimpleNamespace(vertices=np.zeros((1, 3)), pose=curved_pose,
                            sole=lambda q: (np.array([q[0], q[1], 0.]), np.array([0., 0., 1.])))
    q = np.array([.02, 0., -.0004, 0., 0.])
    value = _local_residual(model, q, np.zeros(5), np.eye(4), np.array([.02, 0., 0.]), config, True)
    assert len(value) == 9 and np.linalg.norm(value[:3]) < 1e-10
    assert abs(value[3] + 10) < 1e-10, 'contact midpoint omitted from residual'
    q[2], q[3] = 0., -.02
    assert np.linalg.norm(_local_residual(model, q, np.zeros(5), np.eye(4),
                                         np.array([.02, 0., 0.]), config, True)[:-5]) < 1e-10
    assert len(_local_residual(model, q, np.zeros(5), np.eye(4), np.array([.02, 0., 0.]), config)) == 8
    _, ready_attempts, ready_failed = _local_solve(lambda q: np.r_[np.zeros(3), q * 1e-4],
                                                 np.zeros(5), np.full(5, -.6), np.full(5, .6), config)
    assert not ready_failed and ready_attempts[0]['evaluations'] == 1, 'task tolerance did not stop solver'
    calls = 0
    def unreachable(q):
        nonlocal calls
        calls += 1
        return np.r_[np.ones(3) * 100 + q[:3], q * 1e-4]
    _, attempts, failed = _local_solve(unreachable, np.zeros(5), np.full(5, -.6), np.full(5, .6), config)
    assert failed and calls == sum(a['evaluations'] for a in attempts) <= 36
    assert len(attempts) == 3 and all(a['evaluations'] <= 12 for a in attempts)
    state = {'task_m': [0., 0., 0.], 'all_ground_min_m': 0., 'normal_z': 1.,
             'reverse_bend': False, 'solid_pairs': [], 'chain_q_rad': [0.] * 5}
    assert not _local_failures(state, None, np.zeros(3), config, True)
    for broken, expected in (({**state, 'all_ground_min_m': -.001}, 'ground penetration'),
                             ({**state, 'normal_z': -1.}, 'back-side palm'),
                             ({**state, 'reverse_bend': True}, 'reverse bend'),
                             ({**state, 'solid_pairs': [{'pair': ['a', 'b']}]}, 'solid intersection'),
                             ({**state, 'chain_q_rad': [.051] * 5}, 'joint step')):
        assert expected in _local_failures(broken, state, None, config), expected
    closure = {**state, 'reference_point_m': [0., 0., 0.]}
    assert _local_closed(closure, closure, config)
    assert not _local_closed({**closure, 'chain_q_rad': [.01] * 5}, closure, config)
    print('LOCAL_PATH_SELF_CHECK_OK: strict residual-call budget and geometry/joint-step/closure rejection', flush=True)


def _static_self_check(break_test=None):
    _local_self_check(break_test)
    from types import SimpleNamespace
    from unittest.mock import patch
    refine = _refine_bracket
    if break_test in ('refine_state', 'refine_shrink'):
        # Mutate the actual helper in memory: same checks below, no extra files.
        import inspect
        code = inspect.getsource(_refine_bracket)
        if break_test == 'refine_state':
            code = code.replace("middle['target_collision'] == low['target_collision']",
                                "middle['target_collision'] != low['target_collision']")
        else:
            code = code.replace('low = middle', 'low = low').replace('high = middle', 'high = high')
        scope = {'np': np}
        exec(code, scope)
        refine = scope['_refine_bracket']
    for state in (lambda x: x >= .375, lambda x: x < .375,
                  lambda x: .25 <= x < .5 or x >= .75):
        def check(angle):
            return {'angle_rad': angle, 'target_collision': bool(state(angle))}
        low, high = refine(check(0.), check(1.), .0625, check)
        assert high['angle_rad'] - low['angle_rad'] <= .0625
        assert low == check(low['angle_rad']) and high == check(high['angle_rad'])
        assert low['target_collision'] != high['target_collision'], 'refine state misclassified'
        if state(.375) != state(.374):
            assert low['angle_rad'] <= .375 <= high['angle_rad'], 'step lost'
        assert refine(check(0.), check(1.), 2., check) == (check(0.), check(1.))
    # Same-state endpoints cannot expose an interior narrow band: reject, do not claim safety.
    try:
        refine({'angle_rad': 0., 'target_collision': False},
               {'angle_rad': 1., 'target_collision': False}, .1, check)
    except AssertionError:
        pass
    else:
        raise AssertionError('same-state bracket accepted')
    print('REFINE_SELF_CHECK_OK: both state directions, step bracket, nonmonotonic limits, coarse resolution', flush=True)
    ordered = ['lf_shoulder_swing_joint', 'lf_shoulder_abduct_joint', 'lf_shoulder_twist_joint',
               'lf_elbow_joint', 'lf_wrist_joint']
    # Deliberate extra joint and shifted indices: old hardcoded [2]/[3]/[4] cannot pass.
    ordered.insert(2, 'lf_extra_joint')
    chain = [{'name': n} for n in ordered]
    model = SimpleNamespace(leg='lf', names=tuple(ordered), chain=chain,
                            lo=np.full(6, -.6), hi=np.full(6, .9))
    if break_test == 'misaligned':
        model.chain = list(reversed(chain))
    if break_test == 'missing_twist':
        model.names = tuple(n.replace('shoulder_twist', 'missing') for n in model.names)
        model.chain = [{'name': n} for n in model.names]
    indices, grids = _static_axes(model)
    assert indices == [3, 4, 5], 'named roles shifted'
    assert [len(g) for g in grids] == [3, 9, 5]
    assert all(0 in g and g[0] == -.6 and g[-1] == .9 for g in grids)
    q = dict.fromkeys(ordered + ['tail_joint', 'rr_knee_joint'], 0.)
    q.update({model.names[i]: float(v) for i, v in zip(indices, (.3, .2, -.1))})
    assert q['lf_shoulder_twist_joint'] == .3 and q['lf_extra_joint'] == q['tail_joint'] == q['rr_knee_joint'] == 0
    vertices = np.array([[1., 0., -2.], [0., 1., -1.], [0., 0., 3.]])
    pose, root = np.eye(4), np.eye(4)
    pose[2, 3], root[2, 3] = .5, 1.5
    if break_test == 'ground':
        root = np.eye(4)
    ground = _static_ground(vertices, pose, root)
    assert ground == {'vertex_index': 0, 'position_m': [1., 0., 0.], 'height_m': 0.}, 'root not applied to mesh'
    root[:3, :3] = motion.gait.rotation(np.array([0., 1., 0.]), np.pi / 2)
    assert _static_ground(vertices, pose, root)['vertex_index'] == 0
    assert abs(_static_ground(vertices, pose, root)['height_m'] - .5) < 1e-12
    # Closed outward tetrahedra: overlap, contained component and positive sub-margin gap.
    tetra = np.array([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.], [0., 0., 1.]])
    faces = np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]])
    urdf = {'links': {'a': {'collision': 'a'}, 'b': {'collision': 'b'}}, 'joints': {}}
    def make_collision(vb):
        with patch.object(csc, 'read_obj_faces', side_effect=[(tetra, faces), (vb, faces)]):
            return motion.Collision(urdf, 0. if break_test == 'zero_trigger' else 1e-9)
    overlap = make_collision(tetra + .1).check({})
    containment = make_collision(tetra * .1 + .1).check({})
    near_collision = make_collision(tetra + [1.001, 0., 0.])
    near_collision.clearance = .005  # Fixture reproduces historical proximity fail, not static safety policy.
    near = near_collision.check({})
    if break_test == 'solid':
        # Reproduce wrong use of Collision.fail as a physical solid verdict.
        solid = [r for r in near if r['fail']]
    else:
        solid, positive = _static_pair_readings(near)
        assert positive and positive[0]['gap_lower_m'] > 0
    assert not solid, 'proximity incorrectly classified as solid'
    assert _static_pair_readings(overlap)[0], 'AABB overlap skipped geometry'
    assert _static_pair_readings(containment)[0][0]['contained'], 'containment missed'
    print('STATIC_SELF_CHECK_OK: named roles/full twist, ground mesh transform, intersection/containment vs positive gap', flush=True)


def plot(output, old, new, rows):
    """Write a reviewable geometry comparison and diagnostic curve."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(14, 8))
    selected = next(r for r in rows if r['mode'] == 'pitch' and r['body_angle_deg'] > 2.999)
    for i, (version, models, title) in enumerate((('old', old, 'Current: shoulder/hip has 2 axes'),
                                                 ('new', new, 'Candidate: shoulder/hip has 3 axes'))):
        ax = fig.add_subplot(2, 2, i + 1, projection='3d')
        rotate = np.array(selected['root_rotation'])
        for leg, model in models.items():
            q = selected[version][leg]['q_rad']
            frames = reach.chain_frames(model.chain, q)
            pts = np.array([(model.root @ np.array(frame))[:3, 3] for frame in frames[1:]]) @ rotate.T
            color = {'lf': '#1976d2', 'rf': '#64b5f6', 'rl': '#d86e23', 'rr': '#eab676'}[leg]
            ax.plot(*pts.T, '-o', color=color, markersize=3)
            p, n = model.sole(q)
            ax.scatter(*model.neutral, color='black', s=12)
            ax.quiver(*(rotate @ p), *(rotate @ n * .18), color=color)
            pose = model.pose(q)
            vertices = (model.vertices @ pose[:3, :3].T + pose[:3, 3]) @ rotate.T
            ax.scatter(*vertices[::max(1, len(vertices) // 70)].T, s=1, color=color, alpha=.5)
        ax.set_title(title + '\nBody pitch +3 deg; black dots = fixed sole targets')
        ax.set(xlabel='X [m]', ylabel='Y [m]', zlabel='Z [m]')
        ax.set_box_aspect((2, 2, 1))
        ax.view_init(24, -50)
    ax = fig.add_subplot(2, 1, 2)
    pitch = [r for r in rows if r['mode'] == 'pitch']
    for version, style in (('old', '--'), ('new', '-')):
        for leg in ('lf', 'rl'):
            ax.plot([r['frame'] for r in pitch], [r[version][leg]['tilt_deg'] for r in pitch],
                    style, label=f'{version} {leg}')
    ax.axhline(2, color='gray', linestyle=':', label='Historical diagnostic: 2 deg')
    ax.set(xlabel='Sample in body pitch cycle 0 -> +3 -> 0 -> -3 -> 0 deg', ylabel='Palm tilt [deg]')
    ax.legend(ncol=3)
    ax.grid(alpha=.2)
    fig.suptitle('Spatial palm reconfiguration — geometric diagnostic, not gait/dynamics validation')
    fig.tight_layout()
    fig.savefig(output / 'comparison.png', dpi=150)
    plt.close(fig)


if __name__ == '__main__':
    main()
