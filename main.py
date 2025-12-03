#!/usr/bin/env python3
"""
Image to MIDI Converter
Converts image HSV color data to MIDI file, column-by-column.
"""

import sys
from PIL import Image
import colorsys

try:
    from tkinter import Tk
    from tkinter.filedialog import askopenfilename, asksaveasfilename
except ImportError:
    print("Error: tkinter not available. Install python3-tk package.", file=sys.stderr)
    sys.exit(1)

try:
    from midiutil import MIDIFile
except ImportError:
    print("Error: MIDIUtil not installed. Run: python3 -m pip install --user MIDIUtil", file=sys.stderr)
    sys.exit(1)


def select_image():
    """Open file dialog to select an image."""
    Tk().withdraw()
    filename = askopenfilename(
        title="Select an image file",
        filetypes=[
            ("Image files", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp"),
            ("All files", "*.*")
        ]
    )
    return filename


def save_midi_dialog():
    """Open save dialog for MIDI file."""
    Tk().withdraw()
    filename = asksaveasfilename(
        title="Save MIDI file as",
        defaultextension=".mid",
        filetypes=[("MIDI files", "*.mid"), ("All files", "*.*")]
    )
    return filename


def extract_hsv_data(image_path, target_size=(128, 128)):
    """Extract HSV color data from image, column-by-column."""
    try:
        img = Image.open(image_path)
    except Exception as e:
        print(f"Error opening image: {e}", file=sys.stderr)
        sys.exit(1)
    
    img = img.convert('RGBA')
    img = img.resize(target_size, Image.Resampling.LANCZOS)
    
    width, height = img.size
    pixels = img.load()
    
    color_data = []
    
    # Read column-by-column
    for x in range(width):
        for y in range(height):
            r, g, b, a = pixels[x, y]
            
            # Skip transparent pixels
            if a < 128:
                continue
            
            h, s, v = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)
            
            # Convert to standard ranges
            h = h * 360
            s = s * 100
            v = v * 100
            
            color_data.append((x, y, h, s, v))
    
    return color_data, width, height


def hsv_to_midi_params(h, s, v):
    """
    Convert HSV to MIDI parameters.
    
    Hue (0-360) → Pitch (21-108, A0-C8)
    Saturation (0-100) → Velocity (20-127)
    Value (0-100) → Octave influence (darker=bass, brighter=treble)
    """
    # Map hue to chromatic pitch across full piano range
    # Value influences octave: low value = lower register, high value = higher register
    base_pitch = (h / 360.0) * 12  # 0-12 semitones
    octave_shift = (v / 100.0) * 7  # 0-7 octaves based on brightness
    
    pitch = int(21 + (octave_shift * 12) + base_pitch)  # A0 = 21
    pitch = max(21, min(108, pitch))  # Clamp to piano range (A0-C8)
    
    # Map saturation to velocity (minimum 20 to ensure audibility)
    velocity = int(20 + (s / 100.0) * 107)
    velocity = max(20, min(127, velocity))
    
    return pitch, velocity


def colors_are_close(hsv1, hsv2, threshold_h=15, threshold_s=15, threshold_v=15):
    """Check if two HSV colors are within threshold."""
    h1, s1, v1 = hsv1
    h2, s2, v2 = hsv2
    
    # Handle hue wrap-around (0° and 360° are the same)
    hue_diff = abs(h1 - h2)
    if hue_diff > 180:
        hue_diff = 360 - hue_diff
    
    return (hue_diff <= threshold_h and 
            abs(s1 - s2) <= threshold_s and 
            abs(v1 - v2) <= threshold_v)


def create_midi_from_colors(color_data, output_path, bpm=120):
    """
    Create MIDI file from color data.
    
    Each pixel = 1 eighth note at 120 BPM
    Extend note duration when consecutive colors are similar
    """
    if not color_data:
        print("No color data to convert!")
        return
    
    midi = MIDIFile(1)  # 1 track
    track = 0
    channel = 0
    midi.addTrackName(track, 0, "Image Colors")
    midi.addTempo(track, 0, bpm)
    
    # Eighth note duration in beats (quarter note = 1 beat)
    eighth_note = 0.5
    
    current_time = 0
    prev_hsv = None
    note_start_time = 0
    current_pitch = None
    current_velocity = None
    accumulated_duration = 0
    
    print("\nConverting colors to MIDI...")
    print(f"Total pixels to process: {len(color_data)}")
    
    for i, (x, y, h, s, v) in enumerate(color_data):
        pitch, velocity = hsv_to_midi_params(h, s, v)
        
        # Check if we should extend the previous note
        if prev_hsv and colors_are_close((h, s, v), prev_hsv):
            # Extend current note duration
            accumulated_duration += eighth_note
        else:
            # Write the previous note if it exists
            if current_pitch is not None:
                midi.addNote(track, channel, current_pitch, note_start_time, 
                           accumulated_duration, current_velocity)
            
            # Start new note
            note_start_time = current_time
            current_pitch = pitch
            current_velocity = velocity
            accumulated_duration = eighth_note
        
        prev_hsv = (h, s, v)
        current_time += eighth_note
        
        # Progress indicator
        if (i + 1) % 100 == 0:
            print(f"Processed {i + 1}/{len(color_data)} pixels...")
    
    # Write the final note
    if current_pitch is not None:
        midi.addNote(track, channel, current_pitch, note_start_time, 
                   accumulated_duration, current_velocity)
    
    # Write MIDI file
    try:
        with open(output_path, "wb") as f:
            midi.writeFile(f)
        print(f"\nMIDI file saved: {output_path}")
        print(f"Duration: {current_time / 2:.1f} seconds ({current_time} beats)")
    except Exception as e:
        print(f"Error saving MIDI file: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    print("Image to MIDI Converter")
    print("=" * 50)
    print()
    
    # Select image
    image_path = select_image()
    if not image_path:
        print("No file selected. Exiting.")
        sys.exit(0)
    
    print(f"Selected: {image_path}")
    print("Processing image...")
    
    # Extract colors
    color_data, width, height = extract_hsv_data(image_path)
    
    print(f"Image: {width}×{height}")
    print(f"Non-transparent pixels: {len(color_data)}")
    
    # Select output file
    output_path = save_midi_dialog()
    if not output_path:
        print("No output file selected. Exiting.")
        sys.exit(0)
    
    # Create MIDI
    create_midi_from_colors(color_data, output_path, bpm=120)
    
    print("\nDone! Open the MIDI file in any DAW or music software.")


if __name__ == "__main__":
    main()