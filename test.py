from pydbus import SessionBus
import sounddevice as sd
import numpy as np
import time

# Get PipeWire bus
bus = SessionBus()
pipewire = bus.get('org.pipewire.Protocol.pw_client') 

def test_sine():
    sample_rate = 44100
    t = np.linspace(0, 2, sample_rate * 2)
    sine_wave = np.sin(2 * np.pi * 440 * t)
    
    print("Playing sine wave...")
    # Try using PipeWire device explicitly
    sd.play(sine_wave, sample_rate, device='pipewire', blocking=True)
    time.sleep(0.5)

def test_overlap():
    sample_rate = 44100
    t = np.linspace(0, 1, sample_rate)
    sine1 = np.sin(2 * np.pi * 440 * t)
    sine2 = np.sin(2 * np.pi * 880 * t)
    
    print("Playing first tone...")
    sd.play(sine1, sample_rate, device='pipewire')
    time.sleep(0.5)
    print("Playing second tone...")
    sd.play(sine2, sample_rate, device='pipewire', blocking=True)

if __name__ == "__main__":
    print("Testing single sound:")
    test_sine()
    
    print("\nTesting overlapping sounds:")
    test_overlap()