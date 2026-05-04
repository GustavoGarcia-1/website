#!/usr/bin/env python3
"""
Render a MuJoCo scene with 3 robots in a hero-squad V-formation.
Full bodies visible, angled inward, clean and cinematic.
"""

import mujoco
import numpy as np
from PIL import Image

MENAGERIE = "/home/thewheelneedsme/sim_mujoco/panda_pick_place/mujoco_menagerie"
OUTPUT = "/home/thewheelneedsme/Projects/website/robots_bg.png"
WIDTH, HEIGHT = 3840, 2160

# ── Helpers ──────────────────────────────────────────────────────────────────
def euler_to_quat(roll, pitch, yaw):
    cr, cp, cy = np.cos(np.array([roll, pitch, yaw]) / 2)
    sr, sp, sy = np.sin(np.array([roll, pitch, yaw]) / 2)
    return [
        cr*cp*cy + sr*sp*sy,
        sr*cp*cy - cr*sp*sy,
        cr*sp*cy + sr*cp*sy,
        cr*cp*sy - sr*sp*cy,
    ]

# ── Build composite scene ────────────────────────────────────────────────────
spec = mujoco.MjSpec()
spec.visual.global_.offwidth = WIDTH
spec.visual.global_.offheight = HEIGHT
spec.visual.quality.shadowsize = 4096

# Sky / fog — clean light gradient
spec.visual.rgba.fog = [0.90, 0.93, 0.96, 1.0]
spec.visual.map.fogstart = 10.0
spec.visual.map.fogend = 30.0

# Skybox texture (subtle gradient — light blue to near-white)
sky_tex = spec.add_texture()
sky_tex.name = "sky"
sky_tex.type = mujoco.mjtTexture.mjTEXTURE_SKYBOX
sky_tex.builtin = mujoco.mjtBuiltin.mjBUILTIN_GRADIENT
sky_tex.width = 512
sky_tex.height = 512
sky_tex.rgb1 = [0.82, 0.87, 0.94]  # horizon — soft blue
sky_tex.rgb2 = [0.94, 0.96, 0.98]  # zenith — near white

# ── Ground ───────────────────────────────────────────────────────────────────
tex = spec.add_texture()
tex.name = "grid_tex"
tex.type = mujoco.mjtTexture.mjTEXTURE_2D
tex.builtin = mujoco.mjtBuiltin.mjBUILTIN_CHECKER
tex.width = 512
tex.height = 512
tex.rgb1 = [0.86, 0.88, 0.91]
tex.rgb2 = [0.83, 0.85, 0.88]

mat_grid = spec.add_material()
mat_grid.name = "grid_mat"
mat_grid.texrepeat = [30, 30]
mat_grid.textures[0] = "grid_tex"
mat_grid.reflectance = 0.25  # stronger reflections — Apple product page feel

ground = spec.worldbody.add_geom()
ground.type = mujoco.mjtGeom.mjGEOM_PLANE
ground.size = [40, 40, 0.1]
ground.rgba = [0.88, 0.90, 0.93, 1.0]
ground.name = "ground"
ground.material = "grid_mat"

# ── Lighting (3-point, softer for cleaner look) ─────────────────────────────
key = spec.worldbody.add_light()
key.pos = [2, -6, 10]
key.dir = [-0.1, 0.4, -0.7]
key.diffuse = [1.0, 0.98, 0.95]
key.specular = [0.4, 0.4, 0.4]
key.castshadow = True
key.name = "key_light"

fill_l = spec.worldbody.add_light()
fill_l.pos = [-6, -3, 6]
fill_l.dir = [0.4, 0.2, -0.5]
fill_l.diffuse = [0.60, 0.65, 0.75]
fill_l.specular = [0.10, 0.10, 0.10]
fill_l.castshadow = False
fill_l.name = "fill_light"

rim = spec.worldbody.add_light()
rim.pos = [0, 6, 5]
rim.dir = [0, -0.6, -0.4]
rim.diffuse = [0.35, 0.38, 0.45]
rim.specular = [0.18, 0.18, 0.18]
rim.castshadow = False
rim.name = "rim_light"

# ── Camera — pulled back, elevated, full-body framing ────────────────────────
cam = spec.worldbody.add_camera()
cam.name = "hero_cam"
cam.pos = [0.0, -4.2, 1.4]
cam.quat = euler_to_quat(1.34, 0, 0)
cam.fovy = 44

# ── Load and attach robots ───────────────────────────────────────────────────
print("Loading robot models...")
g1 = mujoco.MjSpec.from_file(f"{MENAGERIE}/unitree_g1/g1_with_hands.xml")
apollo = mujoco.MjSpec.from_file(f"{MENAGERIE}/apptronik_apollo/apptronik_apollo.xml")
h1 = mujoco.MjSpec.from_file(f"{MENAGERIE}/unitree_h1/h1.xml")

f1 = spec.worldbody.add_frame()
f1.name = "g1_frame"
f1.pos = [0, 0, 0]
spec.attach(g1, prefix="g1/", frame=f1)

