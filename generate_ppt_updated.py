"""
Generate Updated ADAS System Workflow PPT (Unified Architecture)
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
import os

# Colors
BG_DARK = RGBColor(15, 23, 42)
BG_CARD = RGBColor(30, 41, 59)
ACCENT_BLUE = RGBColor(59, 130, 246)
ACCENT_GREEN = RGBColor(16, 185, 129)
ACCENT_RED = RGBColor(239, 68, 68)
ACCENT_AMBER = RGBColor(245, 158, 11)
ACCENT_PURPLE = RGBColor(139, 92, 246)
ACCENT_CYAN = RGBColor(6, 182, 212)
WHITE = RGBColor(255, 255, 255)
GRAY = RGBColor(148, 163, 184)
LIGHT_GRAY = RGBColor(203, 213, 225)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

def add_bg(slide, color=BG_DARK):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color

def add_shape(slide, left, top, width, height, fill_color, border_color=None, radius=None):
    if radius:
        shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        shape.adjustments[0] = 0.05
    else:
        shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    if border_color:
        shape.line.color.rgb = border_color
        shape.line.width = Pt(1.5)
    else:
        shape.line.fill.background()
    return shape

def add_text(slide, left, top, width, height, text, font_size=18, color=WHITE, bold=False, align=PP_ALIGN.LEFT):
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(font_size)
    p.font.color.rgb = color
    p.font.bold = bold
    p.alignment = align
    return txBox

def add_bullets(slide, items, left, top, width, font_size=16, color=LIGHT_GRAY, spacing=Pt(8)):
    txBox = slide.shapes.add_textbox(left, top, width, Inches(4))
    tf = txBox.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = item
        p.font.size = Pt(font_size)
        p.font.color.rgb = color
        p.space_after = spacing
    return txBox

def bar(slide, left, top, width, height, color):
    return add_shape(slide, left, top, width, height, color)

# ═══════════════════════════════════════════════════════════
# SLIDE 1: TITLE
# ═══════════════════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide)
bar(slide, Inches(0), Inches(3.2), Inches(13.333), Pt(4), ACCENT_BLUE)
add_text(slide, Inches(1), Inches(1.8), Inches(11), Inches(1.5),
         "Unified ADAS Pipeline", 44, WHITE, True, PP_ALIGN.CENTER)
add_text(slide, Inches(1), Inches(3.5), Inches(11), Inches(1),
         "Tri-Staggered Dual-AI Architecture for Indian Roads", 24, GRAY, False, PP_ALIGN.CENTER)
add_text(slide, Inches(1), Inches(4.5), Inches(11), Inches(0.8),
         "FCW \x00B7 Blind Spot \x00B7 Emergency Preemption \x00B7 Dynamic Skipping", 18, ACCENT_CYAN, False, PP_ALIGN.CENTER)
add_text(slide, Inches(1), Inches(6.2), Inches(11), Inches(0.5),
         "Monthly Committee Technical Update", 16, GRAY, False, PP_ALIGN.CENTER)

# ═══════════════════════════════════════════════════════════
# SLIDE 2: AGENDA
# ═══════════════════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide)
add_text(slide, Inches(0.8), Inches(0.4), Inches(5), Inches(0.7), "Agenda", 36, WHITE, True)
bar(slide, Inches(0.8), Inches(1.1), Inches(2), Pt(3), ACCENT_BLUE)
agenda = [
    ("01", "The True Dual-Model Unified Pipeline Architecture", ACCENT_BLUE),
    ("02", "Core Optimizations: Tri-Staggered Execution & Dynamic Skipping", ACCENT_CYAN),
    ("03", "Module 1: Context-Aware Forward Collision Warning (FCW)", ACCENT_RED),
    ("04", "Module 2: Lane Assist & Blind Spot Analytics (Rear)", ACCENT_GREEN),
    ("05", "Module 3: Multi-Modal Emergency Preemption (EVP)", ACCENT_AMBER),
    ("06", "Advanced Tracking & HUD Rendering", ACCENT_PURPLE),
    ("07", "Profiling & Metrics (unified_profile.csv)", ACCENT_CYAN)
]
for i, (num, title, color) in enumerate(agenda):
    y = Inches(1.8) + Inches(i * 0.7)
    bar(slide, Inches(1.2), y + Pt(4), Pt(4), Inches(0.35), color)
    add_text(slide, Inches(1.5), y, Inches(1), Inches(0.5), num, 20, color, True)
    add_text(slide, Inches(2.3), y, Inches(8), Inches(0.5), title, 20, WHITE)

# ═══════════════════════════════════════════════════════════
# SLIDE 3: UNIFIED ARCHITECTURE
# ═══════════════════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide)
add_text(slide, Inches(0.8), Inches(0.4), Inches(8), Inches(0.7), "True Dual-Model Unified Pipeline", 36, WHITE, True)
bar(slide, Inches(0.8), Inches(1.1), Inches(2), Pt(3), ACCENT_BLUE)
add_text(slide, Inches(0.8), Inches(1.5), Inches(11), Inches(0.6),
         "Previously isolated modules are now unified. Processes Front & Rear cameras simultaneously.", 18, GRAY)
modules_info = [
    ("General Traffic AI", "yolov8n.pt", "Detects Cars, Trucks, Pedestrians, Bikes on Front + Rear cameras.", ACCENT_RED),
    ("Emergency Veh. AI", "yolo_emergency_model.pt", "Specialized model dedicated to Ambulances, Fire Trucks, Police.", ACCENT_AMBER),
    ("DeepSORT Trackers", "3 Independent Streams", "Separate trackers for Front, Rear, and EVP streams ensuring no mixups.", ACCENT_BLUE),
]
for i, (name, val, desc, color) in enumerate(modules_info):
    y = Inches(2.4 + i * 1.3)
    add_shape(slide, Inches(0.8), y, Inches(3.5), Inches(1.1), BG_CARD, color, radius=True)
    add_text(slide, Inches(1.0), y+Inches(0.15), Inches(3.3), Inches(0.4), name, 18, color, True)
    add_text(slide, Inches(1.0), y+Inches(0.6), Inches(3.3), Inches(0.4), val, 14, WHITE, True)
    add_text(slide, Inches(4.7), y+Inches(0.35), Inches(7.5), Inches(0.8), desc, 16, LIGHT_GRAY)

# ═══════════════════════════════════════════════════════════
# SLIDE 4: CORE OPTIMIZATIONS
# ═══════════════════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide)
add_text(slide, Inches(0.8), Inches(0.4), Inches(10), Inches(0.7),
         "Optimizations: Tri-Staggered Exec & Dynamic Skip", 34, WHITE, True)
bar(slide, Inches(0.8), Inches(1.1), Inches(2), Pt(3), ACCENT_CYAN)
add_text(slide, Inches(0.8), Inches(1.5), Inches(11), Inches(0.5),
         "Massive CPU/GPU savings achieved by intelligently staggering workloads and skipping empty frames.", 17, GRAY)

staggered = [
    "Tri-Staggered Detection Rate (Interval = 3):",
    "  \x00B7 Frame N+0: Front Camera AI Inference",
    "  \x00B7 Frame N+1: Rear Camera AI Inference",
    "  \x00B7 Frame N+2: Emergency Camera AI Inference",
    "Result: Avoids running 3 heavy models on the same frame, eliminating latency spikes."
]
add_shape(slide, Inches(0.8), Inches(2.3), Inches(11.5), Inches(2.0), BG_CARD, ACCENT_BLUE, radius=True)
add_bullets(slide, staggered, Inches(1.1), Inches(2.5), Inches(11), 16, WHITE, Pt(6))

skipping = [
    "Dynamic Empty-Road Skipping:",
    "  \x00B7 If the system detects 0 vehicles for 2 consecutive runs (6 frames)...",
    "  \x00B7 It safely assumes an empty road and forces skips for the next 6 frames.",
    "  \x00B7 DeepSORT Coasting keeps existing objects alive seamlessly.",
    "Result: Drastically cuts CPU usage during open highway driving or stopped traffic."
]
add_shape(slide, Inches(0.8), Inches(4.6), Inches(11.5), Inches(2.0), BG_CARD, ACCENT_GREEN, radius=True)
add_bullets(slide, skipping, Inches(1.1), Inches(4.8), Inches(11), 16, WHITE, Pt(6))

# ═══════════════════════════════════════════════════════════
# SLIDE 5: FCW CONTEXT AWARE
# ═══════════════════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide)
add_text(slide, Inches(0.8), Inches(0.4), Inches(10), Inches(0.7),
         "Module 1: Context-Aware FCW", 34, WHITE, True)
bar(slide, Inches(0.8), Inches(1.1), Inches(2), Pt(3), ACCENT_RED)
add_text(slide, Inches(0.8), Inches(1.5), Inches(11), Inches(0.5),
         "Uses 'get_ego_polygon' logic instead of simple bounding box overlaps.", 17, GRAY)

features = [
    "\x00B7 Ego Path Polygon: Defines a 45% width, 65% height corridor ahead of the driver.",
    "\x00B7 Context Validation: Targets must have >25% horizontal overlap with this polygon.",
    "\x00B7 Traffic-Aware TTC Thresholds:",
    "   - FREE (< 4 vehicles): Warns at 4.0s, Critical at 2.0s.",
    "   - HEAVY (>= 8 vehicles): Warns at 2.0s, Critical at 1.0s (avoids false alarms in jams).",
    "\x00B7 DeepSORT Speeds: Closing speed derived from tracking bounding box growth.",
    "\x00B7 Pedestrian Alert: Special DANGER overlay if a pedestrian (Class 0) enters Ego Path."
]
add_bullets(slide, features, Inches(0.8), Inches(2.3), Inches(11.5), 16, LIGHT_GRAY, Pt(8))

# ═══════════════════════════════════════════════════════════
# SLIDE 6: REAR CAMERA
# ═══════════════════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide)
add_text(slide, Inches(0.8), Inches(0.4), Inches(10), Inches(0.7),
         "Module 2: Lane Assist & Blind Spot", 34, WHITE, True)
bar(slide, Inches(0.8), Inches(1.1), Inches(2), Pt(3), ACCENT_GREEN)
add_text(slide, Inches(0.8), Inches(1.5), Inches(11), Inches(0.5),
         "Rear Camera Analytics: Lane Advisory, 3D Cubes, ROI Cropping.", 17, GRAY)

bsd_features = [
    "\x00B7 ROI Cropping: Top 20% of rear frame is cropped to save processing time.",
    "\x00B7 3D Blind Spot Cubes: Projects a polygon to the left/right of detected lanes.",
    "\x00B7 Intersection Testing: If a vehicle bounding box footprint hits the cube = In Blind Spot.",
    "\x00B7 Lane Change Advisor: Evaluates both lanes simultaneously.",
    "\x00B7 Outputs 'UNSAFE_LEFT', 'UNSAFE_RIGHT', 'SAFE_BOTH', triggering an Amber Alert if driver signals."
]
add_bullets(slide, bsd_features, Inches(0.8), Inches(2.3), Inches(11.5), 16, LIGHT_GRAY, Pt(10))

# ═══════════════════════════════════════════════════════════
# SLIDE 7: EVP
# ═══════════════════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide)
add_text(slide, Inches(0.8), Inches(0.4), Inches(10), Inches(0.7),
         "Module 3: Multi-Modal EVP", 34, WHITE, True)
bar(slide, Inches(0.8), Inches(1.1), Inches(2), Pt(3), ACCENT_AMBER)
add_text(slide, Inches(0.8), Inches(1.5), Inches(11), Inches(0.5),
         "Emergency Vehicle Preemption: Identifies active emergency scenarios securely.", 17, GRAY)

cards = [
    ("Visual Detection", ["HSV detection for Red, Blue, Amber.", "Blink frequency verification (1-4Hz).", "Scans only the top 30% of Emergency Bboxes."], ACCENT_RED),
    ("Audio Siren (Optional)", ["FFT Analysis over Indian Siren Band (600-1600Hz).", "Calculates Warble variance.", "Graceful degradation if no Mic."], ACCENT_CYAN),
    ("Multi-Modal Fusion", ["fused = max(visual, audio).", "If both > 0.3, boosts confidence.", "10 frames to reach state 'YIELD'."], ACCENT_AMBER)
]
for i, (title, points, color) in enumerate(cards):
    x = Inches(0.8 + i*4.0)
    add_shape(slide, x, Inches(2.3), Inches(3.7), Inches(3.5), BG_CARD, color, radius=True)
    add_text(slide, x+Inches(0.2), Inches(2.5), Inches(3.3), Inches(0.4), title, 18, color, True)
    add_bullets(slide, points, x+Inches(0.2), Inches(3.2), Inches(3.3), 14, LIGHT_GRAY, Pt(5))

# ═══════════════════════════════════════════════════════════
# SLIDE 8: UI & PROFILING
# ═══════════════════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide)
add_text(slide, Inches(0.8), Inches(0.4), Inches(10), Inches(0.7),
         "HUD Rendering & Performance Profiling", 34, WHITE, True)
bar(slide, Inches(0.8), Inches(1.1), Inches(2), Pt(3), ACCENT_PURPLE)

ui_points = [
    "HUD UIRenderer:",
    "  \x00B7 Semi-transparent panels with Corner-Accent glowing bounding boxes.",
    "  \x00B7 Dynamic Dashboards for Front (FCW/EVP) and Rear (BSD/Lane offset).",
    "  \x00B7 Full-screen Red Alert 'PEDESTRIAN IN PATH!' override when needed."
]
add_shape(slide, Inches(0.8), Inches(1.8), Inches(11.5), Inches(1.8), BG_CARD, ACCENT_BLUE, radius=True)
add_bullets(slide, ui_points, Inches(1.1), Inches(2.0), Inches(11), 16, WHITE, Pt(5))

prof_points = [
    "Metrics & Logging (ModuleProfiler):",
    "  \x00B7 Measures accurate FPS, Time per frame, data bandwidth.",
    "  \x00B7 Logs states directly to unified_profile.csv and evp_profile.csv.",
    "  \x00B7 Ensures real-time evaluation capability to catch bottlenecks in edge deployments."
]
add_shape(slide, Inches(0.8), Inches(4.0), Inches(11.5), Inches(1.8), BG_CARD, ACCENT_GREEN, radius=True)
add_bullets(slide, prof_points, Inches(1.1), Inches(4.2), Inches(11), 16, WHITE, Pt(5))

# ═══════════════════════════════════════════════════════════
# SLIDE 9: THANK YOU
# ═══════════════════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide)
bar(slide, Inches(0), Inches(3.2), Inches(13.333), Pt(4), ACCENT_BLUE)
add_text(slide, Inches(1), Inches(2), Inches(11), Inches(1.2),
         "System Ready for Edge Deployment", 52, WHITE, True, PP_ALIGN.CENTER)
add_text(slide, Inches(1), Inches(3.5), Inches(11), Inches(0.8),
         "Unified Pipeline \x00B7 Tri-Staggered AI \x00B7 Context-Aware FCW", 22, GRAY, False, PP_ALIGN.CENTER)
add_text(slide, Inches(1), Inches(4.5), Inches(11), Inches(0.6),
         "Questions & Discussion", 20, ACCENT_CYAN, False, PP_ALIGN.CENTER)

# SAVE
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ADAS_Unified_Architecture_V2.pptx")
try:
    prs.save(out)
    print(f"PPT saved successfully at: {out}")
except Exception as e:
    print(f"Error saving PPT: {e}")
