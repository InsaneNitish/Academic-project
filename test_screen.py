import cv2
import mss
import numpy as np
import time
import pygetwindow as gw

import sys

def main():
    print("Available windows (with titles):")
    titles = [t for t in gw.getAllTitles() if t.strip()]
    
    # Print a few to the console to help the user
    for title in titles[:10]:
        print(f" - {title}")
    if len(titles) > 10:
        print(f" ... and {len(titles)-10} more.")
        
    target_title = ""
    if len(sys.argv) > 1:
        target_title = sys.argv[1].strip()
        print(f"\nTarget window title provided via argument: '{target_title}'")
    else:
        target_title = input("\nEnter part of the window title to capture (e.g., 'YouTube' or 'Chrome') [Leave blank for full screen]: ").strip()
    
    window = None
    
    if target_title:
        try:
            # Find all matching windows
            matches = gw.getWindowsWithTitle(target_title)
            if matches:
                window = matches[0]
                print(f"Found window: '{window.title}'")
            else:
                print(f"No window containing '{target_title}' found. Defaulting to full screen.")
        except Exception as e:
            print(f"Error finding window: {e}. Defaulting to full screen.")
    
    with mss.mss() as sct:
        if not window:
            monitor = sct.monitors[1]
            print(f"Capturing primary monitor: {monitor['width']}x{monitor['height']}")
            
        print("Press 'q' in the preview window to quit.")
        
        frames = 0
        start_time = time.time()
        
        while True:
            # Update monitor coordinates dynamically in case the window moves or resizes!
            if window:
                monitor = {
                    "top": window.top,
                    "left": window.left,
                    "width": window.width,
                    "height": window.height
                }
                
                # If window is minimized or has invalid dimension
                if monitor["width"] <= 0 or monitor["height"] <= 0:
                    time.sleep(0.1)
                    continue
                    
                if frames == 0:
                    print(f"\n[Debug] Capturing region: {monitor}")
                    
            # Grab the pixels
            img = np.array(sct.grab(monitor))
            
            # Convert BGRA to BGR
            frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
            h, w = frame.shape[:2]
            
            # Scale down for preview so it doesn't cause infinite mirroring
            scale = 0.5 if w > 1200 else 1.0
            display_frame = cv2.resize(frame, (0,0), fx=scale, fy=scale)
            
            label = f"Live Capture: {w}x{h}"
            cv2.putText(display_frame, label, (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            
            # Show the live feed
            cv2.imshow("Screen Capture Test", display_frame)
            
            # Move the preview window away from the capture region to prevent mirroring!
            if frames == 0 and window:
                # If capture is on the right side of the screen, move preview to the left (0,0)
                if window.left > 500:
                    cv2.moveWindow("Screen Capture Test", 0, 0)
                # If capture is on the left side, move preview to the right
                else:
                    cv2.moveWindow("Screen Capture Test", max(800, window.width + 50), 0)
            
            frames += 1
            
            # Press 'q' to quit
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
        fps = frames / max(time.time() - start_time, 0.001)
        print(f"\nStopped. Captured {frames} frames at {fps:.1f} FPS")

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
