"""
Linux-FaceLock — Open Source License Validator.
Always returns valid open-source community status.
"""

class LicenseValidator:
    def __init__(self):
        pass

    def validate(self):
        return {
            'valid': True,
            'open_source': True,
            'license': {
                'type': 'open-source',
                'plan': 'MIT',
                'user': 'community'
            }
        }

    def validate_bundle(self, bundle):
        return self.validate()

    def quick_check(self):
        return True
