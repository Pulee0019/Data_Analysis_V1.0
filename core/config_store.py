import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
MEMORY_DIR = os.path.join(BASE_DIR, "memory")

os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(MEMORY_DIR, exist_ok=True)

CHANNEL_MEMORY_FILE = os.path.join(MEMORY_DIR, "channel_memory.json")
EVENT_CONFIG_FILE = os.path.join(CONFIG_DIR, "event_config.json")
OPTO_POWER_CONFIG_FILE = os.path.join(CONFIG_DIR, "opto_power_config.json")
DRUG_NAME_CONFIG_FILE = os.path.join(CONFIG_DIR, "drug_name_config.json")

channel_memory = {}
event_config = {}
opto_power_config = {}
drug_name_config = {}

def load_channel_memory():
    """Load channel memory from file"""
    global channel_memory
    if os.path.exists(CHANNEL_MEMORY_FILE):
        try:
            with open(CHANNEL_MEMORY_FILE, 'r') as f:
                channel_memory = json.load(f)
        except:
            channel_memory = {}

def save_channel_memory():
    """Save channel memory to file"""
    try:
        with open(CHANNEL_MEMORY_FILE, 'w') as f:
            json.dump(channel_memory, f)
    except:
        pass

def load_event_config():
    """Load event configuration from file"""
    global event_config
    if os.path.exists(EVENT_CONFIG_FILE):
        try:
            with open(EVENT_CONFIG_FILE, 'r') as f:
                event_config = json.load(f)
        except:
            event_config = {
                'drug_event': 'Event1',
                'opto_event': 'Input3',
                'running_start': 'Input2'
            }

def save_event_config():
    """Save event configuration to file"""
    try:
        with open(EVENT_CONFIG_FILE, 'w') as f:
            json.dump(event_config, f)
    except:
        pass

def load_opto_power_config():
    """Load optogenetic power configuration from file"""
    global opto_power_config
    if os.path.exists(OPTO_POWER_CONFIG_FILE):
        try:
            with open(OPTO_POWER_CONFIG_FILE, 'r') as f:
                opto_power_config = json.load(f)
        except:
            opto_power_config = {}

def save_opto_power_config():
    """Save optogenetic power configuration to file"""
    try:
        with open(OPTO_POWER_CONFIG_FILE, 'w') as f:
            json.dump(opto_power_config, f)
    except:
        pass

def load_drug_name_config():
    """Load drug name configuration from file"""
    global drug_name_config
    if os.path.exists(DRUG_NAME_CONFIG_FILE):
        try:
            with open(DRUG_NAME_CONFIG_FILE, 'r') as f:
                drug_name_config = json.load(f)
        except:
            drug_name_config = {}

def save_drug_name_config():
    """Save drug name configuration to file"""
    try:
        with open(DRUG_NAME_CONFIG_FILE, 'w') as f:
            json.dump(drug_name_config, f)
    except:
        pass

load_channel_memory()
load_event_config()
load_opto_power_config()
load_drug_name_config()
