from ultralytics import YOLO

model = YOLO('c:\\Users\\nitis\\.gemini\\antigravity\\scratch\\indian_fcw\\yolo_emergency_model.pt')
print("Model classes:", model.names)