f2 = spec.worldbody.add_frame()
f2.name = "apollo_frame"
f2.pos = [0, 0, 0]
spec.attach(apollo, prefix="apollo/", frame=f2)

f3 = spec.worldbody.add_frame()
f3.name = "h1_frame"
f3.pos = [0, 0, 0]
spec.attach(h1, prefix="h1/", frame=f3)

# ── Compile ──────────────────────────────────────────────────────────────────
print("Compiling scene...")
model = spec.compile()
data = mujoco.MjData(model)
print(f"  {model.nbody} bodies, {model.njnt} joints")

# ── Helper: set joint ────────────────────────────────────────────────────────
def set_joint(name, value):
    jid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
    if jid < 0:
        print(f"  WARN: joint '{name}' not found")
        return
    data.qpos[model.jnt_qposadr[jid]] = value

def set_freejoint_by_body(body_name, pos, quat):
    bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, body_name)
    if bid < 0:
        print(f"  WARN: body '{body_name}' not found")
        return
    jnt_adr = model.body_jntadr[bid]
    if jnt_adr < 0:
        print(f"  WARN: body '{body_name}' has no joint")
        return
    qa = model.jnt_qposadr[jnt_adr]
    data.qpos[qa:qa+3] = pos
    data.qpos[qa+3:qa+7] = quat

def set_freejoint(name, pos, quat):
    jid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
    if jid < 0:
        print(f"  WARN: joint '{name}' not found")
        return
    qa = model.jnt_qposadr[jid]
    data.qpos[qa:qa+3] = pos
    data.qpos[qa+3:qa+7] = quat

# ══════════════════════════════════════════════════════════════════════════════
# POSING — hero squad V-formation
#
#       G1 (left)     Apollo (center)     H1 (right)
#          \               |               /
#           \              |              /
#
# Left/right robots angled inward, center faces straight at camera.
# ══════════════════════════════════════════════════════════════════════════════

# ── G1: left side, angled inward ─────────────────────────────────────────────
print("Posing G1 (left, angled in)...")
set_freejoint("g1/floating_base_joint",
              pos=[-1.6, 0.4, 0.72],
              quat=euler_to_quat(0, 0, -1.20))  # angled ~30° inward

# Clean standing pose — arms relaxed, legs straight
set_joint("g1/left_shoulder_pitch_joint", 0.05)
set_joint("g1/left_shoulder_roll_joint", 0.12)
set_joint("g1/left_elbow_joint", 0.15)
set_joint("g1/right_shoulder_pitch_joint", 0.05)
set_joint("g1/right_shoulder_roll_joint", -0.12)
set_joint("g1/right_elbow_joint", 0.15)

# Legs — straight standing
set_joint("g1/left_hip_pitch_joint", 0.0)
set_joint("g1/right_hip_pitch_joint", 0.0)
set_joint("g1/left_knee_joint", 0.0)
set_joint("g1/right_knee_joint", 0.0)
set_joint("g1/left_ankle_pitch_joint", 0.0)
set_joint("g1/right_ankle_pitch_joint", 0.0)

# ── Apollo: center, slightly forward, facing camera ──────────────────────────
print("Posing Apollo (center, forward)...")
set_freejoint("apollo/floating_base",
              pos=[0.0, -0.15, 1.07],
              quat=euler_to_quat(0, 0, -1.57))  # straight at camera

# Confident standing pose — arms relaxed
set_joint("apollo/l_shoulder_aa", 0.10)
set_joint("apollo/l_shoulder_fe", -0.05)
set_joint("apollo/l_elbow_fe", -0.12)
set_joint("apollo/r_shoulder_aa", -0.10)
set_joint("apollo/r_shoulder_fe", -0.05)
set_joint("apollo/r_elbow_fe", -0.12)

# ── H1: right side, angled inward ───────────────────────────────────────────
print("Posing H1 (right, angled in)...")
set_freejoint_by_body("h1/pelvis",
                      pos=[1.6, 0.4, 1.02],
                      quat=euler_to_quat(0, 0, -1.94))  # angled ~30° inward

# Clean standing pose — arms relaxed
set_joint("h1/left_shoulder_pitch", 0.05)
set_joint("h1/left_shoulder_roll", 0.10)
set_joint("h1/right_shoulder_pitch", 0.05)
set_joint("h1/right_shoulder_roll", -0.10)

# ── Forward kinematics ──────────────────────────────────────────────────────
mujoco.mj_forward(model, data)

# ── Render ───────────────────────────────────────────────────────────────────
print("Rendering...")
renderer = mujoco.Renderer(model, width=WIDTH, height=HEIGHT)

cam_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_CAMERA, "hero_cam")

renderer.update_scene(data, camera=cam_id)

img = renderer.render()
renderer.close()

pil_img = Image.fromarray(img)
pil_img.save(OUTPUT, optimize=True)
print(f"Saved to {OUTPUT} ({img.shape[1]}x{img.shape[0]})")
