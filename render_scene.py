#!/usr/bin/env python3
"""
Render a MuJoCo scene with 3 robots standing and facing the camera.
Clean background, no props — just the robots front and center.
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

# Sky / fog — light blue-gray
spec.visual.rgba.fog = [0.88, 0.91, 0.95, 1.0]
spec.visual.map.fogstart = 8.0
spec.visual.map.fogend = 25.0

# Skybox texture (gradient from light blue to white)
sky_tex = spec.add_texture()
sky_tex.name = "sky"
sky_tex.type = mujoco.mjtTexture.mjTEXTURE_SKYBOX
sky_tex.builtin = mujoco.mjtBuiltin.mjBUILTIN_GRADIENT
sky_tex.width = 512
sky_tex.height = 512
sky_tex.rgb1 = [0.75, 0.82, 0.92]  # horizon
sky_tex.rgb2 = [0.90, 0.93, 0.97]  # zenith

# ── Ground ───────────────────────────────────────────────────────────────────
tex = spec.add_texture()
tex.name = "grid_tex"
tex.type = mujoco.mjtTexture.mjTEXTURE_2D
tex.builtin = mujoco.mjtBuiltin.mjBUILTIN_CHECKER
tex.width = 512
tex.height = 512
tex.rgb1 = [0.82, 0.85, 0.89]
tex.rgb2 = [0.78, 0.81, 0.85]

mat_grid = spec.add_material()
mat_grid.name = "grid_mat"
mat_grid.texrepeat = [24, 24]
mat_grid.textures[0] = "grid_tex"
mat_grid.reflectance = 0.12

ground = spec.worldbody.add_geom()
ground.type = mujoco.mjtGeom.mjGEOM_PLANE
ground.size = [30, 30, 0.1]
ground.rgba = [0.82, 0.84, 0.88, 1.0]
ground.name = "ground"
ground.material = "grid_mat"

# ── Lighting (3-point) ──────────────────────────────────────────────────────
key = spec.worldbody.add_light()
key.pos = [3, -5, 9]
key.dir = [-0.2, 0.4, -0.7]
key.diffuse = [1.0, 0.97, 0.93]
key.specular = [0.5, 0.5, 0.5]
key.castshadow = True
key.name = "key_light"

fill_l = spec.worldbody.add_light()
fill_l.pos = [-5, -2, 5]
fill_l.dir = [0.4, 0.2, -0.5]
fill_l.diffuse = [0.55, 0.60, 0.72]
fill_l.specular = [0.12, 0.12, 0.12]
fill_l.castshadow = False
fill_l.name = "fill_light"

rim = spec.worldbody.add_light()
rim.pos = [0, 5, 4]
rim.dir = [0, -0.6, -0.4]
rim.diffuse = [0.30, 0.35, 0.42]
rim.specular = [0.15, 0.15, 0.15]
rim.castshadow = False
rim.name = "rim_light"

# ── Camera (closer, robots fill the frame) ───────────────────────────────────
cam = spec.worldbody.add_camera()
cam.name = "hero_cam"
cam.pos = [0.0, -3.0, 1.05]
cam.quat = euler_to_quat(1.38, 0, 0)
cam.fovy = 52

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
    """Set free joint via its parent body name."""
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
# POSING — all 3 robots standing, facing the camera
# ══════════════════════════════════════════════════════════════════════════════

# Camera is at y=-2.8, so robots face -Y (toward camera) → yaw = -π/2

# ── G1: standing, left side ──────────────────────────────────────────────────
print("Posing G1 (standing, left)...")
set_freejoint("g1/floating_base_joint",
              pos=[-1.4, 0.1, 0.72],
              quat=euler_to_quat(0, 0, -1.57))  # facing camera

# Relaxed standing pose — arms slightly out
set_joint("g1/left_shoulder_pitch_joint", -0.15)
set_joint("g1/left_shoulder_roll_joint", 0.20)
set_joint("g1/left_elbow_joint", 0.30)
set_joint("g1/right_shoulder_pitch_joint", -0.15)
set_joint("g1/right_shoulder_roll_joint", -0.20)
set_joint("g1/right_elbow_joint", 0.30)

# ── Apollo: standing, center ────────────────────────────────────────────────
print("Posing Apollo (standing, center)...")
set_freejoint("apollo/floating_base",
              pos=[0.0, 0.15, 1.07],
              quat=euler_to_quat(0, 0, -1.57))  # facing camera

# Relaxed standing pose
set_joint("apollo/l_shoulder_aa", 0.15)
set_joint("apollo/l_shoulder_fe", -0.10)
set_joint("apollo/l_elbow_fe", -0.20)
set_joint("apollo/r_shoulder_aa", -0.15)
set_joint("apollo/r_shoulder_fe", -0.10)
set_joint("apollo/r_elbow_fe", -0.20)

# ── H1: standing, right side ────────────────────────────────────────────────
print("Posing H1 (standing, right)...")
set_freejoint_by_body("h1/pelvis",
                      pos=[1.4, 0.1, 1.02],
                      quat=euler_to_quat(0, 0, -1.57))  # facing camera

# Relaxed standing pose
set_joint("h1/left_shoulder_pitch", -0.10)
set_joint("h1/left_shoulder_roll", 0.15)
set_joint("h1/right_shoulder_pitch", -0.10)
set_joint("h1/right_shoulder_roll", -0.15)

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
