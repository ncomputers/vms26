_detectors = {}


def register_detector(name, obj):
    _detectors[name] = obj


def get_detector(name):
    return _detectors[name]
