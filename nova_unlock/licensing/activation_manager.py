
import json
from .license_validator import LicenseValidator
from .storage import SecureStorage
from .hardware_id import get_hardware_fingerprint, get_short_hw_id

class ActivationManager:
    def __init__(self):
        self.validator = LicenseValidator()
        self.storage   = SecureStorage()

    def get_hardware_id(self):
        return get_short_hw_id()

    def activate_from_file(self, path):
        try:
            with open(path) as f:
                bundle = json.load(f)
        except Exception as e:
            return {'success': False, 'error': str(e)}
        return self._validate_and_save(bundle)

    def _validate_and_save(self, bundle):
        hw = get_hardware_fingerprint()
        lic_hw = bundle.get('data', {}).get('hardware_id', '')
        if lic_hw != hw:
            return {'success': False, 'error': 'Wrong device', 'your_hw_id': self.get_hardware_id()}
        status = self.validator.validate_bundle(bundle)
        if status.get('valid'):
            self.storage.save_license(bundle)
            return {'success': True, 'license': bundle['data']}
        return {'success': False, 'error': status.get('reason', 'Invalid')}

    def get_status(self):
        return self.validator.validate()
