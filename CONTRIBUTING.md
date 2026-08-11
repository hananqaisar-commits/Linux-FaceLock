# Contributing to Linux-FaceLock

Thank you for your interest in contributing to **Linux-FaceLock** (NovaUnlock)! We welcome contributions from the open-source community, including bug fixes, feature enhancements, documentation improvements, and distro packaging support.

---

## Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/hananqaisar-commits/Linux-FaceLock.git
   cd Linux-FaceLock
   ```

2. **Create a Python Virtual Environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Run the UI Demo**:
   ```bash
   python3 -m nova_unlock.ui.face_unlock_widget --demo
   ```

4. **Run Unit Tests**:
   ```bash
   pytest tests/
   ```

---

## Submitting Pull Requests

1. Fork the repository and create a feature branch (`git checkout -b feature/amazing-feature`).
2. Follow standard Python coding style (PEP 8 compliance).
3. Ensure unit tests pass before submitting.
4. Open a Pull Request with a detailed summary of your changes.

---

## Code of Conduct

Please maintain a polite, inclusive, and professional environment for all contributors.
