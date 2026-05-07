import pickle
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

data_directory = r"C:\Users\Pulee\Desktop\multi_animal_data_20260427_155431.pickle"
with open(data_directory, "rb") as f:
    multi_animal_data = pickle.load(f)

# Collect all wavelengths
target_wavelengths = []
for animal_data in multi_animal_data:
    if 'target_signal' in animal_data:
        signal = animal_data['target_signal']
        wls = signal.split('+') if '+' in signal else [signal]
        target_wavelengths.extend(wls)
target_wavelengths = sorted(list(set(target_wavelengths)))
    
for animal_data in multi_animal_data:
    running_bouts = animal_data.get('running_bouts', {})
    general_bouts = running_bouts.get("general_bouts", [])
    preprocessed_data = animal_data.get('preprocessed_data')
    if preprocessed_data is None or preprocessed_data.empty:
        continue
        
    channels = animal_data.get('channels', {})
    time_col = channels['time']
    fiber_timestamps = preprocessed_data[time_col].values
    
    dff_data = animal_data.get('dff_data', {})
    active_channels = animal_data.get('active_channels', [])
    
    dff_410 = dff_data.get(f"{active_channels[0]}_{target_wavelengths[0]}", pd.Series()).values
    dff_560 = dff_data.get(f"{active_channels[0]}_{target_wavelengths[1]}", pd.Series()).values
    dff_640 = dff_data.get(f"{active_channels[0]}_{target_wavelengths[2]}", pd.Series()).values
    
    delta_dff_410 = max(dff_410) - min(dff_410)
    delta_dff_560 = max(dff_560) - min(dff_560)
    delta_dff_640 = max(dff_640) - min(dff_640)
                   
    peaks410_x, _ = find_peaks(dff_410, distance=2, prominence=0.05 * delta_dff_410)
    peaks560_x, _ = find_peaks(dff_560, distance=2, prominence=0.05 * delta_dff_560)
    peaks640_x, _ = find_peaks(dff_640, distance=2, prominence=0.05 * delta_dff_640)

    valleys410_x, _ = find_peaks(-dff_410, distance=2, prominence=0.05 * delta_dff_410)
    valleys560_x, _ = find_peaks(-dff_560, distance=2, prominence=0.05 * delta_dff_560)
    valleys640_x, _ = find_peaks(-dff_640, distance=2, prominence=0.05 * delta_dff_640)

    plt.figure(figsize=(16, 9))
    plt.plot(fiber_timestamps, dff_410, label='410nm', color='#44B444')
    plt.plot(fiber_timestamps[peaks410_x], dff_410[peaks410_x], 'x', color='k', label='Peaks')
    plt.plot(fiber_timestamps[valleys410_x], dff_410[valleys410_x], 'o', color='k', label='Valleys')
    plt.axhline(0, color='k', linestyle='--', linewidth=1)
    plt.plot(fiber_timestamps, dff_560 + 1.1*delta_dff_410, label='560nm', color='#FF0000')
    plt.plot(fiber_timestamps[peaks560_x], dff_560[peaks560_x] + 1.1*delta_dff_410, 'x', color='k', label='Peaks')
    plt.plot(fiber_timestamps[valleys560_x], dff_560[valleys560_x] + 1.1*delta_dff_410, 'o', color='k', label='Valleys')
    plt.axhline(1.1*delta_dff_410, color='k', linestyle='--', linewidth=1)
    plt.plot(fiber_timestamps, dff_640 + 1.1*delta_dff_410 + 1.1*delta_dff_560, label='640nm', color='#FF9900')
    plt.plot(fiber_timestamps[peaks640_x], dff_640[peaks640_x] + 1.1*delta_dff_410 + 1.1*delta_dff_560, 'x', color='k', label='Peaks')
    plt.plot(fiber_timestamps[valleys640_x], dff_640[valleys640_x] + 1.1*delta_dff_410 + 1.1*delta_dff_560, 'o', color='k', label='Valleys')
    plt.axhline(1.1*delta_dff_410 + 1.1*delta_dff_560, color='k', linestyle='--', linewidth=1)
    for bout in general_bouts:
        plt.axvspan(bout[0]/20, bout[1]/20, color='red', alpha=0.3)
    # plt.title('410nm dF/F')
    plt.xlim(0, 300)
    plt.xlabel('Time (s)')
    plt.ylabel('dF/F')
    plt.legend()
    plt.tight_layout()
    plt.show()